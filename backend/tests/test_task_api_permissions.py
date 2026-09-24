from datetime import date
from uuid import uuid4

from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.user_permission import UserPermission


def create_case(db, business_id, case_number="TASK-2026-0001"):
    case = FuneralCase(
        business_id=business_id,
        case_number=case_number,
        deceased_full_name="Task Test Deceased",
        status="in_progress",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_task(
    db,
    business_id,
    case_id,
    assigned_to=None,
    title="Prepare funeral documents",
):
    task = CaseTask(
        business_id=business_id,
        case_id=case_id,
        title=title,
        description="Task permission test",
        status="pending",
        due_date=date(2026, 10, 1),
        assigned_to=assigned_to,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    override = UserPermission(
        user_id=user_id,
        permission_id=permission.id,
        effect="deny",
    )
    db.add(override)
    db.commit()


def test_staff_with_tasks_view_can_list_tasks(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    create_task(db, test_data["business_a"].id, case.id)

    headers = auth_headers(test_data["staff"])

    response = client.get(
        f"/cases/{case.id}/tasks",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_staff_denied_tasks_view_cannot_list_tasks(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    create_task(db, test_data["business_a"].id, case.id)

    deny_permission(
        db,
        test_data["staff"].id,
        "tasks.view",
    )

    headers = auth_headers(test_data["staff"])

    response = client.get(
        f"/cases/{case.id}/tasks",
        headers=headers,
    )

    assert response.status_code == 403


def test_staff_with_tasks_view_can_get_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["staff"])

    response = client.get(
        f"/cases/tasks/{task.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(task.id)


def test_staff_with_tasks_manage_can_create_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)

    headers = auth_headers(test_data["staff"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Arrange transport",
            "description": "Confirm hearse availability",
            "status": "pending",
            "due_date": "2026-10-05",
            "assigned_to": str(test_data["staff"].id),
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["title"] == "Arrange transport"
    assert data["business_id"] == str(
        test_data["business_a"].id
    )
    assert data["case_id"] == str(case.id)
    assert data["assigned_to"] == str(
        test_data["staff"].id
    )


def test_staff_denied_tasks_manage_cannot_create_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)

    deny_permission(
        db,
        test_data["staff"].id,
        "tasks.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Restricted task",
            "status": "pending",
        },
    )

    assert response.status_code == 403


def test_staff_with_tasks_manage_can_update_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["staff"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "title": "Updated funeral documents",
            "status": "completed",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "Updated funeral documents"
    assert data["status"] == "completed"
    assert data["completed_at"] is not None


def test_staff_denied_tasks_manage_cannot_update_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "tasks.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "title": "Should not update",
        },
    )

    assert response.status_code == 403


def test_staff_with_tasks_manage_can_delete_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["staff"])

    response = client.delete(
        f"/cases/tasks/{task.id}",
        headers=headers,
    )

    assert response.status_code == 204

    deleted = (
        db.query(CaseTask)
        .filter(CaseTask.id == task.id)
        .first()
    )
    assert deleted is None


def test_staff_denied_tasks_manage_cannot_delete_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "tasks.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.delete(
        f"/cases/tasks/{task.id}",
        headers=headers,
    )

    assert response.status_code == 403

    existing = (
        db.query(CaseTask)
        .filter(CaseTask.id == task.id)
        .first()
    )
    assert existing is not None


def test_other_business_manager_cannot_access_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)
    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(
        test_data["other_business_manager"]
    )

    response = client.get(
        f"/cases/tasks/{task.id}",
        headers=headers,
    )

    assert response.status_code == 404


def test_cannot_assign_task_to_user_from_other_business(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"].id)

    headers = auth_headers(test_data["staff"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Cross-business assignment",
            "status": "pending",
            "assigned_to": str(
                test_data["other_business_manager"].id
            ),
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Assigned user does not belong to this business"
    )
