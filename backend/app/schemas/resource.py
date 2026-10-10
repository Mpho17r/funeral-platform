from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ResourceType = Literal["vehicle", "venue", "equipment"]


def _require_timezone(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError(
            "Datetime must include a timezone offset"
        )
    return value


# ============================================================
# RESOURCES
# ============================================================

class ResourceCreate(BaseModel):
    resource_type: ResourceType
    name: str = Field(..., min_length=1, max_length=200)
    identifier: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class ResourceUpdate(BaseModel):
    # resource_type is intentionally immutable: bookings depend on it.
    name: str | None = Field(default=None, min_length=1, max_length=200)
    identifier: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    resource_type: str
    name: str
    identifier: str | None
    capacity: int | None
    location: str | None
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# BOOKINGS
# ============================================================

class ResourceBookingCreate(BaseModel):
    resource_id: UUID
    driver_user_id: UUID | None = None
    starts_at: datetime
    ends_at: datetime
    purpose: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_timezone(cls, value):
        return _require_timezone(value)


class ResourceBookingUpdate(BaseModel):
    # The booked resource cannot be changed; cancel and re-book instead.
    driver_user_id: UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    purpose: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_timezone(cls, value):
        return _require_timezone(value)


class ResourceBookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    resource_id: UUID
    driver_user_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    purpose: str | None
    status: str
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class AvailabilityResponse(BaseModel):
    resource_id: UUID
    starts_at: datetime
    ends_at: datetime
    is_available: bool
    conflicts: list[ResourceBookingResponse]


# ============================================================
# DASHBOARD SIGNALS
# ============================================================

class ResourceSignalCase(BaseModel):
    case_id: UUID
    case_number: str
    funeral_date: str


class ResourceSignalsResponse(BaseModel):
    window_days: int
    funerals_without_vehicle: list[ResourceSignalCase]
    funerals_without_venue: list[ResourceSignalCase]
    vehicle_bookings_without_driver: int
