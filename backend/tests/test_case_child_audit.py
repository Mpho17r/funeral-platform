import uuid

from datetime import date
from decimal import Decimal
from io import BytesIO

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase


# ============================================================
# HELPERS
# ============================================================

def make_case(db, business):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"AUD-CASE-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Audit Test",
        date_of_death=date(2026, 10, 1),
        status="open",
    )
    db.add(case)
    db.commit()

    return case


def audits(db, action, entity_id=None):
    query = db.query(AuditLog).filter(AuditLog.action == action)

    if entity_id is not None:
        query = query.filter(
            AuditLog.entity_id == uuid.UUID(str(entity_id))
        )

    return query.all()


def one_audit(db, action, entity_id):
    found = audits(db, action, entity_id)
    assert len(found) == 1, f"{action}: expected 1, got {len(found)}"
    return found[0]


def audit_count(db):
    return db.query(AuditLog).count()


def create_service(client, headers, case, **overrides):
    body = {
        "service_type": "catering",
        "service_name": "Funeral Catering",
        "description": "Family catering for Mr Mokoena",
        "quantity": 3,
        "unit_price": "750.00",
        "notes": "Private note",
    }
    body.update(overrides)

    response = client.post(
        f"/cases/{case.id}/services", json=body, headers=headers
    )
    assert response.status_code == 201, response.text

    return response.json()


def create_task(client, headers, case, **overrides):
    body = {
        "title": "Collect Mrs Dlamini from hospital",
        "description": "Bring ID",
    }
    body.update(overrides)

    response = client.post(
        f"/cases/{case.id}/tasks", json=body, headers=headers
    )
    assert response.status_code == 201, response.text

    return response.json()


def create_financial(client, headers, case, subtotal=1000):
    response = client.post(
        f"/cases/{case.id}/financial",
        json={"subtotal": subtotal, "discount": 0, "tax": 0},
        headers=headers,
    )
    assert response.status_code == 201, response.text

    return response.json()


def create_payment(client, headers, case, amount="250.00", **overrides):
    body = {
        "amount": amount,
        "payment_method": "cash",
        "reference": f"AUD-{uuid.uuid4().hex[:8].upper()}",
        "notes": "Handed over at the office",
    }
    body.update(overrides)

    response = client.post(
        f"/cases/{case.id}/payments", json=body, headers=headers
    )
    assert response.status_code == 201, response.text

    return response.json()


