"""KAI: identity, context, follow-ups, access limits and safe actions."""

from datetime import timedelta

import pytest

from app.models.case_task import CaseTask
from app.models.death_record import CasePaperworkItem
from app.models.kai import KaiAction, KaiTurn
from app.services.communications import today_in_south_africa
from tests.test_branches import make_branch, make_case
from tests.test_mortuary import identify, take_in
from tests.test_workspace_groups import make_staff


def say(client, auth_headers, user, text):
    r = client.post("/kai/message", json={"text": text},
                    headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


def named(db, case, name):
    case.deceased_full_name = name
    db.commit()
    return case


def soon_cases(db, business, branch=None, n=2):
    day = today_in_south_africa() + timedelta(days=2)
    out = []
    for i in range(n):
        case = make_case(db, business, branch)
        case.funeral_date = day
        case.deceased_full_name = f"Person Number{i}"
        out.append(case)
    db.commit()
    return out


# ---------------- greeting and context ----------------

def test_hello_uses_verified_branch_and_name(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    soweto = make_branch(db, biz, "Soweto", "SWT")
    worker = make_staff(db, test_data["staff"], biz, branch=soweto, name="Thabo Mokoena")
    r = client.get("/kai/hello", headers=auth_headers(worker))
    assert r.status_code == 200
    body = r.json()
    assert "Thabo" in body["reply"]
    assert "Soweto" in body["reply"]
    assert body["branch"] == "Soweto"


def test_hello_admits_when_branch_unknown(client, auth_headers, db, test_data):
    worker = make_staff(db, test_data["staff"], test_data["business_a"], name="No Branch")
    body = client.get("/kai/hello", headers=auth_headers(worker)).json()
    assert "couldn't confirm your assigned branch" in body["reply"]


def test_hello_briefing_reflects_real_records(client, auth_headers, db, test_data):
    soon_cases(db, test_data["business_a"])
    body = client.get("/kai/hello", headers=auth_headers(test_data["main_admin"])).json()
    assert any(b["key"] == "no_vehicle" for b in body["briefing"])


# ---------------- following a conversation ----------------

def test_second_one_follow_up(client, auth_headers, db, test_data):
    cases = soon_cases(db, test_data["business_a"])
    admin = test_data["main_admin"]
    first = say(client, auth_headers, admin,
                "Which funerals this week have no vehicle booked?")
    assert len(first["items"]) >= 2
    second = say(client, auth_headers, admin, "Tell me about the second one")
    # The second item in the list is the one described.
    wanted = first["items"][1]["label"]
    assert wanted.split(" (")[0] in second["reply"]


def test_that_case_remembers_the_case(client, auth_headers, db, test_data):
    case = named(db, make_case(db, test_data["business_a"]), "Lindiwe Dlamini")
    admin = test_data["main_admin"]
    first = say(client, auth_headers, admin, "Tell me about Lindiwe Dlamini")
    assert "Lindiwe Dlamini" in first["reply"]
    again = say(client, auth_headers, admin, "What is still outstanding on that case?")
    assert "Lindiwe Dlamini" in again["reply"]


def test_unknown_name_is_not_invented(client, auth_headers, test_data):
    r = say(client, auth_headers, test_data["main_admin"], "Tell me about Zanele Quartermain")
    assert "couldn't find" in r["reply"]


def test_ambiguous_name_asks_which(client, auth_headers, db, test_data):
    for suffix in ("A", "B"):
        named(db, make_case(db, test_data["business_a"]), f"Nomsa Khumalo {suffix}")
    r = say(client, auth_headers, test_data["main_admin"], "Tell me about Nomsa Khumalo")
    assert "more than one" in r["reply"]
    assert len(r["items"]) == 2


def test_attention_picks_first_alert(client, auth_headers, db, test_data):
    soon_cases(db, test_data["business_a"], n=1)
    r = say(client, auth_headers, test_data["main_admin"], "Show me the case that needs attention")
    assert "Person Number0" in r["reply"]


# ---------------- accuracy ----------------

def test_missing_lists_real_gaps(client, auth_headers, db, test_data):
    case = named(db, make_case(db, test_data["business_a"]), "Gap Person")
    db.add(CaseTask(business_id=case.business_id, case_id=case.id,
                    title="Call the family", status="pending",
                    due_date=today_in_south_africa() - timedelta(days=3)))
    db.commit()
    r = say(client, auth_headers, test_data["main_admin"], "What is missing on Gap Person?")
    labels = " ".join(i["label"] for i in r["items"])
    assert "Task overdue" in labels and "Call the family" in labels
    assert "No funeral date" in labels


def test_clean_case_reports_nothing_outstanding(client, auth_headers, db, test_data):
    case = named(db, make_case(db, test_data["business_a"], status="completed"), "Tidy Person")
    r = say(client, auth_headers, test_data["main_admin"], "What is outstanding on Tidy Person?")
    assert "Nothing looks outstanding" in r["reply"]


def test_collection_is_not_just_being_in_the_mortuary(
    client, auth_headers, db, test_data
):
    case = named(db, make_case(db, test_data["business_a"]), "Cold Person")
    assert take_in(client, auth_headers, test_data["manager"], case).status_code == 201
    r = say(client, auth_headers, test_data["main_admin"],
            "Is Cold Person ready for collection?")
    assert "wouldn't mark this one ready" in r["reply"]
    assert any("identified" in i["label"] for i in r["items"])


def test_collection_without_a_remains_record(client, auth_headers, db, test_data):
    named(db, make_case(db, test_data["business_a"]), "Nowhere Person")
    r = say(client, auth_headers, test_data["main_admin"],
            "Is Nowhere Person ready for collection?")
    assert "no mortuary record" in r["reply"]


# ---------------- access limits ----------------

def test_staff_cannot_open_another_branchs_case(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    main = make_branch(db, biz, "Main", "MAIN", main=True)
    soweto = make_branch(db, biz, "Soweto", "SWT")
    named(db, make_case(db, biz, main), "Secret Person")
    worker = make_staff(db, test_data["staff"], biz, branch=soweto)
    r = say(client, auth_headers, worker, "Tell me about Secret Person")
    assert "Secret" not in r["reply"].replace("Secret Person.", "") or "couldn't find" in r["reply"]
    assert "couldn't find" in r["reply"]


def test_staff_refused_organisation_wide_views(client, auth_headers, db, test_data):
    worker = make_staff(db, test_data["staff"], test_data["business_a"])
    r = say(client, auth_headers, worker, "Show me every case across all our branches")
    assert "can't provide the organisation-wide" in r["reply"]
    assert r["items"] == []


def test_admin_gets_branch_overview(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    main = make_branch(db, biz, "Main", "MAIN", main=True)
    soweto = make_branch(db, biz, "Soweto", "SWT")
    make_case(db, biz, main)
    make_case(db, biz, soweto)
    r = say(client, auth_headers, test_data["main_admin"], "Compare all branches for me")
    text = " ".join(i["label"] for i in r["items"])
    assert "Main" in text and "Soweto" in text


def test_permissions_limit_answers(client, auth_headers, db, test_data):
    mortuary = make_staff(db, test_data["staff"], test_data["business_a"], role="mortuary")
    r = say(client, auth_headers, mortuary, "How much is outstanding on funerals?")
    assert "can't help with that from your current access" in r["reply"]


# ---------------- memory is private ----------------

def test_conversations_are_private_to_each_person(client, auth_headers, db, test_data):
    admin, manager = test_data["main_admin"], test_data["manager"]
    named(db, make_case(db, test_data["business_a"]), "Private Memory")
    say(client, auth_headers, admin, "Tell me about Private Memory")
    mine = client.get("/kai/history", headers=auth_headers(admin)).json()
    theirs = client.get("/kai/history", headers=auth_headers(manager)).json()
    assert any("Private Memory" in t["text"] for t in mine)
    assert theirs == []


def test_other_person_cannot_use_a_pronoun_from_my_chat(client, auth_headers, db, test_data):
    named(db, make_case(db, test_data["business_a"]), "Lonely Person")
    say(client, auth_headers, test_data["main_admin"], "Tell me about Lonely Person")
    r = say(client, auth_headers, test_data["manager"], "What is outstanding on that case?")
    assert "Lonely" not in r["reply"]


def test_clear_history(client, auth_headers, test_data):
    h = auth_headers(test_data["main_admin"])
    say(client, auth_headers, test_data["main_admin"], "hello")
    assert client.delete("/kai/history", headers=h).status_code == 204
    assert client.get("/kai/history", headers=h).json() == []


# ---------------- actions need confirmation ----------------

def test_task_is_prepared_then_confirmed(client, auth_headers, db, test_data):
    case = named(db, make_case(db, test_data["business_a"]), "Task Person")
    admin = test_data["main_admin"]
    r = say(client, auth_headers, admin,
            "Create a task to call the family for Task Person")
    assert r["action"] is not None
    # Nothing has happened yet.
    assert db.query(CaseTask).filter(CaseTask.case_id == case.id).count() == 0
    done = client.post(f"/kai/actions/{r['action']['id']}/confirm",
                       headers=auth_headers(admin))
    assert done.status_code == 200 and done.json()["ok"], done.text
    db.expire_all()
    tasks = db.query(CaseTask).filter(CaseTask.case_id == case.id).all()
    assert [t.title for t in tasks] == ["call the family for Task Person"]
    # Cannot be run twice.
    again = client.post(f"/kai/actions/{r['action']['id']}/confirm",
                        headers=auth_headers(admin))
    assert again.json()["ok"] is False


def test_cancelled_action_does_nothing(client, auth_headers, db, test_data):
    case = named(db, make_case(db, test_data["business_a"]), "Cancel Person")
    admin = test_data["main_admin"]
    r = say(client, auth_headers, admin, "Add a task for Cancel Person")
    client.post(f"/kai/actions/{r['action']['id']}/cancel", headers=auth_headers(admin))
    out = client.post(f"/kai/actions/{r['action']['id']}/confirm", headers=auth_headers(admin))
    assert out.json()["ok"] is False
    assert db.query(CaseTask).filter(CaseTask.case_id == case.id).count() == 0


def test_someone_else_cannot_confirm_my_action(client, auth_headers, db, test_data):
    named(db, make_case(db, test_data["business_a"]), "Mine Person")
    r = say(client, auth_headers, test_data["main_admin"], "Add a task for Mine Person")
    out = client.post(f"/kai/actions/{r['action']['id']}/confirm",
                      headers=auth_headers(test_data["manager"]))
    assert out.json()["ok"] is False


def test_action_rechecks_permission_at_confirmation(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    named(db, make_case(db, biz), "Recheck Person")
    staffer = make_staff(db, test_data["staff"], biz, role="manager")
    r = say(client, auth_headers, staffer, "Add a task for Recheck Person")
    assert r["action"]
    # Access is taken away between preparing and confirming.
    from app.models.permission import Permission
    from app.models.user_permission import UserPermission

    perm = db.query(Permission).filter(Permission.key == "tasks.manage").one()
    db.add(UserPermission(user_id=staffer.id, permission_id=perm.id, effect="deny"))
    db.commit()
    out = client.post(f"/kai/actions/{r['action']['id']}/confirm",
                      headers=auth_headers(staffer))
    assert out.json()["ok"] is False


def test_expired_action_is_dropped(client, auth_headers, db, test_data):
    case = named(db, make_case(db, test_data["business_a"]), "Late Person")
    admin = test_data["main_admin"]
    r = say(client, auth_headers, admin, "Add a task for Late Person")
    action = db.get(KaiAction, r["action"]["id"])
    action.expires_at = action.expires_at - timedelta(hours=1)
    db.commit()
    out = client.post(f"/kai/actions/{r['action']['id']}/confirm", headers=auth_headers(admin))
    assert out.json()["ok"] is False
    assert db.query(CaseTask).filter(CaseTask.case_id == case.id).count() == 0


def test_every_example_runs(client, auth_headers, test_data):
    admin = test_data["main_admin"]
    body = client.get("/kai/hello", headers=auth_headers(admin)).json()
    for example in body["suggestions"]:
        r = say(client, auth_headers, admin, example)
        assert r["reply"], example


def test_kai_lists_my_services_and_reports_autopilot(client, auth_headers, db, test_data):
    from app.models.business import Business
    from app.models.case_service import CaseServiceAssignee
    from tests.test_financial_documents import make_service

    biz = test_data["business_a"]
    case = make_case(db, biz)
    service = make_service(db, biz, case, name="Hearse")
    staffer = test_data["staff"]
    service.assignee_rows = [CaseServiceAssignee(user_id=staffer.id)]
    db.commit()
    r = say(client, auth_headers, staffer, "what services are waiting for me?")
    assert "1 service" in r["reply"] and r["items"][0]["label"].startswith("Hearse")

    # Plain staff are not told about Autopilot or the team's workload.
    denied = say(client, auth_headers, staffer, "what has autopilot done?")
    assert "can't" in denied["reply"].lower() or "not" in denied["reply"].lower()
    asked = say(client, auth_headers, test_data["manager"], "what has autopilot done?")
    assert "switched off" in asked["reply"]
    db.get(Business, biz.id).autopilot_mode = "auto"
    db.commit()
    asked = say(client, auth_headers, test_data["manager"], "who is free? show the workload")
    assert "lightest" in asked["reply"]
