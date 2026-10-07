from uuid import uuid4

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase


def create_case(
    client,
    *,
    manager,
    auth_headers,
    case_number,
    status="open",
):
    response = client.post(
        "/cases",
        json={
            "case_number": case_number,
            "deceased_full_name": f"Archival Test {case_number}",
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.text

    case_data = response.json()
    case_id = case_data["id"]

    lifecycle_paths = {
        "confirmed": ("confirmed",),
        "in_progress": ("confirmed", "in_progress"),
        "completed": ("confirmed", "in_progress", "completed"),
        "closed": ("confirmed", "in_progress", "completed", "closed"),
        "cancelled": ("cancelled",),
    }

    if status == "open":
        return case_data

    if status not in lifecycle_paths:
        raise ValueError(f"Unsupported test case status: {status}")

    for next_status in lifecycle_paths[status]:
        transition = client.post(
            f"/cases/{case_id}/lifecycle",
            json={"status": next_status},
            headers=auth_headers(manager),
        )
        assert transition.status_code == 200, transition.text

    refreshed = client.get(
        f"/cases/{case_id}",
        headers=auth_headers(manager),
    )
    assert refreshed.status_code == 200, refreshed.text

    return refreshed.json()

def test_manager_can_archive_closed_case(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-API-001",
        status="closed",
    )

    case_id = case_data["id"]

    response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["id"] == case_id
    assert body["status"] == "closed"
    assert body["is_archived"] is True
    assert body["archived_at"] is not None
    assert body["archived_by"] == str(manager.id)

    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()

    assert case is not None
    assert case.is_archived is True
    assert case.status == "closed"
    assert case.archived_by == manager.id


def test_manager_can_archive_cancelled_case(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-API-002",
        status="cancelled",
    )

    case_id = case_data["id"]

    response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_archived"] is True
    assert response.json()["status"] == "cancelled"


def test_staff_cannot_archive_case(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]
    staff = test_data["staff"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-PERM-001",
        status="closed",
    )

    response = client.post(
        f"/cases/{case_data['id']}/archive",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.archive"


def test_main_admin_can_archive_case_without_explicit_permission(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]
    admin = test_data["main_admin"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-ADMIN-001",
        status="closed",
    )

    response = client.post(
        f"/cases/{case_data['id']}/archive",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_archived"] is True
    assert response.json()["archived_by"] == str(admin.id)


def test_archive_rejects_non_terminal_case(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    for case_status in (
        "open",
        "confirmed",
        "in_progress",
        "completed",
    ):
        case_data = create_case(
            client,
            manager=manager,
            auth_headers=auth_headers,
            case_number=f"ARCHIVE-REJECT-{case_status.upper()}",
            status=case_status,
        )

        response = client.post(
            f"/cases/{case_data['id']}/archive",
            headers=auth_headers(manager),
        )

        assert response.status_code == 409
        assert "cannot be archived" in response.json()["detail"]


def test_already_archived_case_cannot_be_archived_again(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-DUP-001",
        status="closed",
    )

    case_id = case_data["id"]

    first_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Case is already archived"


def test_manager_can_restore_archived_closed_case(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="RESTORE-API-001",
        status="closed",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    restore_response = client.post(
        f"/cases/{case_id}/restore",
        headers=auth_headers(manager),
    )

    assert restore_response.status_code == 200, restore_response.text

    body = restore_response.json()

    assert body["id"] == case_id
    assert body["status"] == "closed"
    assert body["is_archived"] is False
    assert body["archived_at"] is None
    assert body["archived_by"] is None

    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()

    assert case is not None
    assert case.status == "closed"
    assert case.is_archived is False


def test_restore_preserves_cancelled_status(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="RESTORE-API-002",
        status="cancelled",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    restore_response = client.post(
        f"/cases/{case_id}/restore",
        headers=auth_headers(manager),
    )

    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == "cancelled"
    assert restore_response.json()["is_archived"] is False


def test_staff_cannot_restore_case(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]
    staff = test_data["staff"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="RESTORE-PERM-001",
        status="closed",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    response = client.post(
        f"/cases/{case_id}/restore",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.restore"


def test_main_admin_can_restore_case_without_explicit_permission(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]
    admin = test_data["main_admin"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="RESTORE-ADMIN-001",
        status="closed",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    restore_response = client.post(
        f"/cases/{case_id}/restore",
        headers=auth_headers(admin),
    )

    assert restore_response.status_code == 200
    assert restore_response.json()["is_archived"] is False
    assert restore_response.json()["status"] == "closed"


def test_non_archived_case_cannot_be_restored(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="RESTORE-REJECT-001",
        status="closed",
    )

    response = client.post(
        f"/cases/{case_data['id']}/restore",
        headers=auth_headers(manager),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Case is not archived"


def test_archived_case_is_excluded_from_active_case_list(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-LIST-001",
        status="closed",
    )

    case_id = case_data["id"]

    before_response = client.get(
        "/cases",
        headers=auth_headers(manager),
    )

    assert before_response.status_code == 200
    assert any(case["id"] == case_id for case in before_response.json())

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    after_response = client.get(
        "/cases",
        headers=auth_headers(manager),
    )

    assert after_response.status_code == 200
    assert not any(case["id"] == case_id for case in after_response.json())


def test_archived_case_can_still_be_retrieved_directly(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-GET-001",
        status="closed",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    response = client.get(
        f"/cases/{case_id}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    assert response.json()["id"] == case_id
    assert response.json()["status"] == "closed"
    assert response.json()["is_archived"] is True


def test_archive_is_tenant_scoped(
    client,
    test_data,
    auth_headers,
):
    manager_a = test_data["manager"]
    manager_b = test_data["other_business_manager"]

    case_data = create_case(
        client,
        manager=manager_a,
        auth_headers=auth_headers,
        case_number="ARCHIVE-TENANT-001",
        status="closed",
    )

    response = client.post(
        f"/cases/{case_data['id']}/archive",
        headers=auth_headers(manager_b),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_restore_is_tenant_scoped(
    client,
    test_data,
    auth_headers,
):
    manager_a = test_data["manager"]
    manager_b = test_data["other_business_manager"]

    case_data = create_case(
        client,
        manager=manager_a,
        auth_headers=auth_headers,
        case_number="RESTORE-TENANT-001",
        status="closed",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager_a),
    )

    assert archive_response.status_code == 200

    response = client.post(
        f"/cases/{case_id}/restore",
        headers=auth_headers(manager_b),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_archive_creates_audit_event(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="ARCHIVE-AUDIT-001",
        status="closed",
    )

    case_id = case_data["id"]

    response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == manager.business_id,
            AuditLog.user_id == manager.id,
            AuditLog.action == "case.archived",
            AuditLog.entity_type == "case",
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )

    assert audit is not None
    assert str(audit.entity_id) == case_id
    assert audit.details == {
        "status": "closed",
        "archived": True,
    }


def test_restore_creates_audit_event(
    client,
    db,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="RESTORE-AUDIT-001",
        status="closed",
    )

    case_id = case_data["id"]

    archive_response = client.post(
        f"/cases/{case_id}/archive",
        headers=auth_headers(manager),
    )

    assert archive_response.status_code == 200

    restore_response = client.post(
        f"/cases/{case_id}/restore",
        headers=auth_headers(manager),
    )

    assert restore_response.status_code == 200

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == manager.business_id,
            AuditLog.user_id == manager.id,
            AuditLog.action == "case.restored",
            AuditLog.entity_type == "case",
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )

    assert audit is not None
    assert str(audit.entity_id) == case_id
    assert audit.details == {
        "status": "closed",
        "archived": False,
    }


def test_permanent_delete_is_not_available(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    case_data = create_case(
        client,
        manager=manager,
        auth_headers=auth_headers,
        case_number="DELETE-BLOCKED-001",
        status="closed",
    )

    case_id = case_data["id"]

    response = client.delete(
        f"/cases/{case_id}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 405

    get_response = client.get(
        f"/cases/{case_id}",
        headers=auth_headers(manager),
    )

    assert get_response.status_code == 200
