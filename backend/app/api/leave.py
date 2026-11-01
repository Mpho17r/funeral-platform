"""Leave: ask, approve or reject, balances and who is off."""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.business import Business
from app.models.leave import LeaveRequest
from app.models.user import User
from app.services import leave as calc
from app.services.audit_service import create_audit_log
from app.services.notifications import notify

router = APIRouter(prefix="/leave", tags=["Leave"])


class LeaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leave_type: str
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=1000)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leave_days_per_year: int = Field(ge=0, le=60)


def _out(r: LeaveRequest, names: dict | None = None) -> dict:
    return {
        "id": str(r.id),
        "user_id": str(r.user_id),
        "user_name": (names or {}).get(r.user_id, ""),
        "leave_type": r.leave_type,
        "start_date": r.start_date.isoformat(),
        "end_date": r.end_date.isoformat(),
        "days": r.days,
        "reason": r.reason,
        "status": r.status,
        "decision_note": r.decision_note,
        "created_at": r.created_at.isoformat(),
    }


def _names(db: Session, business_id) -> dict:
    return {
        u.id: u.full_name
        for u in db.query(User.id, User.full_name).filter(User.business_id == business_id)
    }


def _business(db: Session, user: dict) -> Business:
    return db.get(Business, user["business_id"])


def _deciders(db: Session, business_id, exclude) -> list:
    return [
        u.id
        for u in db.query(User).filter(
            User.business_id == business_id,
            User.is_active.is_(True),
            User.role.in_(("main_admin", "manager")),
            User.id != exclude,
        )
    ]


def _get(db: Session, user: dict, leave_id: UUID) -> LeaveRequest:
    r = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.id == leave_id, LeaveRequest.business_id == user["business_id"])
        .first()
    )
    if r is None:
        raise HTTPException(404, "Leave request not found")
    return r


def _audit(db, user, action, r, notes):
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action=action,
        entity_type="leave",
        entity_id=r.id,
        details={"type": r.leave_type, "from": r.start_date.isoformat(), "to": r.end_date.isoformat()},
        notes=notes,
    )


@router.get("/mine")
def mine(
    year: int | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.request")),
):
    year = year or date.today().year
    business = _business(db, user)
    rows = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.business_id == user["business_id"], LeaveRequest.user_id == user["user_id"])
        .order_by(LeaveRequest.start_date.desc())
        .limit(200)
        .all()
    )
    return {
        "balance": calc.balance(db, user["business_id"], user["user_id"], business.leave_days_per_year, year),
        "types": list(calc.TYPES),
        "items": [_out(r) for r in rows],
    }


@router.post("", status_code=201)
def request_leave(
    data: LeaveIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.request")),
):
    if data.leave_type not in calc.TYPES:
        raise HTTPException(422, "Unknown leave type")
    if data.end_date < data.start_date:
        raise HTTPException(422, "The last day is before the first day")
    if (data.end_date - data.start_date).days > 366:
        raise HTTPException(422, "A single request can be at most a year")
    # Only sick leave can be asked for after the fact.
    if data.start_date < date.today() and data.leave_type != "sick":
        raise HTTPException(422, "Leave must start today or later (sick leave can be backdated)")

    days = calc.working_days(data.start_date, data.end_date)
    if days == 0:
        raise HTTPException(422, "These dates have no working days (weekend only)")

    if calc.clash(db, user["business_id"], user["user_id"], data.start_date, data.end_date):
        raise HTTPException(409, "You already have leave in these dates")

    business = _business(db, user)
    if data.leave_type == "annual":
        # Check the balance for every calendar year the request touches.
        for year in range(data.start_date.year, data.end_date.year + 1):
            start, end = calc.year_bounds(year)
            lo, hi = max(data.start_date, start), min(data.end_date, end)
            need = calc.working_days(lo, hi) if lo <= hi else 0
            left = calc.balance(db, user["business_id"], user["user_id"], business.leave_days_per_year, year)["remaining"]
            if need > left:
                raise HTTPException(
                    422, f"Not enough annual leave left in {year}: {left} day(s) left, {need} asked for"
                )

    r = LeaveRequest(
        business_id=user["business_id"],
        user_id=user["user_id"],
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        days=days,
        reason=(data.reason or "").strip() or None,
    )
    db.add(r)
    db.flush()
    _audit(db, user, "leave.requested", r, "Leave was requested.")

    who = db.get(User, user["user_id"])
    notify(
        db,
        business_id=user["business_id"],
        user_ids=_deciders(db, user["business_id"], user["user_id"]),
        kind="leave_request",
        title=f"{who.full_name} asked for leave",
        body=f"{r.leave_type} · {r.start_date.isoformat()} to {r.end_date.isoformat()} ({days} day{'s' if days != 1 else ''})",
        link="/leave?tab=team",
        actor_id=user["user_id"],
    )
    db.commit()
    return _out(r, {who.id: who.full_name})


