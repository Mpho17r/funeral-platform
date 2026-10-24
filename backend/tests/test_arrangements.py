import uuid

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.arrangement import CaseCollection, FuneralArrangement
from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.funeral_case import FuneralCase
from app.models.mortuary import MortuaryLocation
from app.models.permission import Permission
from app.models.resource import Resource, ResourceBooking
from app.models.user_permission import UserPermission
from app.services.arrangement import (
    ArrangementError,
    check_timeline,
    day_bounds,
    local_date,
)


# South Africa is UTC+2 all year, so these are the same wall-clock
# times the family would be told.
SAST = timezone(timedelta(hours=2))

DAY = date(2027, 3, 10)


def at(day=DAY, hour=9, minute=0):
    """An ISO time on a South African day."""

    return datetime(
        day.year, day.month, day.day, hour, minute, tzinfo=SAST
    ).isoformat()


def past(minutes=60):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def future(minutes=60):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


# ============================================================
# HELPERS
# ============================================================

def make_case(
    db,
    business,
    *,
    archived=False,
    died=None,
    branch=None,
    name="Private Name",
):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"AR-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name=name,
        date_of_death=died,
        status="open",
        is_archived=archived,
        branch_id=branch.id if branch else None,
    )
    db.add(case)
    db.commit()

    return case


def make_resource(db, business, resource_type="vehicle", *, active=True):
    resource = Resource(
        business_id=business.id,
        resource_type=resource_type,
        name=f"Res {uuid.uuid4().hex[:6]}",
        is_active=active,
    )
    db.add(resource)
    db.commit()

    return resource


def book(db, business, case, resource, *, day=DAY, driver=None, hour=8):
    booking = ResourceBooking(
        business_id=business.id,
        case_id=case.id,
        resource_id=resource.id,
        driver_user_id=driver.id if driver else None,
        starts_at=datetime(
            day.year, day.month, day.day, hour, 0, tzinfo=SAST
        ),
        ends_at=datetime(
            day.year, day.month, day.day, hour + 4, 0, tzinfo=SAST
        ),
        purpose="Cortege",
        status="booked",
    )
    db.add(booking)
    db.commit()

    return booking


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


def call(client, auth_headers, user, method, path, **kwargs):
    return client.request(
        method, path, headers=auth_headers(user), **kwargs
    )


def plan(client, auth_headers, user, case, **fields):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        f"/cases/{case.id}/arrangement",
        json=fields,
    )


def full_plan(**overrides):
    values = {
        "wake_at": at(DAY - timedelta(days=1), 18),
        "wake_venue": "Family home",
        "service_at": at(hour=8),
        "service_venue_type": "church",
        "service_venue": "St Paul's Church",
        "departure_at": at(hour=10),
        "departure_point": "St Paul's Church",
        "committal_at": at(hour=11),
        "committal_place": "Westpark Cemetery",
    }
    values.update(overrides)

    return values


def transition(client, auth_headers, user, case, status, **fields):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        f"/cases/{case.id}/arrangement/transition",
        json={"status": status, **fields},
    )


def schedule(client, auth_headers, user, case, **fields):
    body = {"scheduled_at": at(hour=7)}
    body.update(fields)

    return call(
        client,
        auth_headers,
        user,
        "POST",
        f"/cases/{case.id}/collections",
        json=body,
    )


def move(client, auth_headers, user, case, collection_id, status, **fields):
    return call(
        client,
        auth_headers,
        user,
        "POST",
        f"/cases/{case.id}/collections/{collection_id}/transition",
        json={"status": status, **fields},
    )


def run_sheet(client, auth_headers, user, day=DAY, **params):
    return call(
        client,
        auth_headers,
        user,
        "GET",
        "/run-sheet",
        params={"date": day.isoformat(), **params},
    )


def audits(db, action):
    return (
        db.query(AuditLog)
        .filter(AuditLog.action == action)
        .order_by(AuditLog.created_at)
        .all()
    )


def flags(item):
    return {flag["code"] for flag in item["flags"]}


def items_of(sheet, kind):
    return [i for i in sheet["items"] if i["kind"] == kind]


# ============================================================
# TIMELINE RULES (pure)
# ============================================================

def test_timeline_in_order_is_fine():
    values = {
        "wake_at": datetime(2027, 3, 9, 18, tzinfo=SAST),
        "service_at": datetime(2027, 3, 10, 8, tzinfo=SAST),
        "departure_at": datetime(2027, 3, 10, 10, tzinfo=SAST),
        "committal_at": datetime(2027, 3, 10, 11, tzinfo=SAST),
    }

    check_timeline(values, date_of_death=date(2027, 3, 1))


def test_timeline_skips_missing_steps():
    check_timeline(
        {
            "wake_at": datetime(2027, 3, 9, 18, tzinfo=SAST),
            "committal_at": datetime(2027, 3, 10, 11, tzinfo=SAST),
        },
        date_of_death=None,
    )


def test_timeline_out_of_order_is_refused_with_the_names():
    with pytest.raises(ArrangementError) as error:
        check_timeline(
            {
                "service_at": datetime(2027, 3, 10, 12, tzinfo=SAST),
                "committal_at": datetime(2027, 3, 10, 11, tzinfo=SAST),
            },
            date_of_death=None,
        )

    assert "burial or cremation cannot be before the service" in (
        error.value.detail
    )


def test_day_bounds_are_south_african_days():
    start, end = day_bounds(DAY)

    assert start == datetime(2027, 3, 9, 22, 0, tzinfo=timezone.utc)
    assert end - start == timedelta(days=1)
    assert local_date(start) == DAY


# ============================================================
# ARRANGEMENT: CREATE AND READ
# ============================================================

