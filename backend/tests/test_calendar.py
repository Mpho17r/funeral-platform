from datetime import date
from uuid import uuid4

from app.models.case_service import CaseService
from app.models.case_task import CaseTask
from app.models.permission import Permission
from app.models.funeral_case import FuneralCase
from app.models.user_permission import UserPermission


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )
    else:
        existing.effect = "deny"

    db.commit()


def create_case(db, business, *, funeral_date=None):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"CAL-{uuid4().hex[:8].upper()}",
        deceased_full_name="Calendar Test Deceased",
        funeral_date=funeral_date,
        funeral_venue="Test Chapel",
        status="open",
    )
    db.add(case)
    db.flush()
    return case


def test_calendar_returns_funeral_service_and_task_events(
    db,
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(
        db,
        business,
        funeral_date=date(2026, 10, 10),
    )

    service = CaseService(
        business_id=business.id,
        case_id=case.id,
        service_type="transport",
        service_name="Hearse Transport",
        status="pending",
        quantity=1,
        unit_price=1000,
        total_price=1000,
        scheduled_date=date(2026, 10, 8),
    )

    task = CaseTask(
        business_id=business.id,
        case_id=case.id,
        title="Confirm Chapel",
        description="Confirm chapel booking",
        status="pending",
        due_date=date(2026, 10, 6),
        assigned_to=manager.id,
    )

    db.add_all([service, task])
    db.commit()

    response = client.get(
        "/calendar",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    events = response.json()

    # The day the task was given is shown too (today, so a different day).
    assert len(events) == 4

    event_types = {event["event_type"] for event in events}

    assert event_types == {
        "funeral",
        "service",
        "task",
        "task_given",
    }

    dates = {
        event["date"] for event in events if event["event_type"] != "task_given"
    }

    assert dates == {
        "2026-10-06",
        "2026-10-08",
        "2026-10-10",
    }


def test_calendar_excludes_undated_records(
    db,
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)

    service = CaseService(
        business_id=business.id,
        case_id=case.id,
        service_type="flowers",
        service_name="Flowers",
        status="pending",
        quantity=1,
        unit_price=500,
        total_price=500,
        scheduled_date=None,
    )

    task = CaseTask(
        business_id=business.id,
        case_id=case.id,
        title="Undated Task",
        status="pending",
        due_date=None,
    )

    db.add_all([service, task])
    db.commit()

    response = client.get(
        "/calendar",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text
    # No funeral, service or due-date events: only the day the task was given.
    assert {e["event_type"] for e in response.json()} == {"task_given"}


def test_task_with_due_time_shows_given_and_due(
    db,
    client,
    test_data,
    auth_headers,
):
    from datetime import datetime, timedelta, timezone

    business = test_data["business_a"]
    manager = test_data["manager"]
    case = create_case(db, business)

    due = datetime.now(timezone.utc) + timedelta(days=3)
    task = CaseTask(
        business_id=business.id,
        case_id=case.id,
        title="Collect flowers",
        status="pending",
        due_date=due.date(),
        due_at=due,
        assigned_to=manager.id,
    )
    db.add(task)
    db.commit()

    events = client.get("/calendar", headers=auth_headers(manager)).json()
    by_type = {e["event_type"]: e for e in events}
    assert by_type["task"]["due_at"] is not None
    assert by_type["task"]["date"] == due.date().isoformat()
    assert by_type["task_given"]["title"] == "Given: Collect flowers"


def test_archived_tasks_leave_the_calendar(db, client, test_data, auth_headers):
    from datetime import datetime, timezone

    business = test_data["business_a"]
    manager = test_data["manager"]
    case = create_case(db, business)
    db.add(
        CaseTask(
            business_id=business.id,
            case_id=case.id,
            title="Old job",
            status="completed",
            due_date=date.today(),
            archived_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    assert client.get("/calendar", headers=auth_headers(manager)).json() == []


def test_general_business_calendar_shows_tasks(
    db, client, test_data, auth_headers
):
    from tests.test_business_mode import go_general
    from app.services.business_type import workspace_case

    go_general(db, test_data)
    business = test_data["business_a"]
    admin = test_data["main_admin"]
    case = workspace_case(db, business.id)
    db.add(
        CaseTask(
            business_id=business.id,
            case_id=case.id,
            title="Send quote",
            status="pending",
            due_date=date.today(),
        )
    )
    db.commit()

    r = client.get("/calendar", headers=auth_headers(admin))
    assert r.status_code == 200, r.text
    types = {e["event_type"] for e in r.json()}
    assert "task" in types and "funeral" not in types


def test_calendar_is_tenant_isolated(
    db,
    client,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    case_a = create_case(
        db,
        business_a,
        funeral_date=date(2026, 10, 10),
    )

    case_b = create_case(
        db,
        business_b,
        funeral_date=date(2026, 10, 11),
    )

    db.commit()

    response = client.get(
        "/calendar",
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 200, response.text

    events = response.json()

    assert len(events) == 1
    assert events[0]["case_id"] == str(case_a.id)
    assert events[0]["date"] == "2026-10-10"

    assert str(case_b.id) not in {
        event["case_id"]
        for event in events
    }


def test_calendar_respects_service_permission(
    db,
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(
        db,
        business,
        funeral_date=date(2026, 10, 10),
    )

    service = CaseService(
        business_id=business.id,
        case_id=case.id,
        service_type="catering",
        service_name="Catering",
        status="pending",
        quantity=1,
        unit_price=800,
        total_price=800,
        scheduled_date=date(2026, 10, 8),
    )

    db.add(service)
    db.commit()

    response = client.get(
        "/calendar",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    event_types = {
        event["event_type"]
        for event in response.json()
    }

    assert "funeral" in event_types
    assert "service" in event_types

    deny_permission(
        db,
        manager.id,
        "services.view",
    )

    response = client.get(
        "/calendar",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    event_types = {
        event["event_type"]
        for event in response.json()
    }

    assert "funeral" in event_types
    assert "service" not in event_types


def test_calendar_respects_task_permission(
    db,
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(
        db,
        business,
        funeral_date=date(2026, 10, 10),
    )

    task = CaseTask(
        business_id=business.id,
        case_id=case.id,
        title="Prepare Documents",
        status="pending",
        due_date=date(2026, 10, 7),
        assigned_to=manager.id,
    )

    db.add(task)
    db.commit()

    response = client.get(
        "/calendar",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    event_types = {
        event["event_type"]
        for event in response.json()
    }

    assert "funeral" in event_types
    assert "task" in event_types

    deny_permission(
        db,
        manager.id,
        "tasks.view",
    )

    response = client.get(
        "/calendar",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    event_types = {
        event["event_type"]
        for event in response.json()
    }

    assert "funeral" in event_types
    assert "task" not in event_types
