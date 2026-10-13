import uuid

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.case_document import CaseDocument
from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.user_permission import UserPermission
from app.services.identity import validate_sa_id
from app.services.paperwork import (
    paperwork_summary,
    standard_items,
)


# ============================================================
# HELPERS
# ============================================================

def sa_id(birth="800101", seq="5009", citizen="0", filler="8"):
    """Build a valid South African ID number."""

    body = f"{birth}{seq}{citizen}{filler}"

    for check in range(10):
        candidate = f"{body}{check}"

        if validate_sa_id(candidate) is None:
            return candidate

    raise AssertionError("no valid check digit")


VALID_ID = sa_id()


def make_case(db, business, *, archived=False):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"DR-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Private Name",
        date_of_death=date(2026, 10, 1),
        status="open",
        is_archived=archived,
    )
    db.add(case)
    db.commit()

    return case


def make_document(db, case, user):
    document = CaseDocument(
        business_id=case.business_id,
        case_id=case.id,
        document_type="other",
        original_filename="scan.pdf",
        stored_filename=f"{uuid.uuid4().hex}.pdf",
        file_path="storage/x.pdf",
        uploaded_by=user.id,
    )
    db.add(document)
    db.commit()

    return document


def deny(db, user, key):
    permission = (
        db.query(Permission).filter(Permission.key == key).first()
    )
    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()


def call(client, auth_headers, user, method, path, **kwargs):
    return client.request(
        method,
        path,
        headers=auth_headers(user),
        **kwargs,
    )


def create_record(client, auth_headers, user, case, **fields):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        f"/cases/{case.id}/death-record",
        json=fields,
    )


def audits(db, action):
    return db.query(AuditLog).filter(AuditLog.action == action).all()


# ============================================================
# SA ID NUMBER CHECK
# ============================================================

def test_valid_sa_id_passes():
    assert validate_sa_id(VALID_ID) is None


def test_none_is_not_checked():
    assert validate_sa_id(None) is None


@pytest.mark.parametrize(
    "number, reason",
    [
        ("12345", "13 digits"),
        ("80010150090812", "13 digits"),
        ("80010A5009088", "13 digits"),
        ("8013015009088", "date of birth"),
        ("8002305009088", "date of birth"),
        ("8001015009288", "citizenship"),
    ],
)
def test_bad_sa_id_is_refused_with_a_reason(number, reason):
    assert reason in validate_sa_id(number)


def test_wrong_check_digit_is_refused():
    wrong = VALID_ID[:-1] + str((int(VALID_ID[-1]) + 1) % 10)

    assert "check digit" in validate_sa_id(wrong)


def test_leap_day_in_either_century():
    # 29 February is real in 2000 and in 1900-style years only when
    # the year is a leap year; 00 is accepted through 2000.
    candidate = sa_id(birth="000229")

    assert validate_sa_id(candidate) is None


# ============================================================
# DEATH RECORD
# ============================================================

