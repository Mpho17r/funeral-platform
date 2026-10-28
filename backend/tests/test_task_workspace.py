"""Shared tasks, assignee updates, reports, files and the three views."""

from datetime import datetime, timedelta, timezone

from app.models.notification import Notification
from app.models.permission import Permission
from app.models.user_permission import UserPermission
from tests.test_branches import make_case
from tests.test_workspace_groups import make_staff


def deny(db, user, key):
    perm = db.query(Permission).filter(Permission.key == key).one()
    db.add(UserPermission(user_id=user.id, permission_id=perm.id, effect="deny"))
    db.commit()


def give(client, auth_headers, admin, case, people, **extra):
    body = {"title": "Collect the death certificate",
            "assignee_ids": [str(p.id) for p in people], **extra}
    r = client.post(f"/cases/{case.id}/tasks", json=body, headers=auth_headers(admin))
    assert r.status_code == 201, r.text
    return r.json()


def test_a_task_can_be_shared_and_both_people_are_told(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    b = make_staff(db, test_data["staff"], biz, name="Ben")
    c = make_staff(db, test_data["staff"], biz, name="Cee")
    due = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    task = give(client, auth_headers, test_data["main_admin"], case, [a, b], due_at=due.isoformat())
    assert set(task["assignee_ids"]) == {str(a.id), str(b.id)}
    assert task["due_at"]

    for who in (a, b):
        mine = client.get("/tasks/board?scope=mine", headers=auth_headers(who)).json()["tasks"]
        assert [t["id"] for t in mine] == [task["id"]]
        assert mine[0]["shared"] is True
        assert db.query(Notification).filter(Notification.user_id == who.id, Notification.kind == "task_assigned").count() == 1
    assert client.get("/tasks/board?scope=mine", headers=auth_headers(c)).json()["tasks"] == []


def test_assignee_updates_status_without_manage_permission(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    b = make_staff(db, test_data["staff"], biz, name="Ben")
    outsider = make_staff(db, test_data["staff"], biz, name="Out")
    task = give(client, auth_headers, test_data["main_admin"], case, [a, b])
    for who in (a, outsider):
        deny(db, who, "tasks.manage")

    r = client.post(f"/tasks/{task['id']}/status", json={"status": "in_progress"}, headers=auth_headers(a))
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    # The other assignee is told.
    assert db.query(Notification).filter(Notification.user_id == b.id, Notification.kind == "task_update").count() == 1
    # Someone it was not given to cannot change it.
    r = client.post(f"/tasks/{task['id']}/status", json={"status": "completed"}, headers=auth_headers(outsider))
    assert r.status_code == 403
    r = client.post(f"/tasks/{task['id']}/status", json={"status": "completed"}, headers=auth_headers(b))
    assert r.json()["completed_at"]
    r = client.post(f"/tasks/{task['id']}/status", json={"status": "nonsense"}, headers=auth_headers(b))
    assert r.status_code == 422


def test_report_and_file_upload_and_download(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    b = make_staff(db, test_data["staff"], biz, name="Ben")
    task = give(client, auth_headers, test_data["main_admin"], case, [a, b])

    r = client.post(f"/tasks/{task['id']}/report", json={"text": "Collected from Home Affairs."}, headers=auth_headers(a))
    assert r.status_code == 201
    r = client.post(
        f"/tasks/{task['id']}/files",
        files={"file": ("receipt.pdf", b"%PDF-1.4 receipt", "application/pdf")},
        headers=auth_headers(b),
    )
    assert r.status_code == 201, r.text
    bad = client.post(
        f"/tasks/{task['id']}/files",
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        headers=auth_headers(b),
    )
    assert bad.status_code == 400

    detail = client.get(f"/tasks/{task['id']}", headers=auth_headers(a)).json()
    kinds = [e["kind"] for e in detail["entries"]]
    assert kinds == ["report", "file"]
    assert detail["entries"][0]["author"] == "Ann"
    file_id = detail["entries"][1]["id"]
    got = client.get(f"/tasks/{task['id']}/files/{file_id}", headers=auth_headers(a))
    assert got.status_code == 200 and got.content.startswith(b"%PDF")
    # Only the author (or a task manager) can remove it.
    assert client.delete(f"/tasks/{task['id']}/entries/{file_id}", headers=auth_headers(b)).status_code == 204


def test_views_mine_branch_organisation(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    give(client, auth_headers, test_data["main_admin"], case, [a])
    give(client, auth_headers, test_data["main_admin"], case, [])  # given to nobody

    assert len(client.get("/tasks/board?scope=mine", headers=auth_headers(a)).json()["tasks"]) == 1
    assert len(client.get("/tasks/board?scope=branch", headers=auth_headers(test_data["main_admin"])).json()["tasks"]) == 2
    org = client.get("/tasks/board?scope=organisation", headers=auth_headers(test_data["main_admin"]))
    assert org.status_code == 200 and len(org.json()["tasks"]) == 2
    # A person without all-branch access cannot ask for the organisation.
    assert client.get("/tasks/board?scope=organisation", headers=auth_headers(a)).status_code == 403
    deny(db, a, "tasks.manage")
    assert client.get("/tasks/board?scope=branch", headers=auth_headers(a)).status_code == 403
    assert client.get("/tasks/board?scope=mine", headers=auth_headers(a)).json()["scopes"] == ["mine"]


def test_summary_counts_overdue_and_due_today(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    give(client, auth_headers, test_data["main_admin"], case, [a], due_at=past)
    give(client, auth_headers, test_data["main_admin"], case, [a])
    s = client.get("/tasks/summary", headers=auth_headers(a)).json()
    assert s["open"] == 2 and s["overdue"] == 1 and s["not_started"] == 2
    assert len(s["items"]) == 2


def test_changing_assignees_on_update(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    b = make_staff(db, test_data["staff"], biz, name="Ben")
    task = give(client, auth_headers, test_data["main_admin"], case, [a])
    r = client.patch(f"/cases/tasks/{task['id']}", json={"assignee_ids": [str(b.id)]}, headers=auth_headers(test_data["main_admin"]))
    assert r.status_code == 200, r.text
    assert r.json()["assignee_ids"] == [str(b.id)] and r.json()["assigned_to"] == str(b.id)
    assert client.get("/tasks/board?scope=mine", headers=auth_headers(a)).json()["tasks"] == []
