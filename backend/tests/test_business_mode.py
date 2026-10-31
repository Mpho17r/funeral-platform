"""A general business: its own screens, money, tasks and KAI's role matching."""

from datetime import date, datetime, timedelta, timezone

from app.models.business import Business
from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase
from app.services import autopilot, staff_roles
from tests.test_branches import make_case
from tests.test_workspace_groups import make_staff


def go_general(db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    biz.business_type = "general"
    db.commit()
    return biz


def test_role_detection_reads_job_titles_and_wording():
    assert staff_roles.category_for_text("Reconcile the bank statement and chase invoices") == "finance"
    assert staff_roles.category_for_text("Order more stock from the supplier") == "operations"
    assert staff_roles.category_for_text("Say hello") == "general"
    assert staff_roles.profile("Senior Accountant", "staff")[0] == "finance"
    assert staff_roles.profile(None, "manager") == ["management"]
    assert staff_roles.suitability("Bookkeeper", "staff", "finance") == 2
    assert staff_roles.suitability(None, "finance", "finance") == 1
    assert staff_roles.suitability("Driver", "staff", "finance") == 0


def test_general_business_has_no_funeral_screens_but_funeral_is_untouched(
    client, auth_headers, db, test_data
):
    admin = test_data["main_admin"]
    funeral = client.get("/users/me/access", headers=auth_headers(admin)).json()
    assert funeral["business_type"] == "funeral"
    assert "cases.view" in funeral["permissions"] and "income.view" not in funeral["permissions"]
    assert client.get("/cases", headers=auth_headers(admin)).status_code == 200
    assert client.get("/money/summary", headers=auth_headers(admin)).status_code == 403

    go_general(db, test_data)
    general = client.get("/users/me/access", headers=auth_headers(admin)).json()
    assert general["business_type"] == "general"
    for hidden in ("cases.view", "mortuary.view", "memberships.view", "death_records.view"):
        assert hidden not in general["permissions"]
    for kept in ("tasks.view", "income.view", "expenses.view", "chat.use"):
        assert kept in general["permissions"]
    assert client.get("/cases", headers=auth_headers(admin)).status_code == 403
    assert client.get("/mortuary/locations", headers=auth_headers(admin)).status_code in (403, 404)
    assert client.get("/money/summary", headers=auth_headers(admin)).status_code == 200


def test_money_in_and_out_gives_profit_and_loss(client, auth_headers, db, test_data):
    go_general(db, test_data)
    admin = test_data["main_admin"]
    today = date.today().isoformat()
    r = client.post("/money/income", headers=auth_headers(admin), json={
        "category": "sales", "description": "Shop sales", "amount": "1500.00", "income_date": today})
    assert r.status_code == 201, r.text
    spend = client.post("/expenses", headers=auth_headers(admin), json={
        "category": "rent", "description": "October rent", "amount": "600.00", "expense_date": today})
    assert spend.status_code == 201, spend.text

    s = client.get("/money/summary", headers=auth_headers(admin)).json()
    assert s["income"] == 1500.0 and s["expenses"] == 600.0 and s["profit"] == 900.0
    assert s["result"] == "profit"
    assert s["expenses_by_category"][0]["category"] == "rent"

    client.post(f"/money/income/{r.json()['id']}/void", headers=auth_headers(admin),
                json={"reason": "Entered twice"})
    s = client.get("/money/summary", headers=auth_headers(admin)).json()
    assert s["income"] == 0 and s["result"] == "loss" and s["profit"] == -600.0


def test_kai_picks_the_person_whose_job_fits_the_task(client, auth_headers, db, test_data):
    biz = go_general(db, test_data)
    admin = test_data["main_admin"]
    acct = make_staff(db, test_data["staff"], biz, name="Ann")
    acct.job_title = "Accountant"
    driver = make_staff(db, test_data["staff"], biz, name="Dan")
    driver.job_title = "Delivery driver"
    db.commit()

    r = client.post("/work/tasks", headers=auth_headers(admin), json={
        "title": "Chase the unpaid invoices", "let_kai_choose": True})
    assert r.status_code == 201, r.text
    assert r.json()["assignees"] == ["Ann"] and r.json()["chosen_by_kai"] is True
    assert "Accountant" in r.json()["reason"]

    r = client.post("/work/tasks", headers=auth_headers(admin), json={
        "title": "Deliver the parcels to the depot", "let_kai_choose": True})
    assert r.json()["assignees"] == ["Dan"]

    # Their tasks show on their own task list, with no funeral case in sight.
    mine = client.get("/tasks/board?scope=mine", headers=auth_headers(acct)).json()["tasks"]
    assert [t["title"] for t in mine] == ["Chase the unpaid invoices"]


def test_funeral_businesses_still_add_tasks_from_cases(client, auth_headers, test_data):
    r = client.post("/work/tasks", headers=auth_headers(test_data["main_admin"]),
                    json={"title": "x"})
    assert r.status_code == 409


def test_kai_chat_makes_a_task_for_the_right_person_after_confirmation(
    client, auth_headers, db, test_data
):
    biz = go_general(db, test_data)
    admin = test_data["main_admin"]
    ann = make_staff(db, test_data["staff"], biz, name="Ann")
    ann.job_title = "Bookkeeper"
    db.commit()

    said = client.post("/kai/message", headers=auth_headers(admin),
                       json={"text": "Create a task to reconcile the bank statement"}).json()
    assert said["action"] and "Ann" in said["action"]["summary"]
    assert db.query(CaseTask).filter(CaseTask.title.like("reconcile%")).count() == 0

    done = client.post(f"/kai/actions/{said['action']['id']}/confirm", headers=auth_headers(admin)).json()
    assert done["ok"] is True
    assert db.query(CaseTask).filter(CaseTask.title.like("reconcile%")).count() == 1

    money = client.post("/kai/message", headers=auth_headers(admin),
                        json={"text": "How are we doing this month?"}).json()
    assert "coming in" in money["reply"]


def test_autopilot_does_not_invent_funeral_work_for_a_general_business(db, test_data):
    biz = go_general(db, test_data)
    biz.autopilot_mode = "auto"
    from app.services.business_type import workspace_case

    case = workspace_case(db, biz.id)
    case.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.commit()
    proposals = autopilot.plan(db, biz)
    assert [p for p in proposals if p["kind"] == "create_task"] == []


def test_registration_chooses_the_kind_of_business(client):
    from uuid import uuid4

    def register(kind):
        email = f"owner-{uuid4().hex[:8]}@example.com"
        body = {"business_name": f"{kind} biz {uuid4().hex[:4]}", "full_name": "Owner One",
                "email": email, "password": "TestPassword123!"}
        if kind:
            body["business_type"] = kind
        r = client.post("/auth/register", json=body)
        assert r.status_code == 201, r.text
        login = client.post("/auth/login", data={"username": email, "password": "TestPassword123!"})
        if login.status_code != 200:
            login = client.post("/auth/login", json={"email": email, "password": "TestPassword123!"})
        token = login.json()["access_token"]
        return client.get("/users/me/access", headers={"Authorization": f"Bearer {token}"}).json()

    assert register("general")["business_type"] == "general"
    assert register(None)["business_type"] == "funeral"  # unchanged default


def test_general_business_gets_its_own_setup_steps(client, auth_headers, db, test_data):
    admin = test_data["main_admin"]
    funeral = client.get("/onboarding/status", headers=auth_headers(admin)).json()
    assert any(s["key"] == "plans" for s in funeral["steps"])

    go_general(db, test_data)
    general = client.get("/onboarding/status", headers=auth_headers(admin)).json()
    keys = [s["key"] for s in general["steps"]]
    assert "plans" not in keys and "members" not in keys and "case" not in keys
    assert {"income", "task", "team"} <= set(keys)
