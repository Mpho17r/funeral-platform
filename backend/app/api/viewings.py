from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.compliance import RemainsViewing
from app.models.funeral_case import FuneralCase
from app.models.mortuary import RemainsRecord
from app.services.audit_service import create_audit_log
from app.services.notifications import notify, users_with_permission

router = APIRouter(prefix="/mortuary/viewings", tags=["Viewings"])


class ViewingCreate(BaseModel):
    case_id: UUID
    starts_at: datetime
    duration_minutes: int = Field(default=30, ge=10, le=240)
    room: str | None = Field(default=None, max_length=100)
    visitor_name: str | None = Field(default=None, max_length=150)
    expected_visitors: int | None = Field(default=None, ge=1, le=500)
    notes: str | None = Field(default=None, max_length=1000)


class Cancel(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _out(v: RemainsViewing, case: FuneralCase, remains=None) -> dict:
    return {
        "id": str(v.id),
        "case_id": str(v.case_id),
        "case_number": case.case_number,
        "deceased_name": case.deceased_full_name,
        "tag_number": remains.tag_number if remains else None,
        "starts_at": v.starts_at.isoformat(),
        "ends_at": (
            v.starts_at + timedelta(minutes=v.duration_minutes)
        ).isoformat(),
        "duration_minutes": v.duration_minutes,
        "room": v.room,
        "visitor_name": v.visitor_name,
        "expected_visitors": v.expected_visitors,
        "notes": v.notes,
        "status": v.status,
        "cancel_reason": v.cancel_reason,
    }


@router.get("")
def list_viewings(
    days: int = Query(7, ge=1, le=60),
    include_past: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("viewings.view")),
):
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=12) if include_past else now - timedelta(
        minutes=60
    )
    rows = (
        db.query(RemainsViewing, FuneralCase, RemainsRecord)
        .join(FuneralCase, FuneralCase.id == RemainsViewing.case_id)
        .outerjoin(
            RemainsRecord,
            and_(
                RemainsRecord.case_id == RemainsViewing.case_id,
                RemainsRecord.business_id == RemainsViewing.business_id,
            ),
        )
        .filter(
            RemainsViewing.business_id == user["business_id"],
            RemainsViewing.starts_at >= start,
            RemainsViewing.starts_at <= now + timedelta(days=days),
            RemainsViewing.status.in_(
                ["scheduled", "completed"]
                if include_past
                else ["scheduled"]
            ),
        )
        .order_by(RemainsViewing.starts_at)
        .all()
    )
    return {"items": [_out(v, c, r) for v, c, r in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def schedule(
    payload: ViewingCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("viewings.manage")),
):
    biz = user["business_id"]
    starts = _aware(payload.starts_at)
    if starts < datetime.now(timezone.utc) - timedelta(minutes=5):
        raise HTTPException(422, "A viewing cannot be in the past.")

    case = (
        db.query(FuneralCase)
        .filter(FuneralCase.id == payload.case_id, FuneralCase.business_id == biz)
        .first()
    )
    if case is None:
        raise HTTPException(404, "Funeral case not found.")

    remains = (
        db.query(RemainsRecord)
        .filter(
            RemainsRecord.case_id == case.id,
            RemainsRecord.business_id == biz,
        )
        .first()
    )
    if remains is None or remains.status != "in_custody":
        raise HTTPException(
            409, "These remains are not in the mortuary, so cannot be viewed."
        )
    if remains.identified_at is None:
        raise HTTPException(
            409,
            "The remains must be identified before a family viewing.",
        )

    ends = starts + timedelta(minutes=payload.duration_minutes)
    room = (payload.room or "").strip() or None
    if room:
        clash = (
            db.query(RemainsViewing)
            .filter(
                RemainsViewing.business_id == biz,
                RemainsViewing.status == "scheduled",
                RemainsViewing.room == room,
                RemainsViewing.starts_at < ends,
                RemainsViewing.starts_at
                > starts - timedelta(minutes=240),
            )
            .all()
        )
        for other in clash:
            if other.starts_at + timedelta(
                minutes=other.duration_minutes
            ) > starts:
                raise HTTPException(
                    409, f"{room} is already booked at that time."
                )

    viewing = RemainsViewing(
        business_id=biz,
        created_by=user["user_id"],
        case_id=case.id,
        starts_at=starts,
        duration_minutes=payload.duration_minutes,
        room=room,
        visitor_name=payload.visitor_name,
        expected_visitors=payload.expected_visitors,
        notes=payload.notes,
    )
    db.add(viewing)
    db.flush()

    create_audit_log(
        db,
        business_id=biz,
        user_id=user["user_id"],
        action="viewing.scheduled",
        entity_type="remains_viewing",
        entity_id=viewing.id,
        details={"case_id": str(case.id), "starts_at": starts.isoformat()},
        notes="A family viewing was scheduled.",
    )
    notify(
        db,
        business_id=biz,
        user_ids=users_with_permission(db, biz, "mortuary.manage"),
        kind="viewing",
        title=f"Viewing booked: {case.deceased_full_name}",
        body=f"{starts.astimezone(timezone(timedelta(hours=2))):%a %d %b %H:%M}"
        + (f" in {room}" if room else ""),
        link="/mortuary",
        actor_id=user["user_id"],
    )
    db.commit()
    return _out(viewing, case, remains)


def _get(db, user, viewing_id):
    row = (
        db.query(RemainsViewing, FuneralCase)
        .join(FuneralCase, FuneralCase.id == RemainsViewing.case_id)
        .filter(
            RemainsViewing.id == viewing_id,
            RemainsViewing.business_id == user["business_id"],
        )
        .first()
    )
    if row is None:
        raise HTTPException(404, "Viewing not found.")
    return row


@router.post("/{viewing_id}/cancel")
def cancel(
    viewing_id: UUID,
    payload: Cancel,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("viewings.manage")),
):
    viewing, case = _get(db, user, viewing_id)
    if viewing.status != "scheduled":
        raise HTTPException(409, "Only a scheduled viewing can be cancelled.")
    viewing.status = "cancelled"
    viewing.cancel_reason = payload.reason.strip()
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="viewing.cancelled",
        entity_type="remains_viewing",
        entity_id=viewing.id,
        notes="A family viewing was cancelled.",
    )
    notify(
        db,
        business_id=user["business_id"],
        user_ids=users_with_permission(
            db, user["business_id"], "mortuary.manage"
        ),
        kind="viewing",
        title=f"Viewing cancelled: {case.deceased_full_name}",
        body=viewing.cancel_reason,
        link="/mortuary",
        actor_id=user["user_id"],
    )
    db.commit()
    return _out(viewing, case)


@router.post("/{viewing_id}/complete")
def complete(
    viewing_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("viewings.manage")),
):
    viewing, case = _get(db, user, viewing_id)
    if viewing.status != "scheduled":
        raise HTTPException(409, "Only a scheduled viewing can be completed.")
    viewing.status = "completed"
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="viewing.completed",
        entity_type="remains_viewing",
        entity_id=viewing.id,
        notes="A family viewing took place.",
    )
    db.commit()
    return _out(viewing, case)
