import uuid

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.case_payment import CasePayment
from app.models.case_service import CaseService
from app.models.financial_document import (
    FinancialDocument,
    PaymentReceipt,
)
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.user_permission import UserPermission


YEAR = datetime.now(timezone.utc).year


# ============================================================
# HELPERS
# ============================================================

def set_permission(db, user_id, permission_key, effect):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    db.add(
        UserPermission(
            user_id=user_id,
            permission_id=permission.id,
            effect=effect,
        )
    )
    db.commit()


def make_case(db, business, *, archived=False):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"FD-CASE-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Document Test",
        date_of_death=date(2026, 10, 1),
        status="open",
        is_archived=archived,
    )
    db.add(case)
    db.commit()

    return case


def make_service(db, business, case, *, name="Coffin", price=100):
    service = CaseService(
        business_id=business.id,
        case_id=case.id,
        service_type="coffin",
        service_name=name,
        quantity=1,
        unit_price=price,
        total_price=price,
    )
    db.add(service)
    db.commit()

    return service


def make_payment(db, business, case, amount="500.00"):
    payment = CasePayment(
        business_id=business.id,
        case_id=case.id,
        amount=Decimal(amount),
        payment_method="eft",
        reference=f"REF-{uuid.uuid4().hex[:8].upper()}",
        payment_date=date(2026, 10, 2),
    )
    db.add(payment)
    db.commit()

    return payment


def two_lines():
    return [
        {
            "description": "Standard coffin",
            "quantity": "2",
            "unit_price": "100.00",
        },
        {
            "description": "Hearse hire",
            "quantity": "1",
            "unit_price": "50.00",
        },
    ]


def create_document(
    client,
    headers,
    case,
    document_type="quote",
    **overrides,
):
    body = {
        "document_type": document_type,
        "discount": "10.00",
        "tax": "15.00",
        "lines": two_lines(),
    }
    body.update(overrides)

    response = client.post(
        f"/cases/{case.id}/financial-documents",
        json=body,
        headers=headers,
    )

    assert response.status_code == 201, response.text

    return response.json()


def issue(client, headers, document_id):
    return client.post(
        f"/financial-documents/{document_id}/issue",
        headers=headers,
    )


def issued_document(
    client,
    headers,
    case,
    document_type="quote",
    **overrides,
):
    document = create_document(
        client, headers, case, document_type, **overrides
    )

    response = issue(client, headers, document["id"])
    assert response.status_code == 200, response.text

    return response.json()


def audit_entries(db, entity_id, action):
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
        )
        .all()
    )


# ============================================================
# CREATE
# ============================================================

