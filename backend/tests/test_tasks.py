from datetime import date

from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase


def create_case(
    db,
    business_id,
    case_number="TASK-BEHAVIOR-2026-0001",
):
    case = FuneralCase(
        business_id=business_id,
        case_number=case_number,
        deceased_full_name="Task Behavior Deceased",
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
    title="Prepare funeral documents",
    status="pending",
    assigned_to=None,
):
    task = CaseTask(
        business_id=business_id,
        case_id=case_id,
        title=title,
        description="Behavioral task test",
        status=status,
        due_date=date(2026, 10, 1),
        assigned_to=assigned_to,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_create_task_trims_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "  Prepare funeral documents  ",
            "description": "  Confirm all documents  ",
            "status": "  PENDING  ",
            "due_date": "2026-10-05",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Prepare funeral documents"
    assert data["description"] == "  Confirm all documents  "
    assert data["status"] == "pending"
    assert data["due_date"] == "2026-10-05"
    assert data["assigned_to"] is None
    assert data["completed_at"] is None


def test_create_task_without_assignee(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Unassigned task",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Unassigned task"
    assert data["status"] == "pending"
    assert data["assigned_to"] is None
    assert data["completed_at"] is None


def test_create_completed_task_sets_completed_at(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Completed task",
            "status": "completed",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "completed"
    assert data["completed_at"] is not None


def test_create_pending_task_does_not_set_completed_at(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Pending task",
            "status": "pending",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["status"] == "pending"
    assert data["completed_at"] is None


def test_list_tasks_returns_newest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    first = create_task(
        db,
        test_data["business_a"].id,
        case.id,
        title="First task",
    )

    second = create_task(
        db,
        test_data["business_a"].id,
        case.id,
        title="Second task",
    )

    headers = auth_headers(test_data["manager"])

    response = client.get(
        f"/cases/{case.id}/tasks",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == str(second.id)
    assert data[1]["id"] == str(first.id)


def test_get_missing_task_returns_404(
    client,
    test_data,
    auth_headers,
):
    missing_task_id = "00000000-0000-0000-0000-000000000000"

    headers = auth_headers(test_data["manager"])

    response = client.get(
        f"/cases/tasks/{missing_task_id}",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_delete_task_removes_task(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["manager"])

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


def test_delete_missing_task_returns_404(
    client,
    test_data,
    auth_headers,
):
    missing_task_id = "00000000-0000-0000-0000-000000000000"

    headers = auth_headers(test_data["manager"])

    response = client.delete(
        f"/cases/tasks/{missing_task_id}",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_update_task_changes_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "title": "Updated funeral documents",
            "description": "Updated description",
            "due_date": "2026-11-15",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["title"] == "Updated funeral documents"
    assert data["description"] == "Updated description"
    assert data["due_date"] == "2026-11-15"
    assert data["status"] == "pending"


def test_update_pending_task_to_completed_sets_completed_at(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
        status="pending",
    )

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "status": "completed",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed"
    assert data["completed_at"] is not None


def test_update_completed_task_to_pending_clears_completed_at(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
        status="completed",
    )

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "status": "pending",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "pending"
    assert data["completed_at"] is None


def test_update_task_can_assign_user(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "assigned_to": str(test_data["staff"].id),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["assigned_to"] == str(
        test_data["staff"].id
    )


def test_update_missing_task_returns_404(
    client,
    test_data,
    auth_headers,
):
    missing_task_id = "00000000-0000-0000-0000-000000000000"

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/tasks/{missing_task_id}",
        headers=headers,
        json={
            "title": "Does not exist",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_create_task_with_invalid_status_returns_422(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Invalid status task",
            "status": "cancelled",
        },
    )

    assert response.status_code == 422


def test_create_task_with_blank_title_returns_422(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "   ",
        },
    )

    assert response.status_code == 422


def test_create_task_with_title_over_200_characters_returns_422(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "A" * 201,
        },
    )

    assert response.status_code == 422


def test_create_task_with_invalid_assigned_user_uuid_returns_422(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Invalid assignee task",
            "assigned_to": "not-a-uuid",
        },
    )

    assert response.status_code == 422


def test_create_task_with_invalid_due_date_returns_422(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/tasks",
        headers=headers,
        json={
            "title": "Invalid date task",
            "due_date": "not-a-date",
        },
    )

    assert response.status_code == 422


def test_update_task_with_invalid_status_returns_422(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
    )

    task = create_task(
        db,
        test_data["business_a"].id,
        case.id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/tasks/{task.id}",
        headers=headers,
        json={
            "status": "cancelled",
        },
    )

    assert response.status_code == 422
