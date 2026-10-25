"""Ask FuneralOS: answers come from real data, within the person's access."""

from datetime import timedelta

import pytest

from app.services.communications import today_in_south_africa
from tests.test_branches import make_branch, make_case
from tests.test_workspace_groups import make_staff


def ask(client, auth_headers, user, q):
    r = client.post("/assistant/ask", json={"question": q},
                    headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


def test_unknown_question_lists_what_can_be_asked(
    client, auth_headers, test_data
):
    out = ask(client, auth_headers, test_data["main_admin"], "tell me a joke")
    assert out["understood"] is False
    assert len(out["suggestions"]) >= 5


def test_funerals_with_no_booking_are_found(
    client, auth_headers, db, test_data
):
    case = make_case(db, test_data["business_a"])
    case.funeral_date = today_in_south_africa() + timedelta(days=2)
    db.commit()
    out = ask(client, auth_headers, test_data["main_admin"],
              "Which funerals this week have no vehicle booked?")
    assert out["question"] == "no_vehicle"
    assert any(case.case_number in i["label"] for i in out["items"])


def test_questions_respect_permissions(client, auth_headers, db, test_data):
    mortuary = make_staff(db, test_data["staff"], test_data["business_a"],
                          role="mortuary")
    out = ask(client, auth_headers, mortuary, "What was collected this month?")
    assert "do not have access" in out["answer"]
    keys = {s["key"] for s in out["suggestions"]}
    assert "collected" not in keys and "custody" in keys


def test_answers_follow_branch_limits(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    main = make_branch(db, biz, "Main", "MAIN", main=True)
    soweto = make_branch(db, biz, "Soweto", "SWT")
    soon = today_in_south_africa() + timedelta(days=1)
    mine, theirs = make_case(db, biz, soweto), make_case(db, biz, main)
    for c in (mine, theirs):
        c.funeral_date = soon
    db.commit()
    worker = make_staff(db, test_data["staff"], biz, branch=soweto)
    out = ask(client, auth_headers, worker, "What funerals are coming up?")
    labels = " ".join(i["label"] for i in out["items"])
    assert mine.case_number in labels
    assert theirs.case_number not in labels


def test_money_answers(client, auth_headers, test_data):
    out = ask(client, auth_headers, test_data["main_admin"],
              "How much was collected this month?")
    assert out["question"] == "collected"
    assert out["answer"].startswith("R ")


def test_every_question_runs(client, auth_headers, test_data):
    from app.services.assistant import QUESTIONS

    for key, _, _, _, example in QUESTIONS:
        out = ask(client, auth_headers, test_data["main_admin"], example)
        assert out["understood"] and out["question"] == key, example
        assert out["answer"]
