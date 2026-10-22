import uuid

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase
from app.models.mortuary import (
    CustodyEvent,
    MortuaryLocation,
    RemainsRecord,
)
from app.models.permission import Permission
from app.models.resource import Resource
from app.models.user_permission import UserPermission


# ============================================================
# HELPERS
# ============================================================

def iso(delta_minutes=0):
    value = datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)

    return value.isoformat()


def make_case(db, business, *, number=None, archived=False):
    case = FuneralCase(
        business_id=business.id,
        case_number=number or f"MC-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Private Name",
        status="open",
        is_archived=archived,
    )
    db.add(case)
    db.commit()

    return case


def make_location(
    db,
    business,
    name="Fridge 1",
    kind="fridge",
    capacity=None,
    *,
    active=True,
):
    location = MortuaryLocation(
        business_id=business.id,
        name=name,
        kind=kind,
        capacity=capacity,
        is_active=active,
    )
    db.add(location)
    db.commit()

    return location


def make_vehicle(db, business, resource_type="vehicle"):
    resource = Resource(
        business_id=business.id,
        resource_type=resource_type,
        name=f"Res {uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(resource)
    db.commit()

    return resource


def deny(db, user, key):
    permission = (
        db.query(Permission).filter(Permission.key == key).first()
    )
    assert permission is not None, key
    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()


def take_in(client, auth_headers, user, case, **fields):
    body = {"received_from_type": "hospital"}
    body.update(fields)

    return client.post(
        f"/cases/{case.id}/remains",
        json=body,
        headers=auth_headers(user),
    )


def event(client, auth_headers, user, case, **fields):
    body = dict(fields)
    if body.get("event_type") == "moved":
        body.setdefault("handed_over_by_name", "Mortuary Staff")
        body.setdefault("accepted_by_name", "Receiving Staff")

    return client.post(
        f"/cases/{case.id}/remains/events",
        json=body,
        headers=auth_headers(user),
    )


def release(client, auth_headers, user, case, **fields):
    body = {
        "confirm_tag_number": f"T-{case.case_number}",
        "released_to_name": "Family Member",
    }
    body.update(fields)

    return client.post(
        f"/cases/{case.id}/remains/release",
        json=body,
        headers=auth_headers(user),
    )


def prepare_paperwork(client, auth_headers, user, case, *, disposal="burial"):
    """A death record and a checklist with the release paper in hand."""

    response = client.post(
        f"/cases/{case.id}/death-record",
        json={"disposal_method": disposal},
        headers=auth_headers(user),
    )
    assert response.status_code == 201, response.text

    client.post(
        f"/cases/{case.id}/paperwork/standard",
        headers=auth_headers(user),
    )

    items = client.get(
        f"/cases/{case.id}/paperwork", headers=auth_headers(user)
    ).json()["items"]

    paper = {
        "burial": "burial_order",
        "cremation": "cremation_permit",
        "repatriation": "export_permit",
    }[disposal]

    item = next(i for i in items if i["item_type"] == paper)

    response = client.patch(
        f"/cases/{case.id}/paperwork/{item['id']}",
        json={"status": "obtained"},
        headers=auth_headers(user),
    )
    assert response.status_code == 200, response.text


def identify(client, auth_headers, user, case):
    response = event(
        client,
        auth_headers,
        user,
        case,
        event_type="identified",
        identified_by_name="Thandi Nkosi",
        identified_relationship="Daughter",
    )
    assert response.status_code == 201, response.text


def ready_remains(client, db, auth_headers, test_data, **intake):
    """Remains in care, identified, with the paperwork in place."""

    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    assert take_in(
        client, auth_headers, manager, case, **intake
    ).status_code == 201

    prepare_paperwork(client, auth_headers, manager, case)
    identify(client, auth_headers, manager, case)

    return case


def audits(db, action):
    return (
        db.query(AuditLog)
        .filter(AuditLog.action == action)
        .order_by(AuditLog.created_at)
        .all()
    )


# ============================================================
# LOCATIONS
# ============================================================

def test_manager_creates_location_with_audit(
    client, db, test_data, auth_headers
):
    response = client.post(
        "/mortuary/locations",
        json={"name": "  Fridge A ", "kind": "fridge", "capacity": 6},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Fridge A"
    assert data["capacity"] == 6
    assert data["occupied"] == 0
    assert data["is_active"] is True

    entry = audits(db, "mortuary_location.created")[0]
    assert entry.details["name"] == "Fridge A"
    assert entry.details["capacity"] == 6


def test_location_name_is_unique_ignoring_case(
    client, db, test_data, auth_headers
):
    make_location(db, test_data["business_a"], name="Cold Room")

    response = client.post(
        "/mortuary/locations",
        json={"name": "cold room", "kind": "cold_room"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_two_businesses_may_use_the_same_location_name(
    client, db, test_data, auth_headers
):
    make_location(db, test_data["business_b"], name="Fridge 1")

    response = client.post(
        "/mortuary/locations",
        json={"name": "Fridge 1", "kind": "fridge"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {"name": "X", "kind": "fridge", "capacity": 0},
        {"name": "X", "kind": "fridge", "capacity": -2},
        {"name": "X", "kind": "garage"},
        {"name": "   ", "kind": "fridge"},
    ],
)
def test_invalid_locations_are_rejected(
    client, test_data, auth_headers, body
):
    response = client.post(
        "/mortuary/locations",
        json=body,
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_list_shows_occupancy_and_hides_inactive(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    fridge = make_location(db, business, "Fridge 1", capacity=4)
    make_location(db, business, "Old", active=False)

    case = make_case(db, business)
    take_in(
        client, auth_headers, test_data["manager"], case,
        location_id=str(fridge.id),
    )

    listed = client.get(
        "/mortuary/locations",
        headers=auth_headers(test_data["staff"]),
    ).json()

    assert [row["name"] for row in listed] == ["Fridge 1"]
    assert listed[0]["occupied"] == 1

    everything = client.get(
        "/mortuary/locations",
        params={"include_inactive": True},
        headers=auth_headers(test_data["staff"]),
    ).json()

    assert {row["name"] for row in everything} == {"Fridge 1", "Old"}


def test_update_location_is_audited(
    client, db, test_data, auth_headers
):
    location = make_location(db, test_data["business_a"], capacity=3)

    response = client.patch(
        f"/mortuary/locations/{location.id}",
        json={"capacity": 8},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json()["capacity"] == 8

    entry = audits(db, "mortuary_location.updated")[0]
    assert entry.details["changes"]["capacity"] == {"old": 3, "new": 8}


def test_capacity_cannot_drop_below_occupancy(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    fridge = make_location(db, business, capacity=3)

    for _ in range(2):
        take_in(
            client, auth_headers, test_data["manager"],
            make_case(db, business), location_id=str(fridge.id),
        )

    response = client.patch(
        f"/mortuary/locations/{fridge.id}",
        json={"capacity": 1},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "cannot hold fewer than 2" in response.json()["detail"]


def test_occupied_location_cannot_be_deactivated(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    fridge = make_location(db, business)

    take_in(
        client, auth_headers, test_data["manager"],
        make_case(db, business), location_id=str(fridge.id),
    )

    response = client.post(
        f"/mortuary/locations/{fridge.id}/deactivate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "Move them first" in response.json()["detail"]


def test_empty_location_can_be_deactivated_and_reactivated(
    client, db, test_data, auth_headers
):
    fridge = make_location(db, test_data["business_a"])
    manager = test_data["manager"]

    off = client.post(
        f"/mortuary/locations/{fridge.id}/deactivate",
        headers=auth_headers(manager),
    )
    assert off.status_code == 200
    assert off.json()["is_active"] is False

    again = client.post(
        f"/mortuary/locations/{fridge.id}/deactivate",
        headers=auth_headers(manager),
    )
    assert again.status_code == 409

    on = client.post(
        f"/mortuary/locations/{fridge.id}/reactivate",
        headers=auth_headers(manager),
    )
    assert on.status_code == 200
    assert on.json()["is_active"] is True

    assert len(audits(db, "mortuary_location.deactivated")) == 1
    assert len(audits(db, "mortuary_location.reactivated")) == 1


def test_staff_can_view_but_not_manage_locations(
    client, db, test_data, auth_headers
):
    location = make_location(db, test_data["business_a"])
    staff = test_data["staff"]

    assert client.get(
        "/mortuary/locations", headers=auth_headers(staff)
    ).status_code == 200

    assert client.post(
        "/mortuary/locations",
        json={"name": "New", "kind": "fridge"},
        headers=auth_headers(staff),
    ).status_code == 403

    assert client.patch(
        f"/mortuary/locations/{location.id}",
        json={"name": "Renamed"},
        headers=auth_headers(staff),
    ).status_code == 403


def test_locations_are_tenant_isolated(
    client, db, test_data, auth_headers
):
    foreign = make_location(db, test_data["business_b"], "Foreign")

    for call in (
        lambda: client.patch(
            f"/mortuary/locations/{foreign.id}",
            json={"name": "Hijack"},
            headers=auth_headers(test_data["manager"]),
        ),
        lambda: client.post(
            f"/mortuary/locations/{foreign.id}/deactivate",
            headers=auth_headers(test_data["manager"]),
        ),
    ):
        assert call().status_code == 404

    names = [
        row["name"]
        for row in client.get(
            "/mortuary/locations",
            headers=auth_headers(test_data["manager"]),
        ).json()
    ]
    assert "Foreign" not in names


# ============================================================
# TAKING REMAINS INTO CARE
# ============================================================

def test_intake_creates_record_log_and_audit(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    case = make_case(db, business, number="C-100")
    fridge = make_location(db, business, capacity=4)

    response = take_in(
        client,
        auth_headers,
        test_data["staff"],
        case,
        received_from_type="home",
        received_from="12 Main Road",
        collected_by_name="Driver Dan",
        condition_notes="Peaceful",
        belongings="Wedding ring",
        location_id=str(fridge.id),
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["remains"]["tag_number"] == "T-C-100"
    assert data["remains"]["status"] == "in_custody"
    assert data["remains"]["current_location_id"] == str(fridge.id)
    assert data["remains"]["received_by"] == str(test_data["staff"].id)
    assert [e["event_type"] for e in data["events"]] == ["received"]
    assert data["events"][0]["to_location_id"] == str(fridge.id)

    entry = audits(db, "remains.received")[0]
    assert entry.details["case_number"] == "C-100"
    assert entry.details["tag_number"] == "T-C-100"

    # The audit trail never copies who, where from or what was found.
    flat = str(entry.details)
    for secret in ("12 Main Road", "Driver Dan", "Wedding ring", "Peaceful"):
        assert secret not in flat


def test_custom_tag_is_used(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = take_in(
        client, auth_headers, test_data["manager"], case,
        tag_number="  RFID-0042 ",
    )

    assert response.json()["remains"]["tag_number"] == "RFID-0042"


def test_tag_must_be_unique_within_the_business(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    first = make_case(db, business)
    second = make_case(db, business)

    assert take_in(
        client, auth_headers, manager, first, tag_number="TAG-1"
    ).status_code == 201

    response = take_in(
        client, auth_headers, manager, second, tag_number="TAG-1"
    )

    assert response.status_code == 409
    assert "tag number is already in use" in response.json()["detail"]

    # Nothing half-created was left behind.
    assert (
        db.query(RemainsRecord)
        .filter(RemainsRecord.case_id == second.id)
        .count()
        == 0
    )


def test_a_case_can_only_be_taken_in_once(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    assert take_in(client, auth_headers, manager, case).status_code == 201

    again = take_in(client, auth_headers, manager, case)

    assert again.status_code == 409
    assert "already has a custody record" in again.json()["detail"]


def test_cold_location_counts_as_cooled_on_arrival(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    fridge = make_location(db, business, kind="fridge")
    case = make_case(db, business)

    data = take_in(
        client, auth_headers, test_data["manager"], case,
        location_id=str(fridge.id),
    ).json()

    assert data["remains"]["cooled_at"] is not None
    assert data["cooling"] == {
        "cooled": True,
        "cooling_due_at": None,
        "cooling_overdue": False,
    }


def test_warm_arrival_gets_a_three_hour_cooling_deadline(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    prep = make_location(db, business, "Prep", kind="preparation_room")
    case = make_case(db, business)

    arrived = datetime.now(timezone.utc) - timedelta(minutes=30)

    data = take_in(
        client, auth_headers, test_data["manager"], case,
        received_at=arrived.isoformat(),
        location_id=str(prep.id),
    ).json()

    assert data["remains"]["cooled_at"] is None
    assert data["cooling"]["cooled"] is False
    assert data["cooling"]["cooling_overdue"] is False

    due = datetime.fromisoformat(data["cooling"]["cooling_due_at"])
    assert abs((due - (arrived + timedelta(hours=3))).total_seconds()) < 1


def test_intake_rejects_a_future_arrival_time(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = take_in(
        client, auth_headers, test_data["manager"], case,
        received_at=iso(+120),
    )

    assert response.status_code == 422
    assert "future" in response.json()["detail"]


def test_vehicle_must_be_a_vehicle_of_this_business(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    equipment = make_vehicle(db, business, "equipment")
    foreign = make_vehicle(db, test_data["business_b"])
    good = make_vehicle(db, business)

    for resource in (equipment, foreign):
        response = take_in(
            client, auth_headers, manager, make_case(db, business),
            vehicle_resource_id=str(resource.id),
        )
        assert response.status_code == 422, response.text
        assert "Vehicle not found" in response.json()["detail"]

    ok = take_in(
        client, auth_headers, manager, make_case(db, business),
        vehicle_resource_id=str(good.id),
    )
    assert ok.status_code == 201


def test_intake_refuses_inactive_unknown_and_full_locations(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    inactive = make_location(db, business, "Off", active=False)
    tiny = make_location(db, business, "Tiny", capacity=1)

    assert take_in(
        client, auth_headers, manager, make_case(db, business),
        location_id=str(tiny.id),
    ).status_code == 201

    full = take_in(
        client, auth_headers, manager, make_case(db, business),
        location_id=str(tiny.id),
    )
    assert full.status_code == 409
    assert "Tiny is full (1 of 1)" in full.json()["detail"]

    off = take_in(
        client, auth_headers, manager, make_case(db, business),
        location_id=str(inactive.id),
    )
    assert off.status_code == 409
    assert "inactive" in off.json()["detail"]

    missing = take_in(
        client, auth_headers, manager, make_case(db, business),
        location_id=str(uuid.uuid4()),
    )
    assert missing.status_code == 422

    foreign = make_location(db, test_data["business_b"], "Foreign")
    other = take_in(
        client, auth_headers, manager, make_case(db, business),
        location_id=str(foreign.id),
    )
    assert other.status_code == 422


def test_a_refused_intake_leaves_no_record(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    tiny = make_location(db, business, capacity=1)
    manager = test_data["manager"]

    take_in(
        client, auth_headers, manager, make_case(db, business),
        location_id=str(tiny.id),
    )

    refused = make_case(db, business)
    take_in(
        client, auth_headers, manager, refused, location_id=str(tiny.id)
    )

    assert (
        db.query(RemainsRecord)
        .filter(RemainsRecord.case_id == refused.id)
        .count()
        == 0
    )


def test_archived_case_cannot_take_remains(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"], archived=True)

    response = take_in(client, auth_headers, test_data["manager"], case)

    assert response.status_code == 409
    assert "Archived" in response.json()["detail"]


def test_other_business_case_is_not_found(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_b"])

    for call in (
        lambda: take_in(client, auth_headers, test_data["manager"], case),
        lambda: client.get(
            f"/cases/{case.id}/remains",
            headers=auth_headers(test_data["manager"]),
        ),
    ):
        assert call().status_code == 404


def test_read_before_intake_is_not_found(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = client.get(
        f"/cases/{case.id}/remains",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 404
    assert "taken into care" in response.json()["detail"]


def test_intake_needs_the_remains_permission(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    deny(db, test_data["staff"], "remains.manage")

    assert take_in(
        client, auth_headers, test_data["staff"], case
    ).status_code == 403


def test_unknown_fields_are_rejected_on_intake(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = take_in(
        client, auth_headers, test_data["manager"], case,
        status="released",
    )

    assert response.status_code == 422


# ============================================================
# UPDATING THE RECORD
# ============================================================

def test_update_remains_audits_with_redaction(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case, belongings="Watch")

    response = client.patch(
        f"/cases/{case.id}/remains",
        json={"belongings": "Watch and glasses"},
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    assert response.json()["remains"]["belongings"] == "Watch and glasses"

    entry = audits(db, "remains.updated")[0]
    change = entry.details["changes"]["belongings"]
    assert change["old"] == "[redacted]"
    assert change["new"] == "[redacted]"
    assert "glasses" not in str(entry.details)


def test_update_cannot_null_the_arrival_source(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    response = client.patch(
        f"/cases/{case.id}/remains",
        json={"received_from_type": None},
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_update_cannot_change_tag_or_status(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    for field in ("tag_number", "status", "current_location_id"):
        response = client.patch(
            f"/cases/{case.id}/remains",
            json={field: "x"},
            headers=auth_headers(manager),
        )

        assert response.status_code == 422, field


# ============================================================
# CUSTODY EVENTS
# ============================================================

def test_moving_into_a_cold_place_cools_the_remains(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    prep = make_location(db, business, "Prep", kind="preparation_room")
    fridge = make_location(db, business, "Fridge", kind="fridge")
    case = make_case(db, business)

    take_in(
        client, auth_headers, manager, case, location_id=str(prep.id)
    )

    moved = event(
        client, auth_headers, manager, case,
        event_type="moved", to_location_id=str(fridge.id),
    )

    assert moved.status_code == 201, moved.text
    data = moved.json()

    assert data["remains"]["current_location_id"] == str(fridge.id)
    assert data["remains"]["cooled_at"] is not None
    assert data["cooling"]["cooled"] is True
    assert [e["event_type"] for e in data["events"]] == [
        "received",
        "moved",
    ]
    assert data["events"][1]["from_location_id"] == str(prep.id)
    assert data["events"][1]["to_location_id"] == str(fridge.id)
    assert data["events"][1]["handed_over_by_name"] == "Mortuary Staff"
    assert data["events"][1]["accepted_by_name"] == "Receiving Staff"

    entry = audits(db, "remains.moved")[0]
    assert entry.details["from_location_id"] == str(prep.id)
    assert entry.details["to_location_id"] == str(fridge.id)
    assert entry.details["handed_over_by_name"] == "Mortuary Staff"
    assert entry.details["accepted_by_name"] == "Receiving Staff"


def test_move_requires_both_handover_names(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    prep = make_location(db, business, "Prep", kind="preparation_room")
    fridge = make_location(db, business, "Fridge", kind="fridge")
    case = make_case(db, business)

    take_in(
        client, auth_headers, manager, case, location_id=str(prep.id)
    )

    response = client.post(
        f"/cases/{case.id}/remains/events",
        json={"event_type": "moved", "to_location_id": str(fridge.id)},
        headers=auth_headers(manager),
    )

    assert response.status_code == 422
    assert "handing over" in response.json()["detail"]

    current = client.get(
        f"/cases/{case.id}/remains", headers=auth_headers(manager)
    ).json()
    assert current["remains"]["current_location_id"] == str(prep.id)
    assert [entry["event_type"] for entry in current["events"]] == ["received"]


def test_cooled_time_is_not_reset_by_later_moves(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    one = make_location(db, business, "One", kind="fridge")
    two = make_location(db, business, "Two", kind="cold_room")
    case = make_case(db, business)

    first = take_in(
        client, auth_headers, manager, case, location_id=str(one.id)
    ).json()["remains"]["cooled_at"]

    after = event(
        client, auth_headers, manager, case,
        event_type="moved", to_location_id=str(two.id),
    ).json()["remains"]["cooled_at"]

    assert after == first


def test_move_rules(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    manager = test_data["manager"]
    fridge = make_location(db, business, "Fridge")
    case = make_case(db, business)

    take_in(
        client, auth_headers, manager, case, location_id=str(fridge.id)
    )

    needs_target = event(
        client, auth_headers, manager, case, event_type="moved"
    )
    assert needs_target.status_code == 422

    same = event(
        client, auth_headers, manager, case,
        event_type="moved", to_location_id=str(fridge.id),
    )
    assert same.status_code == 409
    assert "already there" in same.json()["detail"]


def test_a_full_place_refuses_a_move_until_space_is_made(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    tiny = make_location(db, business, "Tiny", capacity=1)
    other = make_location(db, business, "Other")

    first = make_case(db, business)
    second = make_case(db, business)

    take_in(client, auth_headers, manager, first, location_id=str(tiny.id))
    take_in(client, auth_headers, manager, second, location_id=str(other.id))

    blocked = event(
        client, auth_headers, manager, second,
        event_type="moved", to_location_id=str(tiny.id),
    )
    assert blocked.status_code == 409
    assert "full" in blocked.json()["detail"]

    # The refused move changed nothing, and wrote no log entry.
    still = client.get(
        f"/cases/{second.id}/remains", headers=auth_headers(manager)
    ).json()
    assert still["remains"]["current_location_id"] == str(other.id)
    assert [e["event_type"] for e in still["events"]] == ["received"]

    event(
        client, auth_headers, manager, first,
        event_type="moved", to_location_id=str(other.id),
    )

    ok = event(
        client, auth_headers, manager, second,
        event_type="moved", to_location_id=str(tiny.id),
    )
    assert ok.status_code == 201


def test_preparation_is_logged(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    missing = event(
        client, auth_headers, manager, case, event_type="prepared"
    )
    assert missing.status_code == 422

    ok = event(
        client, auth_headers, manager, case,
        event_type="prepared", procedure="embalmed", notes="Done well",
    )
    assert ok.status_code == 201
    assert ok.json()["events"][-1]["procedure"] == "embalmed"

    entry = audits(db, "remains.prepared")[0]
    assert entry.details["procedure"] == "embalmed"

    bad = event(
        client, auth_headers, manager, case,
        event_type="prepared", procedure="polished",
    )
    assert bad.status_code == 422


def test_identification_is_recorded_once(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    nameless = event(
        client, auth_headers, manager, case, event_type="identified"
    )
    assert nameless.status_code == 422

    ok = event(
        client, auth_headers, manager, case,
        event_type="identified",
        identified_by_name="Thandi Nkosi",
        identified_relationship="Daughter",
    )
    assert ok.status_code == 201

    remains = ok.json()["remains"]
    assert remains["identified_by_name"] == "Thandi Nkosi"
    assert remains["identified_at"] is not None

    again = event(
        client, auth_headers, manager, case,
        event_type="identified", identified_by_name="Someone Else",
    )
    assert again.status_code == 409
    assert "already identified" in again.json()["detail"]

    entry = audits(db, "remains.identified")[0]
    assert "Thandi" not in str(entry.details)


def test_temperature_readings(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    assert event(
        client, auth_headers, manager, case, event_type="temperature"
    ).status_code == 422

    assert event(
        client, auth_headers, manager, case,
        event_type="temperature", temperature_c=500,
    ).status_code == 422

    ok = event(
        client, auth_headers, manager, case,
        event_type="temperature", temperature_c="4.5",
    )

    assert ok.status_code == 201
    assert ok.json()["events"][-1]["temperature_c"] == "4.5"


def test_notes_need_text(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    assert event(
        client, auth_headers, manager, case, event_type="note"
    ).status_code == 422

    ok = event(
        client, auth_headers, manager, case,
        event_type="note", notes="Family visited",
    )
    assert ok.status_code == 201


def test_event_times_are_checked(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(
        client, auth_headers, manager, case, received_at=iso(-60)
    )

    early = event(
        client, auth_headers, manager, case,
        event_type="note", notes="x", occurred_at=iso(-180),
    )
    assert early.status_code == 422
    assert "before the remains arrived" in early.json()["detail"]

    future = event(
        client, auth_headers, manager, case,
        event_type="note", notes="x", occurred_at=iso(+240),
    )
    assert future.status_code == 422


def test_log_is_returned_in_time_order(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case, received_at=iso(-120))

    event(
        client, auth_headers, manager, case,
        event_type="note", notes="later", occurred_at=iso(-10),
    )
    event(
        client, auth_headers, manager, case,
        event_type="note", notes="earlier", occurred_at=iso(-90),
    )

    notes = [
        e["notes"]
        for e in client.get(
            f"/cases/{case.id}/remains", headers=auth_headers(manager)
        ).json()["events"]
    ]

    assert notes == [None, "earlier", "later"]


def test_staff_can_record_events(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    take_in(client, auth_headers, test_data["staff"], case)

    assert event(
        client, auth_headers, test_data["staff"], case,
        event_type="note", notes="Hello",
    ).status_code == 201


def test_events_need_the_remains_permission(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    take_in(client, auth_headers, test_data["manager"], case)
    deny(db, test_data["staff"], "remains.manage")

    assert event(
        client, auth_headers, test_data["staff"], case,
        event_type="note", notes="Hello",
    ).status_code == 403


# ============================================================
# THE LOG CANNOT BE REWRITTEN
# ============================================================

def test_database_refuses_to_change_a_custody_event(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    take_in(client, auth_headers, test_data["manager"], case)

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE custody_events SET notes = 'edited'"))

    db.rollback()

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM custody_events"))

    db.rollback()

    assert db.query(CustodyEvent).count() == 1


def test_a_case_with_remains_cannot_be_deleted(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    take_in(client, auth_headers, test_data["manager"], case)

    with pytest.raises(IntegrityError):
        db.execute(
            text("DELETE FROM funeral_cases WHERE id = :id"),
            {"id": case.id},
        )

    db.rollback()


# ============================================================
# RELEASE
# ============================================================

def test_release_with_everything_in_place(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    fridge = make_location(db, business, capacity=2)

    case = ready_remains(
        client, db, auth_headers, test_data, location_id=str(fridge.id)
    )

    response = release(
        client, auth_headers, test_data["manager"], case,
        released_to_name="Thandi Nkosi",
        released_to_id_number="8001015009087",
        released_to_relationship="Daughter",
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["remains"]["status"] == "released"
    assert data["remains"]["current_location_id"] is None
    assert data["remains"]["released_to_name"] == "Thandi Nkosi"
    assert data["remains"]["released_by"] == str(test_data["manager"].id)
    assert data["remains"]["release_override_reason"] is None
    assert data["release_blockers"] == []
    assert data["events"][-1]["event_type"] == "released"
    assert data["events"][-1]["from_location_id"] == str(fridge.id)

    entry = audits(db, "remains.released")[0]
    assert entry.details["override_used"] is False
    assert "Thandi" not in str(entry.details)
    assert "8001015009087" not in str(entry.details)

    # The tray is free again.
    listed = client.get(
        "/mortuary/locations", headers=auth_headers(test_data["manager"])
    ).json()
    assert listed[0]["occupied"] == 0


def test_release_tag_check_ignores_case_and_spaces(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)

    response = release(
        client, auth_headers, test_data["manager"], case,
        confirm_tag_number=f"  t-{case.case_number.lower()} ",
    )

    assert response.status_code == 200, response.text


def test_wrong_tag_stops_the_release_and_is_recorded(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)

    response = release(
        client, auth_headers, test_data["manager"], case,
        confirm_tag_number="T-SOMEONE-ELSE",
    )

    assert response.status_code == 422
    assert "does not match" in response.json()["detail"]

    remains = db.query(RemainsRecord).filter_by(case_id=case.id).one()
    db.refresh(remains)
    assert remains.status == "in_custody"

    entry = audits(db, "remains.release_refused")[0]
    assert entry.details["reason"] == "tag_mismatch"


def test_wrong_tag_cannot_be_overridden(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)

    response = release(
        client, auth_headers, test_data["main_admin"], case,
        confirm_tag_number="T-WRONG",
        override_reason="Trust me",
    )

    assert response.status_code == 422


def test_release_needs_a_tag_and_a_recipient(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)

    for body in (
        {"released_to_name": "A"},
        {"confirm_tag_number": "x"},
        {"confirm_tag_number": "  ", "released_to_name": "A"},
        {"confirm_tag_number": "x", "released_to_name": "  "},
    ):
        response = client.post(
            f"/cases/{case.id}/remains/release",
            json=body,
            headers=auth_headers(test_data["manager"]),
        )

        assert response.status_code == 422, body


def test_release_lists_every_missing_requirement(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    response = release(client, auth_headers, manager, case)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "not been formally identified" in detail
    assert "No death record" in detail

    entry = audits(db, "remains.release_refused")[0]
    assert entry.details["reason"] == "requirements"
    assert len(entry.details["blockers"]) == 2


def test_release_needs_the_burial_order(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)
    identify(client, auth_headers, manager, case)

    client.post(
        f"/cases/{case.id}/death-record",
        json={"disposal_method": "burial"},
        headers=auth_headers(manager),
    )
    client.post(
        f"/cases/{case.id}/paperwork/standard",
        headers=auth_headers(manager),
    )

    response = release(client, auth_headers, manager, case)

    assert response.status_code == 409
    assert "burial order has not been obtained" in response.json()["detail"]


def test_cremation_needs_the_cremation_permit(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)
    identify(client, auth_headers, manager, case)
    prepare_paperwork(
        client, auth_headers, manager, case, disposal="cremation"
    )

    assert release(client, auth_headers, manager, case).status_code == 200


def test_cremation_without_the_permit_is_blocked(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)
    identify(client, auth_headers, manager, case)

    client.post(
        f"/cases/{case.id}/death-record",
        json={"disposal_method": "cremation"},
        headers=auth_headers(manager),
    )
    client.post(
        f"/cases/{case.id}/paperwork/standard",
        headers=auth_headers(manager),
    )

    response = release(client, auth_headers, manager, case)

    assert response.status_code == 409
    assert "cremation permit" in response.json()["detail"]


def test_unnatural_death_needs_forensic_release(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)
    manager = test_data["manager"]

    client.patch(
        f"/cases/{case.id}/death-record",
        json={"manner_of_death": "unnatural", "forensic_status": "referred"},
        headers=auth_headers(manager),
    )

    blocked = release(client, auth_headers, manager, case)
    assert blocked.status_code == 409
    assert "Forensic pathology has not released" in blocked.json()["detail"]

    client.patch(
        f"/cases/{case.id}/death-record",
        json={"forensic_status": "released"},
        headers=auth_headers(manager),
    )

    # The extra police and post-mortem papers do not stop the release:
    # only the one for how the person is laid to rest does.
    assert release(client, auth_headers, manager, case).status_code == 200


def test_manager_can_override_with_a_reason(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)

    response = release(
        client, auth_headers, manager, case,
        override_reason="Family collecting urgently, papers to follow",
    )

    assert response.status_code == 200, response.text
    remains = response.json()["remains"]
    assert remains["status"] == "released"
    assert "papers to follow" in remains["release_override_reason"]
    assert "Released with override" in response.json()["events"][-1]["notes"]

    entry = audits(db, "remains.released")[0]
    assert entry.details["override_used"] is True
    assert len(entry.details["blockers_overridden"]) == 2


def test_override_reason_is_dropped_when_nothing_was_overridden(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)

    response = release(
        client, auth_headers, test_data["manager"], case,
        override_reason="Not needed",
    )

    assert response.status_code == 200
    assert response.json()["remains"]["release_override_reason"] is None
    assert audits(db, "remains.released")[0].details["override_used"] is False


def test_override_needs_its_own_permission(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    take_in(client, auth_headers, manager, case)
    deny(db, manager, "remains.release_override")

    response = release(
        client, auth_headers, manager, case, override_reason="Urgent"
    )

    assert response.status_code == 403
    assert "remains.release_override" in response.json()["detail"]

    remains = db.query(RemainsRecord).filter_by(case_id=case.id).one()
    db.refresh(remains)
    assert remains.status == "in_custody"


def test_staff_cannot_release_by_default(
    client, db, test_data, auth_headers
):
    case = ready_remains(client, db, auth_headers, test_data)

    response = release(client, auth_headers, test_data["staff"], case)

    assert response.status_code == 403
    assert "remains.release" in response.json()["detail"]


def test_released_remains_are_frozen(client, db, test_data, auth_headers):
    case = ready_remains(client, db, auth_headers, test_data)
    manager = test_data["manager"]

    assert release(client, auth_headers, manager, case).status_code == 200

    again = release(client, auth_headers, manager, case)
    assert again.status_code == 409
    assert "released" in again.json()["detail"]

    assert event(
        client, auth_headers, manager, case,
        event_type="note", notes="Late note",
    ).status_code == 409

    assert client.patch(
        f"/cases/{case.id}/remains",
        json={"belongings": "x"},
        headers=auth_headers(manager),
    ).status_code == 409


def test_release_time_is_checked(client, db, test_data, auth_headers):
    case = ready_remains(client, db, auth_headers, test_data)
    manager = test_data["manager"]

    assert release(
        client, auth_headers, manager, case, released_at=iso(+240)
    ).status_code == 422

    assert release(
        client, auth_headers, manager, case, released_at=iso(-60 * 24 * 5)
    ).status_code == 422


def test_blockers_are_shown_before_release_is_attempted(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    detail = take_in(client, auth_headers, manager, case).json()

    assert len(detail["release_blockers"]) == 2

    prepare_paperwork(client, auth_headers, manager, case)
    identify(client, auth_headers, manager, case)

    detail = client.get(
        f"/cases/{case.id}/remains", headers=auth_headers(manager)
    ).json()

    assert detail["release_blockers"] == []


# ============================================================
# BOARD
# ============================================================

def test_board_lists_who_is_where(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    manager = test_data["manager"]
    fridge = make_location(db, business, "Fridge 1", capacity=4)

    here = make_case(db, business, number="C-1")
    gone = ready_remains(client, db, auth_headers, test_data)

    take_in(client, auth_headers, manager, here, location_id=str(fridge.id))
    release(client, auth_headers, manager, gone)

    board = client.get(
        "/mortuary/board", headers=auth_headers(test_data["staff"])
    ).json()

    assert board["in_custody"] == 1
    assert [e["case_number"] for e in board["entries"]] == ["C-1"]

    entry = board["entries"][0]
    assert entry["tag_number"] == "T-C-1"
    assert entry["location_name"] == "Fridge 1"
    assert entry["identified"] is False
    assert entry["cooled"] is True
    assert entry["deceased_full_name"] == "Private Name"

    assert [
        (loc["name"], loc["occupied"]) for loc in board["locations"]
    ] == [("Fridge 1", 1)]


def test_board_puts_overdue_cooling_first(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    prep = make_location(db, business, "Prep", kind="preparation_room")

    recent = make_case(db, business, number="C-RECENT")
    late = make_case(db, business, number="C-LATE")

    take_in(
        client, auth_headers, manager, recent,
        received_at=iso(-10), location_id=str(prep.id),
    )
    take_in(
        client, auth_headers, manager, late,
        received_at=iso(-30), location_id=str(prep.id),
    )

    # Four hours without being cooled.
    remains = db.query(RemainsRecord).filter_by(case_id=late.id).one()
    remains.received_at = datetime.now(timezone.utc) - timedelta(hours=4)
    db.commit()

    board = client.get(
        "/mortuary/board", headers=auth_headers(manager)
    ).json()

    assert board["cooling_overdue"] == 1
    assert [e["case_number"] for e in board["entries"]] == [
        "C-LATE",
        "C-RECENT",
    ]
    assert board["entries"][0]["cooling_overdue"] is True
    assert board["entries"][1]["cooling_overdue"] is False


def test_board_filters(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    manager = test_data["manager"]
    one = make_location(db, business, "One")
    two = make_location(db, business, "Two")

    first = make_case(db, business, number="C-ONE")
    second = make_case(db, business, number="C-TWO")

    take_in(client, auth_headers, manager, first, location_id=str(one.id))
    take_in(client, auth_headers, manager, second, location_id=str(two.id))

    board = client.get(
        "/mortuary/board",
        params={"location_id": str(two.id)},
        headers=auth_headers(manager),
    ).json()

    assert [e["case_number"] for e in board["entries"]] == ["C-TWO"]

    case = db.query(FuneralCase).filter_by(id=first.id).one()
    assert case.branch_id is None

    nothing = client.get(
        "/mortuary/board",
        params={"branch_id": str(uuid.uuid4())},
        headers=auth_headers(manager),
    ).json()

    assert nothing["entries"] == []


def test_board_never_shows_another_business(
    client, db, test_data, auth_headers
):
    other_case = make_case(db, test_data["business_b"])
    foreign = make_location(db, test_data["business_b"], "Foreign")

    take_in(
        client, auth_headers, test_data["other_business_manager"],
        other_case, location_id=str(foreign.id),
    )

    board = client.get(
        "/mortuary/board", headers=auth_headers(test_data["manager"])
    ).json()

    assert board["entries"] == []
    assert board["locations"] == []


def test_board_needs_permission(client, db, test_data, auth_headers):
    deny(db, test_data["staff"], "mortuary.view")

    assert client.get(
        "/mortuary/board", headers=auth_headers(test_data["staff"])
    ).status_code == 403


# ============================================================
# DEFAULT PERMISSIONS
# ============================================================

def test_role_defaults(client, db, test_data, auth_headers):
    from app.services.permission_seed import DEFAULT_ROLE_PERMISSIONS

    manager = DEFAULT_ROLE_PERMISSIONS["manager"]
    staff = DEFAULT_ROLE_PERMISSIONS["staff"]

    for key in (
        "mortuary.view",
        "mortuary.manage",
        "remains.view",
        "remains.manage",
        "remains.release",
        "remains.release_override",
    ):
        assert key in manager, key

    for key in ("mortuary.view", "remains.view", "remains.manage"):
        assert key in staff, key

    for key in (
        "mortuary.manage",
        "remains.release",
        "remains.release_override",
    ):
        assert key not in staff, key