def test_create_with_defaults(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = plan(client, auth_headers, test_data["manager"], case)

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["status"] == "draft"
    assert data["grave_confirmed"] is False
    assert data["case_id"] == str(case.id)
    assert data["committal_at"] is None

    db.refresh(case)
    assert case.funeral_date is None


def test_create_full_plan_trims_and_blanks_to_null(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        **full_plan(
            officiant="  Pastor Dlamini  ",
            wake_address="   ",
            notes="",
            grave_number=" 14B ",
        ),
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["officiant"] == "Pastor Dlamini"
    assert data["wake_address"] is None
    assert data["notes"] is None
    assert data["grave_number"] == "14B"
    assert data["service_venue_type"] == "church"


def test_naive_datetime_is_refused(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        committal_at="2027-03-10T11:00:00",
    )

    assert response.status_code == 422
    assert "timezone" in response.text


def test_unknown_venue_type_is_refused(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        service_venue_type="stadium",
    )

    assert response.status_code == 422


def test_second_arrangement_for_a_case_is_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    assert plan(
        client, auth_headers, test_data["manager"], case
    ).status_code == 201

    response = plan(client, auth_headers, test_data["manager"], case)

    assert response.status_code == 409


def test_order_of_events_is_enforced(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        service_at=at(hour=12),
        departure_at=at(hour=10),
    )

    assert response.status_code == 422
    assert "departure cannot be before the service" in response.text


def test_nothing_can_be_before_the_date_of_death(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"], died=date(2027, 3, 12))

    response = plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        committal_at=at(hour=11),
    )

    assert response.status_code == 422
    assert "date of death" in response.text


def test_read_returns_the_arrangement(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    response = call(
        client,
        auth_headers,
        test_data["staff"],
        "GET",
        f"/cases/{case.id}/arrangement",
    )

    assert response.status_code == 200
    assert response.json()["committal_place"] == "Westpark Cemetery"


def test_read_before_any_plan_is_404(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "GET",
        f"/cases/{case.id}/arrangement",
    )

    assert response.status_code == 404


def test_unknown_case_is_404(client, test_data, auth_headers):
    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "GET",
        f"/cases/{uuid.uuid4()}/arrangement",
    )

    assert response.status_code == 404


def test_other_business_cannot_see_or_plan(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    other = test_data["other_business_manager"]

    assert call(
        client, auth_headers, other, "GET", f"/cases/{case.id}/arrangement"
    ).status_code == 404

    assert plan(client, auth_headers, other, case).status_code == 404

    assert transition(
        client, auth_headers, other, case, "confirmed"
    ).status_code == 404


def test_archived_case_is_frozen(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"], archived=True)

    response = plan(client, auth_headers, test_data["manager"], case)

    assert response.status_code == 409
    assert "Archived" in response.text


def test_unauthenticated_is_refused(client, db, test_data):
    case = make_case(db, test_data["business_a"])

    assert client.get(f"/cases/{case.id}/arrangement").status_code in (
        401,
        403,
    )


# ============================================================
# ARRANGEMENT: PERMISSIONS
# ============================================================

def test_staff_can_plan_by_default(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    assert plan(
        client, auth_headers, test_data["staff"], case
    ).status_code == 201


def test_denied_manage_cannot_create_or_change(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case)

    deny(db, test_data["staff"], "arrangements.manage")

    assert plan(
        client, auth_headers, test_data["staff"], case
    ).status_code == 403

    assert call(
        client,
        auth_headers,
        test_data["staff"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"notes": "x"},
    ).status_code == 403

    assert transition(
        client, auth_headers, test_data["staff"], case, "cancelled",
        reason="x",
    ).status_code == 403


def test_denied_view_cannot_read(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case)

    deny(db, test_data["staff"], "arrangements.view")

    assert call(
        client,
        auth_headers,
        test_data["staff"],
        "GET",
        f"/cases/{case.id}/arrangement",
    ).status_code == 403


# ============================================================
# ARRANGEMENT: UPDATE
# ============================================================

def test_update_changes_fields_and_audits_with_redaction(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={
            "service_address": "12 Private Road, Soweto",
            "grave_number": "22C",
            "grave_confirmed": True,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["grave_confirmed"] is True

    log = audits(db, "arrangement.updated")[-1]
    changes = log.details["changes"]

    assert changes["service_address"]["old"] == "[redacted]"
    assert changes["service_address"]["new"] == "[redacted]"
    assert "Private Road" not in str(log.details)
    assert changes["grave_confirmed"] == {"old": False, "new": True}
    assert changes["grave_number"]["new"] == "22C"
    assert log.details["case_number"] == case.case_number


def test_update_with_no_change_writes_no_audit(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    before = len(audits(db, "arrangement.updated"))

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"departure_point": "St Paul's Church"},
    )

    assert response.status_code == 200
    assert len(audits(db, "arrangement.updated")) == before


def test_update_cannot_null_grave_confirmed(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case)

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"grave_confirmed": None},
    )

    assert response.status_code == 422


def test_update_refuses_unknown_and_status_fields(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case)

    for body in ({"status": "completed"}, {"surprise": 1}):
        response = call(
            client,
            auth_headers,
            test_data["manager"],
            "PATCH",
            f"/cases/{case.id}/arrangement",
            json=body,
        )

        assert response.status_code == 422


def test_update_checks_order_against_stored_times(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"departure_at": at(hour=12)},
    )

    assert response.status_code == 422
    assert "burial or cremation cannot be before the departure" in (
        response.text
    )


def test_update_missing_arrangement_is_404(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"notes": "x"},
    )

    assert response.status_code == 404


def test_update_on_archived_case_is_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case)
    case.is_archived = True
    db.commit()

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"notes": "x"},
    )

    assert response.status_code == 409


# ============================================================
# ARRANGEMENT: CASE DATE SYNC
# ============================================================

