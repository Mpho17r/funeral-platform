from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


PAYMENT_METHODS = (
    "cash",
    "card",
    "eft",
    "debit_order",
    "other",
)


class MembershipPaymentCreate(BaseModel):
    membership_id: UUID
    contribution_id: UUID | None = None
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        max_digits=12,
    )
    payment_method: str = "cash"
    reference: str | None = Field(
        default=None,
        max_length=255,
    )
    payment_date: date = Field(default_factory=date.today)
    notes: str | None = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in PAYMENT_METHODS:
            raise ValueError(
                "Payment method must be one of: "
                "cash, card, eft, debit_order, other"
            )

        return value


class MembershipPaymentUpdate(BaseModel):
    amount: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
        max_digits=12,
    )
    payment_method: str | None = None
    reference: str | None = Field(
        default=None,
        max_length=255,
    )
    payment_date: date | None = None
    notes: str | None = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in PAYMENT_METHODS:
            raise ValueError(
                "Payment method must be one of: "
                "cash, card, eft, debit_order, other"
            )

        return value


class MembershipPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    membership_id: UUID
    contribution_id: UUID | None
    amount: Decimal
    payment_method: str
    reference: str | None
    payment_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime

