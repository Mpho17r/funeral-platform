from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.services.identity import normalise_identity_number


MEMBER_STATUSES = (
    "active",
    "arrears",
    "lapsed",
    "cancelled",
    "deceased",
)


def _clean_region(value):
    if value is None:
        return None
    value = " ".join(str(value).split())
    return value or None


class MemberCreate(BaseModel):
    member_number: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    id_number: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    region: str | None = Field(default=None, max_length=100)
    join_date: date = Field(default_factory=date.today)
    status: str = "active"

    # Defaults to the creator's branch. Moving a member later uses the
    # transfer endpoint.
    branch_id: UUID | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in MEMBER_STATUSES:
            raise ValueError(
                "Member status must be one of: "
                "active, arrears, lapsed, cancelled, deceased"
            )

        return value

    @field_validator("region", mode="after")
    @classmethod
    def clean_region(cls, value):
        return _clean_region(value)

    @field_validator("id_number", mode="after")
    @classmethod
    def check_identity_number(cls, value: str | None) -> str | None:
        return normalise_identity_number(value)



class MemberUpdate(BaseModel):
    member_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    id_number: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    region: str | None = Field(default=None, max_length=100)
    join_date: date | None = None
    status: str | None = None

    @field_validator("region", mode="after")
    @classmethod
    def clean_region(cls, value):
        return _clean_region(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in MEMBER_STATUSES:
            raise ValueError(
                "Member status must be one of: "
                "active, arrears, lapsed, cancelled, deceased"
            )

        return value

    @field_validator("id_number", mode="after")
    @classmethod
    def check_identity_number(cls, value: str | None) -> str | None:
        return normalise_identity_number(value)



class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    member_number: str
    first_name: str
    last_name: str
    id_number: str | None
    date_of_birth: date | None
    phone: str | None
    email: EmailStr | None
    address: str | None
    region: str | None = None
    join_date: date
    status: str
    branch_id: UUID | None = None
    archived_at: datetime | None = None
    archive_reason: str | None = None
    anonymised_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MemberAnonymise(BaseModel):
    """Permanent removal of a former member's personal details. The
    member number must be typed back so it cannot be done by accident."""

    model_config = ConfigDict(extra="forbid")

    confirm_member_number: str = Field(min_length=1, max_length=50)
