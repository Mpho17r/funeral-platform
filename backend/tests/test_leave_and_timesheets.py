"""Leave requests, approval, balances and weekly timesheets."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.notification import Notification
from app.models.staff_attendance_session import StaffAttendanceSession
from app.models.staff_break_session import StaffBreakSession
from app.services import leave as leave_service
from app.services.autopilot import pick_person  # noqa: F401  (imported to prove no cycle)

ZONE = ZoneInfo("Africa/Johannesburg")


def next_monday(weeks: int = 1) -> date:
    today = date.today()
    return today + timedelta(days=(7 - today.weekday())) + timedelta(weeks=weeks - 1)


def ask(client, headers, kind="annual", start=None, end=None, reason=None):
    start = start or next_monday()
    end = end or start + timedelta(days=4)
    return client.post(
        "/leave",
        json={
            "leave_type": kind,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": reason,
        },
        headers=headers,
    )


def test_working_days_skip_weekends():
    monday = date(2026, 11, 2)
    assert leave_service.working_days(monday, monday + timedelta(days=4)) == 5
    assert leave_service.working_days(monday, monday + timedelta(days=6)) == 5
    assert leave_service.working_days(date(2026, 11, 7), date(2026, 11, 8)) == 0


def test_request_approve_balance_and_notifications(client, auth_headers, db, test_data):
    staff, manager = test_data["staff"], test_data["manager"]
    sh, mh = auth_headers(staff), auth_headers(manager)

    r = ask(client, sh, reason="Family trip")
    assert r.status_code == 201, r.text
    leave = r.json()
    assert leave["days"] == 5 and leave["status"] == "pending"

    # The deciders were told; staff cannot see the team list or decide.
    assert db.query(Notification).filter(Notification.kind == "leave_request").count() >= 1
    assert client.get("/leave/team", headers=sh).status_code == 403
    assert client.post(f"/leave/{leave['id']}/approve", json={}, headers=sh).status_code == 403

    mine = client.get("/leave/mine", headers=sh).json()
    assert mine["balance"]["pending"] == 5 and mine["balance"]["remaining"] == 10

    # A clash with their own pending leave is refused.
    assert ask(client, sh, start=next_monday() + timedelta(days=2), end=next_monday() + timedelta(days=9)).status_code == 409

    assert client.post(f"/leave/{leave['id']}/approve", json={}, headers=mh).status_code == 200
    mine = client.get("/leave/mine", headers=sh).json()
    assert mine["balance"]["taken"] == 5 and mine["balance"]["pending"] == 0
    assert db.query(Notification).filter(Notification.kind == "leave_decision").count() == 1

    # Deciding twice is refused.
    assert client.post(f"/leave/{leave['id']}/reject", json={"note": "x"}, headers=mh).status_code == 409

    team = client.get("/leave/team", headers=mh).json()
    assert any(i["user_name"] for i in team["items"])


def test_rules(client, auth_headers, test_data):
    sh = auth_headers(test_data["staff"])
    yesterday = date.today() - timedelta(days=1)

    # Not in the past, except sick leave.
    assert ask(client, sh, start=yesterday, end=yesterday).status_code == 422
    past_weekday = date.today() - timedelta(days=3)
    while past_weekday.weekday() >= 5:
        past_weekday -= timedelta(days=1)
    sick = ask(client, sh, kind="sick", start=past_weekday, end=past_weekday)
    assert sick.status_code == 201, sick.text

    # Bad dates, weekend only, unknown type.
    assert ask(client, sh, start=next_monday() + timedelta(days=3), end=next_monday()).status_code == 422
    sat = next_monday() + timedelta(days=5)
    assert ask(client, sh, start=sat, end=sat + timedelta(days=1)).status_code == 422
    assert ask(client, sh, kind="holiday").status_code == 422

    # Too much annual leave.
    assert ask(client, sh, start=next_monday(), end=next_monday() + timedelta(days=27)).status_code == 422


def test_cannot_decide_own_leave_and_reject_needs_reason(client, auth_headers, test_data):
    mh = auth_headers(test_data["manager"])
    mine = ask(client, mh).json()
    assert client.post(f"/leave/{mine['id']}/approve", json={}, headers=mh).status_code == 403

    sh = auth_headers(test_data["staff"])
    theirs = ask(client, sh, start=next_monday(3)).json()
    assert client.post(f"/leave/{theirs['id']}/reject", json={}, headers=mh).status_code == 422
    r = client.post(f"/leave/{theirs['id']}/reject", json={"note": "Busy week"}, headers=mh)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    # Rejected leave does not use up days.
    assert client.get("/leave/mine", headers=sh).json()["balance"]["remaining"] == 15


def test_cancel_and_allowance_setting(client, auth_headers, test_data):
    sh, mh = auth_headers(test_data["staff"]), auth_headers(test_data["manager"])
    leave = ask(client, sh).json()
    assert client.post(f"/leave/{leave['id']}/cancel", headers=mh).status_code == 403
    assert client.post(f"/leave/{leave['id']}/cancel", headers=sh).json()["status"] == "cancelled"
    assert client.post(f"/leave/{leave['id']}/cancel", headers=sh).status_code == 409

    assert client.put("/leave/settings", json={"leave_days_per_year": 21}, headers=sh).status_code == 403
    assert client.put("/leave/settings", json={"leave_days_per_year": 21}, headers=mh).status_code == 200
    assert client.get("/leave/mine", headers=sh).json()["balance"]["entitlement"] == 21


def test_people_on_approved_leave_are_not_given_work_and_show_on_calendar(
    client, auth_headers, db, test_data
):
    sh, mh = auth_headers(test_data["staff"]), auth_headers(test_data["manager"])
    today = date.today()
    start = today if today.weekday() < 5 else today + timedelta(days=(7 - today.weekday()))
    leave = ask(client, sh, start=start, end=start).json()
    client.post(f"/leave/{leave['id']}/approve", json={}, headers=mh)

    assert test_data["staff"].id in leave_service.on_leave(db, test_data["business_a"].id, start)

    # KAI never picks someone who is off today (even on a weekend date).
    from app.models.leave import LeaveRequest

    db.add(
        LeaveRequest(
            business_id=test_data["business_a"].id,
            user_id=test_data["staff"].id,
            leave_type="sick",
            start_date=today,
            end_date=today,
            days=1,
            status="approved",
        )
    )
    db.commit()
    picked = pick_person(
        db, test_data["business_a"], permission="tasks.view", branch_id=None, area="general"
    )
    assert picked is None or picked.id != test_data["staff"].id

    events = client.get("/calendar", headers=mh).json()
    assert any(e["event_type"] == "leave" and e["date"] == start.isoformat() for e in events)
    # Staff only see their own leave there; managers see everyone's.
    others = client.get("/calendar", headers=auth_headers(test_data["staff"])).json()
    assert all(e["assigned_to"] == str(test_data["staff"].id) for e in others if e["event_type"] == "leave")


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=ZONE).astimezone(timezone.utc)


def test_timesheet_hours_breaks_and_midnight(client, auth_headers, db, test_data):
    staff = test_data["staff"]
    biz = test_data["business_a"]
    monday = date.today() - timedelta(days=date.today().weekday()) - timedelta(days=14)

    s1 = StaffAttendanceSession(
        business_id=biz.id, user_id=staff.id, status="checked_out",
        checked_in_at=at(monday, 8), checked_out_at=at(monday, 17),
    )
    # Works past midnight into Wednesday.
    tue = monday + timedelta(days=1)
    s2 = StaffAttendanceSession(
        business_id=biz.id, user_id=staff.id, status="checked_out",
        checked_in_at=at(tue, 22), checked_out_at=at(tue + timedelta(days=1), 2),
    )
    db.add_all([s1, s2])
    db.flush()
    db.add(
        StaffBreakSession(
            attendance_session_id=s1.id, business_id=biz.id, user_id=staff.id,
            break_type="lunch", started_at=at(monday, 12), ended_at=at(monday, 13),
        )
    )
    db.commit()

    sh = auth_headers(staff)
    week = client.get("/timesheets/week", params={"week_of": (monday + timedelta(days=3)).isoformat()}, headers=sh).json()
    assert week["week_start"] == monday.isoformat()
    by = {d["date"]: d for d in week["days"]}
    assert by[monday.isoformat()]["net_seconds"] == 8 * 3600
    assert by[monday.isoformat()]["break_seconds"] == 3600
    assert by[monday.isoformat()]["first_in"] == "08:00"
    assert by[tue.isoformat()]["net_seconds"] == 2 * 3600
    assert by[(tue + timedelta(days=1)).isoformat()]["net_seconds"] == 2 * 3600
    assert week["net_seconds"] == (8 + 2 + 2) * 3600


def test_timesheet_permissions_and_export(client, auth_headers, test_data):
    sh, mh = auth_headers(test_data["staff"]), auth_headers(test_data["manager"])
    other = str(test_data["manager"].id)

    assert client.get("/timesheets/week", params={"user_id": other}, headers=sh).status_code == 403
    assert client.get("/timesheets/team", headers=sh).status_code == 403
    assert client.get("/timesheets/export", headers=sh).status_code == 403

    assert client.get("/timesheets/week", params={"user_id": str(test_data["staff"].id)}, headers=mh).status_code == 200
    team = client.get("/timesheets/team", headers=mh).json()
    assert len(team["dates"]) == 7 and team["people"]
    csv = client.get("/timesheets/export", headers=mh)
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert "Total hours" in csv.text
