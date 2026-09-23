from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MEMBERSHIP_STATUSES = (
    "active",
    "arrears",
    "lapsed",
    "cancelled",
)


class MembershipCreate(BaseModel):
    member_id: UUID
    plan_id: UUID
    membership_number: str = Field(
        min_length=1,
        max_length=50,
    )
    start_date: date = Field(
        default_factory=date.today,
    )
    status: str = "active"
    next_due_date: date | None = None

    @field_validator("membership_number")
    @classmethod
    def validate_membership_number(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Membership number cannot be empty")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in MEMBERSHIP_STATUSES:
            raise ValueError(
                "Membership status must be one of: "
                "active, arrears, lapsed, cancelled"
            )

        return value


class MembershipUpdate(BaseModel):
    membership_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    plan_id: UUID | None = None
    start_date: date | None = None
    status: str | None = None
    next_due_date: date | None = None
    arrears_since: date | None = None
    lapsed_at: date | None = None
    cancelled_at: date | None = None

    @field_validator("membership_number")
    @classmethod
    def validate_membership_number(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Membership number cannot be empty")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in MEMBERSHIP_STATUSES:
            raise ValueError(
                "Membership status must be one of: "
                "active, arrears, lapsed, cancelled"
            )

        return value


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    member_id: UUID
    plan_id: UUID
    membership_number: str
    start_date: date
    status: str
    next_due_date: date | None
    arrears_since: date | None
    lapsed_at: date | None
    cancelled_at: date | None
    created_at: datetime
    updated_at: datetime
