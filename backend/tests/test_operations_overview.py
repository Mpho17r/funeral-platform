"""The operations dashboard feed."""

from datetime import date, datetime, timedelta, timezone

from app.models.arrangement import CaseCollection, FuneralArrangement
from app.models.case_task import CaseTask
from app.models.death_record import DeathRecord
from app.models.resource import ResourceBooking
from tests.test_mortuary import (
    deny,
    make_case,
    make_vehicle,
    take_in,
)

NOW = datetime.now(timezone.utc)


def get(client, auth_headers, user, **params):
    return client.get(
        "/operations/overview", params=params, headers=auth_headers(user)
    )


def case_row(body, case):
    return next(c for c in body["cases"] if c["case_id"] == str(case.id))


def test_a_new_case_starts_at_arranging_the_collection(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    body = get(client, auth_headers, test_data["manager"]).json()

    row = case_row(body, case)
    assert row["next_action"] == "arrange_collection"
    assert row["steps"]["collection"] == "todo"
    assert body["kpis"]["live_cases"] == 1
    assert body["kpis"]["needing_action"] == 1


def test_next_action_follows_the_funeral_sequence(
    client, db, test_data, auth_headers
):
    biz, manager = test_data["business_a"], test_data["manager"]
    case = make_case(db, biz)

    # A scheduled collection: waiting for the pick-up.
    col = CaseCollection(
        business_id=biz.id, case_id=case.id, status="scheduled",
        scheduled_at=NOW + timedelta(hours=2), pickup_type="home",
    )
    db.add(col)
    db.commit()
    row = case_row(get(client, auth_headers, manager).json(), case)
    assert row["next_action"] == "await_collection"

    # Remains taken in: collection done, now the death record.
    assert take_in(client, auth_headers, manager, case).status_code == 201
    row = case_row(get(client, auth_headers, manager).json(), case)
    assert row["steps"]["collection"] == "done"
    assert row["next_action"] == "death_record"

    db.add(DeathRecord(business_id=biz.id, case_id=case.id,
                       disposal_method="burial"))
    db.commit()
    row = case_row(get(client, auth_headers, manager).json(), case)
    assert row["next_action"] == "plan_arrangement"

    arr = FuneralArrangement(business_id=biz.id, case_id=case.id,
                             status="draft")
    db.add(arr)
    db.commit()
    row = case_row(get(client, auth_headers, manager).json(), case)
    assert row["next_action"] == "confirm_arrangement"

    arr.status = "confirmed"
    db.commit()
    row = case_row(get(client, auth_headers, manager).json(), case)
    # A death record with no paperwork list yet counts as outstanding.
    assert row["next_action"] == "paperwork"


def test_vehicle_is_needed_only_when_the_funeral_is_close(
    client, db, test_data, auth_headers
):
    biz, manager = test_data["business_a"], test_data["manager"]
    soon = make_case(db, biz)
    far = make_case(db, biz)
    soon.funeral_date = date.today() + timedelta(days=2)
    far.funeral_date = date.today() + timedelta(days=20)
    for c in (soon, far):
        db.add(DeathRecord(business_id=biz.id, case_id=c.id,
                           disposal_method="burial"))
        db.add(FuneralArrangement(business_id=biz.id, case_id=c.id,
                                  status="confirmed"))
        take_in(client, auth_headers, manager, c)
    db.commit()

    from app.models.death_record import CasePaperworkItem
    for c in (soon, far):
        db.add(CasePaperworkItem(business_id=biz.id, case_id=c.id,
                                 item_type="custom", label="Done",
                                 status="obtained"))
    db.commit()

    body = get(client, auth_headers, manager).json()
    assert case_row(body, soon)["next_action"] == "book_vehicle"
    assert case_row(body, soon)["urgent"] is True
    assert case_row(body, far)["next_action"] == "on_track"

    # Cases are ordered by how soon the funeral is.
    ids = [c["case_id"] for c in body["cases"]]
    assert ids.index(str(soon.id)) < ids.index(str(far.id))

    van = make_vehicle(db, biz)
    db.add(ResourceBooking(
        business_id=biz.id, case_id=soon.id, resource_id=van.id,
        starts_at=NOW + timedelta(days=2),
        ends_at=NOW + timedelta(days=2, hours=3), status="booked",
    ))
    db.commit()
    body = get(client, auth_headers, manager).json()
    assert case_row(body, soon)["next_action"] == "on_track"


def test_collections_due_and_overdue(client, db, test_data, auth_headers):
    biz = test_data["business_a"]
    late = make_case(db, biz)
    db.add(CaseCollection(
        business_id=biz.id, case_id=late.id, status="scheduled",
        scheduled_at=NOW - timedelta(hours=1), pickup_type="hospital",
    ))
    tomorrow = make_case(db, biz)
    db.add(CaseCollection(
        business_id=biz.id, case_id=tomorrow.id, status="scheduled",
        scheduled_at=NOW + timedelta(days=2), pickup_type="home",
    ))
    db.commit()

    body = get(client, auth_headers, test_data["manager"]).json()
    due = body["collections_due"]
    assert [c["case_id"] for c in due] == [str(late.id)]
    assert due[0]["overdue"] is True


def test_overdue_tasks_are_counted(client, db, test_data, auth_headers):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    db.add(CaseTask(business_id=biz.id, case_id=case.id, title="Call family",
                    status="open", due_date=date.today() - timedelta(days=1)))
    db.add(CaseTask(business_id=biz.id, case_id=case.id, title="Later",
                    status="open", due_date=date.today() + timedelta(days=4)))
    db.commit()

    body = get(client, auth_headers, test_data["manager"]).json()
    assert body["kpis"]["overdue_tasks"] == 1
    row = case_row(body, case)
    assert row["open_tasks"] == 2 and row["overdue_tasks"] == 1
    assert row["urgent"] is True


def test_closed_archived_and_other_business_cases_are_left_out(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    live = make_case(db, biz)
    done = make_case(db, biz)
    done.status = "closed"
    make_case(db, biz, archived=True)
    make_case(db, test_data["business_b"])
    db.commit()

    body = get(client, auth_headers, test_data["manager"]).json()
    assert [c["case_id"] for c in body["cases"]] == [str(live.id)]


def test_the_feed_has_no_money_in_it(client, db, test_data, auth_headers):
    make_case(db, test_data["business_a"])
    text = get(client, auth_headers, test_data["manager"]).text.lower()
    for word in ("balance", "total", "paid", "price", "amount", "contribution"):
        assert word not in text


def test_permission(client, db, test_data, auth_headers):
    deny(db, test_data["manager"], "cases.view")
    assert get(client, auth_headers, test_data["manager"]).status_code == 403


def test_todays_programme_lists_timed_moments_in_order(
    client, db, test_data, auth_headers
):
    from app.services.mortuary_overview import SAST

    biz = test_data["business_a"]
    case = make_case(db, biz)
    today_sa = datetime.now(SAST).date()

    def at(hour):
        return datetime(today_sa.year, today_sa.month, today_sa.day,
                        hour, 0, tzinfo=SAST)

    db.add(FuneralArrangement(
        business_id=biz.id, case_id=case.id, status="confirmed",
        departure_at=at(6), service_at=at(8), committal_at=at(10),
        service_venue="Hope Church",
    ))
    other = make_case(db, biz)
    db.add(FuneralArrangement(
        business_id=biz.id, case_id=other.id, status="confirmed",
        service_at=at(8) + timedelta(days=2),
    ))
    db.commit()

    body = get(client, auth_headers, test_data["manager"]).json()
    labels = [(p["label"], p["case_id"]) for p in body["programme"]]
    assert labels == [
        ("Departure", str(case.id)),
        ("Service", str(case.id)),
        ("Committal", str(case.id)),
    ]
    assert body["programme"][1]["venue"] == "Hope Church"
    assert body["kpis"]["funerals_today"] == 1
