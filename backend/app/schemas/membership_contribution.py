from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTRIBUTION_STATUSES = (
    "due",
    "partially_paid",
    "paid",
    "overdue",
    "waived",
    "refunded",
)


class MembershipContributionCreate(BaseModel):
    membership_id: UUID
    contribution_period: date
    amount_due: Decimal = Field(
        ge=0,
        decimal_places=2,
        max_digits=12,
    )
    due_date: date
    status: str = "due"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in {"due", "overdue"}:
            raise ValueError(
                "New contributions must start as due or overdue."
            )

        return value


class MembershipContributionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_due: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=12,
    )

    due_date: date | None = None


class MembershipContributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    membership_id: UUID
    contribution_period: date
    amount_due: Decimal
    amount_paid: Decimal
    due_date: date
    status: str
    paid_at: date | None
    created_at: datetime
    updated_at: datetime