def test_committal_sets_the_case_funeral_date_and_venue(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    db.refresh(case)
    assert case.funeral_date == DAY
    assert case.funeral_venue == "Westpark Cemetery"

    log = audits(db, "arrangement.created")[-1]
    assert log.details["case_changes"]["funeral_date"] == {
        "old": None,
        "new": DAY.isoformat(),
    }


def test_funeral_date_is_the_south_african_day(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    # 22:30 UTC on the 9th is 00:30 on the 10th in South Africa.
    plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        committal_at="2027-03-09T22:30:00+00:00",
        committal_place="Westpark Cemetery",
    )

    db.refresh(case)
    assert case.funeral_date == DAY


def test_moving_the_burial_moves_the_case_date(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    new_day = DAY + timedelta(days=2)

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={
            "service_at": at(new_day, 8),
            "departure_at": at(new_day, 10),
            "committal_at": at(new_day, 11),
        },
    )

    assert response.status_code == 200, response.text

    db.refresh(case)
    assert case.funeral_date == new_day


# ============================================================
# ARRANGEMENT: STATUS
# ============================================================

def test_confirm_needs_burial_time_and_place(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case)

    response = transition(
        client, auth_headers, test_data["manager"], case, "confirmed"
    )

    assert response.status_code == 422
    assert "burial or cremation time" in response.text
    assert "cemetery or crematorium" in response.text


def test_confirm_records_who_and_when(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    response = transition(
        client, auth_headers, test_data["manager"], case, "confirmed"
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "confirmed"
    assert data["confirmed_at"] is not None
    assert data["confirmed_by"] == str(test_data["manager"].id)

    log = audits(db, "arrangement.confirmed")[-1]
    assert log.details["from"] == "draft"
    assert log.details["to"] == "confirmed"


def test_confirmed_arrangement_cannot_lose_its_burial_time(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())
    transition(client, auth_headers, test_data["manager"], case, "confirmed")

    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"committal_at": None},
    )

    assert response.status_code == 422


def test_confirmed_can_go_back_to_draft(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())
    transition(client, auth_headers, test_data["manager"], case, "confirmed")

    response = transition(
        client, auth_headers, test_data["manager"], case, "draft"
    )

    assert response.status_code == 200
    assert response.json()["confirmed_at"] is None
    assert response.json()["confirmed_by"] is None


def test_same_status_and_skipped_steps_are_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    assert transition(
        client, auth_headers, test_data["manager"], case, "draft"
    ).status_code == 409

    assert transition(
        client, auth_headers, test_data["manager"], case, "completed"
    ).status_code == 409


def test_cannot_complete_before_it_has_happened(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())
    transition(client, auth_headers, test_data["manager"], case, "confirmed")

    response = transition(
        client, auth_headers, test_data["manager"], case, "completed"
    )

    assert response.status_code == 422
    assert "before the burial or cremation has happened" in response.text


def test_complete_after_the_burial_and_then_locked(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(
        client,
        auth_headers,
        test_data["manager"],
        case,
        committal_at=past(120),
        committal_place="Westpark Cemetery",
    )
    transition(client, auth_headers, test_data["manager"], case, "confirmed")

    response = transition(
        client, auth_headers, test_data["manager"], case, "completed"
    )

    assert response.status_code == 200, response.text
    assert response.json()["completed_at"] is not None

    edit = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"notes": "x"},
    )

    assert edit.status_code == 409
    assert "completed" in edit.text

    assert transition(
        client, auth_headers, test_data["manager"], case, "draft"
    ).status_code == 409


def test_cancel_needs_a_reason_and_clears_the_case_date(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())

    assert transition(
        client, auth_headers, test_data["manager"], case, "cancelled"
    ).status_code == 422

    response = transition(
        client,
        auth_headers,
        test_data["manager"],
        case,
        "cancelled",
        reason="Family moved the funeral to the Eastern Cape",
    )

    assert response.status_code == 200, response.text
    assert response.json()["cancel_reason"].startswith("Family moved")

    db.refresh(case)
    assert case.funeral_date is None
    assert case.funeral_venue is None

    log = audits(db, "arrangement.cancelled")[-1]
    assert log.details["reason_given"] is True
    assert "Eastern Cape" not in str(log.details)
    assert "Eastern Cape" not in (log.notes or "")


def test_cancelled_is_locked_until_reopened(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, test_data["manager"], case, **full_plan())
    transition(
        client, auth_headers, test_data["manager"], case, "cancelled",
        reason="Postponed",
    )

    edit = call(
        client,
        auth_headers,
        test_data["manager"],
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"notes": "x"},
    )

    assert edit.status_code == 409
    assert "Reopen" in edit.text

    reopened = transition(
        client, auth_headers, test_data["manager"], case, "draft"
    )

    assert reopened.status_code == 200
    assert reopened.json()["cancel_reason"] is None
    assert reopened.json()["cancelled_at"] is None

    db.refresh(case)
    assert case.funeral_date == DAY


# ============================================================
# COLLECTIONS
# ============================================================

