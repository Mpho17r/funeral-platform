import uuid

from datetime import date, datetime, timedelta, timezone

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.resource import Resource, ResourceBooking
from app.models.user import User
from app.models.user_permission import UserPermission
from app.security import hash_password


# ============================================================
# HELPERS
# ============================================================

def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    db.add(
        UserPermission(
            user_id=user_id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()


def make_case(
    db,
    business,
    *,
    status="open",
    funeral_date=None,
    archived=False,
):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"RES-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Resource Test",
        funeral_date=funeral_date,
        status=status,
        is_archived=archived,
    )
    db.add(case)
    db.commit()
    return case


def make_resource(
    db,
    business,
    *,
    resource_type="vehicle",
    name="Hearse 1",
    identifier=None,
    active=True,
):
    resource = Resource(
        business_id=business.id,
        resource_type=resource_type,
        name=name,
        identifier=identifier,
        is_active=active,
    )
    db.add(resource)
    db.commit()
    return resource


def make_driver(db, business, *, active=True):
    driver = User(
        business_id=business.id,
        full_name="Driver",
        email=f"driver-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("TestPassword123!"),
        role="staff",
        is_active=active,
    )
    db.add(driver)
    db.commit()
    return driver


BASE = datetime(2030, 1, 10, 8, 0, tzinfo=timezone.utc)


def window(start_hours, end_hours):
    return {
        "starts_at": (BASE + timedelta(hours=start_hours)).isoformat(),
        "ends_at": (BASE + timedelta(hours=end_hours)).isoformat(),
    }


def book(client, headers, case, resource, start, end, **extra):
    return client.post(
        f"/cases/{case.id}/resource-bookings",
        json={
            "resource_id": str(resource.id),
            **window(start, end),
            **extra,
        },
        headers=headers,
    )


def audit_actions(db, business):
    return {
        row.action
        for row in db.query(AuditLog)
        .filter(AuditLog.business_id == business.id)
        .all()
    }


# ============================================================
# CATALOGUE
# ============================================================

def test_manager_can_create_and_list_resources(
    client, test_data, auth_headers, db
):
    manager = test_data["manager"]
    headers = auth_headers(manager)

    response = client.post(
        "/resources",
        json={
            "resource_type": "vehicle",
            "name": "Hearse 1",
            "identifier": "CA 123-456",
            "capacity": 4,
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_active"] is True
    assert body["business_id"] == str(test_data["business_a"].id)

    listing = client.get("/resources", headers=headers)
    assert listing.status_code == 200
    assert [r["name"] for r in listing.json()] == ["Hearse 1"]

    assert "resource.created" in audit_actions(db, test_data["business_a"])


def test_staff_can_view_but_not_manage_resources(
    client, test_data, auth_headers, db
):
    resource = make_resource(db, test_data["business_a"])
    headers = auth_headers(test_data["staff"])

    assert client.get("/resources", headers=headers).status_code == 200
    assert (
        client.get(f"/resources/{resource.id}", headers=headers)
        .status_code
        == 200
    )

    create = client.post(
        "/resources",
        json={"resource_type": "venue", "name": "Hall"},
        headers=headers,
    )
    assert create.status_code == 403

    update = client.patch(
        f"/resources/{resource.id}",
        json={"name": "Renamed"},
        headers=headers,
    )
    assert update.status_code == 403

    deactivate = client.post(
        f"/resources/{resource.id}/deactivate",
        headers=headers,
    )
    assert deactivate.status_code == 403


def test_user_deny_override_blocks_resource_view(
    client, test_data, auth_headers, db
):
    manager = test_data["manager"]
    deny_permission(db, manager.id, "resources.view")

    response = client.get("/resources", headers=auth_headers(manager))

    assert response.status_code == 403


def test_resource_tenant_isolation(client, test_data, auth_headers, db):
    other = make_resource(
        db, test_data["business_b"], name="Other Hearse"
    )
    headers = auth_headers(test_data["manager"])

    assert client.get("/resources", headers=headers).json() == []
    assert (
        client.get(f"/resources/{other.id}", headers=headers)
        .status_code
        == 404
    )
    assert (
        client.patch(
            f"/resources/{other.id}",
            json={"name": "Hijack"},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/resources/{other.id}/deactivate", headers=headers
        ).status_code
        == 404
    )


def test_duplicate_identifier_rejected_per_type_and_business(
    client, test_data, auth_headers, db
):
    headers = auth_headers(test_data["manager"])
    payload = {
        "resource_type": "vehicle",
        "name": "Hearse",
        "identifier": "CA 111",
    }

    assert client.post(
        "/resources", json=payload, headers=headers
    ).status_code == 201

    duplicate = client.post("/resources", json=payload, headers=headers)
    assert duplicate.status_code == 409

    # Same identifier on a different type is fine.
    other_type = client.post(
        "/resources",
        json={**payload, "resource_type": "equipment"},
        headers=headers,
    )
    assert other_type.status_code == 201

    # Same identifier in another business is fine.
    make_resource(
        db,
        test_data["business_b"],
        identifier="CA 222",
    )
    cross = client.post(
        "/resources",
        json={**payload, "identifier": "CA 222"},
        headers=headers,
    )
    assert cross.status_code == 201


def test_update_resource_audits_changes_and_redacts_notes(
    client, test_data, auth_headers, db
):
    resource = make_resource(db, test_data["business_a"])
    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/resources/{resource.id}",
        json={"name": "Hearse 2", "notes": "Private note"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Hearse 2"

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "resource.updated")
        .one()
    )
    assert log.details["changes"]["name"]["new"] == "Hearse 2"
    assert log.details["changes"]["notes"]["new"] == "[redacted]"


def test_resource_type_cannot_be_changed(
    client, test_data, auth_headers, db
):
    resource = make_resource(db, test_data["business_a"])

    response = client.patch(
        f"/resources/{resource.id}",
        json={"resource_type": "venue"},
        headers=auth_headers(test_data["manager"]),
    )

    # Unknown field is ignored; the type must be unchanged.
    assert response.status_code == 200
    assert response.json()["resource_type"] == "vehicle"


def test_deactivate_and_reactivate_resource(
    client, test_data, auth_headers, db
):
    resource = make_resource(db, test_data["business_a"])
    headers = auth_headers(test_data["manager"])

    first = client.post(
        f"/resources/{resource.id}/deactivate", headers=headers
    )
    assert first.status_code == 200
    assert first.json()["is_active"] is False

    again = client.post(
        f"/resources/{resource.id}/deactivate", headers=headers
    )
    assert again.status_code == 409

    # Hidden from the default listing, visible when asked for.
    assert client.get("/resources", headers=headers).json() == []
    assert (
        len(
            client.get(
                "/resources?include_inactive=true", headers=headers
            ).json()
        )
        == 1
    )

    back = client.post(
        f"/resources/{resource.id}/reactivate", headers=headers
    )
    assert back.status_code == 200
    assert back.json()["is_active"] is True

    actions = audit_actions(db, test_data["business_a"])
    assert {"resource.deactivated", "resource.reactivated"} <= actions


def test_list_resources_filters_by_type(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    make_resource(db, business, resource_type="vehicle", name="V")
    make_resource(db, business, resource_type="venue", name="H")

    response = client.get(
        "/resources?resource_type=venue",
        headers=auth_headers(test_data["staff"]),
    )

    assert [r["name"] for r in response.json()] == ["H"]


def test_invalid_resource_type_rejected(
    client, test_data, auth_headers
):
    response = client.post(
        "/resources",
        json={"resource_type": "spaceship", "name": "X"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


# ============================================================
# BOOKINGS: BASICS
# ============================================================

def test_staff_can_book_resource_for_case(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)

    response = book(
        client,
        auth_headers(test_data["staff"]),
        case,
        resource,
        0,
        4,
        purpose="Funeral procession",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "booked"
    assert body["case_id"] == str(case.id)
    assert body["created_by"] == str(test_data["staff"].id)

    assert "resource_booking.created" in audit_actions(db, business)

    listing = client.get(
        f"/cases/{case.id}/resource-bookings",
        headers=auth_headers(test_data["staff"]),
    )
    assert len(listing.json()) == 1


def test_booking_requires_manage_permission(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    staff = test_data["staff"]
    deny_permission(db, staff.id, "resource_bookings.manage")

    response = book(
        client, auth_headers(staff), case, resource, 0, 4
    )

    assert response.status_code == 403
    assert db.query(ResourceBooking).count() == 0


def test_viewing_bookings_requires_view_permission(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    staff = test_data["staff"]
    deny_permission(db, staff.id, "resource_bookings.view")

    response = client.get(
        f"/cases/{case.id}/resource-bookings",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403


def test_booking_rejects_naive_datetimes(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)

    response = client.post(
        f"/cases/{case.id}/resource-bookings",
        json={
            "resource_id": str(resource.id),
            "starts_at": "2030-01-10T08:00:00",
            "ends_at": "2030-01-10T12:00:00",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_booking_rejects_end_before_start(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)

    response = book(
        client,
        auth_headers(test_data["manager"]),
        case,
        resource,
        4,
        4,
    )

    assert response.status_code == 422


# ============================================================
# BOOKINGS: TENANCY AND CASE RULES
# ============================================================

def test_cannot_book_other_business_resource_or_case(
    client, test_data, auth_headers, db
):
    own_case = make_case(db, test_data["business_a"])
    other_case = make_case(db, test_data["business_b"])
    own_resource = make_resource(db, test_data["business_a"])
    other_resource = make_resource(db, test_data["business_b"])
    headers = auth_headers(test_data["manager"])

    assert (
        book(client, headers, own_case, other_resource, 0, 2)
        .status_code
        == 404
    )
    assert (
        book(client, headers, other_case, own_resource, 0, 2)
        .status_code
        == 404
    )
    assert db.query(ResourceBooking).count() == 0


def test_cannot_use_other_business_user_as_driver(
    client, test_data, auth_headers, db
):
    case = make_case(db, test_data["business_a"])
    resource = make_resource(db, test_data["business_a"])
    outsider = test_data["other_business_manager"]

    response = book(
        client,
        auth_headers(test_data["manager"]),
        case,
        resource,
        0,
        2,
        driver_user_id=str(outsider.id),
    )

    assert response.status_code == 404


def test_cannot_book_archived_or_closed_case(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    archived = make_case(
        db, business, status="closed", archived=True
    )
    closed = make_case(db, business, status="closed")
    cancelled = make_case(db, business, status="cancelled")

    for case in (archived, closed, cancelled):
        assert (
            book(client, headers, case, resource, 0, 2).status_code
            == 409
        )


def test_cannot_book_inactive_resource(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business, active=False)

    response = book(
        client,
        auth_headers(test_data["manager"]),
        case,
        resource,
        0,
        2,
    )

    assert response.status_code == 409


# ============================================================
# CONFLICT DETECTION
# ============================================================

def test_overlapping_resource_booking_is_rejected(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case_a = make_case(db, business)
    case_b = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    assert (
        book(client, headers, case_a, resource, 0, 4).status_code
        == 201
    )

    for start, end in ((2, 6), (-2, 1), (1, 3), (-1, 5)):
        response = book(client, headers, case_b, resource, start, end)
        assert response.status_code == 409, (start, end)

    assert db.query(ResourceBooking).count() == 1


def test_back_to_back_bookings_are_allowed(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case_a = make_case(db, business)
    case_b = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    assert (
        book(client, headers, case_a, resource, 0, 4).status_code
        == 201
    )
    assert (
        book(client, headers, case_b, resource, 4, 8).status_code
        == 201
    )
    assert (
        book(client, headers, case_b, resource, -3, 0).status_code
        == 201
    )


def test_same_time_different_resources_is_allowed(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    first = make_resource(db, business, name="Hearse 1")
    second = make_resource(db, business, name="Hearse 2")
    headers = auth_headers(test_data["manager"])

    assert (
        book(client, headers, case, first, 0, 4).status_code == 201
    )
    assert (
        book(client, headers, case, second, 0, 4).status_code == 201
    )


def test_driver_double_booking_is_rejected(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    first = make_resource(db, business, name="Hearse 1")
    second = make_resource(db, business, name="Hearse 2")
    driver = make_driver(db, business)
    headers = auth_headers(test_data["manager"])

    assert (
        book(
            client, headers, case, first, 0, 4,
            driver_user_id=str(driver.id),
        ).status_code
        == 201
    )

    clash = book(
        client, headers, case, second, 2, 6,
        driver_user_id=str(driver.id),
    )
    assert clash.status_code == 409
    assert "Driver" in clash.json()["detail"]

    after = book(
        client, headers, case, second, 4, 8,
        driver_user_id=str(driver.id),
    )
    assert after.status_code == 201


def test_driver_only_allowed_on_vehicles(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    venue = make_resource(
        db, business, resource_type="venue", name="Hall"
    )
    driver = make_driver(db, business)

    response = book(
        client,
        auth_headers(test_data["manager"]),
        case,
        venue,
        0,
        4,
        driver_user_id=str(driver.id),
    )

    assert response.status_code == 422


def test_inactive_driver_is_rejected(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    driver = make_driver(db, business, active=False)

    response = book(
        client,
        auth_headers(test_data["manager"]),
        case,
        resource,
        0,
        4,
        driver_user_id=str(driver.id),
    )

    assert response.status_code == 409


def test_cancelled_booking_frees_the_slot(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    first = book(client, headers, case, resource, 0, 4).json()

    cancel = client.post(
        f"/resource-bookings/{first['id']}/cancel", headers=headers
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    assert (
        "resource_booking.cancelled"
        in audit_actions(db, business)
    )

    assert (
        book(client, headers, case, resource, 0, 4).status_code
        == 201
    )

    again = client.post(
        f"/resource-bookings/{first['id']}/cancel", headers=headers
    )
    assert again.status_code == 409


def test_completed_booking_cannot_be_changed(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    booking = book(client, headers, case, resource, 0, 4).json()

    done = client.post(
        f"/resource-bookings/{booking['id']}/complete",
        headers=headers,
    )
    assert done.status_code == 200
    assert done.json()["status"] == "completed"

    patch = client.patch(
        f"/resource-bookings/{booking['id']}",
        json={"purpose": "Too late"},
        headers=headers,
    )
    assert patch.status_code == 409


def test_update_booking_rechecks_conflicts(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    first = book(client, headers, case, resource, 0, 4).json()
    second = book(client, headers, case, resource, 4, 8).json()

    clash = client.patch(
        f"/resource-bookings/{second['id']}",
        json=window(3, 8),
        headers=headers,
    )
    assert clash.status_code == 409

    # Moving a booking within its own slot must not conflict with itself.
    shrink = client.patch(
        f"/resource-bookings/{first['id']}",
        json=window(0, 3),
        headers=headers,
    )
    assert shrink.status_code == 200, shrink.text

    ok = client.patch(
        f"/resource-bookings/{second['id']}",
        json=window(3, 8),
        headers=headers,
    )
    assert ok.status_code == 200, ok.text

    assert "resource_booking.updated" in audit_actions(db, business)


def test_update_booking_to_partial_window_validated(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    booking = book(client, headers, case, resource, 0, 4).json()

    # Only moving the end before the existing start is invalid.
    response = client.patch(
        f"/resource-bookings/{booking['id']}",
        json={"ends_at": (BASE - timedelta(hours=1)).isoformat()},
        headers=headers,
    )

    assert response.status_code == 422


def test_assigning_driver_via_update_checks_driver_conflicts(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    first = make_resource(db, business, name="Hearse 1")
    second = make_resource(db, business, name="Hearse 2")
    driver = make_driver(db, business)
    headers = auth_headers(test_data["manager"])

    book(
        client, headers, case, first, 0, 4,
        driver_user_id=str(driver.id),
    )
    other = book(client, headers, case, second, 2, 6).json()

    response = client.patch(
        f"/resource-bookings/{other['id']}",
        json={"driver_user_id": str(driver.id)},
        headers=headers,
    )

    assert response.status_code == 409


# ============================================================
# AVAILABILITY
# ============================================================

def test_availability_reports_conflicts(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["staff"])

    book(
        client,
        auth_headers(test_data["manager"]),
        case,
        resource,
        0,
        4,
    )

    busy = client.get(
        f"/resources/{resource.id}/availability",
        params=window(2, 6),
        headers=headers,
    )
    assert busy.status_code == 200
    assert busy.json()["is_available"] is False
    assert len(busy.json()["conflicts"]) == 1

    free = client.get(
        f"/resources/{resource.id}/availability",
        params=window(4, 6),
        headers=headers,
    )
    assert free.json()["is_available"] is True
    assert free.json()["conflicts"] == []


def test_availability_other_business_resource_not_found(
    client, test_data, auth_headers, db
):
    other = make_resource(db, test_data["business_b"])

    response = client.get(
        f"/resources/{other.id}/availability",
        params=window(0, 2),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404


# ============================================================
# BOOKING LIST FILTERS
# ============================================================

def test_list_bookings_filters_and_tenant_scope(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    first = make_resource(db, business, name="Hearse 1")
    second = make_resource(db, business, name="Hearse 2")
    headers = auth_headers(test_data["manager"])

    book(client, headers, case, first, 0, 2)
    book(client, headers, case, second, 10, 12)

    other_case = make_case(db, test_data["business_b"])
    other_resource = make_resource(db, test_data["business_b"])
    db.add(
        ResourceBooking(
            business_id=test_data["business_b"].id,
            case_id=other_case.id,
            resource_id=other_resource.id,
            starts_at=BASE,
            ends_at=BASE + timedelta(hours=1),
        )
    )
    db.commit()

    everything = client.get("/resource-bookings", headers=headers)
    assert len(everything.json()) == 2

    by_resource = client.get(
        f"/resource-bookings?resource_id={second.id}", headers=headers
    )
    assert len(by_resource.json()) == 1

    in_window = client.get(
        "/resource-bookings",
        params={
            "from": (BASE + timedelta(hours=9)).isoformat(),
            "to": (BASE + timedelta(hours=13)).isoformat(),
        },
        headers=headers,
    )
    assert len(in_window.json()) == 1

    other_booking = db.query(ResourceBooking).filter(
        ResourceBooking.business_id == test_data["business_b"].id
    ).one()
    assert (
        client.get(
            f"/resource-bookings/{other_booking.id}", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/resource-bookings/{other_booking.id}/cancel",
            headers=headers,
        ).status_code
        == 404
    )


# ============================================================
# OPERATIONAL SIGNALS
# ============================================================

def test_resource_signals_flag_funerals_missing_resources(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    soon = date.today() + timedelta(days=2)
    far = date.today() + timedelta(days=40)

    bare = make_case(db, business, funeral_date=soon)
    covered = make_case(db, business, funeral_date=soon)
    make_case(db, business, funeral_date=far)
    make_case(
        db, business, funeral_date=soon, status="closed"
    )

    vehicle = make_resource(db, business)
    venue = make_resource(
        db, business, resource_type="venue", name="Hall"
    )
    headers = auth_headers(test_data["manager"])

    now = datetime.now(timezone.utc)
    for resource in (vehicle, venue):
        db.add(
            ResourceBooking(
                business_id=business.id,
                case_id=covered.id,
                resource_id=resource.id,
                starts_at=now + timedelta(days=2),
                ends_at=now + timedelta(days=2, hours=3),
            )
        )
    db.commit()

    response = client.get("/resource-signals", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()

    assert [c["case_id"] for c in body["funerals_without_vehicle"]] == [
        str(bare.id)
    ]
    assert [c["case_id"] for c in body["funerals_without_venue"]] == [
        str(bare.id)
    ]
    # The covered case's vehicle booking has no driver.
    assert body["vehicle_bookings_without_driver"] == 1


def test_resource_signals_are_tenant_scoped_and_permissioned(
    client, test_data, auth_headers, db
):
    soon = date.today() + timedelta(days=1)
    make_case(db, test_data["business_b"], funeral_date=soon)

    own = client.get(
        "/resource-signals",
        headers=auth_headers(test_data["manager"]),
    )
    assert own.json()["funerals_without_vehicle"] == []

    staff = test_data["staff"]
    deny_permission(db, staff.id, "resource_bookings.view")
    denied = client.get(
        "/resource-signals", headers=auth_headers(staff)
    )
    assert denied.status_code == 403


def test_resource_signals_window_validated(
    client, test_data, auth_headers
):
    response = client.get(
        "/resource-signals?window_days=0",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


# ============================================================
# HISTORICAL INTEGRITY
# ============================================================

def test_deactivating_resource_keeps_booking_history(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business)
    resource = make_resource(db, business)
    headers = auth_headers(test_data["manager"])

    booking = book(client, headers, case, resource, 0, 2).json()

    deactivate = client.post(
        f"/resources/{resource.id}/deactivate", headers=headers
    )
    assert deactivate.status_code == 200

    kept = client.get(
        f"/resource-bookings/{booking['id']}", headers=headers
    )
    assert kept.status_code == 200
    assert kept.json()["resource_id"] == str(resource.id)
