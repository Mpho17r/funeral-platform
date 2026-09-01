from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_CASE_STATUSES = {
    "open",
    "confirmed",
    "in_progress",
    "completed",
    "closed",
    "cancelled",
}


class FuneralCaseCreate(BaseModel):

    case_number: str = Field(..., min_length=1, max_length=50)
    deceased_full_name: str = Field(..., min_length=1, max_length=200)

    date_of_birth: date | None = None
    date_of_death: date | None = None

    next_of_kin_name: str | None = Field(
        default=None,
        max_length=200,
    )

    next_of_kin_phone: str | None = Field(
        default=None,
        max_length=30,
    )

    funeral_date: date | None = None

    funeral_venue: str | None = Field(
        default=None,
        max_length=255,
    )

    status: str = "open"

    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_CASE_STATUSES:
            raise ValueError(
                f"Invalid case status. Allowed values: "
                f"{', '.join(sorted(ALLOWED_CASE_STATUSES))}"
            )

        return value


class FuneralCaseUpdate(BaseModel):

    case_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    deceased_full_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    date_of_birth: date | None = None
    date_of_death: date | None = None

    next_of_kin_name: str | None = Field(
        default=None,
        max_length=200,
    )

    next_of_kin_phone: str | None = Field(
        default=None,
        max_length=30,
    )

    funeral_date: date | None = None

    funeral_venue: str | None = Field(
        default=None,
        max_length=255,
    )

    status: str | None = None

    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip().lower()

        if value not in ALLOWED_CASE_STATUSES:
            raise ValueError(
                f"Invalid case status. Allowed values: "
                f"{', '.join(sorted(ALLOWED_CASE_STATUSES))}"
            )

        return value


class FuneralCaseResponse(BaseModel):

    id: UUID
    business_id: UUID
    case_number: str
    deceased_full_name: str

    date_of_birth: date | None = None
    date_of_death: date | None = None

    next_of_kin_name: str | None = None
    next_of_kin_phone: str | None = None

    funeral_date: date | None = None
    funeral_venue: str | None = None

    status: str
    notes: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)