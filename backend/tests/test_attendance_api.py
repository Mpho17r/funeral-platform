from datetime import datetime, timedelta, timezone
from app.models.business import Business
from app.models.staff_attendance_session import StaffAttendanceSession
from app.models.staff_break_session import StaffBreakSession
from app.models.staff_presence import StaffPresence


def test_staff_can_check_in(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["business_id"] == str(staff.business_id)
    assert data["user_id"] == str(staff.id)
    assert data["status"] == "active"
    assert data["checked_in_at"] is not None
    assert data["checked_out_at"] is None

    session = (
        db.query(StaffAttendanceSession)
        .filter(
            StaffAttendanceSession.business_id
            == staff.business_id,
            StaffAttendanceSession.user_id
            == staff.id,
            StaffAttendanceSession.checked_out_at.is_(None),
        )
        .first()
    )

    assert session is not None

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == staff.business_id,
            StaffPresence.user_id == staff.id,
        )
        .first()
    )

    assert presence is not None
    assert presence.status == "online"
    assert presence.checked_in_at is not None
    assert presence.checked_out_at is None


def test_staff_cannot_check_in_twice(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    first_response = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "You are already checked in"
    )


def test_completed_session_allows_new_check_in(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    first_response = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert first_response.status_code == 201

    session = (
        db.query(StaffAttendanceSession)
        .filter(
            StaffAttendanceSession.business_id
            == staff.business_id,
            StaffAttendanceSession.user_id
            == staff.id,
            StaffAttendanceSession.checked_out_at.is_(None),
        )
        .first()
    )

    assert session is not None

    from datetime import datetime, timezone

    session.checked_out_at = datetime.now(timezone.utc)
    session.status = "completed"
    db.commit()

    second_response = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert second_response.status_code == 201

    data = second_response.json()

    assert data["user_id"] == str(staff.id)
    assert data["status"] == "active"
    assert data["checked_out_at"] is None


def test_staff_can_check_out(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    response = client.post(
        "/attendance/check-out",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["business_id"] == str(staff.business_id)
    assert data["user_id"] == str(staff.id)
    assert data["status"] == "completed"
    assert data["checked_in_at"] is not None
    assert data["checked_out_at"] is not None

    session = (
        db.query(StaffAttendanceSession)
        .filter(
            StaffAttendanceSession.business_id
            == staff.business_id,
            StaffAttendanceSession.user_id
            == staff.id,
        )
        .order_by(StaffAttendanceSession.checked_in_at.desc())
        .first()
    )

    assert session is not None
    assert session.status == "completed"
    assert session.checked_out_at is not None

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == staff.business_id,
            StaffPresence.user_id == staff.id,
        )
        .first()
    )

    assert presence is not None
    assert presence.status == "offline"
    assert presence.checked_out_at is not None


def test_staff_cannot_check_out_when_not_checked_in(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/attendance/check-out",
        headers=auth_headers(staff),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "You are not checked in"
    )


def test_staff_can_start_tea_break(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    response = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["business_id"] == str(staff.business_id)
    assert data["user_id"] == str(staff.id)
    assert data["break_type"] == "tea"
    assert data["started_at"] is not None
    assert data["ended_at"] is None

    break_session = (
        db.query(StaffBreakSession)
        .filter(
            StaffBreakSession.business_id == staff.business_id,
            StaffBreakSession.user_id == staff.id,
            StaffBreakSession.ended_at.is_(None),
        )
        .first()
    )

    assert break_session is not None
    assert break_session.break_type == "tea"


def test_staff_cannot_start_break_when_not_checked_in(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "You must be checked in to start a break"
    )


def test_staff_cannot_start_second_active_break(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    first_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )

    assert first_break.status_code == 201

    second_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "lunch"},
        headers=auth_headers(staff),
    )

    assert second_break.status_code == 409
    assert second_break.json()["detail"] == (
        "You already have an active break"
    )