@router.post("/{leave_id}/cancel")
def cancel(
    leave_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.request")),
):
    r = _get(db, user, leave_id)
    if r.user_id != user["user_id"]:
        raise HTTPException(403, "You can only cancel your own leave")
    if r.status == "pending" or (r.status == "approved" and r.end_date >= date.today()):
        was = r.status
        r.status = "cancelled"
        _audit(db, user, "leave.cancelled", r, "Leave was cancelled by the worker.")
        if was == "approved":
            who = db.get(User, r.user_id)
            notify(
                db,
                business_id=user["business_id"],
                user_ids=_deciders(db, user["business_id"], user["user_id"]),
                kind="leave_cancelled",
                title=f"{who.full_name} cancelled approved leave",
                body=f"{r.start_date.isoformat()} to {r.end_date.isoformat()}",
                link="/leave?tab=team",
                actor_id=user["user_id"],
            )
        db.commit()
        return _out(r)
    raise HTTPException(409, "This leave can no longer be cancelled")


# ------------------------------------------------------------ managers


@router.get("/team")
def team(
    status: str | None = None,
    year: int | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.manage")),
):
    year = year or date.today().year
    start, end = calc.year_bounds(year)
    q = db.query(LeaveRequest).filter(
        LeaveRequest.business_id == user["business_id"],
        LeaveRequest.end_date >= start,
        LeaveRequest.start_date <= end,
    )
    if status:
        q = q.filter(LeaveRequest.status == status)
    rows = q.order_by(LeaveRequest.start_date.asc()).limit(500).all()
    names = _names(db, user["business_id"])
    business = _business(db, user)
    return {
        "leave_days_per_year": business.leave_days_per_year,
        "off_today": sorted(names.get(i, "") for i in calc.on_leave(db, user["business_id"], date.today())),
        "items": [_out(r, names) for r in rows],
    }


def _decide(db: Session, user: dict, leave_id: UUID, approve: bool, note: str | None):
    r = _get(db, user, leave_id)
    if r.status != "pending":
        raise HTTPException(409, "This request has already been decided")
    if r.user_id == user["user_id"] and user["role"] != "main_admin":
        raise HTTPException(403, "You cannot decide your own leave")
    note = (note or "").strip() or None
    if not approve and not note:
        raise HTTPException(422, "Say why the leave is rejected")

    if approve:
        business = _business(db, user)
        if r.leave_type == "annual":
            for year in range(r.start_date.year, r.end_date.year + 1):
                bal = calc.balance(db, user["business_id"], r.user_id, business.leave_days_per_year, year)
                # This request is itself counted as pending in the balance.
                if bal["remaining"] < 0:
                    raise HTTPException(409, f"They do not have enough annual leave left in {year}")

    r.status = "approved" if approve else "rejected"
    r.decided_by = user["user_id"]
    r.decided_at = datetime.now(timezone.utc)
    r.decision_note = note
    _audit(db, user, "leave.approved" if approve else "leave.rejected", r, f"Leave was {r.status}.")
    notify(
        db,
        business_id=user["business_id"],
        user_ids=[r.user_id],
        kind="leave_decision",
        title=f"Your leave was {r.status}",
        body=f"{r.start_date.isoformat()} to {r.end_date.isoformat()}" + (f" - {note}" if note else ""),
        link="/leave",
        actor_id=user["user_id"],
    )
    db.commit()
    return _out(r, _names(db, user["business_id"]))


@router.post("/{leave_id}/approve")
def approve(
    leave_id: UUID,
    data: DecisionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.manage")),
):
    return _decide(db, user, leave_id, True, data.note)


@router.post("/{leave_id}/reject")
def reject(
    leave_id: UUID,
    data: DecisionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.manage")),
):
    return _decide(db, user, leave_id, False, data.note)


@router.put("/settings")
def settings(
    data: SettingsIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("leave.manage")),
):
    business = _business(db, user)
    business.leave_days_per_year = data.leave_days_per_year
    db.commit()
    return {"leave_days_per_year": business.leave_days_per_year}
