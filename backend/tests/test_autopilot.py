"""KAI Autopilot: KAI as the platform manager, only when allowed."""

from datetime import datetime, timedelta, timezone

from app.models.business import Business
from app.models.case_task import CaseTask, CaseTaskAssignee
from app.models.kai import KaiAutopilotItem
from app.models.notification import Notification
from app.services import autopilot
from tests.test_branches import make_case
from tests.test_financial_documents import make_service
from tests.test_task_workspace import deny
from tests.test_workspace_groups import make_staff


def aged_case(db, biz, **kw):
    case = make_case(db, biz, **kw)
    case.created_at = datetime.now(timezone.utc) - timedelta(days=3)
    db.commit()
    return case


def mode(db, test_data, value, **extra):
    biz = db.get(Business, test_data["business_a"].id)
    biz.autopilot_mode = value
    for k, v in extra.items():
        setattr(biz, k, v)
    db.commit()
    return biz


def titles(db, case):
    return sorted(t.title for t in db.query(CaseTask).filter(CaseTask.case_id == case.id))


def test_off_does_nothing(client, db, test_data):
    aged_case(db, test_data["business_a"])
    biz = mode(db, test_data, "off")
    assert autopilot.run(db, biz) == {"proposed": 0, "applied": 0, "escalated": 0}
    assert db.query(KaiAutopilotItem).count() == 0


def test_suggest_waits_for_approval_and_never_repeats(client, auth_headers, db, test_data):
    case = aged_case(db, test_data["business_a"])
    biz = mode(db, test_data, "suggest")
    result = autopilot.run(db, biz)
    assert result["proposed"] >= 2 and result["applied"] == 0
    assert titles(db, case) == []  # nothing happened yet

    assert autopilot.run(db, biz)["proposed"] == 0  # not proposed twice

    manager = test_data["manager"]
    pending = client.get("/autopilot/items?status=pending", headers=auth_headers(manager)).json()
    record = next(i for i in pending if "death record" in i["summary"])
    r = client.post(f"/autopilot/items/{record['id']}/approve", headers=auth_headers(manager))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert "Capture the death record" in titles(db, case)
    task = db.query(CaseTask).filter(CaseTask.title == "Capture the death record").one()
    assert task.by_kai is True and task.assignee_ids  # given to someone

    other = next(i for i in pending if i["id"] != record["id"])
    assert client.post(f"/autopilot/items/{other['id']}/dismiss", headers=auth_headers(manager)).status_code == 200
    autopilot.run(db, biz)
    assert db.query(KaiAutopilotItem).filter(KaiAutopilotItem.id == other["id"]).one().status == "dismissed"
    # Dismissed means dismissed: it does not come back.
    assert not any(i["summary"] == other["summary"] for i in
                   client.get("/autopilot/items?status=pending", headers=auth_headers(manager)).json())


def test_auto_creates_and_gives_out_work_by_workload(client, db, test_data):
    biz_row = test_data["business_a"]
    case = aged_case(db, biz_row)
    busy = make_staff(db, test_data["staff"], biz_row, name="Busy")
    free = make_staff(db, test_data["staff"], biz_row, name="Free")
    for n in range(3):
        t = CaseTask(business_id=biz_row.id, case_id=case.id, title=f"Existing {n}", status="pending")
        t.assignee_rows = [CaseTaskAssignee(user_id=busy.id)]
        db.add(t)
    db.commit()
    biz = mode(db, test_data, "auto")
    autopilot.run(db, biz)
    made = db.query(CaseTask).filter(CaseTask.by_kai.is_(True)).all()
    assert made
    for t in made:
        assert t.assignee_ids, t.title
    # The free person is given at least as much as the busy one.
    free_n = sum(1 for t in made if free.id in t.assignee_ids)
    busy_n = sum(1 for t in made if busy.id in t.assignee_ids)
    assert free_n >= busy_n
    # Everything is logged and can be undone.
    items = db.query(KaiAutopilotItem).filter(KaiAutopilotItem.status == "applied").all()
    assert items and all(i.result for i in items)