def test_staff_can_end_break(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )

    assert start_break.status_code == 201

    break_id = start_break.json()["id"]

    response = client.post(
        "/attendance/breaks/end",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == break_id
    assert data["business_id"] == str(staff.business_id)
    assert data["user_id"] == str(staff.id)
    assert data["break_type"] == "tea"
    assert data["started_at"] is not None
    assert data["ended_at"] is not None

    break_session = db.get(
        StaffBreakSession,
        break_id,
    )

    assert break_session is not None
    assert break_session.ended_at is not None


def test_staff_cannot_end_break_when_no_active_break(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/attendance/breaks/end",
        headers=auth_headers(staff),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "You are not checked in"
    )


def test_staff_can_get_my_attendance_before_check_in(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["attendance"] is None
    assert data["current_break"] is None
    assert data["presence"] == "offline"
    assert data["last_seen_at"] is None


def test_staff_can_get_my_attendance_after_check_in(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["attendance"] is not None
    assert data["attendance"]["user_id"] == str(staff.id)
    assert data["attendance"]["status"] == "active"
    assert data["attendance"]["checked_in_at"] is not None
    assert data["attendance"]["checked_out_at"] is None

    assert data["current_break"] is None
    assert data["presence"] == "online"
    assert data["last_seen_at"] is not None


def test_staff_can_get_my_attendance_during_break(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "lunch"},
        headers=auth_headers(staff),
    )

    assert start_break.status_code == 201

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["attendance"] is not None
    assert data["attendance"]["status"] == "active"

    assert data["current_break"] is not None
    assert data["current_break"]["break_type"] == "lunch"
    assert data["current_break"]["started_at"] is not None
    assert data["current_break"]["ended_at"] is None

    assert data["presence"] == "online"


def test_staff_can_get_my_attendance_after_break_ends(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )

    assert start_break.status_code == 201

    end_break = client.post(
        "/attendance/breaks/end",
        headers=auth_headers(staff),
    )

    assert end_break.status_code == 200

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["attendance"] is not None
    assert data["attendance"]["status"] == "active"
    assert data["current_break"] is None
    assert data["presence"] == "online"


def test_staff_can_get_my_attendance_after_check_out(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    check_out = client.post(
        "/attendance/check-out",
        headers=auth_headers(staff),
    )

    assert check_out.status_code == 200

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["attendance"] is None
    assert data["current_break"] is None
    assert data["presence"] == "offline"
    assert data["last_seen_at"] is not None


def test_check_out_ends_active_break(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "lunch"},
        headers=auth_headers(staff),
    )

    assert start_break.status_code == 201

    break_id = start_break.json()["id"]

    check_out = client.post(
        "/attendance/check-out",
        headers=auth_headers(staff),
    )

    assert check_out.status_code == 200

    break_session = db.get(
        StaffBreakSession,
        break_id,
    )

    assert break_session is not None
    assert break_session.ended_at is not None


def test_staff_can_send_attendance_heartbeat(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    response = client.post(
        "/attendance/heartbeat",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["attendance"] is not None
    assert data["attendance"]["user_id"] == str(staff.id)
    assert data["attendance"]["status"] == "active"
    assert data["current_break"] is None
    assert data["presence"] == "online"
    assert data["last_seen_at"] is not None

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == staff.business_id,
            StaffPresence.user_id == staff.id,
        )
        .first()
    )

    assert presence is not None
    assert presence.status == "online"
    assert presence.last_seen_at is not None


def test_staff_cannot_send_attendance_heartbeat_when_not_checked_in(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/attendance/heartbeat",
        headers=auth_headers(staff),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "You are not checked in"
    )


def test_attendance_me_stays_online_with_recent_activity(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == staff.business_id,
            StaffPresence.user_id == staff.id,
        )
        .first()
    )

    assert presence is not None

    presence.last_seen_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=1)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["presence"] == "online"
    assert data["attendance"] is not None
    assert data["attendance"]["status"] == "active"


def test_attendance_me_becomes_away_after_idle_timeout(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    business = db.get(Business, staff.business_id)
    business.idle_timeout_minutes = 15

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == staff.business_id,
            StaffPresence.user_id == staff.id,
        )
        .first()
    )

    assert presence is not None

    presence.last_seen_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=16)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["presence"] == "away"
    assert data["attendance"] is not None
    assert data["attendance"]["status"] == "active"

    db.refresh(presence)

    assert presence.status == "away"


