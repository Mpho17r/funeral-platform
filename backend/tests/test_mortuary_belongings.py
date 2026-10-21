import uuid

import pytest

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase
from app.models.mortuary import MortuaryBelonging, RemainsRecord
from app.models.permission import Permission
from app.models.user_permission import UserPermission


def make_case(db, business):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"MB-{uuid.uuid4().hex[:10].upper()}",
        deceased_full_name="Belongings Test Person",
        status="open",
        is_archived=False,
    )
    db.add(case)
    db.commit()
    return case


def take_in(client, auth_headers, user, case):
    response = client.post(
        f"/cases/{case.id}/remains",
        json={
            "received_from_type": "hospital",
            "belongings": "Legacy text must remain unchanged",
        },
        headers=auth_headers(user),
    )
    assert response.status_code == 201, response.text
    return response


def create_item(client, auth_headers, user, case, **overrides):
    payload = {
        "description": "Wallet",
        "quantity": 1,
        "condition": "Sealed in an evidence bag",
        "storage_location": "Secure cabinet A",
        "received_from": "Hospital representative",
        "received_by_name": "Receiving staff",
        "notes": "Handle carefully",
    }
    payload.update(overrides)

    return client.post(
        f"/cases/{case.id}/remains/belongings",
        json=payload,
        headers=auth_headers(user),
    )


def deny(db, user, key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == key)
        .first()
    )
    assert permission is not None, key

    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()


def make_ready_case(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    take_in(client, auth_headers, test_data["manager"], case)
    return case


def test_create_and_list_belongings(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)

    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text

    item = created.json()
    assert item["description"] == "Wallet"
    assert item["quantity"] == 1
    assert item["storage_location"] == "Secure cabinet A"
    assert item["status"] == "in_safekeeping"
    assert item["received_by"] is not None
    assert item["received_at"] is not None

    listed = client.get(
        f"/cases/{case.id}/remains/belongings",
        headers=auth_headers(manager),
    )
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()] == [item["id"]]

    stored = (
        db.query(MortuaryBelonging)
        .filter(MortuaryBelonging.id == item["id"])
        .one()
    )
    assert str(stored.business_id) == str(test_data["business_a"].id)


