from app.models.audit_log import AuditLog


def get_case_audits(db, case_id):
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "case",
            AuditLog.entity_id == case_id,
        )
        .order_by(AuditLog.created_at.asc())
        .all()
    )


def test_case_creation_creates_audit_event(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    response = client.post(
        "/cases",
        json={
            "case_number": "AUDIT-CREATE-001",
            "deceased_full_name": "Audit Creation Test",
            "date_of_death": "2026-10-01",
            "funeral_date": "2026-10-05",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    case_id = response.json()["id"]

    audits = get_case_audits(db, case_id)

    assert len(audits) == 1

    audit = audits[0]

    assert audit.business_id == business.id
    assert audit.user_id == manager.id
    assert audit.action == "case.created"
    assert audit.entity_type == "case"
    assert str(audit.entity_id) == case_id
    assert audit.details == {
        "case_number": "AUDIT-CREATE-001",
    }


def test_case_update_creates_audit_with_exact_changed_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    create_response = client.post(
        "/cases",
        json={
            "case_number": "AUDIT-UPDATE-001",
            "deceased_full_name": "Audit Update Test",
            "funeral_date": "2026-10-10",
            "funeral_venue": "Old Chapel",
        },
        headers=auth_headers(manager),
    )

    assert create_response.status_code == 201

    case_id = create_response.json()["id"]

    update_response = client.patch(
        f"/cases/{case_id}",
        json={
            "funeral_date": "2026-10-14",
            "funeral_venue": "New Chapel",
        },
        headers=auth_headers(manager),
    )

    assert update_response.status_code == 200, update_response.text

    audits = get_case_audits(db, case_id)

    assert len(audits) == 2

    update_audit = audits[1]

    assert update_audit.business_id == business.id
    assert update_audit.user_id == manager.id
    assert update_audit.action == "case.updated"
    assert update_audit.entity_type == "case"

    assert update_audit.details == {
        "changes": {
            "funeral_date": {
                "old": "2026-10-10",
                "new": "2026-10-14",
            },
            "funeral_venue": {
                "old": "Old Chapel",
                "new": "New Chapel",
            },
        }
    }


def test_case_update_redacts_sensitive_values(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    create_response = client.post(
        "/cases",
        json={
            "case_number": "AUDIT-REDACT-001",
            "deceased_full_name": "Original Name",
        },
        headers=auth_headers(manager),
    )

    assert create_response.status_code == 201

    case_id = create_response.json()["id"]

    update_response = client.patch(
        f"/cases/{case_id}",
        json={
            "deceased_full_name": "New Name",
        },
        headers=auth_headers(manager),
    )

    assert update_response.status_code == 200

    audits = get_case_audits(db, case_id)

    update_audit = audits[-1]

    change = update_audit.details["changes"]["deceased_full_name"]

    assert change == {
        "changed": True,
        "old": "[redacted]",
        "new": "[redacted]",
    }

    assert "Original Name" not in str(update_audit.details)
    assert "New Name" not in str(update_audit.details)


def test_failed_case_update_creates_no_audit_event(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    first = client.post(
        "/cases",
        json={
            "case_number": "AUDIT-DUP-001",
            "deceased_full_name": "First Case",
        },
        headers=auth_headers(manager),
    )

    assert first.status_code == 201

    second = client.post(
        "/cases",
        json={
            "case_number": "AUDIT-DUP-002",
            "deceased_full_name": "Second Case",
        },
        headers=auth_headers(manager),
    )

    assert second.status_code == 201

    second_id = second.json()["id"]

    failed_update = client.patch(
        f"/cases/{second_id}",
        json={
            "case_number": "AUDIT-DUP-001",
        },
        headers=auth_headers(manager),
    )

    assert failed_update.status_code == 409

    audits = get_case_audits(db, second_id)

    assert len(audits) == 1
    assert audits[0].action == "case.created"


def test_case_lifecycle_audit_is_preserved(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    create_response = client.post(
        "/cases",
        json={
            "case_number": "AUDIT-LIFECYCLE-001",
            "deceased_full_name": "Lifecycle Audit Test",
        },
        headers=auth_headers(manager),
    )

    assert create_response.status_code == 201

    case_id = create_response.json()["id"]

    lifecycle_response = client.post(
        f"/cases/{case_id}/lifecycle",
        json={
            "status": "confirmed",
        },
        headers=auth_headers(manager),
    )

    assert lifecycle_response.status_code == 200

    audits = get_case_audits(db, case_id)

    assert len(audits) == 2

    assert audits[0].action == "case.created"
    assert audits[1].action == "case.status_changed"

    assert audits[1].details == {
        "old_status": "open",
        "new_status": "confirmed",
    }

    assert audits[1].user_id == manager.id
    assert audits[1].business_id == test_data["business_a"].id


def test_audit_transaction_rolls_back(
    db,
    test_data,
):
    from app.services.audit_service import create_audit_log

    business = test_data["business_a"]
    manager = test_data["manager"]

    create_audit_log(
        db,
        business_id=business.id,
        user_id=manager.id,
        action="case.test_rollback",
        entity_type="case",
        details={"test": True},
    )

    db.rollback()

    audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == business.id,
            AuditLog.action == "case.test_rollback",
        )
        .all()
    )

    assert audits == []