def test_attendance_me_does_not_mark_staff_away_during_break(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )

    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )

    assert start_break.status_code == 201

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == staff.business_id,
            StaffPresence.user_id == staff.id,
        )
        .first()
    )

    assert presence is not None

    presence.last_seen_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=30)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["presence"] == "online"
    assert data["current_break"] is not None
    assert data["current_break"]["break_type"] == "tea"

    db.refresh(presence)

    assert presence.status == "online"

def test_expired_tea_break_auto_returns_to_normal_attendance(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_expiry_behavior = "auto_return"

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert start_break.status_code == 201

    break_session = db.get(
        StaffBreakSession,
        start_break.json()["id"],
    )
    assert break_session is not None

    break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=16)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_break"] is None
    assert data["attendance"] is not None
    assert data["attendance"]["status"] == "active"

    db.refresh(break_session)

    assert break_session.ended_at is not None


def test_expired_break_stays_active_with_keep_active_policy(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_expiry_behavior = "keep_active"

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert start_break.status_code == 201

    break_session = db.get(
        StaffBreakSession,
        start_break.json()["id"],
    )
    assert break_session is not None

    break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=16)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_break"] is not None
    assert data["current_break"]["break_type"] == "tea"
    assert data["current_break"]["ended_at"] is None

    db.refresh(break_session)

    assert break_session.ended_at is None


def test_expired_break_stays_active_with_notify_and_keep_active_policy(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_expiry_behavior = "notify_and_keep_active"

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert start_break.status_code == 201

    break_session = db.get(
        StaffBreakSession,
        start_break.json()["id"],
    )
    assert break_session is not None

    break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=16)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_break"] is not None
    assert data["current_break"]["break_type"] == "tea"
    assert data["current_break"]["ended_at"] is None

    db.refresh(break_session)

    assert break_session.ended_at is None


def test_break_warning_window_is_configurable(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_warning_enabled = True
    business.break_warning_minutes = 5

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert start_break.status_code == 201

    break_session = db.get(
        StaffBreakSession,
        start_break.json()["id"],
    )
    assert break_session is not None

    break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=11)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_break"] is not None
    assert data["current_break"]["break_type"] == "tea"


def test_expired_auto_return_break_allows_starting_new_break(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_expiry_behavior = "auto_return"

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    first_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert first_break.status_code == 201

    first_break_session = db.get(
        StaffBreakSession,
        first_break.json()["id"],
    )
    assert first_break_session is not None

    first_break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=16)
    )
    db.commit()

    second_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "lunch"},
        headers=auth_headers(staff),
    )

    assert second_break.status_code == 201
    assert second_break.json()["break_type"] == "lunch"

    db.refresh(first_break_session)

    assert first_break_session.ended_at is not None


def test_break_warning_becomes_active_inside_warning_window(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_warning_enabled = True
    business.break_warning_minutes = 5

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert start_break.status_code == 201

    break_session = db.get(
        StaffBreakSession,
        start_break.json()["id"],
    )
    assert break_session is not None

    break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=11)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_break"] is not None
    assert data["break_warning_active"] is True
    assert data["break_expires_at"] is not None


def test_break_warning_is_inactive_before_warning_window(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    business = db.get(Business, staff.business_id)
    business.tea_break_minutes = 15
    business.break_warning_enabled = True
    business.break_warning_minutes = 5

    check_in = client.post(
        "/attendance/check-in",
        headers=auth_headers(staff),
    )
    assert check_in.status_code == 201

    start_break = client.post(
        "/attendance/breaks/start",
        json={"break_type": "tea"},
        headers=auth_headers(staff),
    )
    assert start_break.status_code == 201

    break_session = db.get(
        StaffBreakSession,
        start_break.json()["id"],
    )
    assert break_session is not None

    break_session.started_at = (
        datetime.now(timezone.utc)
        - timedelta(minutes=5)
    )
    db.commit()

    response = client.get(
        "/attendance/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_break"] is not None
    assert data["break_warning_active"] is False
    assert data["break_expires_at"] is not None