def upload_document(client, headers, case, description="Scan of ID"):
    response = client.post(
        f"/cases/{case.id}/documents",
        headers=headers,
        data={
            "document_type": "id_document",
            "description": description,
        },
        files={
            "file": (
                "mokoena-id.pdf",
                BytesIO(b"test document"),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201, response.text

    return response.json()


# ============================================================
# SERVICES
# ============================================================

def test_service_create_update_delete_are_audited(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, business)

    service = create_service(client, headers, case)

    created = one_audit(db, "case.service_created", service["id"])
    assert created.business_id == business.id
    assert created.user_id == manager.id
    assert created.entity_type == "case_service"
    assert created.details["case_id"] == str(case.id)
    assert created.details["service_type"] == "catering"
    assert created.details["quantity"] == 3
    assert Decimal(created.details["total_price"]) == Decimal("2250.00")

    response = client.patch(
        f"/cases/services/{service['id']}",
        json={"status": "confirmed", "quantity": 4},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    updated = one_audit(db, "case.service_updated", service["id"])
    changes = updated.details["changes"]

    assert set(changes) == {"status", "quantity", "total_price"}
    assert changes["status"] == {"old": "pending", "new": "confirmed"}
    assert changes["quantity"] == {"old": 3, "new": 4}
    assert Decimal(str(changes["total_price"]["new"])) == Decimal("3000.00")

    response = client.delete(
        f"/cases/services/{service['id']}", headers=headers
    )
    assert response.status_code == 204

    deleted = one_audit(db, "case.service_deleted", service["id"])
    assert deleted.details["case_id"] == str(case.id)
    assert deleted.details["service_type"] == "catering"


def test_service_audit_redacts_free_text(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    service = create_service(client, headers, case)

    client.patch(
        f"/cases/services/{service['id']}",
        json={
            "description": "Catering for the Nkosi family",
            "notes": "Allergic to peanuts",
        },
        headers=headers,
    )

    updated = one_audit(db, "case.service_updated", service["id"])

    assert set(updated.details["changes"]) == {"description", "notes"}

    for field in ("description", "notes"):
        assert updated.details["changes"][field]["old"] == "[redacted]"
        assert updated.details["changes"][field]["new"] == "[redacted]"

    everything = str(updated.details)
    assert "Nkosi" not in everything
    assert "peanuts" not in everything
    assert "Mokoena" not in everything


def test_unchanged_service_update_writes_no_audit(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    service = create_service(client, headers, case)

    response = client.patch(
        f"/cases/services/{service['id']}",
        json={"service_name": service["service_name"]},
        headers=headers,
    )

    assert response.status_code == 200
    assert audits(db, "case.service_updated") == []


# ============================================================
# TASKS
# ============================================================

def test_task_create_update_delete_are_audited(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    staff = test_data["staff"]
    headers = auth_headers(manager)
    case = make_case(db, business)

    task = create_task(client, headers, case)

    created = one_audit(db, "case.task_created", task["id"])
    assert created.business_id == business.id
    assert created.user_id == manager.id
    assert created.details["status"] == "pending"
    assert created.details["assigned_to"] is None
    assert "Dlamini" not in str(created.details)

    response = client.patch(
        f"/cases/tasks/{task['id']}",
        json={
            "status": "completed",
            "assigned_to": str(staff.id),
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    updated = one_audit(db, "case.task_updated", task["id"])
    changes = updated.details["changes"]

    assert set(changes) == {"status", "assigned_to", "completed_at"}
    assert changes["status"] == {"old": "pending", "new": "completed"}
    assert changes["assigned_to"] == {"old": None, "new": str(staff.id)}
    assert changes["completed_at"]["old"] is None
    assert changes["completed_at"]["new"] is not None

    response = client.delete(
        f"/cases/tasks/{task['id']}", headers=headers
    )
    assert response.status_code == 204

    deleted = one_audit(db, "case.task_deleted", task["id"])
    assert deleted.details["status"] == "completed"


def test_task_audit_redacts_title_and_description(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["manager"])
    case = make_case(db, test_data["business_a"])
    task = create_task(client, headers, case)

    client.patch(
        f"/cases/tasks/{task['id']}",
        json={
            "title": "Collect Mr Zulu from the mortuary",
            "description": "Family wants a private viewing",
        },
        headers=headers,
    )

    updated = one_audit(db, "case.task_updated", task["id"])

    assert set(updated.details["changes"]) == {"title", "description"}

    everything = str(updated.details)
    assert "Zulu" not in everything
    assert "Dlamini" not in everything
    assert "viewing" not in everything


# ============================================================
# DOCUMENTS
# ============================================================

def test_document_upload_update_delete_are_audited(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, business)

    document = upload_document(client, headers, case)

    uploaded = one_audit(db, "case.document_uploaded", document["id"])
    assert uploaded.business_id == business.id
    assert uploaded.user_id == manager.id
    assert uploaded.details["case_id"] == str(case.id)
    assert uploaded.details["document_type"] == "id_document"
    assert uploaded.details["mime_type"] == "application/pdf"

    # File names often contain the name of the deceased.
    assert "mokoena" not in str(uploaded.details).lower()

    response = client.patch(
        f"/cases/documents/{document['id']}",
        json={
            "document_type": "death_certificate",
            "description": "Replaced scan of Mr Mokoena's certificate",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text

    updated = one_audit(db, "case.document_updated", document["id"])
    changes = updated.details["changes"]

    assert set(changes) == {"document_type", "description"}
    assert changes["document_type"] == {
        "old": "id_document",
        "new": "death_certificate",
    }
    assert changes["description"]["new"] == "[redacted]"
    assert "Mokoena" not in str(updated.details)

    response = client.delete(
        f"/cases/documents/{document['id']}", headers=headers
    )
    assert response.status_code == 204

    deleted = one_audit(db, "case.document_deleted", document["id"])
    assert deleted.details["document_type"] == "death_certificate"
    assert "mokoena" not in str(deleted.details).lower()


# ============================================================
# FINANCIAL RECORDS
# ============================================================

def test_financial_create_update_recalculate_delete_are_audited(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, business)

    financial = create_financial(client, headers, case, subtotal=1000)

    created = one_audit(db, "case.financial_created", financial["id"])
    assert created.business_id == business.id
    assert created.user_id == manager.id
    assert Decimal(created.details["subtotal"]) == Decimal("1000.00")
    assert Decimal(created.details["total"]) == Decimal("1000.00")

    response = client.patch(
        f"/cases/financial/{financial['id']}",
        json={"discount": 100, "notes": "Family hardship"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    updated = one_audit(db, "case.financial_updated", financial["id"])
    changes = updated.details["changes"]

    # Calculated fields are included so the history shows how the
    # balance moved.
    assert {"discount", "total", "balance", "notes"} <= set(changes)
    assert Decimal(changes["total"]["old"]) == Decimal("1000.00")
    assert Decimal(changes["total"]["new"]) == Decimal("900.00")
    assert changes["notes"]["new"] == "[redacted]"
    assert "hardship" not in str(updated.details)

    # Recalculating with no services resets the subtotal to zero.
    response = client.post(
        f"/cases/{case.id}/financial/recalculate", headers=headers
    )
    assert response.status_code == 200, response.text

    recalculated = one_audit(
        db, "case.financial_recalculated", financial["id"]
    )
    assert "subtotal" in recalculated.details["changes"]

    response = client.delete(
        f"/cases/financial/{financial['id']}", headers=headers
    )
    assert response.status_code == 204

    deleted = one_audit(db, "case.financial_deleted", financial["id"])
    assert deleted.details["case_id"] == str(case.id)
    assert "balance" in deleted.details


# ============================================================
# PAYMENTS
# ============================================================

def test_payment_audit_records_effect_on_balance(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    headers = auth_headers(manager)
    case = make_case(db, business)
    create_financial(client, headers, case, subtotal=1000)

    payment = create_payment(client, headers, case, "250.00")

    created = one_audit(db, "case.payment_created", payment["id"])
    assert created.business_id == business.id
    assert created.user_id == manager.id
    assert Decimal(created.details["amount"]) == Decimal("250.00")
    after = created.details["financial_after"]
    assert Decimal(after["amount_paid"]) == Decimal("250.00")
    assert Decimal(after["balance"]) == Decimal("750.00")

    response = client.patch(
        f"/cases/payments/{payment['id']}",
        json={"amount": "400.00", "notes": "Corrected amount"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    updated = one_audit(db, "case.payment_updated", payment["id"])
    changes = updated.details["changes"]

    assert set(changes) == {"amount", "notes"}
    assert Decimal(changes["amount"]["old"]) == Decimal("250.00")
    assert Decimal(changes["amount"]["new"]) == Decimal("400.00")
    assert changes["notes"]["new"] == "[redacted]"
    assert Decimal(
        updated.details["financial_after"]["balance"]
    ) == Decimal("600.00")

    response = client.delete(
        f"/cases/payments/{payment['id']}", headers=headers
    )
    assert response.status_code == 204

    deleted = one_audit(db, "case.payment_deleted", payment["id"])
    assert Decimal(deleted.details["amount"]) == Decimal("400.00")
    assert Decimal(
        deleted.details["financial_after"]["balance"]
    ) == Decimal("1000.00")


# ============================================================
# AUDIT IS ALL-OR-NOTHING AND TENANT SAFE
# ============================================================

def test_denied_and_cross_tenant_requests_write_no_audit(
    client, db, test_data, auth_headers,
):
    headers_a = auth_headers(test_data["manager"])
    staff_headers = auth_headers(test_data["staff"])
    headers_b = auth_headers(test_data["other_business_manager"])
    case = make_case(db, test_data["business_a"])

    service = create_service(client, headers_a, case)
    task = create_task(client, headers_a, case)
    create_financial(client, headers_a, case)
    payment = create_payment(client, headers_a, case)

    before = audit_count(db)

    attempts = [
        # Staff lack these permissions.
        client.delete(
            f"/cases/payments/{payment['id']}", headers=staff_headers
        ),
        # Another business cannot reach them at all.
        client.patch(
            f"/cases/services/{service['id']}",
            json={"status": "confirmed"},
            headers=headers_b,
        ),
        client.delete(
            f"/cases/tasks/{task['id']}", headers=headers_b
        ),
        client.patch(
            f"/cases/payments/{payment['id']}",
            json={"amount": "1.00"},
            headers=headers_b,
        ),
        client.post(
            f"/cases/{case.id}/services",
            json={
                "service_type": "x",
                "service_name": "y",
                "quantity": 1,
                "unit_price": "1.00",
            },
            headers=headers_b,
        ),
    ]

    for response in attempts:
        assert response.status_code in {403, 404}, response.text

    assert audit_count(db) == before


def test_audit_entries_belong_to_the_acting_business(
    client, db, test_data, auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]

    case_a = make_case(db, business_a)
    case_b = make_case(db, business_b)

    task_a = create_task(
        client, auth_headers(test_data["manager"]), case_a
    )
    task_b = create_task(
        client, auth_headers(test_data["other_business_manager"]), case_b
    )

    assert one_audit(
        db, "case.task_created", task_a["id"]
    ).business_id == business_a.id
    assert one_audit(
        db, "case.task_created", task_b["id"]
    ).business_id == business_b.id
