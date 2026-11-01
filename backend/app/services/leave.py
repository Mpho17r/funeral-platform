"""Leave rules: working days, the yearly balance, clashes, and who is off."""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.leave import LeaveRequest

TYPES = ("annual", "sick", "family", "study", "unpaid", "other")
LIVE = ("pending", "approved")


def working_days(start: date, end: date) -> int:
    """Monday to Friday days from start to end, inclusive."""

    days = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            days += 1
        d += timedelta(days=1)
    return days


def year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _days_in_year(req: LeaveRequest, year: int) -> int:
    start, end = year_bounds(year)
    lo, hi = max(req.start_date, start), min(req.end_date, end)
    return working_days(lo, hi) if lo <= hi else 0


def balance(db: Session, business_id: UUID, user_id: UUID, entitlement: int, year: int) -> dict:
    """Annual leave only: allowance, taken (approved), waiting (pending)."""

    start, end = year_bounds(year)
    rows = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.business_id == business_id,
            LeaveRequest.user_id == user_id,
            LeaveRequest.leave_type == "annual",
            LeaveRequest.status.in_(LIVE),
            LeaveRequest.end_date >= start,
            LeaveRequest.start_date <= end,
        )
        .all()
    )
    taken = sum(_days_in_year(r, year) for r in rows if r.status == "approved")
    waiting = sum(_days_in_year(r, year) for r in rows if r.status == "pending")
    return {
        "year": year,
        "entitlement": entitlement,
        "taken": taken,
        "pending": waiting,
        "remaining": entitlement - taken - waiting,
    }


def clash(db: Session, business_id: UUID, user_id: UUID, start: date, end: date, ignore: UUID | None = None):
    """Another live request of the same person that overlaps these dates."""

    q = db.query(LeaveRequest).filter(
        LeaveRequest.business_id == business_id,
        LeaveRequest.user_id == user_id,
        LeaveRequest.status.in_(LIVE),
        LeaveRequest.start_date <= end,
        LeaveRequest.end_date >= start,
    )
    if ignore:
        q = q.filter(LeaveRequest.id != ignore)
    return q.first()


def on_leave(db: Session, business_id: UUID, day: date) -> set[UUID]:
    """Everyone with approved leave on this day."""

    rows = (
        db.query(LeaveRequest.user_id)
        .filter(
            LeaveRequest.business_id == business_id,
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= day,
            LeaveRequest.end_date >= day,
        )
        .all()
    )
    return {r[0] for r in rows}


def approved_days(db: Session, business_id: UUID, user_id: UUID, start: date, end: date) -> list[dict]:
    rows = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.business_id == business_id,
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == "approved",
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        )
        .all()
    )
    return [{"start": r.start_date, "end": r.end_date, "type": r.leave_type} for r in rows]