def test_schedule_a_collection(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])

    response = schedule(
        client,
        auth_headers,
        test_data["manager"],
        case,
        pickup_type="hospital",
        pickup_address="  Chris Hani Baragwanath, ward 4  ",
        pickup_contact_name="Sister Mokoena",
        pickup_contact_phone="0825550000",
        notes="  ",
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["status"] == "scheduled"
    assert data["pickup_type"] == "hospital"
    assert data["pickup_address"] == "Chris Hani Baragwanath, ward 4"
    assert data["notes"] is None

    log = audits(db, "collection.created")[-1]
    assert log.entity_type == "case_collection"
    assert "Baragwanath" not in str(log.details)


def test_schedule_needs_a_time_with_offset(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    for body in ({}, {"scheduled_at": "2027-03-10T07:00:00"}):
        response = call(
            client,
            auth_headers,
            test_data["manager"],
            "POST",
            f"/cases/{case.id}/collections",
            json=body,
        )

        assert response.status_code == 422


def test_collection_cannot_be_before_the_date_of_death(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"], died=date(2027, 3, 12))

    response = schedule(client, auth_headers, test_data["manager"], case)

    assert response.status_code == 422
    assert "date of death" in response.text


def test_only_one_open_collection_per_case(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])

    assert schedule(
        client, auth_headers, test_data["manager"], case
    ).status_code == 201

    response = schedule(client, auth_headers, test_data["manager"], case)

    assert response.status_code == 409
    assert "open collection" in response.text


def test_a_new_collection_is_allowed_after_cancel_or_collect(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    first = schedule(client, auth_headers, manager, case).json()
    move(
        client, auth_headers, manager, case, first["id"], "cancelled",
        reason="Family took the body themselves",
    )

    second = schedule(client, auth_headers, manager, case)
    assert second.status_code == 201

    move(client, auth_headers, manager, case, second.json()["id"], "collected")

    assert schedule(client, auth_headers, manager, case).status_code == 201

    listing = call(
        client,
        auth_headers,
        manager,
        "GET",
        f"/cases/{case.id}/collections",
    ).json()

    assert len(listing) == 3


def test_vehicle_must_be_a_vehicle_of_this_business(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    venue = make_resource(db, test_data["business_a"], "venue")
    foreign = make_resource(db, test_data["business_b"])
    inactive = make_resource(db, test_data["business_a"], active=False)

    assert schedule(
        client, auth_headers, manager, case,
        vehicle_resource_id=str(venue.id),
    ).status_code == 422

    assert schedule(
        client, auth_headers, manager, case,
        vehicle_resource_id=str(foreign.id),
    ).status_code == 404

    assert schedule(
        client, auth_headers, manager, case,
        vehicle_resource_id=str(inactive.id),
    ).status_code == 422

    assert schedule(
        client, auth_headers, manager, case,
        vehicle_resource_id=str(uuid.uuid4()),
    ).status_code == 404


def test_driver_must_be_an_active_user_of_this_business(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    outsider = test_data["other_business_manager"]

    assert schedule(
        client, auth_headers, manager, case,
        driver_user_id=str(outsider.id),
    ).status_code == 404

    staff = test_data["staff"]
    staff.is_active = False
    db.commit()

    assert schedule(
        client, auth_headers, manager, case,
        driver_user_id=str(staff.id),
    ).status_code == 422


def test_dispatch_needs_vehicle_and_driver(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    vehicle = make_resource(db, test_data["business_a"])

    created = schedule(client, auth_headers, manager, case).json()

    no_vehicle = move(
        client, auth_headers, manager, case, created["id"], "en_route"
    )
    assert no_vehicle.status_code == 422
    assert "vehicle" in no_vehicle.text

    call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/collections/{created['id']}",
        json={"vehicle_resource_id": str(vehicle.id)},
    )

    no_driver = move(
        client, auth_headers, manager, case, created["id"], "en_route"
    )
    assert no_driver.status_code == 422
    assert "driver" in no_driver.text

    call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/collections/{created['id']}",
        json={"driver_user_id": str(test_data["staff"].id)},
    )

    sent = move(
        client, auth_headers, manager, case, created["id"], "en_route"
    )

    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "en_route"
    assert sent.json()["en_route_at"] is not None


def test_en_route_collection_keeps_its_vehicle_and_driver(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    vehicle = make_resource(db, test_data["business_a"])

    created = schedule(
        client, auth_headers, manager, case,
        vehicle_resource_id=str(vehicle.id),
        driver_user_id=str(test_data["staff"].id),
    ).json()
    move(client, auth_headers, manager, case, created["id"], "en_route")

    for field in ("vehicle_resource_id", "driver_user_id"):
        response = call(
            client,
            auth_headers,
            manager,
            "PATCH",
            f"/cases/{case.id}/collections/{created['id']}",
            json={field: None},
        )

        assert response.status_code == 422
        assert "on its way" in response.text


def test_en_route_can_return_to_scheduled(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]
    vehicle = make_resource(db, test_data["business_a"])

    created = schedule(
        client, auth_headers, manager, case,
        vehicle_resource_id=str(vehicle.id),
        driver_user_id=str(test_data["staff"].id),
    ).json()
    move(client, auth_headers, manager, case, created["id"], "en_route")

    response = move(
        client, auth_headers, manager, case, created["id"], "scheduled"
    )

    assert response.status_code == 200
    assert response.json()["en_route_at"] is None


def test_collected_defaults_to_now_and_is_final(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    created = schedule(client, auth_headers, manager, case).json()

    response = move(
        client, auth_headers, manager, case, created["id"], "collected"
    )

    assert response.status_code == 200, response.text
    assert response.json()["collected_at"] is not None

    for target in ("scheduled", "en_route", "cancelled", "collected"):
        again = move(
            client, auth_headers, manager, case, created["id"], target,
            reason="x",
        )

        assert again.status_code == 409

    edit = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/collections/{created['id']}",
        json={"notes": "x"},
    )
    assert edit.status_code == 409


def test_collected_time_can_be_recorded_in_the_past_not_the_future(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    created = schedule(client, auth_headers, manager, case).json()

    ahead = move(
        client, auth_headers, manager, case, created["id"], "collected",
        collected_at=future(120),
    )
    assert ahead.status_code == 422

    stamp = past(90)
    done = move(
        client, auth_headers, manager, case, created["id"], "collected",
        collected_at=stamp,
    )

    assert done.status_code == 200
    assert datetime.fromisoformat(done.json()["collected_at"]) == (
        datetime.fromisoformat(stamp)
    )


def test_cancel_collection_needs_a_reason_and_keeps_it_private(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    created = schedule(client, auth_headers, manager, case).json()

    assert move(
        client, auth_headers, manager, case, created["id"], "cancelled"
    ).status_code == 422

    response = move(
        client, auth_headers, manager, case, created["id"], "cancelled",
        reason="Family used another undertaker",
    )

    assert response.status_code == 200
    assert response.json()["cancel_reason"] == (
        "Family used another undertaker"
    )

    log = audits(db, "collection.cancelled")[-1]
    assert "another undertaker" not in str(log.details)


def test_update_collection_audits_with_redaction(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    created = schedule(
        client, auth_headers, manager, case,
        pickup_address="1 Secret Street",
    ).json()

    response = call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/collections/{created['id']}",
        json={
            "pickup_address": "2 Other Street",
            "pickup_contact_phone": "0711111111",
            "scheduled_at": at(hour=9),
        },
    )

    assert response.status_code == 200, response.text

    log = audits(db, "collection.updated")[-1]
    changes = log.details["changes"]

    assert changes["pickup_address"]["new"] == "[redacted]"
    assert changes["pickup_contact_phone"]["new"] == "[redacted]"
    assert "scheduled_at" in changes
    assert "Street" not in str(log.details)


def test_update_collection_cannot_null_the_time_or_type(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    created = schedule(client, auth_headers, manager, case).json()

    for body in ({"scheduled_at": None}, {"pickup_type": None}):
        response = call(
            client,
            auth_headers,
            manager,
            "PATCH",
            f"/cases/{case.id}/collections/{created['id']}",
            json=body,
        )

        assert response.status_code == 422


def test_collection_of_another_case_or_business_is_404(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    other_case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    created = schedule(client, auth_headers, manager, case).json()

    assert move(
        client, auth_headers, manager, other_case, created["id"],
        "collected",
    ).status_code == 404

    outsider = test_data["other_business_manager"]

    assert call(
        client,
        auth_headers,
        outsider,
        "GET",
        f"/cases/{case.id}/collections",
    ).status_code == 404

    assert move(
        client, auth_headers, outsider, case, created["id"], "collected"
    ).status_code == 404


def test_collection_on_archived_case_is_refused(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"], archived=True)

    assert schedule(
        client, auth_headers, test_data["manager"], case
    ).status_code == 409


def test_collections_list_is_newest_first(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_a"])
    manager = test_data["manager"]

    first = schedule(
        client, auth_headers, manager, case, scheduled_at=at(hour=6)
    ).json()
    move(client, auth_headers, manager, case, first["id"], "collected")
    second = schedule(
        client, auth_headers, manager, case, scheduled_at=at(hour=14)
    ).json()

    listing = call(
        client,
        auth_headers,
        manager,
        "GET",
        f"/cases/{case.id}/collections",
    ).json()

    assert [c["id"] for c in listing] == [second["id"], first["id"]]


def test_collection_permissions(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_a"])
    staff = test_data["staff"]

    assert schedule(
        client, auth_headers, staff, case
    ).status_code == 201

    deny(db, staff, "collections.manage")

    assert schedule(
        client, auth_headers, staff, case
    ).status_code == 403

    assert call(
        client, auth_headers, staff, "GET", f"/cases/{case.id}/collections"
    ).status_code == 200

    deny(db, staff, "collections.view")

    assert call(
        client, auth_headers, staff, "GET", f"/cases/{case.id}/collections"
    ).status_code == 403


def test_database_refuses_collected_without_a_time(
    db, test_data
):
    case = make_case(db, test_data["business_a"])

    db.add(
        CaseCollection(
            business_id=case.business_id,
            case_id=case.id,
            status="collected",
            scheduled_at=datetime.now(timezone.utc),
            pickup_type="home",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_allows_one_open_collection_per_case(db, test_data):
    case = make_case(db, test_data["business_a"])

    for _ in range(2):
        db.add(
            CaseCollection(
                business_id=case.business_id,
                case_id=case.id,
                status="scheduled",
                scheduled_at=datetime.now(timezone.utc),
                pickup_type="home",
            )
        )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_database_refuses_unknown_arrangement_status(db, test_data):
    case = make_case(db, test_data["business_a"])

    db.add(
        FuneralArrangement(
            business_id=case.business_id,
            case_id=case.id,
            status="postponed",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


# ============================================================
# RUN SHEET
# ============================================================

def test_empty_day(client, test_data, auth_headers):
    response = run_sheet(client, auth_headers, test_data["manager"])

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["date"] == DAY.isoformat()
    assert data["timezone"] == "Africa/Johannesburg"
    assert data["items"] == []
    assert data["summary"] == {
        "collections": 0,
        "funerals": 0,
        "items": 0,
        "flagged_items": 0,
        "overdue_collections": 0,
    }


def test_date_defaults_to_today_in_south_africa(
    client, test_data, auth_headers
):
    response = call(
        client, auth_headers, test_data["manager"], "GET", "/run-sheet"
    )

    assert response.status_code == 200
    assert response.json()["date"] == local_date(
        datetime.now(timezone.utc)
    ).isoformat()


def test_bad_date_is_refused(client, test_data, auth_headers):
    response = call(
        client,
        auth_headers,
        test_data["manager"],
        "GET",
        "/run-sheet",
        params={"date": "tomorrow"},
    )

    assert response.status_code == 422


def test_run_sheet_lists_the_funeral_in_time_order(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"], name="Mama Dlamini")
    plan(client, auth_headers, manager, case, **full_plan())
    schedule(
        client, auth_headers, manager, make_case(db, test_data["business_a"]),
        scheduled_at=at(hour=6, minute=30),
        pickup_type="home",
        pickup_address="7 Vilakazi Street",
        pickup_contact_name="Sipho",
        pickup_contact_phone="0825551234",
    )

    data = run_sheet(client, auth_headers, manager).json()

    kinds = [i["kind"] for i in data["items"]]

    # The wake was the evening before, so it is not on this day.
    assert kinds == ["collection", "service", "departure", "committal"]

    service = items_of(data, "service")[0]
    assert service["title"] == "Funeral service"
    assert service["location"] == "St Paul's Church"
    assert service["deceased_full_name"] == "Mama Dlamini"
    assert service["case_number"] == case.case_number

    collection = items_of(data, "collection")[0]
    assert collection["address"] == "7 Vilakazi Street"
    assert collection["contact_name"] == "Sipho"
    assert collection["contact_phone"] == "0825551234"

    assert data["summary"]["collections"] == 1
    assert data["summary"]["funerals"] == 1
    assert data["summary"]["items"] == 4


def test_wake_shows_on_its_own_day(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    plan(client, auth_headers, manager, case, **full_plan())

    data = run_sheet(
        client, auth_headers, manager, DAY - timedelta(days=1)
    ).json()

    assert [i["kind"] for i in data["items"]] == ["wake"]
    assert data["items"][0]["location"] == "Family home"
    assert data["summary"]["funerals"] == 0


def test_day_edges_follow_south_african_midnight(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    # 22:30 UTC on the 9th is 00:30 on the 10th in South Africa.
    plan(
        client,
        auth_headers,
        manager,
        case,
        committal_at="2027-03-09T22:30:00+00:00",
        committal_place="Westpark Cemetery",
    )

    on_tenth = run_sheet(client, auth_headers, manager, DAY).json()
    on_ninth = run_sheet(
        client, auth_headers, manager, DAY - timedelta(days=1)
    ).json()

    assert len(on_tenth["items"]) == 1
    assert on_ninth["items"] == []


def test_cancelled_arrangement_and_archived_case_are_left_off(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]

    cancelled = make_case(db, test_data["business_a"])
    plan(client, auth_headers, manager, cancelled, **full_plan())
    transition(
        client, auth_headers, manager, cancelled, "cancelled", reason="x"
    )

    archived = make_case(db, test_data["business_a"])
    plan(client, auth_headers, manager, archived, **full_plan())
    archived.is_archived = True
    db.commit()

    assert run_sheet(client, auth_headers, manager).json()["items"] == []


def test_other_business_is_not_on_the_sheet(
    client, db, test_data, auth_headers
):
    case = make_case(db, test_data["business_b"])
    plan(
        client,
        auth_headers,
        test_data["other_business_manager"],
        case,
        **full_plan(),
    )

    assert run_sheet(
        client, auth_headers, test_data["manager"]
    ).json()["items"] == []


def test_branch_filter(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    business = test_data["business_a"]

    branch = Branch(
        business_id=business.id, name="Soweto", code="SOW", is_main=False
    )
    db.add(branch)
    db.commit()

    here = make_case(db, business, branch=branch)
    elsewhere = make_case(db, business)

    plan(client, auth_headers, manager, here, **full_plan())
    plan(client, auth_headers, manager, elsewhere, **full_plan())

    everything = run_sheet(client, auth_headers, manager).json()
    filtered = run_sheet(
        client, auth_headers, manager, branch_id=str(branch.id)
    ).json()

    assert len({i["case_id"] for i in everything["items"]}) == 2
    assert {i["case_id"] for i in filtered["items"]} == {str(here.id)}
    assert filtered["branch_id"] == str(branch.id)


def test_run_sheet_permission(client, db, test_data, auth_headers):
    staff = test_data["staff"]

    assert run_sheet(client, auth_headers, staff).status_code == 200

    deny(db, staff, "run_sheet.view")

    assert run_sheet(client, auth_headers, staff).status_code == 403


# ---- flags: funerals -------------------------------------------------

def bury(client, auth_headers, user, case, **plan_fields):
    assert plan(
        client, auth_headers, user, case, **full_plan(**plan_fields)
    ).status_code == 201


def paperwork(client, auth_headers, user, case, *, disposal="burial",
              obtained=True):
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

    if not obtained:
        return

    items = client.get(
        f"/cases/{case.id}/paperwork", headers=auth_headers(user)
    ).json()["items"]

    key = {
        "burial": "burial_order",
        "cremation": "cremation_permit",
    }[disposal]
    # The family's signed authorisation is part of being ready to release.
    for wanted in (key, "release_authorisation"):
        item = next(i for i in items if i["item_type"] == wanted)

        response = client.patch(
            f"/cases/{case.id}/paperwork/{item['id']}",
            json={"status": "obtained"},
            headers=auth_headers(user),
        )
        assert response.status_code == 200, response.text


def take_in(client, auth_headers, user, case):
    response = client.post(
        f"/cases/{case.id}/remains",
        json={"received_from_type": "hospital"},
        headers=auth_headers(user),
    )
    assert response.status_code == 201, response.text


def test_draft_arrangement_is_flagged_on_the_departure_only(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)

    data = run_sheet(client, auth_headers, manager).json()

    assert "not_confirmed" in flags(items_of(data, "departure")[0])
    assert "not_confirmed" not in flags(items_of(data, "committal")[0])
    assert "not_confirmed" not in flags(items_of(data, "service")[0])


def test_confirmed_arrangement_is_not_flagged_as_draft(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)
    transition(client, auth_headers, manager, case, "confirmed")

    data = run_sheet(client, auth_headers, manager).json()

    assert "not_confirmed" not in flags(items_of(data, "departure")[0])


def test_anchor_is_the_burial_when_there_is_no_departure(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    plan(
        client,
        auth_headers,
        manager,
        case,
        committal_at=at(hour=11),
        committal_place="Westpark Cemetery",
    )

    data = run_sheet(client, auth_headers, manager).json()

    assert "not_confirmed" in flags(items_of(data, "committal")[0])


def test_grave_not_confirmed_is_flagged_on_a_burial_only(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)

    data = run_sheet(client, auth_headers, manager).json()
    assert "grave_not_confirmed" in flags(items_of(data, "committal")[0])

    call(
        client,
        auth_headers,
        manager,
        "PATCH",
        f"/cases/{case.id}/arrangement",
        json={"grave_confirmed": True},
    )

    data = run_sheet(client, auth_headers, manager).json()
    assert "grave_not_confirmed" not in flags(items_of(data, "committal")[0])


def test_cremation_has_no_grave_flag_and_its_own_title(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)
    paperwork(client, auth_headers, manager, case, disposal="cremation")

    data = run_sheet(client, auth_headers, manager).json()
    committal = items_of(data, "committal")[0]

    assert committal["title"] == "Cremation"
    assert "grave_not_confirmed" not in flags(committal)


def test_missing_burial_order_is_a_danger(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)
    paperwork(client, auth_headers, manager, case, obtained=False)

    data = run_sheet(client, auth_headers, manager).json()
    departure = items_of(data, "departure")[0]

    flag = next(
        f for f in departure["flags"] if f["code"] == "burial_order_missing"
    )

    assert flag["severity"] == "danger"
    assert "burial order" in flag["message"]


def test_missing_cremation_permit_is_a_danger(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)
    paperwork(
        client, auth_headers, manager, case,
        disposal="cremation", obtained=False,
    )

    data = run_sheet(client, auth_headers, manager).json()

    assert "cremation_permit_missing" in flags(
        items_of(data, "departure")[0]
    )


def test_obtained_paperwork_clears_the_flag(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)
    paperwork(client, auth_headers, manager, case)

    data = run_sheet(client, auth_headers, manager).json()
    departure_flags = flags(items_of(data, "departure")[0])

    assert "burial_order_missing" not in departure_flags
    assert "paperwork_not_started" not in departure_flags


def test_paperwork_not_started_is_a_warning(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)

    data = run_sheet(client, auth_headers, manager).json()
    departure = items_of(data, "departure")[0]

    flag = next(
        f for f in departure["flags"]
        if f["code"] == "paperwork_not_started"
    )

    assert flag["severity"] == "warning"


def test_remains_flags_follow_custody(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)
    bury(client, auth_headers, manager, case)

    # No record yet.
    data = run_sheet(client, auth_headers, manager).json()
    assert "no_remains_record" in flags(items_of(data, "departure")[0])

    # In care, in a fridge, not yet identified.
    fridge = MortuaryLocation(
        business_id=business.id, name="Fridge 1", kind="fridge", capacity=2
    )
    db.add(fridge)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/remains",
        json={
            "received_from_type": "hospital",
            "location_id": str(fridge.id),
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.text

    data = run_sheet(client, auth_headers, manager).json()
    departure = items_of(data, "departure")[0]

    assert "no_remains_record" not in flags(departure)
    assert {"remains_in_custody", "not_identified"} <= flags(departure)

    in_custody = next(
        f for f in departure["flags"] if f["code"] == "remains_in_custody"
    )
    assert "Fridge 1" in in_custody["message"]

    not_identified = next(
        f for f in departure["flags"] if f["code"] == "not_identified"
    )
    assert not_identified["severity"] == "danger"

    # Identified, still in custody.
    response = client.post(
        f"/cases/{case.id}/remains/events",
        json={
            "event_type": "identified",
            "identified_by_name": "Thandi Nkosi",
            "identified_relationship": "Daughter",
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.text

    data = run_sheet(client, auth_headers, manager).json()
    departure_flags = flags(items_of(data, "departure")[0])

    assert "remains_in_custody" in departure_flags
    assert "not_identified" not in departure_flags


def test_released_remains_clear_the_remains_flags(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)
    paperwork(client, auth_headers, manager, case)
    take_in(client, auth_headers, manager, case)

    client.post(
        f"/cases/{case.id}/remains/events",
        json={
            "event_type": "identified",
            "identified_by_name": "Thandi Nkosi",
            "identified_relationship": "Daughter",
        },
        headers=auth_headers(manager),
    )

    response = client.post(
        f"/cases/{case.id}/remains/release",
        json={
            "confirm_tag_number": f"T-{case.case_number}",
            "confirm_deceased_identifier": case.deceased_full_name,
            "released_to_name": "Family Member",
            "released_to_id_number": "8001015009087",
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 200, response.text

    data = run_sheet(client, auth_headers, manager).json()
    departure_flags = flags(items_of(data, "departure")[0])

    assert not (
        {"remains_in_custody", "not_identified", "no_remains_record"}
        & departure_flags
    )


def test_cortege_without_a_vehicle_is_a_danger(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    bury(client, auth_headers, manager, case)

    data = run_sheet(client, auth_headers, manager).json()
    departure = items_of(data, "departure")[0]

    flag = next(f for f in departure["flags"] if f["code"] == "no_vehicle")
    assert flag["severity"] == "danger"


def test_a_booked_vehicle_clears_the_cortege_flag_and_shows_the_driver(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)
    bury(client, auth_headers, manager, case)

    hearse = make_resource(db, business)
    hearse.name = "Hearse 1"
    db.commit()

    book(db, business, case, hearse, driver=test_data["staff"])

    data = run_sheet(client, auth_headers, manager).json()

    assert "no_vehicle" not in flags(items_of(data, "departure")[0])

    booking = items_of(data, "booking")[0]
    assert booking["vehicle"] == "Hearse 1"
    assert booking["driver"] == test_data["staff"].full_name
    assert booking["ends_at"] is not None
    assert booking["case_id"] == str(case.id)


def test_a_venue_booking_does_not_count_as_a_vehicle(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)
    bury(client, auth_headers, manager, case)

    book(db, business, case, make_resource(db, business, "venue"))

    data = run_sheet(client, auth_headers, manager).json()

    assert "no_vehicle" in flags(items_of(data, "departure")[0])
    assert items_of(data, "booking")[0]["vehicle"] is None


def test_cancelled_booking_does_not_count(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)
    bury(client, auth_headers, manager, case)

    booking = book(db, business, case, make_resource(db, business))
    booking.status = "cancelled"
    db.commit()

    data = run_sheet(client, auth_headers, manager).json()

    assert "no_vehicle" in flags(items_of(data, "departure")[0])
    assert items_of(data, "booking") == []


# ---- flags: collections ---------------------------------------------

def test_open_collection_without_vehicle_or_driver_is_flagged(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])
    schedule(client, auth_headers, manager, case)

    data = run_sheet(client, auth_headers, manager).json()

    assert {"no_vehicle", "no_driver"} <= flags(
        items_of(data, "collection")[0]
    )
    assert data["summary"]["flagged_items"] == 1


def test_assigned_collection_is_clean(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)
    vehicle = make_resource(db, business)
    vehicle.name = "Removal van"
    db.commit()

    schedule(
        client,
        auth_headers,
        manager,
        case,
        vehicle_resource_id=str(vehicle.id),
        driver_user_id=str(test_data["staff"].id),
    )

    data = run_sheet(client, auth_headers, manager).json()
    collection = items_of(data, "collection")[0]

    assert collection["flags"] == []
    assert collection["vehicle"] == "Removal van"
    assert collection["driver"] == test_data["staff"].full_name


def test_collection_with_a_vehicle_booking_has_no_vehicle_flag(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)

    schedule(client, auth_headers, manager, case)
    book(db, business, case, make_resource(db, business), hour=6)

    data = run_sheet(client, auth_headers, manager).json()

    assert "no_vehicle" not in flags(items_of(data, "collection")[0])


def test_finished_collection_is_not_flagged(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    created = schedule(client, auth_headers, manager, case).json()
    move(client, auth_headers, manager, case, created["id"], "collected")

    data = run_sheet(client, auth_headers, manager).json()
    collection = items_of(data, "collection")[0]

    assert collection["status"] == "collected"
    assert collection["flags"] == []


def test_cancelled_collection_is_left_off(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    created = schedule(client, auth_headers, manager, case).json()
    move(
        client, auth_headers, manager, case, created["id"], "cancelled",
        reason="Not needed",
    )

    assert run_sheet(client, auth_headers, manager).json()["items"] == []


def test_a_collection_that_is_late_is_a_danger_on_its_own_day(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]
    case = make_case(db, business)

    # One hour ago, still open.
    created = schedule(
        client, auth_headers, manager, case, scheduled_at=past(60)
    )
    assert created.status_code == 201, created.text

    today = local_date(datetime.now(timezone.utc))
    when = datetime.fromisoformat(created.json()["scheduled_at"])
    day = local_date(when)

    data = run_sheet(client, auth_headers, manager, day).json()
    item = items_of(data, "collection")[0]

    flag = next(f for f in item["flags"] if f["code"] == "collection_overdue")
    assert flag["severity"] == "danger"

    # It is on its own day's sheet, so it is not repeated as overdue.
    assert data["overdue_collections"] == []
    assert data["summary"]["overdue_collections"] == 0
    assert today >= day


def test_overdue_collections_from_earlier_days_show_on_any_sheet(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]

    stale = make_case(db, business, name="Stale Case")
    done = make_case(db, business)
    future_case = make_case(db, business)

    schedule(
        client, auth_headers, manager, stale,
        scheduled_at=at(date(2026, 10, 1), 8),
    )
    finished = schedule(
        client, auth_headers, manager, done,
        scheduled_at=at(date(2026, 10, 2), 8),
    ).json()
    move(client, auth_headers, manager, done, finished["id"], "collected")
    schedule(
        client, auth_headers, manager, future_case,
        scheduled_at=at(DAY, 8),
    )

    data = run_sheet(client, auth_headers, manager).json()

    assert data["summary"]["overdue_collections"] == 1
    assert len(data["overdue_collections"]) == 1

    overdue = data["overdue_collections"][0]
    assert overdue["deceased_full_name"] == "Stale Case"
    assert "collection_overdue" in flags(overdue)

    # The overdue list is not mixed into the day's own items.
    assert all(
        i["case_id"] != overdue["case_id"] for i in data["items"]
    )


def test_overdue_collections_respect_the_branch_filter(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    business = test_data["business_a"]

    branch = Branch(business_id=business.id, name="Soweto", code="SOW", is_main=False)
    db.add(branch)
    db.commit()

    stale = make_case(db, business)
    schedule(
        client, auth_headers, manager, stale,
        scheduled_at=at(date(2026, 10, 1), 8),
    )

    filtered = run_sheet(
        client, auth_headers, manager, branch_id=str(branch.id)
    ).json()

    assert filtered["overdue_collections"] == []


def test_collection_and_funeral_of_same_case_both_appear(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    case = make_case(db, test_data["business_a"])

    bury(client, auth_headers, manager, case)
    schedule(client, auth_headers, manager, case, scheduled_at=at(hour=5))

    data = run_sheet(client, auth_headers, manager).json()

    assert [i["kind"] for i in data["items"]][0] == "collection"
    assert len({i["case_id"] for i in data["items"]}) == 1
