from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


VenueType = Literal["church", "home", "chapel", "hall", "graveside", "other"]
PickupType = Literal["home", "hospital", "scene", "mortuary", "other"]
ArrangementStatus = Literal["draft", "confirmed", "completed", "cancelled"]
CollectionStatus = Literal["scheduled", "en_route", "collected", "cancelled"]

TIME_FIELDS = ("wake_at", "service_at", "departure_at", "committal_at")


def _strip(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()

    return stripped or None


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Datetime must include a timezone offset")

    return value


# ============================================================
# ARRANGEMENT
# ============================================================

class ArrangementBase(BaseModel):
    wake_at: datetime | None = None
    wake_venue: str | None = Field(default=None, max_length=255)
    wake_address: str | None = None
    service_at: datetime | None = None
    service_venue_type: VenueType | None = None
    service_venue: str | None = Field(default=None, max_length=255)
    service_address: str | None = None
    officiant: str | None = Field(default=None, max_length=150)
    departure_at: datetime | None = None
    departure_point: str | None = Field(default=None, max_length=255)
    committal_at: datetime | None = None
    committal_place: str | None = Field(default=None, max_length=255)
    committal_section: str | None = Field(default=None, max_length=100)
    grave_number: str | None = Field(default=None, max_length=50)
    notes: str | None = None

    @field_validator(*TIME_FIELDS, mode="after")
    @classmethod
    def needs_offset(cls, value):
        return _aware(value)

    @field_validator(
        "wake_venue",
        "wake_address",
        "service_venue",
        "service_address",
        "officiant",
        "departure_point",
        "committal_place",
        "committal_section",
        "grave_number",
        "notes",
        mode="after",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class ArrangementCreate(ArrangementBase):
    grave_confirmed: bool = False


class ArrangementUpdate(ArrangementBase):
    model_config = ConfigDict(extra="forbid")

    grave_confirmed: bool | None = None


class ArrangementTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ArrangementStatus
    reason: str | None = None

    @field_validator("reason", mode="after")
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class ArrangementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    status: str
    wake_at: datetime | None
    wake_venue: str | None
    wake_address: str | None
    service_at: datetime | None
    service_venue_type: str | None
    service_venue: str | None
    service_address: str | None
    officiant: str | None
    departure_at: datetime | None
    departure_point: str | None
    committal_at: datetime | None
    committal_place: str | None
    committal_section: str | None
    grave_number: str | None
    grave_confirmed: bool
    notes: str | None
    confirmed_at: datetime | None
    confirmed_by: UUID | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# COLLECTIONS
# ============================================================

class CollectionBase(BaseModel):
    pickup_address: str | None = None
    pickup_contact_name: str | None = Field(default=None, max_length=150)
    pickup_contact_phone: str | None = Field(default=None, max_length=30)
    vehicle_resource_id: UUID | None = None
    driver_user_id: UUID | None = None
    notes: str | None = None

    @field_validator(
        "pickup_address",
        "pickup_contact_name",
        "pickup_contact_phone",
        "notes",
        mode="after",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class CollectionCreate(CollectionBase):
    scheduled_at: datetime
    pickup_type: PickupType = "home"

    @field_validator("scheduled_at", mode="after")
    @classmethod
    def needs_offset(cls, value):
        return _aware(value)


class CollectionUpdate(CollectionBase):
    model_config = ConfigDict(extra="forbid")

    scheduled_at: datetime | None = None
    pickup_type: PickupType | None = None

    @field_validator("scheduled_at", mode="after")
    @classmethod
    def needs_offset(cls, value):
        return _aware(value)


class CollectionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CollectionStatus
    collected_at: datetime | None = None
    reason: str | None = None

    @field_validator("collected_at", mode="after")
    @classmethod
    def needs_offset(cls, value):
        return _aware(value)

    @field_validator("reason", mode="after")
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    status: str
    scheduled_at: datetime
    pickup_type: str
    pickup_address: str | None
    pickup_contact_name: str | None
    pickup_contact_phone: str | None
    vehicle_resource_id: UUID | None
    driver_user_id: UUID | None
    en_route_at: datetime | None
    collected_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# RUN SHEET
# ============================================================

class RunSheetFlag(BaseModel):
    code: str
    severity: Literal["warning", "danger"]
    message: str


class RunSheetItem(BaseModel):
    id: str
    kind: Literal[
        "collection",
        "wake",
        "service",
        "departure",
        "committal",
        "booking",
    ]
    at: datetime
    ends_at: datetime | None = None
    case_id: UUID
    case_number: str
    deceased_full_name: str
    title: str
    location: str | None = None
    address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    vehicle: str | None = None
    driver: str | None = None
    status: str
    flags: list[RunSheetFlag] = []


class RunSheetSummary(BaseModel):
    collections: int
    funerals: int
    items: int
    flagged_items: int
    overdue_collections: int


class RunSheetResponse(BaseModel):
    date: date
    timezone: str
    branch_id: UUID | None
    summary: RunSheetSummary
    items: list[RunSheetItem]
    overdue_collections: list[RunSheetItem]