def test_create_draft_quote_calculates_totals(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    case = make_case(db, business)

    document = create_document(
        client, auth_headers(manager), case
    )

    # 2 x 100.00 + 1 x 50.00 = 250.00, less 10.00, plus 15.00
    assert document["status"] == "draft"
    assert document["number"] is None
    assert Decimal(document["subtotal"]) == Decimal("250.00")
    assert Decimal(document["total"]) == Decimal("255.00")
    assert [line["position"] for line in document["lines"]] == [0, 1]
    assert Decimal(document["lines"][0]["line_total"]) == Decimal("200.00")

    audit = audit_entries(
        db, uuid.UUID(document["id"]), "financial_document.created"
    )

    assert len(audit) == 1
    assert audit[0].user_id == manager.id
    assert audit[0].business_id == business.id
    assert audit[0].details["line_count"] == 2


def test_type_specific_dates_are_enforced(
    client, db, test_data, auth_headers,
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    headers = auth_headers(manager)

    bad_invoice = client.post(
        f"/cases/{case.id}/financial-documents",
        json={
            "document_type": "invoice",
            "valid_until": "2027-01-01",
            "lines": two_lines(),
        },
        headers=headers,
    )
    bad_quote = client.post(
        f"/cases/{case.id}/financial-documents",
        json={
            "document_type": "quote",
            "due_date": "2027-01-01",
            "lines": two_lines(),
        },
        headers=headers,
    )

    assert bad_invoice.status_code == 422
    assert bad_quote.status_code == 422
    assert db.query(FinancialDocument).count() == 0


def test_discount_above_subtotal_is_rejected_and_nothing_is_saved(
    client, db, test_data, auth_headers,
):
    case = make_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial-documents",
        json={
            "document_type": "quote",
            "discount": "500.00",
            "lines": two_lines(),
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422
    assert "Discount" in response.json()["detail"]
    assert db.query(FinancialDocument).count() == 0


def test_line_can_link_only_to_a_service_on_the_same_case(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])
    case = make_case(db, business)
    other_case = make_case(db, business)
    own_service = make_service(db, business, case)
    foreign_service = make_service(db, business, other_case)

    ok = create_document(
        client,
        headers,
        case,
        lines=[
            {
                "description": "Coffin",
                "unit_price": "100.00",
                "case_service_id": str(own_service.id),
            }
        ],
    )
    assert ok["lines"][0]["case_service_id"] == str(own_service.id)

    rejected = client.post(
        f"/cases/{case.id}/financial-documents",
        json={
            "document_type": "quote",
            "lines": [
                {
                    "description": "Coffin",
                    "unit_price": "100.00",
                    "case_service_id": str(foreign_service.id),
                }
            ],
        },
        headers=headers,
    )

    assert rejected.status_code == 422


def test_archived_case_cannot_receive_documents(
    client, db, test_data, auth_headers,
):
    case = make_case(db, test_data["business_a"], archived=True)

    response = client.post(
        f"/cases/{case.id}/financial-documents",
        json={"document_type": "quote", "lines": two_lines()},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409


# ============================================================
# DRAFT EDITING
# ============================================================

def test_editing_draft_recalculates_and_audits_exact_changes(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    document = create_document(client, headers, case)

    response = client.patch(
        f"/financial-documents/{document['id']}",
        json={"discount": "0.00", "tax": "37.50", "notes": "Private"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert Decimal(response.json()["total"]) == Decimal("287.50")

    audit = audit_entries(
        db, uuid.UUID(document["id"]), "financial_document.updated"
    )[0]
    changes = audit.details["changes"]

    assert set(changes) == {"discount", "tax", "notes"}
    assert changes["discount"] == {"old": "10.00", "new": "0.00"}
    assert changes["tax"] == {"old": "15.00", "new": "37.50"}
    assert changes["notes"]["old"] == "[redacted]"
    assert "Private" not in str(audit.details)


def test_line_changes_flow_into_totals_and_audit(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    document = create_document(
        client, headers, case, discount="0.00", tax="0.00"
    )
    document_id = document["id"]

    added = client.post(
        f"/financial-documents/{document_id}/lines",
        json={
            "description": "Flowers for Mr Dlamini",
            "quantity": "1",
            "unit_price": "75.00",
        },
        headers=headers,
    )
    assert added.status_code == 201, added.text
    assert Decimal(added.json()["total"]) == Decimal("325.00")
    assert added.json()["lines"][-1]["position"] == 2

    new_line = added.json()["lines"][-1]

    updated = client.patch(
        f"/financial-documents/{document_id}/lines/{new_line['id']}",
        json={"quantity": "2", "description": "Flowers for the Dlamini family"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert Decimal(updated.json()["total"]) == Decimal("400.00")

    removed = client.delete(
        f"/financial-documents/{document_id}/lines/{new_line['id']}",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text
    assert Decimal(removed.json()["total"]) == Decimal("250.00")
    assert len(removed.json()["lines"]) == 2

    doc_uuid = uuid.UUID(document_id)

    for action in (
        "financial_document.line_added",
        "financial_document.line_updated",
        "financial_document.line_removed",
    ):
        assert len(audit_entries(db, doc_uuid, action)) == 1

    line_audit = audit_entries(
        db, doc_uuid, "financial_document.line_updated"
    )[0]

    # Line descriptions can name the deceased, so they are redacted.
    assert line_audit.details["changes"]["description"]["old"] == "[redacted]"
    assert "Dlamini" not in str(line_audit.details)
    assert line_audit.details["changes"]["quantity"] == {
        "old": "1.00",
        "new": "2.00",
    }


def test_removing_a_line_cannot_leave_discount_above_subtotal(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    document = create_document(
        client, headers, case, discount="120.00", tax="0.00"
    )
    big_line = document["lines"][0]   # 200.00 of the 250.00 subtotal

    response = client.delete(
        f"/financial-documents/{document['id']}/lines/{big_line['id']}",
        headers=headers,
    )

    assert response.status_code == 422

    unchanged = client.get(
        f"/financial-documents/{document['id']}",
        headers=headers,
    ).json()

    assert len(unchanged["lines"]) == 2
    assert Decimal(unchanged["subtotal"]) == Decimal("250.00")


def test_draft_can_be_deleted_with_audit(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    document = create_document(client, headers, case)

    response = client.delete(
        f"/financial-documents/{document['id']}",
        headers=headers,
    )

    assert response.status_code == 204
    assert db.query(FinancialDocument).count() == 0
    assert len(
        audit_entries(
            db,
            uuid.UUID(document["id"]),
            "financial_document.deleted",
        )
    ) == 1


# ============================================================
# ISSUING
# ============================================================

def test_issue_assigns_number_dates_and_issuer(
    client, db, test_data, auth_headers,
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    quote = issued_document(client, auth_headers(manager), case)

    assert quote["status"] == "issued"
    assert quote["number"] == f"QUO-{YEAR}-00001"
    assert quote["issued_by"] == str(manager.id)
    assert quote["issued_at"] is not None

    expected = date.today() + timedelta(days=30)
    assert abs(
        (date.fromisoformat(quote["valid_until"]) - expected).days
    ) <= 1

    invoice = issued_document(
        client,
        auth_headers(manager),
        make_case(db, test_data["business_a"]),
        "invoice",
    )

    expected_due = date.today() + timedelta(days=14)
    assert abs(
        (date.fromisoformat(invoice["due_date"]) - expected_due).days
    ) <= 1


def test_numbers_are_sequential_per_type_and_per_business(
    client, db, test_data, auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    headers_a = auth_headers(test_data["manager"])
    headers_b = auth_headers(test_data["other_business_manager"])

    first = issued_document(
        client, headers_a, make_case(db, business_a)
    )
    second = issued_document(
        client, headers_a, make_case(db, business_a)
    )
    invoice = issued_document(
        client, headers_a, make_case(db, business_a), "invoice"
    )
    other_business = issued_document(
        client, headers_b, make_case(db, business_b)
    )

    assert first["number"] == f"QUO-{YEAR}-00001"
    assert second["number"] == f"QUO-{YEAR}-00002"
    assert invoice["number"] == f"INV-{YEAR}-00001"
    assert other_business["number"] == f"QUO-{YEAR}-00001"


def test_discarded_drafts_leave_no_gaps_in_numbers(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])

    discarded = create_document(client, headers, case)
    client.delete(
        f"/financial-documents/{discarded['id']}", headers=headers
    )

    kept = issued_document(client, headers, case)

    assert kept["number"] == f"QUO-{YEAR}-00001"


def test_document_without_lines_cannot_be_issued(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    document = create_document(
        client, headers, case, lines=[], discount="0.00", tax="0.00"
    )

    response = issue(client, headers, document["id"])

    assert response.status_code == 422
    assert "at least one line" in response.json()["detail"]


def test_issue_is_audited_and_cannot_be_repeated(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)

    audit = audit_entries(
        db, uuid.UUID(quote["id"]), "financial_document.issued"
    )

    assert len(audit) == 1
    assert audit[0].details["number"] == quote["number"]

    again = issue(client, headers, quote["id"])

    assert again.status_code == 409


def test_number_collision_is_reported_and_leaves_draft_intact(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])
    case = make_case(db, business)

    # A numbered quote that makes the next computed number collide.
    db.add(
        FinancialDocument(
            business_id=business.id,
            case_id=case.id,
            document_type="quote",
            number=f"QUO-{YEAR}-00002",
            status="issued",
        )
    )
    db.commit()

    draft = create_document(client, headers, case)

    response = issue(client, headers, draft["id"])

    assert response.status_code == 409
    assert "number" in response.json()["detail"].lower()

    reloaded = client.get(
        f"/financial-documents/{draft['id']}", headers=headers
    ).json()

    assert reloaded["status"] == "draft"
    assert reloaded["number"] is None


# ============================================================
# ISSUED DOCUMENTS ARE PERMANENT
# ============================================================

def test_issued_document_cannot_be_edited_or_deleted(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)
    document_id = quote["id"]
    line_id = quote["lines"][0]["id"]

    attempts = [
        client.patch(
            f"/financial-documents/{document_id}",
            json={"tax": "0.00"},
            headers=headers,
        ),
        client.post(
            f"/financial-documents/{document_id}/lines",
            json={"description": "Extra", "unit_price": "1.00"},
            headers=headers,
        ),
        client.patch(
            f"/financial-documents/{document_id}/lines/{line_id}",
            json={"unit_price": "1.00"},
            headers=headers,
        ),
        client.delete(
            f"/financial-documents/{document_id}/lines/{line_id}",
            headers=headers,
        ),
        client.delete(
            f"/financial-documents/{document_id}",
            headers=headers,
        ),
    ]

    for response in attempts:
        assert response.status_code == 409, response.text

    unchanged = client.get(
        f"/financial-documents/{document_id}", headers=headers
    ).json()

    assert unchanged["total"] == quote["total"]
    assert len(unchanged["lines"]) == 2


# ============================================================
# VOID
# ============================================================

def test_void_requires_reason_and_records_it_on_the_document(
    client, db, test_data, auth_headers,
):
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)

    missing = client.post(
        f"/financial-documents/{quote['id']}/void",
        json={"reason": ""},
        headers=headers,
    )
    assert missing.status_code == 422

    response = client.post(
        f"/financial-documents/{quote['id']}/void",
        json={"reason": "Family chose another coffin"},
        headers=headers,
    )

    assert response.status_code == 200, response.text

    voided = response.json()

    assert voided["status"] == "void"
    assert voided["void_reason"] == "Family chose another coffin"
    assert voided["voided_by"] == str(manager.id)
    assert voided["voided_at"] is not None
    # The number is kept: voiding never reuses or removes it.
    assert voided["number"] == quote["number"]

    audit = audit_entries(
        db, uuid.UUID(quote["id"]), "financial_document.voided"
    )[0]

    assert audit.details["reason_recorded"] is True
    assert "coffin" not in str(audit.details)


def test_draft_and_void_documents_cannot_be_voided(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])

    draft = create_document(client, headers, case)
    on_draft = client.post(
        f"/financial-documents/{draft['id']}/void",
        json={"reason": "No"},
        headers=headers,
    )
    assert on_draft.status_code == 409

    quote = issued_document(client, headers, case)
    client.post(
        f"/financial-documents/{quote['id']}/void",
        json={"reason": "First"},
        headers=headers,
    )
    twice = client.post(
        f"/financial-documents/{quote['id']}/void",
        json={"reason": "Second"},
        headers=headers,
    )
    assert twice.status_code == 409


def test_case_can_hold_only_one_issued_invoice_until_it_is_voided(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])

    first = issued_document(client, headers, case, "invoice")
    second = create_document(client, headers, case, "invoice")

    blocked = issue(client, headers, second["id"])
    assert blocked.status_code == 409
    assert first["number"] in blocked.json()["detail"]

    client.post(
        f"/financial-documents/{first['id']}/void",
        json={"reason": "Wrong amounts"},
        headers=headers,
    )

    allowed = issue(client, headers, second["id"])

    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["number"] == f"INV-{YEAR}-00002"


# ============================================================
# QUOTE WORKFLOW
# ============================================================

def test_accepted_quote_converts_into_draft_invoice(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)

    accepted = client.post(
        f"/financial-documents/{quote['id']}/accept", headers=headers
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["accepted_at"] is not None

    converted = client.post(
        f"/financial-documents/{quote['id']}/convert", headers=headers
    )

    assert converted.status_code == 201, converted.text

    invoice = converted.json()

    assert invoice["document_type"] == "invoice"
    assert invoice["status"] == "draft"
    assert invoice["number"] is None
    assert invoice["source_quote_id"] == quote["id"]
    assert invoice["total"] == quote["total"]
    assert len(invoice["lines"]) == 2

    reloaded = client.get(
        f"/financial-documents/{quote['id']}", headers=headers
    ).json()
    assert reloaded["status"] == "converted"

    again = client.post(
        f"/financial-documents/{quote['id']}/convert", headers=headers
    )
    assert again.status_code == 409

    quote_audit = audit_entries(
        db, uuid.UUID(quote["id"]), "financial_document.converted"
    )[0]
    assert quote_audit.details["invoice_id"] == invoice["id"]


def test_quote_must_be_accepted_before_conversion(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)

    response = client.post(
        f"/financial-documents/{quote['id']}/convert", headers=headers
    )

    assert response.status_code == 409


def test_declined_quote_is_final(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)

    declined = client.post(
        f"/financial-documents/{quote['id']}/decline", headers=headers
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"

    for action in ("accept", "convert"):
        response = client.post(
            f"/financial-documents/{quote['id']}/{action}",
            headers=headers,
        )
        assert response.status_code == 409


def test_expired_quote_cannot_be_accepted(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    quote = issued_document(
        client, headers, case, valid_until="2020-01-01"
    )

    response = client.post(
        f"/financial-documents/{quote['id']}/accept", headers=headers
    )

    assert response.status_code == 409
    assert "expired" in response.json()["detail"]


def test_quote_decisions_do_not_apply_to_invoices(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    invoice = issued_document(client, headers, case, "invoice")

    for action in ("accept", "decline", "convert"):
        response = client.post(
            f"/financial-documents/{invoice['id']}/{action}",
            headers=headers,
        )
        assert response.status_code == 409, action


# ============================================================
# READING
# ============================================================

def test_listing_filters_by_type_status_and_case(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])
    case_one = make_case(db, business)
    case_two = make_case(db, business)

    draft_quote = create_document(client, headers, case_one)
    issued_invoice = issued_document(
        client, headers, case_two, "invoice"
    )

    everything = client.get(
        "/financial-documents", headers=headers
    ).json()
    assert {d["id"] for d in everything} == {
        draft_quote["id"],
        issued_invoice["id"],
    }

    quotes = client.get(
        "/financial-documents?document_type=quote", headers=headers
    ).json()
    assert [d["id"] for d in quotes] == [draft_quote["id"]]

    issued = client.get(
        "/financial-documents?document_status=issued", headers=headers
    ).json()
    assert [d["id"] for d in issued] == [issued_invoice["id"]]

    by_case = client.get(
        f"/cases/{case_two.id}/financial-documents", headers=headers
    ).json()
    assert [d["id"] for d in by_case] == [issued_invoice["id"]]


# ============================================================
# PERMISSIONS
# ============================================================

def test_staff_can_view_but_not_create_issue_or_void(
    client, db, test_data, auth_headers,
):
    manager_headers = auth_headers(test_data["manager"])
    staff_headers = auth_headers(test_data["staff"])
    case = make_case(db, test_data["business_a"])
    draft = create_document(client, manager_headers, case)
    quote = issued_document(client, manager_headers, case)

    assert client.get(
        f"/financial-documents/{draft['id']}", headers=staff_headers
    ).status_code == 200
    assert client.get(
        "/financial-documents", headers=staff_headers
    ).status_code == 200

    forbidden = [
        client.post(
            f"/cases/{case.id}/financial-documents",
            json={"document_type": "quote", "lines": two_lines()},
            headers=staff_headers,
        ),
        client.patch(
            f"/financial-documents/{draft['id']}",
            json={"tax": "0.00"},
            headers=staff_headers,
        ),
        issue(client, staff_headers, draft["id"]),
        client.post(
            f"/financial-documents/{quote['id']}/void",
            json={"reason": "No"},
            headers=staff_headers,
        ),
        client.delete(
            f"/financial-documents/{draft['id']}",
            headers=staff_headers,
        ),
    ]

    for response in forbidden:
        assert response.status_code == 403, response.text


def test_denying_issue_blocks_issuing_but_not_drafting(
    client, db, test_data, auth_headers,
):
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, test_data["business_a"])
    draft = create_document(client, headers, case)

    set_permission(db, manager.id, "financial_documents.issue", "deny")

    assert issue(client, headers, draft["id"]).status_code == 403

    still_editable = client.patch(
        f"/financial-documents/{draft['id']}",
        json={"tax": "0.00"},
        headers=headers,
    )
    assert still_editable.status_code == 200


def test_denying_void_blocks_voiding_but_not_viewing(
    client, db, test_data, auth_headers,
):
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, test_data["business_a"])
    quote = issued_document(client, headers, case)

    set_permission(db, manager.id, "financial_documents.void", "deny")

    voided = client.post(
        f"/financial-documents/{quote['id']}/void",
        json={"reason": "No"},
        headers=headers,
    )
    assert voided.status_code == 403

    assert client.get(
        f"/financial-documents/{quote['id']}", headers=headers
    ).json()["status"] == "issued"


# ============================================================
# TENANT ISOLATION
# ============================================================

def test_other_business_cannot_see_or_change_documents(
    client, db, test_data, auth_headers,
):
    headers_a = auth_headers(test_data["manager"])
    headers_b = auth_headers(test_data["other_business_manager"])
    case = make_case(db, test_data["business_a"])
    draft = create_document(client, headers_a, case)
    quote = issued_document(client, headers_a, case)

    responses = [
        client.get(f"/financial-documents/{draft['id']}", headers=headers_b),
        client.patch(
            f"/financial-documents/{draft['id']}",
            json={"tax": "0.00"},
            headers=headers_b,
        ),
        issue(client, headers_b, draft["id"]),
        client.post(
            f"/financial-documents/{quote['id']}/void",
            json={"reason": "No"},
            headers=headers_b,
        ),
        client.post(
            f"/financial-documents/{quote['id']}/accept",
            headers=headers_b,
        ),
        client.delete(
            f"/financial-documents/{draft['id']}", headers=headers_b
        ),
        client.get(
            f"/cases/{case.id}/financial-documents", headers=headers_b
        ),
        client.post(
            f"/cases/{case.id}/financial-documents",
            json={"document_type": "quote", "lines": two_lines()},
            headers=headers_b,
        ),
    ]

    for response in responses:
        assert response.status_code == 404, response.text

    assert client.get(
        "/financial-documents", headers=headers_b
    ).json() == []


# ============================================================
# RECEIPTS
# ============================================================

def test_receipt_snapshots_the_payment(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, business)
    payment = make_payment(db, business, case, "500.00")

    response = client.post(
        f"/cases/payments/{payment.id}/receipt", headers=headers
    )

    assert response.status_code == 201, response.text

    receipt = response.json()

    assert receipt["receipt_number"] == f"REC-{YEAR}-00001"
    assert receipt["case_number"] == case.case_number
    assert Decimal(receipt["amount"]) == Decimal("500.00")
    assert receipt["payment_method"] == "eft"
    assert receipt["payment_reference"] == payment.reference
    assert receipt["payment_date"] == "2026-10-02"
    assert receipt["issued_by"] == str(manager.id)

    audit = audit_entries(
        db, uuid.UUID(receipt["id"]), "receipt.issued"
    )

    assert len(audit) == 1
    assert audit[0].details["payment_id"] == str(payment.id)


def test_payment_can_only_be_receipted_once(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])
    payment = make_payment(
        db, business, make_case(db, business)
    )

    first = client.post(
        f"/cases/payments/{payment.id}/receipt", headers=headers
    )
    second = client.post(
        f"/cases/payments/{payment.id}/receipt", headers=headers
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert first.json()["receipt_number"] in second.json()["detail"]
    assert db.query(PaymentReceipt).count() == 1


def test_receipts_can_be_read_by_payment_id_and_case(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])
    case = make_case(db, business)
    first_payment = make_payment(db, business, case, "100.00")
    second_payment = make_payment(db, business, case, "200.00")

    first = client.post(
        f"/cases/payments/{first_payment.id}/receipt", headers=headers
    ).json()
    second = client.post(
        f"/cases/payments/{second_payment.id}/receipt", headers=headers
    ).json()

    assert second["receipt_number"] == f"REC-{YEAR}-00002"

    by_payment = client.get(
        f"/cases/payments/{first_payment.id}/receipt", headers=headers
    )
    assert by_payment.json()["id"] == first["id"]

    by_id = client.get(f"/receipts/{second['id']}", headers=headers)
    assert by_id.json()["id"] == second["id"]

    listed = client.get(
        f"/cases/{case.id}/receipts", headers=headers
    ).json()
    assert {r["id"] for r in listed} == {first["id"], second["id"]}

    unreceipted = make_payment(db, business, case)
    missing = client.get(
        f"/cases/payments/{unreceipted.id}/receipt", headers=headers
    )
    assert missing.status_code == 404


def test_receipted_payment_cannot_be_edited_or_deleted(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])
    case = make_case(db, business)
    receipted = make_payment(db, business, case, "500.00")
    free = make_payment(db, business, case, "50.00")

    receipt = client.post(
        f"/cases/payments/{receipted.id}/receipt", headers=headers
    ).json()

    edit = client.patch(
        f"/cases/payments/{receipted.id}",
        json={"amount": "1.00"},
        headers=headers,
    )
    delete = client.delete(
        f"/cases/payments/{receipted.id}", headers=headers
    )

    assert edit.status_code == 409
    assert delete.status_code == 409
    assert receipt["receipt_number"] in edit.json()["detail"]

    db.expire_all()
    assert db.get(CasePayment, receipted.id).amount == Decimal("500.00")

    # A payment without a receipt is still editable and deletable.
    assert client.patch(
        f"/cases/payments/{free.id}",
        json={"amount": "60.00"},
        headers=headers,
    ).status_code == 200
    assert client.delete(
        f"/cases/payments/{free.id}", headers=headers
    ).status_code == 204


def test_receipt_permissions(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager_headers = auth_headers(test_data["manager"])
    staff_headers = auth_headers(test_data["staff"])
    case = make_case(db, business)
    payment = make_payment(db, business, case)

    denied = client.post(
        f"/cases/payments/{payment.id}/receipt", headers=staff_headers
    )
    assert denied.status_code == 403

    receipt = client.post(
        f"/cases/payments/{payment.id}/receipt",
        headers=manager_headers,
    ).json()

    assert client.get(
        f"/receipts/{receipt['id']}", headers=staff_headers
    ).status_code == 200
    assert client.get(
        f"/cases/{case.id}/receipts", headers=staff_headers
    ).status_code == 200


def test_receipts_are_tenant_isolated_and_numbered_per_business(
    client, db, test_data, auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    headers_a = auth_headers(test_data["manager"])
    headers_b = auth_headers(test_data["other_business_manager"])
    case_a = make_case(db, business_a)
    case_b = make_case(db, business_b)
    payment_a = make_payment(db, business_a, case_a)
    payment_b = make_payment(db, business_b, case_b)

    receipt_a = client.post(
        f"/cases/payments/{payment_a.id}/receipt", headers=headers_a
    ).json()
    receipt_b = client.post(
        f"/cases/payments/{payment_b.id}/receipt", headers=headers_b
    ).json()

    assert receipt_a["receipt_number"] == receipt_b["receipt_number"]

    cross = [
        client.post(
            f"/cases/payments/{payment_a.id}/receipt", headers=headers_b
        ),
        client.get(
            f"/cases/payments/{payment_a.id}/receipt", headers=headers_b
        ),
        client.get(f"/receipts/{receipt_a['id']}", headers=headers_b),
        client.get(f"/cases/{case_a.id}/receipts", headers=headers_b),
    ]

    for response in cross:
        assert response.status_code == 404, response.text
