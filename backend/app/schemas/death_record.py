from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


IdType = Literal["sa_id", "passport", "other"]
PlaceType = Literal["home", "hospital", "public_place", "other"]
Manner = Literal["pending", "natural", "unnatural"]
ForensicStatus = Literal[
    "not_applicable", "referred", "post_mortem_done", "released"
]
Disposal = Literal["burial", "cremation", "repatriation"]
ItemStatus = Literal["pending", "obtained", "not_applicable"]


def _strip(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()

    return stripped or None


class DeathRecordBase(BaseModel):
    deceased_id_number: str | None = Field(default=None, max_length=50)
    time_of_death: time | None = None
    place_of_death_type: PlaceType | None = None
    place_of_death: str | None = None
    cause_of_death: str | None = None
    certifier_name: str | None = Field(default=None, max_length=150)
    police_case_number: str | None = Field(default=None, max_length=50)
    informant_name: str | None = Field(default=None, max_length=150)
    informant_relationship: str | None = Field(
        default=None, max_length=100
    )
    informant_phone: str | None = Field(default=None, max_length=30)
    informant_id_number: str | None = Field(default=None, max_length=50)
    notes: str | None = None

    @field_validator(
        "deceased_id_number",
        "place_of_death",
        "cause_of_death",
        "certifier_name",
        "police_case_number",
        "informant_name",
        "informant_relationship",
        "informant_phone",
        "informant_id_number",
        "notes",
        mode="after",
    )
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class DeathRecordCreate(DeathRecordBase):
    deceased_id_type: IdType = "sa_id"
    manner_of_death: Manner = "pending"
    forensic_status: ForensicStatus = "not_applicable"
    infectious_remains: bool = False
    disposal_method: Disposal = "burial"


class DeathRecordUpdate(DeathRecordBase):
    model_config = ConfigDict(extra="forbid")

    deceased_id_type: IdType | None = None
    manner_of_death: Manner | None = None
    forensic_status: ForensicStatus | None = None
    infectious_remains: bool | None = None
    disposal_method: Disposal | None = None


class DeathRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    deceased_id_type: str
    deceased_id_number: str | None
    time_of_death: time | None
    place_of_death_type: str | None
    place_of_death: str | None
    manner_of_death: str
    cause_of_death: str | None
    certifier_name: str | None
    forensic_status: str
    police_case_number: str | None
    infectious_remains: bool
    disposal_method: str
    informant_name: str | None
    informant_relationship: str | None
    informant_phone: str | None
    informant_id_number: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# PAPERWORK
# ============================================================

class PaperworkItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=150)
    required: bool = False
    notes: str | None = None

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        stripped = value.strip()

        if not stripped:
            raise ValueError("Label cannot be blank")

        return stripped


class PaperworkItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ItemStatus | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    obtained_on: date | None = None
    document_id: UUID | None = None
    notes: str | None = None
    # Only custom items may be renamed or have this changed.
    label: str | None = Field(default=None, min_length=1, max_length=150)
    required: bool | None = None

    @field_validator("reference_number", "notes", mode="after")
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class PaperworkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    item_type: str
    label: str
    required: bool
    sort_order: int
    status: str
    reference_number: str | None
    obtained_on: date | None
    obtained_by: UUID | None
    document_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PaperworkSummary(BaseModel):
    required_total: int
    required_done: int
    outstanding: list[str]
    ready: bool


class PaperworkResponse(BaseModel):
    items: list[PaperworkItemResponse]
    summary: PaperworkSummary
