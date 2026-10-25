from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


LocationKind = Literal[
    "fridge",
    "cold_room",
    "preparation_room",
    "chapel_of_rest",
    "other",
]
ReceivedFrom = Literal[
    "home", "hospital", "state_mortuary", "scene", "other"
]
Procedure = Literal["washed", "embalmed", "dressed", "other"]
EventKind = Literal[
    "moved", "prepared", "identified", "temperature", "note"
]


def _strip(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()

    return stripped or None


# ============================================================
# LOCATIONS
# ============================================================

class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    kind: LocationKind
    capacity: int | None = Field(default=None, gt=0, le=500)
    branch_id: UUID | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        stripped = value.strip()

        if not stripped:
            raise ValueError("Name cannot be blank")

        return stripped

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        return _strip(value)


class LocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    kind: LocationKind | None = None
    capacity: int | None = Field(default=None, gt=0, le=500)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if value is None:
            return None

        stripped = value.strip()

        if not stripped:
            raise ValueError("Name cannot be blank")

        return stripped

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        return _strip(value)


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID | None
    name: str
    kind: str
    capacity: int | None
    notes: str | None
    is_active: bool
    occupied: int = 0
    shared_with: list[UUID] = []
    created_at: datetime
    updated_at: datetime


# ============================================================
# REMAINS
# ============================================================

class RemainsCreate(BaseModel):
    """Taking remains into care."""

    model_config = ConfigDict(extra="forbid")

    tag_number: str | None = Field(default=None, max_length=50)
    received_at: datetime | None = None
    received_from_type: ReceivedFrom
    received_from: str | None = None
    collected_by_name: str | None = Field(default=None, max_length=150)
    vehicle_resource_id: UUID | None = None
    condition_notes: str | None = None
    belongings: str | None = None
    location_id: UUID | None = None

    @field_validator(
        "tag_number",
        "received_from",
        "collected_by_name",
        "condition_notes",
        "belongings",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class RemainsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received_from_type: ReceivedFrom | None = None
    received_from: str | None = None
    collected_by_name: str | None = Field(default=None, max_length=150)
    vehicle_resource_id: UUID | None = None
    condition_notes: str | None = None
    belongings: str | None = None

    @field_validator(
        "received_from",
        "collected_by_name",
        "condition_notes",
        "belongings",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class CustodyEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventKind
    occurred_at: datetime | None = None
    to_location_id: UUID | None = None
    handed_over_by_name: str | None = Field(default=None, max_length=150)
    accepted_by_name: str | None = Field(default=None, max_length=150)
    procedure: Procedure | None = None
    temperature_c: Decimal | None = Field(
        default=None, ge=-40, le=60, decimal_places=1
    )
    identified_by_name: str | None = Field(default=None, max_length=150)
    identified_relationship: str | None = Field(
        default=None, max_length=100
    )
    notes: str | None = None

    @field_validator(
        "identified_by_name",
        "identified_relationship",
        "handed_over_by_name",
        "accepted_by_name",
        "notes",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class ReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Typed in again by the person releasing, not copied from the
    # screen, so the wrong tag cannot slip through.
    confirm_tag_number: str = Field(min_length=1, max_length=50)
    # A second, independent check against the body itself: the
    # deceased's surname or ID number as read from the toe tag or
    # wristband. Two matching identifiers are what stops a mix-up.
    confirm_deceased_identifier: str = Field(min_length=1, max_length=50)
    released_to_name: str = Field(min_length=1, max_length=150)
    # Who the remains went to must always be traceable.
    released_to_id_number: str = Field(min_length=1, max_length=50)
    released_to_relationship: str | None = Field(
        default=None, max_length=100
    )
    released_at: datetime | None = None
    override_reason: str | None = None

    @field_validator(
        "confirm_tag_number",
        "confirm_deceased_identifier",
        "released_to_name",
        "released_to_id_number",
    )
    @classmethod
    def required_text(cls, value):
        stripped = value.strip()

        if not stripped:
            raise ValueError("This field cannot be blank")

        return stripped

    @field_validator(
        "released_to_relationship",
        "override_reason",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class CustodyEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    from_location_id: UUID | None
    to_location_id: UUID | None
    handed_over_by_name: str | None
    accepted_by_name: str | None
    procedure: str | None
    temperature_c: Decimal | None
    performed_by: UUID | None
    occurred_at: datetime
    notes: str | None
    created_at: datetime


class CoolingStatus(BaseModel):
    cooled: bool
    cooling_due_at: datetime | None
    cooling_overdue: bool


class RemainsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    tag_number: str
    status: str
    received_at: datetime
    received_from_type: str
    received_from: str | None
    collected_by_name: str | None
    vehicle_resource_id: UUID | None
    condition_notes: str | None
    belongings: str | None
    current_location_id: UUID | None
    cooled_at: datetime | None
    identified_at: datetime | None
    identified_by_name: str | None
    identified_relationship: str | None
    received_by: UUID | None
    released_at: datetime | None
    released_by: UUID | None
    released_to_name: str | None
    released_to_id_number: str | None
    released_to_relationship: str | None
    release_override_reason: str | None
    created_at: datetime
    updated_at: datetime


class RemainsDetail(BaseModel):
    remains: RemainsResponse
    cooling: CoolingStatus
    release_blockers: list[str]
    events: list[CustodyEventResponse]


# ============================================================
# BOARD
# ============================================================

class BoardEntry(BaseModel):
    remains_id: UUID
    case_id: UUID
    case_number: str
    deceased_full_name: str
    tag_number: str
    location_id: UUID | None
    location_name: str | None
    received_at: datetime
    identified: bool
    cooled: bool
    cooling_due_at: datetime | None
    cooling_overdue: bool


class BoardResponse(BaseModel):
    in_custody: int
    cooling_overdue: int
    entries: list[BoardEntry]
    locations: list[LocationResponse]


# ============================================================
# MORTUARY BELONGINGS REGISTER
# ============================================================

class MortuaryBelongingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, gt=0, le=10000)
    condition: str | None = Field(default=None, max_length=2000)
    storage_location: str = Field(min_length=1, max_length=150)
    received_from: str | None = Field(default=None, max_length=150)
    received_by_name: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("description", "storage_location")
    @classmethod
    def required_text_cannot_be_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator(
        "condition",
        "received_from",
        "received_by_name",
        "notes",
    )
    @classmethod
    def clean_optional_text(cls, value):
        return _strip(value)


class MortuaryBelongingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: int | None = Field(default=None, gt=0, le=10000)
    condition: str | None = Field(default=None, max_length=2000)
    storage_location: str | None = Field(
        default=None, min_length=1, max_length=150
    )
    received_from: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("description", "storage_location")
    @classmethod
    def clean_required_text_when_provided(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("condition", "received_from", "notes")
    @classmethod
    def clean_optional_text(cls, value):
        return _strip(value)


class MortuaryBelongingReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    returned_to_name: str = Field(min_length=1, max_length=150)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("returned_to_name")
    @classmethod
    def clean_recipient_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Recipient name cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        return _strip(value)


class MortuaryBelongingTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transferred_to_location: str = Field(min_length=1, max_length=150)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("transferred_to_location")
    @classmethod
    def clean_destination(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Destination cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value):
        return _strip(value)


class MortuaryBelongingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    remains_id: UUID
    description: str
    quantity: int
    condition: str | None
    storage_location: str
    received_from: str | None
    received_by: UUID | None
    received_by_name: str | None
    received_at: datetime
    status: str
    returned_to_name: str | None
    returned_by: UUID | None
    returned_at: datetime | None
    transferred_to_location: str | None
    transferred_by: UUID | None
    transferred_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
