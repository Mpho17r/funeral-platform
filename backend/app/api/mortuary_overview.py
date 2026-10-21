"""Dashboard feed and cold-room temperature log for the mortuary team."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.mortuary import COLD_LOCATION_KINDS, MortuaryLocation
from app.services.audit_service import create_audit_log
from app.services.mortuary import now_utc
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
    db.commit()

    return {
        "id": str(reading.id),
        "location_id": str(location.id),
        "temperature_c": float(reading.temperature_c),
        "recorded_at": reading.recorded_at.isoformat(),
    }