def test_create_with_defaults(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client, auth_headers, test_data["manager"], case
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["case_id"] == str(case.id)
    assert data["manner_of_death"] == "pending"
    assert data["forensic_status"] == "not_applicable"
    assert data["disposal_method"] == "burial"
    assert data["deceased_id_type"] == "sa_id"
    assert data["infectious_remains"] is False


def test_create_with_full_details_and_blank_text_becomes_null(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        deceased_id_number=VALID_ID,
        time_of_death="14:35:00",
        place_of_death_type="hospital",
        place_of_death="Chris Hani Baragwanath",
        manner_of_death="natural",
        cause_of_death="  Heart failure  ",
        certifier_name="Dr Mokoena",
        informant_name="Thandi Nkosi",
        informant_relationship="Daughter",
        informant_phone="0825550000",
        informant_id_number=sa_id(birth="900505"),
        notes="   ",
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["cause_of_death"] == "Heart failure"
    assert data["notes"] is None
    assert data["time_of_death"] == "14:35:00"


def test_create_is_audited_without_personal_details(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        deceased_id_number=VALID_ID,
        cause_of_death="Secret cause",
        informant_name="Secret Informant",
        manner_of_death="natural",
    )
    assert response.status_code == 201

    [entry] = audits(db, "death_record.created")

    assert entry.entity_type == "death_record"
    assert entry.details["case_number"] == case.case_number
    assert entry.details["manner_of_death"] == "natural"

    text = str(entry.details) + str(entry.notes)

    assert "Secret" not in text
    assert VALID_ID not in text


def test_second_record_for_a_case_is_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    assert create_record(
        client, auth_headers, manager, case
    ).status_code == 201

    again = create_record(client, auth_headers, manager, case)

    assert again.status_code == 409
    assert db.query(DeathRecord).count() == 1


def test_invalid_sa_id_is_refused_on_create(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        deceased_id_number="1234567890123",
    )

    assert response.status_code == 422
    assert db.query(DeathRecord).count() == 0


def test_passport_numbers_are_not_checked_as_sa_ids(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        deceased_id_type="passport",
        deceased_id_number="A1234567",
    )

    assert response.status_code == 201


def test_invalid_informant_sa_id_is_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        informant_id_number="1234567890123",
    )

    assert response.status_code == 422
    assert "Informant" in response.json()["detail"]


def test_natural_death_cannot_have_a_forensic_status(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        manner_of_death="natural",
        forensic_status="referred",
    )

    assert response.status_code == 422


def test_database_also_refuses_natural_with_forensic(db, test_data):
    case = make_case(db, test_data["business_a"])

    db.add(
        DeathRecord(
            business_id=case.business_id,
            case_id=case.id,
            manner_of_death="natural",
            forensic_status="referred",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_unknown_values_are_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = create_record(
        client,
        auth_headers,
        test_data["manager"],
        case,
        manner_of_death="mystery",
    )

    assert response.status_code == 422


def test_read_before_and_after_capture(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    url = f"/cases/{case.id}/death-record"

    assert call(
        client, auth_headers, manager, "GET", url
    ).status_code == 404

    create_record(client, auth_headers, manager, case)

    response = call(client, auth_headers, manager, "GET", url)

    assert response.status_code == 200
    assert response.json()["case_id"] == str(case.id)


def test_update_changes_fields_and_redacts_the_audit(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    create_record(
        client,
        auth_headers,
        manager,
        case,
        cause_of_death="Old cause",
        manner_of_death="pending",
    )

    response = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/death-record",
        json={
            "cause_of_death": "New cause",
            "manner_of_death": "natural",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["cause_of_death"] == "New cause"

    [entry] = audits(db, "death_record.updated")
    changes = entry.details["changes"]

    assert changes["cause_of_death"]["old"] == "[redacted]"
    assert changes["cause_of_death"]["new"] == "[redacted]"
    assert changes["manner_of_death"] == {
        "old": "pending",
        "new": "natural",
    }
    assert "New cause" not in str(entry.details)


def test_update_with_no_change_writes_no_audit(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    create_record(
        client, auth_headers, manager, case,
        manner_of_death="natural",
    )

    response = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/death-record",
        json={"manner_of_death": "natural"},
    )

    assert response.status_code == 200
    assert audits(db, "death_record.updated") == []


def test_update_rules_use_the_merged_values(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    create_record(
        client,
        auth_headers,
        manager,
        case,
        manner_of_death="unnatural",
        forensic_status="referred",
    )

    response = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/death-record",
        json={"manner_of_death": "natural"},
    )

    assert response.status_code == 422

    # Clearing the forensic status in the same request is fine.
    fixed = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/death-record",
        json={
            "manner_of_death": "natural",
            "forensic_status": "not_applicable",
        },
    )

    assert fixed.status_code == 200


def test_update_cannot_null_required_fields_or_add_unknown_ones(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    create_record(client, auth_headers, manager, case)

    url = f"/cases/{case.id}/death-record"

    nulled = call(
        client, auth_headers, manager, "PATCH", url,
        json={"manner_of_death": None},
    )
    unknown = call(
        client, auth_headers, manager, "PATCH", url,
        json={"case_id": str(uuid.uuid4())},
    )

    assert nulled.status_code == 422
    assert unknown.status_code == 422


def test_update_missing_record_is_not_found(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/death-record",
        json={"cause_of_death": "x"},
    )

    assert response.status_code == 404


def test_archived_cases_are_frozen(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"], archived=True)

    response = create_record(
        client, auth_headers, test_data["manager"], case
    )

    assert response.status_code == 409
    assert "Archived" in response.json()["detail"]


def test_another_business_cannot_see_or_change_a_record(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    create_record(
        client, auth_headers, test_data["manager"], case
    )

    outsider = test_data["other_business_manager"]
    url = f"/cases/{case.id}/death-record"

    assert call(
        client, auth_headers, outsider, "GET", url
    ).status_code == 404
    assert call(
        client, auth_headers, outsider, "PATCH", url,
        json={"notes": "x"},
    ).status_code == 404
    assert create_record(
        client, auth_headers, outsider, case
    ).status_code == 404


def test_record_permissions(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    staff = test_data["staff"]

    create_record(client, auth_headers, manager, case)
    url = f"/cases/{case.id}/death-record"

    # Defaults: staff may view and capture.
    assert call(
        client, auth_headers, staff, "GET", url
    ).status_code == 200
    assert call(
        client, auth_headers, staff, "PATCH", url,
        json={"notes": "from staff"},
    ).status_code == 200

    deny(db, staff, "death_records.manage")

    assert call(
        client, auth_headers, staff, "PATCH", url,
        json={"notes": "again"},
    ).status_code == 403

    deny(db, staff, "death_records.view")

    assert call(
        client, auth_headers, staff, "GET", url
    ).status_code == 403


# ============================================================
# STANDARD CHECKLIST RULES
# ============================================================

def keys(items):
    return [item.item_type for item in items]


def test_burial_checklist():
    items = standard_items(
        manner_of_death="natural",
        disposal_method="burial",
        infectious_remains=False,
    )

    assert keys(items) == [
        "notification_of_death",
        "formal_identification",
        "death_report",
        "death_certificate",
        "burial_order",
        "informant_id_copy",
    ]


def test_unnatural_adds_police_and_post_mortem_before_the_death_report():
    items = keys(
        standard_items(
            manner_of_death="unnatural",
            disposal_method="burial",
            infectious_remains=False,
        )
    )

    assert items.index("police_case_registered") < items.index(
        "death_report"
    )
    assert "post_mortem_release" in items


def test_cremation_and_repatriation_replace_the_burial_order():
    cremation = keys(
        standard_items(
            manner_of_death="natural",
            disposal_method="cremation",
            infectious_remains=False,
        )
    )
    repatriation = keys(
        standard_items(
            manner_of_death="natural",
            disposal_method="repatriation",
            infectious_remains=False,
        )
    )

    assert "cremation_permit" in cremation
    assert "burial_order" not in cremation
    assert "export_permit" in repatriation
    assert "embalming_certificate" in repatriation
    assert "burial_order" not in repatriation


def test_infectious_remains_add_a_declaration():
    items = keys(
        standard_items(
            manner_of_death="natural",
            disposal_method="burial",
            infectious_remains=True,
        )
    )

    assert "infectious_remains_declaration" in items


def test_summary_counts_only_required_items():
    class Item:
        def __init__(self, required, status, label="x"):
            self.required = required
            self.status = status
            self.label = label

    summary = paperwork_summary(
        [
            Item(True, "obtained"),
            Item(True, "not_applicable"),
            Item(True, "pending", "Burial order"),
            Item(False, "pending", "Optional"),
        ]
    )

    assert summary == {
        "required_total": 3,
        "required_done": 2,
        "outstanding": ["Burial order"],
        "ready": False,
    }
    assert paperwork_summary([])["ready"] is False


# ============================================================
# PAPERWORK API
# ============================================================

def start_case(client, db, test_data, auth_headers, **fields):
    case = make_case(db, test_data["business_a"])

    assert create_record(
        client, auth_headers, test_data["manager"], case, **fields
    ).status_code == 201

    return case


def add_standard(client, auth_headers, user, case):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        f"/cases/{case.id}/paperwork/standard",
    )


def read_paperwork(client, auth_headers, user, case):
    return call(
        client, auth_headers, user, "GET", f"/cases/{case.id}/paperwork"
    ).json()


def item_ids(data):
    return {item["item_type"]: item["id"] for item in data["items"]}


def test_standard_needs_a_death_record_first(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = add_standard(
        client, auth_headers, test_data["manager"], case
    )

    assert response.status_code == 409
    assert "death record" in response.json()["detail"]


def test_standard_creates_the_checklist_in_order(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)

    response = add_standard(
        client, auth_headers, test_data["manager"], case
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert [i["item_type"] for i in data["items"]] == [
        "notification_of_death",
        "formal_identification",
        "death_report",
        "death_certificate",
        "burial_order",
        "informant_id_copy",
    ]
    assert all(i["status"] == "pending" for i in data["items"])
    assert data["summary"]["required_total"] == 5
    assert data["summary"]["required_done"] == 0
    assert data["summary"]["ready"] is False

    [entry] = audits(db, "paperwork.standard_added")
    assert len(entry.details["added"]) == 6


def test_standard_is_safe_to_repeat_and_adds_only_what_is_new(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]

    first = add_standard(client, auth_headers, manager, case).json()
    ids = item_ids(first)

    again = add_standard(client, auth_headers, manager, case).json()

    assert item_ids(again) == ids
    assert len(audits(db, "paperwork.standard_added")) == 1

    # The manner of death turns out to be unnatural.
    call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/death-record",
        json={
            "manner_of_death": "unnatural",
            "forensic_status": "referred",
        },
    )

    grown = add_standard(client, auth_headers, manager, case).json()
    grown_ids = item_ids(grown)

    assert {"police_case_registered", "post_mortem_release"} <= set(
        grown_ids
    )
    # Existing items keep their identity.
    assert all(grown_ids[key] == value for key, value in ids.items())


def test_obtaining_an_item_records_who_and_when(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())

    response = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/paperwork/{ids['burial_order']}",
        json={"status": "obtained", "reference_number": "BO-12345"},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "obtained"
    assert data["obtained_on"] == date.today().isoformat()
    assert data["obtained_by"] == str(manager.id)

    summary = read_paperwork(client, auth_headers, manager, case)["summary"]

    assert summary["required_done"] == 1
    assert "Burial order (BI-14)" not in summary["outstanding"]

    [entry] = audits(db, "paperwork.item_updated")

    assert entry.details["changes"]["status"] == {
        "old": "pending",
        "new": "obtained",
    }
    assert entry.details["changes"]["reference_number"]["new"] == (
        "[redacted]"
    )
    assert "BO-12345" not in str(entry.details)


def test_putting_an_item_back_to_pending_clears_who_and_when(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())
    url = f"/cases/{case.id}/paperwork/{ids['death_report']}"

    call(client, auth_headers, manager, "PATCH", url,
         json={"status": "obtained", "obtained_on": "2026-10-03"})

    assert call(
        client, auth_headers, manager, "PATCH", url,
        json={"status": "pending"},
    ).json()["obtained_on"] is None

    item = db.get(CasePaperworkItem, uuid.UUID(ids["death_report"]))
    db.refresh(item)

    assert item.obtained_by is None


def test_everything_obtained_makes_the_case_ready(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    data = add_standard(client, auth_headers, manager, case).json()

    for item in data["items"]:
        if item["required"]:
            assert call(
                client,
                auth_headers,
                manager,
                "PATCH",
                f"/cases/{case.id}/paperwork/{item['id']}",
                json={"status": "obtained"},
            ).status_code == 200

    summary = read_paperwork(client, auth_headers, manager, case)["summary"]

    assert summary["ready"] is True
    assert summary["outstanding"] == []


def test_waiving_a_required_item_needs_a_reason(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())
    url = f"/cases/{case.id}/paperwork/{ids['burial_order']}"

    refused = call(
        client, auth_headers, manager, "PATCH", url,
        json={"status": "not_applicable"},
    )

    assert refused.status_code == 422
    assert "reason" in refused.json()["detail"]

    allowed = call(
        client, auth_headers, manager, "PATCH", url,
        json={
            "status": "not_applicable",
            "notes": "Family will cremate instead",
        },
    )

    assert allowed.status_code == 200

    # An optional item can be waived without a reason.
    optional = call(
        client, auth_headers, manager, "PATCH",
        f"/cases/{case.id}/paperwork/{ids['informant_id_copy']}",
        json={"status": "not_applicable"},
    )

    assert optional.status_code == 200


def test_standard_items_cannot_be_renamed_or_made_optional(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())
    url = f"/cases/{case.id}/paperwork/{ids['burial_order']}"

    for body in ({"label": "Something else"}, {"required": False}):
        response = call(
            client, auth_headers, manager, "PATCH", url, json=body
        )

        assert response.status_code == 422, body


def test_custom_items_can_be_added_renamed_and_repeated(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    base = f"/cases/{case.id}/paperwork"

    first = call(
        client, auth_headers, manager, "POST", base,
        json={"label": "  Church approval  ", "required": True},
    )
    second = call(
        client, auth_headers, manager, "POST", base,
        json={"label": "Church approval"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201
    assert first.json()["label"] == "Church approval"
    assert first.json()["item_type"] == "custom"

    renamed = call(
        client, auth_headers, manager, "PATCH",
        f"{base}/{first.json()['id']}",
        json={"label": "Parish approval", "required": False},
    )

    assert renamed.status_code == 200
    assert renamed.json()["label"] == "Parish approval"
    assert len(audits(db, "paperwork.item_added")) == 2


def test_custom_item_needs_a_label(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)

    response = call(
        client, auth_headers, test_data["manager"], "POST",
        f"/cases/{case.id}/paperwork",
        json={"label": "   "},
    )

    assert response.status_code == 422


def test_custom_items_come_after_standard_ones(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    base = f"/cases/{case.id}/paperwork"

    call(client, auth_headers, manager, "POST", base,
         json={"label": "Early custom"})
    add_standard(client, auth_headers, manager, case)

    labels = [
        i["label"]
        for i in read_paperwork(client, auth_headers, manager, case)["items"]
    ]

    assert labels[0] == "Early custom"
    assert labels[-1] == "Copy of the informant's ID"


def test_a_document_must_belong_to_the_same_case(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    other_case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())
    url = f"/cases/{case.id}/paperwork/{ids['death_certificate']}"

    foreign = make_document(db, other_case, manager)
    own = make_document(db, case, manager)

    refused = call(
        client, auth_headers, manager, "PATCH", url,
        json={"document_id": str(foreign.id)},
    )
    accepted = call(
        client, auth_headers, manager, "PATCH", url,
        json={"document_id": str(own.id)},
    )

    assert refused.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json()["document_id"] == str(own.id)


def test_unknown_item_and_wrong_case_are_not_found(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    other_case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())

    missing = call(
        client, auth_headers, manager, "PATCH",
        f"/cases/{case.id}/paperwork/{uuid.uuid4()}",
        json={"status": "obtained"},
    )
    wrong_case = call(
        client, auth_headers, manager, "PATCH",
        f"/cases/{other_case.id}/paperwork/{ids['burial_order']}",
        json={"status": "obtained"},
    )

    assert missing.status_code == 404
    assert wrong_case.status_code == 404


def test_paperwork_is_frozen_on_archived_cases(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    ids = item_ids(add_standard(client, auth_headers, manager, case).json())

    case.is_archived = True
    db.commit()

    for method, path, body in (
        ("POST", f"/cases/{case.id}/paperwork/standard", None),
        ("POST", f"/cases/{case.id}/paperwork", {"label": "x"}),
        (
            "PATCH",
            f"/cases/{case.id}/paperwork/{ids['burial_order']}",
            {"status": "obtained"},
        ),
    ):
        response = call(
            client, auth_headers, manager, method, path, json=body
        )

        assert response.status_code == 409, path

    # It can still be read.
    assert call(
        client, auth_headers, manager, "GET",
        f"/cases/{case.id}/paperwork",
    ).status_code == 200


def test_another_business_cannot_use_the_checklist(
    client, db, test_data, auth_headers
):
    case = start_case(client, db, test_data, auth_headers)
    manager = test_data["manager"]
    add_standard(client, auth_headers, manager, case)

    outsider = test_data["other_business_manager"]
    base = f"/cases/{case.id}/paperwork"

    assert call(
        client, auth_headers, outsider, "GET", base
    ).status_code == 404
    assert call(
        client, auth_headers, outsider, "POST", base + "/standard"
    ).status_code == 404
    assert call(
        client, auth_headers, outsider, "POST", base,
        json={"label": "x"},
    ).status_code == 404


def test_paperwork_permissions(client, db, test_data, auth_headers):
    case = start_case(client, db, test_data, auth_headers)
    staff = test_data["staff"]
    base = f"/cases/{case.id}/paperwork"

    assert add_standard(
        client, auth_headers, staff, case
    ).status_code == 200

    deny(db, staff, "paperwork.manage")

    assert call(
        client, auth_headers, staff, "POST", base, json={"label": "x"}
    ).status_code == 403
    assert call(
        client, auth_headers, staff, "GET", base
    ).status_code == 200

    deny(db, staff, "paperwork.view")

    assert call(
        client, auth_headers, staff, "GET", base
    ).status_code == 403


def test_main_admin_has_full_access(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    admin = test_data["main_admin"]

    assert create_record(
        client, auth_headers, admin, case
    ).status_code == 201
    assert add_standard(
        client, auth_headers, admin, case
    ).status_code == 200


def test_checklist_needs_a_login(client, db, test_data):
    case = make_case(db, test_data["business_a"])

    assert client.get(f"/cases/{case.id}/paperwork").status_code in (
        401,
        403,
    )
    assert client.get(
        f"/cases/{case.id}/death-record"
    ).status_code in (401, 403)