def test_update_belonging_in_safekeeping(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)
    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text

    item_id = created.json()["id"]
    updated = client.patch(
        f"/cases/{case.id}/remains/belongings/{item_id}",
        json={
            "quantity": 2,
            "storage_location": "Secure cabinet B",
        },
        headers=auth_headers(manager),
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["quantity"] == 2
    assert updated.json()["storage_location"] == "Secure cabinet B"


def test_return_one_item_without_returning_another(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)

    first = create_item(
        client, auth_headers, manager, case, description="Wallet"
    )
    second = create_item(
        client, auth_headers, manager, case, description="Watch"
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    first_id = first.json()["id"]
    second_id = second.json()["id"]

    returned = client.post(
        f"/cases/{case.id}/remains/belongings/{first_id}/return",
        json={
            "returned_to_name": "Family representative",
            "notes": "Identity checked",
        },
        headers=auth_headers(manager),
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "returned"
    assert returned.json()["returned_to_name"] == "Family representative"
    assert returned.json()["returned_at"] is not None

    listed = client.get(
        f"/cases/{case.id}/remains/belongings",
        headers=auth_headers(manager),
    )
    items = {item["id"]: item for item in listed.json()}
    assert items[first_id]["status"] == "returned"
    assert items[second_id]["status"] == "in_safekeeping"


def test_cannot_edit_returned_item_or_return_it_twice(
    client, test_data, auth_headers, db
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)
    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    returned = client.post(
        f"/cases/{case.id}/remains/belongings/{item_id}/return",
        json={"returned_to_name": "Family representative"},
        headers=auth_headers(manager),
    )
    assert returned.status_code == 200, returned.text

    edit_again = client.patch(
        f"/cases/{case.id}/remains/belongings/{item_id}",
        json={"quantity": 3},
        headers=auth_headers(manager),
    )
    assert edit_again.status_code == 409

    return_again = client.post(
        f"/cases/{case.id}/remains/belongings/{item_id}/return",
        json={"returned_to_name": "Another recipient"},
        headers=auth_headers(manager),
    )
    assert return_again.status_code == 409


def test_transfer_item_records_destination(
    client, test_data, auth_headers, db
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)
    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    response = client.post(
        f"/cases/{case.id}/remains/belongings/{item_id}/transfer",
        json={
            "transferred_to_location": "Secure cabinet B",
            "notes": "Moved under supervision",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text
    item = response.json()
    assert item["status"] == "transferred"
    assert item["transferred_to_location"] == "Secure cabinet B"
    assert item["storage_location"] == "Secure cabinet B"
    assert item["transferred_by"] is not None
    assert item["transferred_at"] is not None

    edit_again = client.patch(
        f"/cases/{case.id}/remains/belongings/{item_id}",
        json={"quantity": 4},
        headers=auth_headers(manager),
    )
    assert edit_again.status_code == 409


def test_rejects_invalid_item_values(client, test_data, auth_headers, db):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)

    response = create_item(
        client, auth_headers, manager, case, quantity=0
    )
    assert response.status_code == 422

    response = create_item(
        client, auth_headers, manager, case, description=""
    )
    assert response.status_code == 422


def test_belongings_are_tenant_isolated(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    other_manager = test_data["other_business_manager"]

    case_a = make_ready_case(client, db, test_data, auth_headers)
    created = create_item(client, auth_headers, manager, case_a)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    other_case = make_case(db, test_data["business_b"])

    # Another business cannot access the first business's case.
    response = client.get(
        f"/cases/{case_a.id}/remains/belongings",
        headers=auth_headers(other_manager),
    )
    assert response.status_code == 404

    # Even a valid case ID cannot be used to address an item
    # attached to a different remains record.
    take_in(client, auth_headers, other_manager, other_case)

    response = client.get(
        f"/cases/{other_case.id}/remains/belongings",
        headers=auth_headers(other_manager),
    )
    assert response.status_code == 200, response.text
    assert response.json() == []

    response = client.patch(
        f"/cases/{other_case.id}/remains/belongings/{item_id}",
        json={"quantity": 9},
        headers=auth_headers(other_manager),
    )
    assert response.status_code == 404


def test_staff_role_can_view_and_manage_belongings_by_default(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    staff = test_data["staff"]
    case = make_ready_case(client, db, test_data, auth_headers)

    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text

    listed = client.get(
        f"/cases/{case.id}/remains/belongings",
        headers=auth_headers(staff),
    )
    assert listed.status_code == 200, listed.text

    # The existing FuneralOS staff role includes remains.manage.
    staff_created = create_item(
        client,
        auth_headers,
        staff,
        case,
        description="Staff-recorded item",
    )
    assert staff_created.status_code == 201, staff_created.text


def test_explicit_remains_manage_deny_blocks_belongings_creation(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)
    deny(db, manager, "remains.manage")

    response = create_item(client, auth_headers, manager, case)
    assert response.status_code == 403


def test_audit_events_do_not_store_sensitive_belonging_text(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)

    secret_description = "PRIVATE-WALLET-DESCRIPTION-92A"
    secret_recipient = "PRIVATE-RECIPIENT-NAME-92B"
    secret_note = "PRIVATE-NOTE-CONTENT-92C"

    created = create_item(
        client,
        auth_headers,
        manager,
        case,
        description=secret_description,
        notes=secret_note,
    )
    assert created.status_code == 201, created.text

    item_id = created.json()["id"]
    returned = client.post(
        f"/cases/{case.id}/remains/belongings/{item_id}/return",
        json={
            "returned_to_name": secret_recipient,
            "notes": secret_note,
        },
        headers=auth_headers(manager),
    )
    assert returned.status_code == 200, returned.text

    entries = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "mortuary_belonging")
        .all()
    )
    assert len(entries) >= 2

    serialized = " ".join(
        f"{entry.details} {entry.notes}" for entry in entries
    )
    assert secret_description not in serialized
    assert secret_recipient not in serialized
    assert secret_note not in serialized

    actions = {entry.action for entry in entries}
    assert "mortuary.belonging.created" in actions
    assert "mortuary.belonging.returned" in actions


def test_legacy_belongings_text_is_not_overwritten(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)

    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text

    remains = (
        db.query(RemainsRecord)
        .filter(RemainsRecord.case_id == case.id)
        .one()
    )
    assert remains.belongings == "Legacy text must remain unchanged"

    listed = client.get(
        f"/cases/{case.id}/remains/belongings",
        headers=auth_headers(manager),
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1


def test_belongings_return_does_not_release_remains(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_ready_case(client, db, test_data, auth_headers)

    remains = (
        db.query(RemainsRecord)
        .filter(RemainsRecord.case_id == case.id)
        .one()
    )
    original_status = remains.status

    created = create_item(client, auth_headers, manager, case)
    assert created.status_code == 201, created.text

    returned = client.post(
        f"/cases/{case.id}/remains/belongings/"
        f"{created.json()['id']}/return",
        json={"returned_to_name": "Family representative"},
        headers=auth_headers(manager),
    )
    assert returned.status_code == 200, returned.text

    db.refresh(remains)
    assert remains.status == original_status
    assert remains.status != "released"
    assert remains.released_at is None
