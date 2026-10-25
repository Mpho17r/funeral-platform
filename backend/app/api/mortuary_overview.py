"""Dashboard feed and cold-room temperature log for the mortuary team."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.funeral_case import FuneralCase
from app.models.mortuary import (
    COLD_LOCATION_KINDS,
    HYGIENE_TASKS,
    MortuaryHygieneLog,
    MortuaryLocation,
    RemainsRecord,
)
from app.models.user import User
from app.services.audit_service import create_audit_log
from app.services.mortuary import now_utc
from app.services.mortuary_alerts import temperature_breach
from app.services.mortuary_hygiene import TASK_LABELS
from app.services.mortuary_overview import (
    MAX_HOURS,
    overview,
    record_temperature,
)

router = APIRouter(prefix="/mortuary", tags=["Mortuary"])


class TemperatureIn(BaseModel):
    temperature_c: Decimal = Field(ge=Decimal("-40"), le=Decimal("40"),
                                   max_digits=4, decimal_places=1)
    recorded_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=300)


@router.get("/overview")
def mortuary_overview(
    branch_id: UUID | None = None,
    hours: int = Query(default=24, ge=1, le=MAX_HOURS),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.view")),
):
    return overview(
        db,
        business_id=UUID(str(current_user["business_id"])),
        branch_id=branch_id,
        hours=hours,
    )


@router.post(
    "/locations/{location_id}/temperature",
    status_code=status.HTTP_201_CREATED,
)
def log_temperature(
    location_id: UUID,
    data: TemperatureIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.manage")),
):
    business_id = UUID(str(current_user["business_id"]))

    location = (
        db.query(MortuaryLocation)
        .filter(
            MortuaryLocation.id == location_id,
            MortuaryLocation.business_id == business_id,
        )
        .first()
    )
    if location is None:
        raise HTTPException(404, "Mortuary location not found")
    if location.kind not in COLD_LOCATION_KINDS:
        raise HTTPException(
            409, "Temperatures are only logged for fridges and cold rooms"
        )

    when = data.recorded_at or now_utc()
    if when > now_utc() + timedelta(minutes=5):
        raise HTTPException(422, "The reading time cannot be in the future")
    if when < now_utc() - timedelta(days=7):
        raise HTTPException(422, "That reading is too old to record")

    reading = record_temperature(
        db,
        business_id=business_id,
        location=location,
        temperature_c=data.temperature_c,
        recorded_by=UUID(str(current_user["user_id"])),
        recorded_at=when,
        notes=data.notes,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="mortuary_location.temperature_logged",
        entity_type="mortuary_location",
        entity_id=location.id,
        details={
            "name": location.name,
            "temperature_c": str(data.temperature_c),
        },
        notes="A cold place temperature was recorded.",
    )
    temperature_breach(
        db,
        business_id=business_id,
        location=location,
        temperature_c=data.temperature_c,
    )
    db.commit()

    return {
        "id": str(reading.id),
        "location_id": str(location.id),
        "temperature_c": float(reading.temperature_c),
        "recorded_at": reading.recorded_at.isoformat(),
    }


# ---------------------------------------------------------------- cleaning


class HygieneIn(BaseModel):
    task: str
    remains_id: UUID | None = None
    performed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=300)


def _hygiene_out(row, who, case_name=None):
    return {
        "id": str(row.id),
        "task": row.task,
        "label": TASK_LABELS.get(row.task, row.task),
        "remains_id": str(row.remains_id) if row.remains_id else None,
        "case_name": case_name,
        "performed_by": who,
        "performed_at": row.performed_at.isoformat(),
        "notes": row.notes,
    }


@router.post("/hygiene", status_code=status.HTTP_201_CREATED)
def log_hygiene(
    data: HygieneIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.manage")),
):
    """Record that something was cleaned and disinfected (R363 reg 11)."""
    business_id = UUID(str(current_user["business_id"]))
    user_id = UUID(str(current_user["user_id"]))

    if data.task not in HYGIENE_TASKS:
        raise HTTPException(
            422, f"Task must be one of: {', '.join(HYGIENE_TASKS)}"
        )

    if data.remains_id is not None:
        found = (
            db.query(RemainsRecord.id)
            .filter(
                RemainsRecord.id == data.remains_id,
                RemainsRecord.business_id == business_id,
            )
            .first()
        )
        if found is None:
            raise HTTPException(404, "Remains record not found")

    when = data.performed_at or now_utc()
    if when > now_utc() + timedelta(minutes=5):
        raise HTTPException(422, "The time cannot be in the future")
    if when < now_utc() - timedelta(days=7):
        raise HTTPException(422, "That is too long ago to record")

    row = MortuaryHygieneLog(
        business_id=business_id,
        task=data.task,
        remains_id=data.remains_id,
        performed_by=user_id,
        performed_at=when,
        notes=data.notes,
    )
    db.add(row)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="mortuary.hygiene_logged",
        entity_type="mortuary_hygiene_log",
        entity_id=row.id,
        details={"task": data.task},
        notes="A cleaning and disinfection record was added.",
    )
    db.commit()

    who = (
        db.query(User.full_name).filter(User.id == user_id).scalar()
    )
    return _hygiene_out(row, who)


@router.get("/hygiene")
def list_hygiene(
    days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("mortuary.view")),
):
    business_id = UUID(str(current_user["business_id"]))
    since = now_utc() - timedelta(days=days)

    rows = (
        db.query(MortuaryHygieneLog, User.full_name, FuneralCase.deceased_full_name)
        .outerjoin(User, User.id == MortuaryHygieneLog.performed_by)
        .outerjoin(
            RemainsRecord, RemainsRecord.id == MortuaryHygieneLog.remains_id
        )
        .outerjoin(FuneralCase, FuneralCase.id == RemainsRecord.case_id)
        .filter(
            MortuaryHygieneLog.business_id == business_id,
            MortuaryHygieneLog.performed_at >= since,
        )
        .order_by(MortuaryHygieneLog.performed_at.desc())
        .limit(200)
        .all()
    )
    return {
        "tasks": [
            {"key": k, "label": TASK_LABELS[k]} for k in HYGIENE_TASKS
        ],
        "items": [_hygiene_out(r, who, name) for r, who, name in rows],
    }
