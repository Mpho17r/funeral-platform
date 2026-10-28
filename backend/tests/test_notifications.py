"""In-app notifications."""

from datetime import datetime, timedelta, timezone

from tests.test_reports import make_case


def inbox(client, auth_headers, user, **params):
    response = client.get(
        "/notifications", params=params, headers=auth_headers(user)
    )
    assert response.status_code == 200
    return response.json()


def test_task_assignment_notifies_the_assignee_only(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    manager, staff = test_data["manager"], test_data["staff"]

    response = client.post(
        f"/cases/{case.id}/tasks",
        json={"title": "Call the family", "assigned_to": str(staff.id)},
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.text

    mine = inbox(client, auth_headers, staff)
    assert mine["unread"] == 1
    note = mine["items"][0]
    assert note["kind"] == "task_assigned"
    assert note["body"] == "Call the family"
    assert note["link"] == "/tasks"  # opens the task list

    # The person who assigned it is not told about their own action.
    assert inbox(client, auth_headers, manager)["unread"] == 0


def test_assigning_to_yourself_is_silent(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    client.post(
        f"/cases/{case.id}/tasks",
        json={"title": "Mine", "assigned_to": str(manager.id)},
        headers=auth_headers(manager),
    )
    assert inbox(client, auth_headers, manager)["unread"] == 0


def test_reassigning_a_task_notifies_the_new_person(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager, staff = test_data["manager"], test_data["staff"]
    task = client.post(
        f"/cases/{case.id}/tasks",
        json={"title": "Order flowers"},
        headers=auth_headers(manager),
    ).json()
    assert inbox(client, auth_headers, staff)["unread"] == 0

    r = client.patch(
        f"/cases/tasks/{task['id']}",
        json={"assigned_to": str(staff.id)},
        headers=auth_headers(manager),
    )
    assert r.status_code == 200, r.text
    assert inbox(client, auth_headers, staff)["unread"] == 1


def test_meeting_invite_and_mention(client, db, test_data, auth_headers):
    manager, staff = test_data["manager"], test_data["staff"]
    start = datetime.now(timezone.utc) + timedelta(days=1)

    r = client.post(
        "/meetings",
        json={
            "title": "Friday planning",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
            "user_ids": [str(staff.id)],
        },
        headers=auth_headers(manager),
    )
    assert r.status_code in (200, 201), r.text

    items = inbox(client, auth_headers, staff)["items"]
    assert any(
        n["kind"] == "meeting_invite" and "Friday planning" in n["title"]
        for n in items
    )


def test_read_one_read_all_and_privacy(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager, staff = test_data["manager"], test_data["staff"]
    for title in ("One", "Two"):
        client.post(
            f"/cases/{case.id}/tasks",
            json={"title": title, "assigned_to": str(staff.id)},
            headers=auth_headers(manager),
        )

    mine = inbox(client, auth_headers, staff)
    assert mine["unread"] == 2
    first = mine["items"][0]["id"]

    # Someone else cannot touch it.
    assert client.post(
        f"/notifications/{first}/read", headers=auth_headers(manager)
    ).status_code == 404

    r = client.post(
        f"/notifications/{first}/read", headers=auth_headers(staff)
    )
    assert r.status_code == 200 and r.json()["read"] is True
    assert inbox(client, auth_headers, staff)["unread"] == 1
    assert len(inbox(client, auth_headers, staff, unread_only=True)["items"]) == 1

    assert client.post(
        "/notifications/read-all", headers=auth_headers(staff)
    ).json() == {"unread": 0}
    assert inbox(client, auth_headers, staff)["unread"] == 0
    assert len(inbox(client, auth_headers, staff)["items"]) == 2


def test_reconciliation_difference_alerts_other_managers(
    client, db, test_data, auth_headers
):
    admin, manager = test_data["main_admin"], test_data["manager"]
    from datetime import date

    from tests.test_expenses_reconciliation import add_expense

    add_expense(client, auth_headers, manager, amount="100.00")
    r = client.post(
        "/reconciliation",
        json={
            "recon_date": date.today().isoformat(),
            "payment_method": "cash",
            "counted_amount": "0.00",
            "notes": "Cash went to the hearse driver",
        },
        headers=auth_headers(manager),
    )
    assert r.status_code == 200, r.text

    kinds = [n["kind"] for n in inbox(client, auth_headers, admin)["items"]]
    assert "reconciliation_difference" in kinds
    assert inbox(client, auth_headers, manager)["unread"] == 0


def test_requires_login(client):
    assert client.get("/notifications").status_code in (401, 403)
