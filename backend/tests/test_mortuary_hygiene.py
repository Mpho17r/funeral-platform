"""Cleaning and disinfection records (R363 regulation 11)."""

from app.models.audit_log import AuditLog
from app.services import mortuary_alerts
from tests.test_mortuary import (
    event,
    iso,
    make_case,
    make_location,
    take_in,
)
from tests.test_mortuary_alerts import notes, team
from tests.test_mortuary_overview import overview


def clean(client, auth_headers, user, task, **fields):
    return client.post(
        "/mortuary/hygiene",
        json={"task": task, **fields},
        headers=auth_headers(user),
    )


def prepared_hours_ago(client, db, test_data, auth_headers, hours=3):
    """Remains taken in 5 hours ago and prepared `hours` ago."""
    biz = test_data["business_a"]
    manager = test_data["manager"]
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    case = make_case(db, biz)
    assert take_in(
        client, auth_headers, manager, case,
        location_id=str(fridge.id), received_at=iso(-300),
    ).status_code == 201
    assert event(
        client, auth_headers, manager, case,
        event_type="prepared", procedure="washed",
        occurred_at=iso(-60 * hours),
    ).status_code == 201
    return case


def reasons(client, auth_headers, user):
    return [
        a["reason"]
        for a in overview(client, auth_headers, user).json()["attention"]
    ]


def test_a_preparation_with_no_cleaning_record_is_flagged(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    prepared_hours_ago(client, db, test_data, auth_headers)

    assert "cleaning_overdue" in reasons(client, auth_headers, manager)


def test_cleaning_surfaces_and_equipment_clears_it(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    prepared_hours_ago(client, db, test_data, auth_headers)

    clean(client, auth_headers, manager, "surfaces")
    # Surfaces alone is not enough: equipment too.
    assert "cleaning_overdue" in reasons(client, auth_headers, manager)

    clean(client, auth_headers, manager, "equipment")
    assert "cleaning_overdue" not in reasons(client, auth_headers, manager)


def test_cleaning_done_before_the_preparation_does_not_count(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    biz = test_data["business_a"]
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    case = make_case(db, biz)
    take_in(client, auth_headers, manager, case,
            location_id=str(fridge.id), received_at=iso(-400))

    clean(client, auth_headers, manager, "surfaces", performed_at=iso(-300))
    clean(client, auth_headers, manager, "equipment", performed_at=iso(-300))
    event(client, auth_headers, manager, case, event_type="prepared",
          procedure="washed", occurred_at=iso(-200))

    assert "cleaning_overdue" in reasons(client, auth_headers, manager)


def test_a_fresh_preparation_gets_time_to_clean_up(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    prepared_hours_ago(client, db, test_data, auth_headers, hours=0.5)

    assert "cleaning_overdue" not in reasons(client, auth_headers, manager)


def test_the_mortuary_team_is_alerted_once_a_day(
    client, db, test_data, auth_headers
):
    people = team(db, test_data)
    prepared_hours_ago(client, db, test_data, auth_headers)

    first = mortuary_alerts.run_for_business(db, test_data["business_a"].id)
    again = mortuary_alerts.run_for_business(db, test_data["business_a"].id)
    assert first > 0 and again == 0

    titles = [n.title for n in notes(db, people["mortuary"], "mortuary_alert")]
    assert "Cleaning record missing" in titles


def test_logging_is_audited_validated_and_listed(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]

    ok = clean(client, auth_headers, manager, "protective_clothing",
               notes="Washed on site")
    assert ok.status_code == 201
    assert ok.json()["label"] == "Protective clothing"

    assert clean(client, auth_headers, manager, "mopping").status_code == 422
    assert clean(client, auth_headers, manager, "surfaces",
                 performed_at=iso(60)).status_code == 422
    assert clean(client, auth_headers, manager, "surfaces",
                 performed_at=iso(-60 * 24 * 30)).status_code == 422

    listed = client.get("/mortuary/hygiene", headers=auth_headers(manager))
    assert listed.status_code == 200
    assert [i["task"] for i in listed.json()["items"]] == ["protective_clothing"]
    assert len(listed.json()["tasks"]) == 6

    assert (
        db.query(AuditLog)
        .filter(AuditLog.action == "mortuary.hygiene_logged")
        .count()
        == 1
    )


def test_permissions_and_isolation(client, db, test_data, auth_headers):
    staff = test_data["staff"]
    manager = test_data["manager"]
    other = test_data["other_business_manager"]

    clean(client, auth_headers, manager, "waste")

    # Staff may not log; a manager of another business sees nothing.
    assert clean(client, auth_headers, staff, "waste").status_code == 403
    theirs = client.get("/mortuary/hygiene", headers=auth_headers(other))
    assert theirs.status_code == 200 and theirs.json()["items"] == []

    # Cannot attach a record to another business's remains.
    biz_b = test_data["business_b"]
    fridge = make_location(db, biz_b, "Other fridge", "fridge", 2)
    case_b = make_case(db, biz_b)
    from tests.test_mortuary import take_in as take
    made = take(client, auth_headers, other, case_b,
                location_id=str(fridge.id))
    assert made.status_code == 201
    remains_id = made.json()["remains"]["id"]
    refused = clean(client, auth_headers, manager, "surfaces",
                    remains_id=remains_id)
    assert refused.status_code == 404
