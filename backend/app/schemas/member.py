from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


MEMBER_STATUSES = (
    "active",
    "arrears",
    "lapsed",
    "cancelled",
    "deceased",
)


class MemberCreate(BaseModel):
    member_number: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    id_number: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    join_date: date = Field(default_factory=date.today)
    status: str = "active"

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
    join_date: date | None = None
    status: str | None = None

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
    join_date: date
    status: str
    created_at: datetime
    updated_at: datetime
