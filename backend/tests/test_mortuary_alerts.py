"""People are told about the mortuary, not left to go and look."""

from datetime import datetime, timedelta, timezone

from app.models.notification import Notification
from app.services import mortuary_alerts
from tests.test_mortuary import (
    identify,
    make_case,
    make_location,
    prepare_paperwork,
    release,
    take_in,
)
from tests.test_mortuary_overview import log, overview
from tests.test_workspace_groups import make_staff


def notes(db, user, kind=None):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if kind:
        query = query.filter(Notification.kind == kind)
    return query.order_by(Notification.created_at).all()


def team(db, test_data):
    biz = test_data["business_a"]
    base = test_data["staff"]
    return {
        "ops": make_staff(db, base, biz, role="operations", name="Ops"),
        "mortuary": make_staff(db, base, biz, role="mortuary", name="Morgue"),
        "finance": make_staff(db, base, biz, role="finance", name="Money"),
    }


def test_taking_remains_in_tells_operations_only(
    client, db, test_data, auth_headers
):
    people = team(db, test_data)
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    assert take_in(client, auth_headers, manager, case).status_code == 201

    got = notes(db, people["ops"], "mortuary_update")
    assert len(got) == 1
    assert "taken into the mortuary" in got[0].title
    assert got[0].link == f"/cases/{case.id}"
    # Finance has no part in this step, and the actor is not told.
    assert not notes(db, people["finance"], "mortuary_update")
    assert not notes(db, manager, "mortuary_update")


def test_release_tells_operations(client, db, test_data, auth_headers):
    people = team(db, test_data)
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    take_in(client, auth_headers, manager, case)
    prepare_paperwork(client, auth_headers, manager, case)
    identify(client, auth_headers, manager, case)

    assert release(client, auth_headers, manager, case).status_code == 200

    titles = [n.title for n in notes(db, people["ops"], "mortuary_update")]
    assert any("released from the mortuary" in t for t in titles)


def test_a_warm_reading_alerts_the_mortuary_team_once_an_hour(
    client, db, test_data, auth_headers
):
    people = team(db, test_data)
    manager = test_data["manager"]
    fridge = make_location(db, test_data["business_a"], "Fridge 1", "fridge", 4)

    assert log(client, auth_headers, manager, fridge, 3.5).status_code == 201
    assert not notes(db, people["mortuary"], "mortuary_alert")

    log(client, auth_headers, manager, fridge, 9.0)
    log(client, auth_headers, manager, fridge, 9.5)

    got = notes(db, people["mortuary"], "mortuary_alert")
    assert len(got) == 1  # the second warm reading stays quiet
    assert got[0].title == "Cold place too warm"
    assert "Fridge 1" in got[0].body
    assert not notes(db, people["finance"], "mortuary_alert")


def test_a_missed_temperature_check_shows_and_is_sent_once_a_day(
    client, db, test_data, auth_headers
):
    people = team(db, test_data)
    manager = test_data["manager"]
    biz = test_data["business_a"]
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    take_in(client, auth_headers, manager, make_case(db, biz),
            location_id=str(fridge.id))

    reasons = [
        a["reason"]
        for a in overview(client, auth_headers, manager).json()["attention"]
    ]
    assert "reading_overdue" in reasons

    first = mortuary_alerts.run_for_business(db, biz.id)
    again = mortuary_alerts.run_for_business(db, biz.id)
    assert first > 0 and again == 0

    mine = [
        n.title for n in notes(db, people["mortuary"], "mortuary_alert")
    ]
    assert "Temperature check missed" in mine

    # Writing the temperature down clears the problem.
    log(client, auth_headers, manager, fridge, 3.0)
    reasons = [
        a["reason"]
        for a in overview(client, auth_headers, manager).json()["attention"]
    ]
    assert "reading_overdue" not in reasons


def test_an_old_reading_counts_as_missed(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    biz = test_data["business_a"]
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    take_in(client, auth_headers, manager, make_case(db, biz),
            location_id=str(fridge.id))
    stale = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
    log(client, auth_headers, manager, fridge, 3.0, recorded_at=stale)

    reasons = [
        a["reason"]
        for a in overview(client, auth_headers, manager).json()["attention"]
    ]
    assert "reading_overdue" in reasons


def test_an_empty_cold_place_needs_no_check(
    client, db, test_data, auth_headers
):
    make_location(db, test_data["business_a"], "Spare", "fridge", 2)
    reasons = [
        a["reason"]
        for a in overview(
            client, auth_headers, test_data["manager"]
        ).json()["attention"]
    ]
    assert "reading_overdue" not in reasons


def test_other_businesses_are_not_alerted(
    client, db, test_data, auth_headers
):
    team(db, test_data)
    other = test_data["other_business_manager"]
    biz = test_data["business_a"]
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    take_in(client, auth_headers, test_data["manager"],
            make_case(db, biz), location_id=str(fridge.id))

    mortuary_alerts.run_for_business(db, biz.id)
    assert not notes(db, other, "mortuary_alert")
    assert not notes(db, other, "mortuary_update")