def test_it_respects_the_workload_limit_and_permissions(client, db, test_data):
    biz_row = test_data["business_a"]
    case = aged_case(db, biz_row)
    only = make_staff(db, test_data["staff"], biz_row, name="Only")
    for u in (test_data["manager"], test_data["staff"]):
        deny(db, u, "tasks.view")
    biz = mode(db, test_data, "auto", autopilot_max_open=1)
    autopilot.run(db, biz)
    given = [t for t in db.query(CaseTask).filter(CaseTask.by_kai.is_(True)) if only.id in t.assignee_ids]
    assert len(given) == 1  # the limit holds
    for t in db.query(CaseTask).filter(CaseTask.by_kai.is_(True)):
        assert test_data["manager"].id not in t.assignee_ids
        assert test_data["staff"].id not in t.assignee_ids


def test_unassigned_tasks_and_services_get_someone(client, db, test_data):
    biz_row = test_data["business_a"]
    case = make_case(db, biz_row)
    case.created_at = datetime.now(timezone.utc)  # too new for case rules
    person = make_staff(db, test_data["staff"], biz_row, name="Helper")
    task = CaseTask(business_id=biz_row.id, case_id=case.id, title="Order flowers", status="pending")
    service = make_service(db, biz_row, case, name="Hearse")
    db.add(task)
    db.commit()
    biz = mode(db, test_data, "auto", autopilot_create_tasks=False)
    result = autopilot.run(db, biz)
    assert result["applied"] == 2
    db.refresh(task); db.refresh(service)
    assert task.assignee_ids and service.assignee_ids


def test_undo_removes_what_kai_made_unless_work_started(client, db, test_data):
    case = aged_case(db, test_data["business_a"])
    biz = mode(db, test_data, "auto")
    autopilot.run(db, biz)
    items = db.query(KaiAutopilotItem).filter(KaiAutopilotItem.kind == "create_task",
                                              KaiAutopilotItem.status == "applied").all()
    first, second = items[0], items[1]
    task_id = first.result["task_id"]
    autopilot.undo(db, first)
    db.commit()
    assert db.get(CaseTask, task_id) is None and first.status == "undone"
    autopilot.run(db, biz)  # an undone item is not made again
    assert db.query(CaseTask).filter(CaseTask.id == task_id).count() == 0

    started = db.get(CaseTask, second.result["task_id"])
    started.status = "in_progress"
    db.commit()
    try:
        autopilot.undo(db, second)
        assert False, "should refuse"
    except autopilot.AutopilotError as error:
        assert error.status_code == 409


def test_only_main_admin_changes_settings_and_managers_see_them(client, auth_headers, test_data):
    body = {"mode": "auto", "create_tasks": True, "assign": True, "escalate": False, "max_open": 5}
    assert client.put("/autopilot/settings", json=body, headers=auth_headers(test_data["manager"])).status_code == 403
    r = client.put("/autopilot/settings", json=body, headers=auth_headers(test_data["main_admin"]))
    assert r.status_code == 200 and r.json()["mode"] == "auto"
    got = client.get("/autopilot/settings", headers=auth_headers(test_data["manager"])).json()
    assert got["mode"] == "auto" and got["escalate"] is False and got["can_change"] is False
    assert client.put("/autopilot/settings", json={**body, "mode": "wild"},
                      headers=auth_headers(test_data["main_admin"])).status_code == 422
    # Plain staff cannot see or use any of it.
    assert client.get("/autopilot/items", headers=auth_headers(test_data["staff"])).status_code == 403


def test_late_work_is_escalated_to_managers_once(client, db, test_data):
    biz_row = test_data["business_a"]
    case = make_case(db, biz_row)
    case.created_at = datetime.now(timezone.utc)
    late = CaseTask(business_id=biz_row.id, case_id=case.id, title="Very late", status="pending",
                    due_at=datetime.now(timezone.utc) - timedelta(hours=30))
    db.add(late)
    db.commit()
    biz = mode(db, test_data, "suggest", autopilot_create_tasks=False, autopilot_assign=False)
    assert autopilot.run(db, biz)["escalated"] >= 1
    assert autopilot.run(db, biz)["escalated"] == 0
    assert db.query(Notification).filter(Notification.kind == "kai_escalation").count() >= 1


def test_briefing_goes_to_managers_once_a_day(client, db, test_data):
    aged_case(db, test_data["business_a"])
    biz = mode(db, test_data, "suggest")
    autopilot.run(db, biz)
    assert autopilot.briefing(db, biz) >= 1
    assert autopilot.briefing(db, biz) == 0
