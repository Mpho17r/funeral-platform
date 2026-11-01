"""Hours worked each week, worked out from clock-in/out and breaks."""

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies.roles import get_current_user
from app.models.staff_attendance_session import StaffAttendanceSession
from app.models.staff_break_session import StaffBreakSession
from app.models.user import User
from app.services import leave as leave_service
from app.services.permission_service import has_permission

router = APIRouter(prefix="/timesheets", tags=["Timesheets"])


def _zone() -> ZoneInfo:
    return ZoneInfo(settings.scheduler_timezone)


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _overlap_seconds(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> int:
    lo, hi = max(a_start, b_start), min(a_end, b_end)
    return max(int((hi - lo).total_seconds()), 0)


def week_for(
    db: Session, business_id: UUID, user_id: UUID, monday: date, now: datetime | None = None
) -> dict:
    """Worked, break and net seconds for each of the seven days. A session
    that runs past midnight is split between the days."""

    zone = _zone()
    now = now or datetime.now(timezone.utc)
    days = [monday + timedelta(days=i) for i in range(7)]
    start = datetime.combine(monday, time.min, tzinfo=zone)
    end = datetime.combine(monday + timedelta(days=7), time.min, tzinfo=zone)

    sessions = (
        db.query(StaffAttendanceSession)
        .filter(
            StaffAttendanceSession.business_id == business_id,
            StaffAttendanceSession.user_id == user_id,
            StaffAttendanceSession.checked_in_at < end,
        )
        .all()
    )
    sessions = [
        s for s in sessions
        if _aware(s.checked_out_at or now) > start
    ]
    breaks = (
        db.query(StaffBreakSession)
        .filter(
            StaffBreakSession.business_id == business_id,
            StaffBreakSession.user_id == user_id,
            StaffBreakSession.started_at < end,
        )
        .all()
    )
    breaks = [b for b in breaks if _aware(b.ended_at or now) > start]

    leave = leave_service.approved_days(db, business_id, user_id, days[0], days[-1])

    out = []
    for d in days:
        d0 = datetime.combine(d, time.min, tzinfo=zone)
        d1 = datetime.combine(d + timedelta(days=1), time.min, tzinfo=zone)
        worked = sum(
            _overlap_seconds(_aware(s.checked_in_at), _aware(s.checked_out_at or now), d0, d1)
            for s in sessions
        )
        paused = sum(
            _overlap_seconds(_aware(b.started_at), _aware(b.ended_at or now), d0, d1)
            for b in breaks
        )
        first = [
            _aware(s.checked_in_at).astimezone(zone)
            for s in sessions
            if d0 <= _aware(s.checked_in_at) < d1
        ]
        last_out = [
            _aware(s.checked_out_at).astimezone(zone)
            for s in sessions
            if s.checked_out_at and d0 <= _aware(s.checked_out_at) < d1
        ]
        off = next((l["type"] for l in leave if l["start"] <= d <= l["end"]), None)
        out.append(
            {
                "date": d.isoformat(),
                "weekday": d.strftime("%a"),
                "worked_seconds": worked,
                "break_seconds": paused,
                "net_seconds": max(worked - paused, 0),
                "first_in": min(first).strftime("%H:%M") if first else None,
                "last_out": max(last_out).strftime("%H:%M") if last_out else None,
                "leave": off,
                "still_clocked_in": any(
                    s.checked_out_at is None and d0 <= _aware(s.checked_in_at) < d1 for s in sessions
                ),
            }
        )
    return {
        "week_start": monday.isoformat(),
        "days": out,
        "net_seconds": sum(x["net_seconds"] for x in out),
        "break_seconds": sum(x["break_seconds"] for x in out),
    }


def _can_manage(db: Session, user: dict) -> bool:
    return has_permission(
        db, user_id=UUID(str(user["user_id"])), role=user["role"], permission_key="timesheets.manage"
    )


def _need(db: Session, user: dict, key: str):
    if not has_permission(db, user_id=UUID(str(user["user_id"])), role=user["role"], permission_key=key):
        raise HTTPException(403, f"Permission required: {key}")


@router.get("/week")
def my_or_their_week(
    week_of: date | None = None,
    user_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Your own week, or anybody's if you may manage timesheets."""

    target = user_id or UUID(str(user["user_id"]))
    if target != UUID(str(user["user_id"])):
        _need(db, user, "timesheets.manage")
    else:
        _need(db, user, "timesheets.view")

    person = (
        db.query(User)
        .filter(User.id == target, User.business_id == user["business_id"])
        .first()
    )
    if person is None:
        raise HTTPException(404, "Person not found")

    monday = monday_of(week_of or date.today())
    data = week_for(db, user["business_id"], target, monday)
    data["user_id"] = str(target)
    data["user_name"] = person.full_name
    return data


def _team(db: Session, user: dict, monday: date) -> list[dict]:
    rows = []
    people = (
        db.query(User)
        .filter(User.business_id == user["business_id"], User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )
    for p in people:
        w = week_for(db, user["business_id"], p.id, monday)
        rows.append(
            {
                "user_id": str(p.id),
                "user_name": p.full_name,
                "job_title": p.job_title,
                "days": [d["net_seconds"] for d in w["days"]],
                "leave_days": [d["leave"] for d in w["days"]],
                "net_seconds": w["net_seconds"],
            }
        )
    return rows


@router.get("/team")
def team_week(
    week_of: date | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _need(db, user, "timesheets.manage")
    monday = monday_of(week_of or date.today())
    return {
        "week_start": monday.isoformat(),
        "dates": [(monday + timedelta(days=i)).isoformat() for i in range(7)],
        "people": _team(db, user, monday),
    }


@router.get("/export")
def export(
    week_of: date | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """A CSV of everyone's hours for the week, for payroll."""

    _need(db, user, "timesheets.manage")
    monday = monday_of(week_of or date.today())
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Name", "Job title"] + [(monday + timedelta(days=i)).isoformat() for i in range(7)] + ["Total hours"])
    for p in _team(db, user, monday):
        w.writerow(
            [p["user_name"], p["job_title"] or ""]
            + [("Leave" if l and not s else f"{s / 3600:.2f}") for s, l in zip(p["days"], p["leave_days"])]
            + [f"{p['net_seconds'] / 3600:.2f}"]
        )
    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="timesheet-{monday.isoformat()}.csv"'},
    )
