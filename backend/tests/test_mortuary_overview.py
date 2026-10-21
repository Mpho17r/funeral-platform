"""The mortuary dashboard feed and the cold-room temperature log."""

from datetime import datetime, timedelta, timezone

from app.models.audit_log import AuditLog
from tests.test_mortuary import (
    deny,
    identify,
    make_case,
    make_location,
    prepare_paperwork,
    take_in,
)


def overview(client, auth_headers, user, **params):
    return client.get(
        "/mortuary/overview", params=params, headers=auth_headers(user)
    )


def log(client, auth_headers, user, location, temp, **extra):
    return client.post(
        f"/mortuary/locations/{location.id}/temperature",
        json={"temperature_c": temp, **extra},
        headers=auth_headers(user),
    )


def test_occupancy_counts_cold_places_only(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    manager = test_data["manager"]
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    make_location(db, biz, "Cold room", "cold_room", 6)
    make_location(db, biz, "Prep room", "preparation_room", 2)

    case = make_case(db, biz)
    assert take_in(client, auth_headers, manager, case,
                   location_id=str(fridge.id)).status_code == 201

    body = overview(client, auth_headers, manager).json()
    assert body["occupancy"]["occupied"] == 1
    assert body["occupancy"]["capacity"] == 10
    assert body["occupancy"]["percent"] == 10.0
    assert [u["name"] for u in body["units"]] == ["Cold room", "Fridge 1"]
    unit = next(u for u in body["units"] if u["name"] == "Fridge 1")
    assert unit["status"] == "occupied"
    assert unit["occupants"][0]["name"] == "Private Name"
    assert body["admissions_today"] == 1
    assert body["in_care"] == 1


def test_a_full_place_and_an_empty_one(client, db, test_data, auth_headers):
    biz, manager = test_data["business_a"], test_data["manager"]
    one = make_location(db, biz, "Single", "fridge", 1)
    make_location(db, biz, "Spare", "fridge", 1)
    take_in(client, auth_headers, manager, make_case(db, biz),
            location_id=str(one.id))

    units = {
        u["name"]: u["status"]
        for u in overview(client, auth_headers, manager).json()["units"]
    }
    assert units == {"Single": "full", "Spare": "available"}


def test_sequence_stages_follow_the_journey(
    client, db, test_data, auth_headers
):
    biz, manager = test_data["business_a"], test_data["manager"]
    fridge = make_location(db, biz, "F", "fridge", 10)

    # 1 not identified, 1 identified but not prepared,
    # 1 identified + prepared but no paperwork, 1 fully ready.
    c1 = make_case(db, biz)
    take_in(client, auth_headers, manager, c1, location_id=str(fridge.id))

    c2 = make_case(db, biz)
    take_in(client, auth_headers, manager, c2, location_id=str(fridge.id))
    identify(client, auth_headers, manager, c2)

    c3 = make_case(db, biz)
    take_in(client, auth_headers, manager, c3, location_id=str(fridge.id))
    identify(client, auth_headers, manager, c3)
    client.post(f"/cases/{c3.id}/remains/events", headers=auth_headers(manager),
                json={"event_type": "prepared", "procedure": "washed"})

    c4 = make_case(db, biz)
    take_in(client, auth_headers, manager, c4, location_id=str(fridge.id))
    prepare_paperwork(client, auth_headers, manager, c4)
    identify(client, auth_headers, manager, c4)
    client.post(f"/cases/{c4.id}/remains/events", headers=auth_headers(manager),
                json={"event_type": "prepared", "procedure": "washed"})

    body = overview(client, auth_headers, manager).json()
    assert body["stages"] == {
        "awaiting_identification": 1,
        "awaiting_preparation": 1,
        "awaiting_paperwork": 1,
        "ready_for_release": 1,
    }
    assert body["pending_releases"] == 1
    assert body["ready_for_release"][0]["case_id"] == str(c4.id)


def test_temperature_log_chart_and_alerts(
    client, db, test_data, auth_headers
):
    biz, manager = test_data["business_a"], test_data["manager"]
    fridge = make_location(db, biz, "F", "fridge", 4)

    assert log(client, auth_headers, manager, fridge, 2.5).status_code == 201
    assert log(client, auth_headers, manager, fridge, 3.5).status_code == 201

    t = overview(client, auth_headers, manager).json()["temperature"]
    assert t["readings"] == 2 and t["average_c"] == 3.0
    assert t["min_c"] == 2.5 and t["max_c"] == 3.5
    assert t["out_of_range"] == 0 and len(t["points"]) >= 1

    assert log(client, auth_headers, manager, fridge, 8.0).status_code == 201
    body = overview(client, auth_headers, manager).json()
    assert body["units"][0]["status"] == "out_of_range"
    assert body["units"][0]["temperature_c"] == 8.0
    assert any(a["reason"] == "temperature" for a in body["attention"])

    audit = db.query(AuditLog).filter_by(
        action="mortuary_location.temperature_logged").count()
    assert audit == 3


def test_temperature_validation(client, db, test_data, auth_headers):
    biz, manager = test_data["business_a"], test_data["manager"]
    fridge = make_location(db, biz, "F", "fridge", 4)
    prep = make_location(db, biz, "P", "preparation_room", 2)

    assert log(client, auth_headers, manager, prep, 3).status_code == 409
    assert log(client, auth_headers, manager, fridge, 99).status_code == 422
    soon = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert log(client, auth_headers, manager, fridge, 3,
               recorded_at=soon).status_code == 422
    old = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
    assert log(client, auth_headers, manager, fridge, 3,
               recorded_at=old).status_code == 422
    other = make_location(db, test_data["business_b"], "Other", "fridge", 2)
    assert log(client, auth_headers, manager, other, 3).status_code == 404


def test_cooling_overdue_and_unidentified_surface_as_attention(
    client, db, test_data, auth_headers
):
    biz, manager = test_data["business_a"], test_data["manager"]
    case = make_case(db, biz)
    late = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    assert take_in(client, auth_headers, manager, case,
                   received_at=late).status_code == 201

    body = overview(client, auth_headers, manager).json()
    reasons = {a["reason"] for a in body["attention"]}
    assert "cooling_overdue" in reasons
    assert body["not_in_a_cold_place"][0]["case_id"] == str(case.id)


def test_other_businesses_are_invisible(client, db, test_data, auth_headers):
    take_in(client, auth_headers, test_data["other_business_manager"],
            make_case(db, test_data["business_b"]))
    make_location(db, test_data["business_b"], "Theirs", "fridge", 3)

    body = overview(client, auth_headers, test_data["manager"]).json()
    assert body["in_care"] == 0 and body["units"] == []


def test_permissions(client, db, test_data, auth_headers):
    staff, manager = test_data["staff"], test_data["manager"]
    fridge = make_location(db, test_data["business_a"], "F", "fridge", 2)

    # Plain staff may look but not log temperatures.
    assert overview(client, auth_headers, staff).status_code in (200, 403)
    deny(db, manager, "mortuary.view")
    assert overview(client, auth_headers, manager).status_code == 403
    deny(db, test_data["main_admin"], "mortuary.manage")
    assert log(client, auth_headers, test_data["main_admin"],
               fridge, 3).status_code == 201  # main admin holds everything
