from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


PAYMENT_METHODS = (
    "cash",
    "eft",
    "card",
    "insurance",
    "other",
)


class CasePaymentCreate(BaseModel):

    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        max_digits=12,
    )

    payment_method: str = Field(
        default="cash",
        min_length=1,
        max_length=50,
    )

    reference: str | None = Field(
        default=None,
        max_length=255,
    )

    payment_date: date = Field(
        default_factory=date.today,
    )

    notes: str | None = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in PAYMENT_METHODS:
            raise ValueError(
                "Payment method must be one of: "
                "cash, eft, card, insurance, other"
            )

        return value


class CasePaymentUpdate(BaseModel):

    amount: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
        max_digits=12,
    )

    payment_method: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    reference: str | None = Field(
        default=None,
        max_length=255,
    )

    payment_date: date | None = None

    notes: str | None = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in PAYMENT_METHODS:
            raise ValueError(
                "Payment method must be one of: "
                "cash, eft, card, insurance, other"
            )

        return value


class CasePaymentResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    amount: Decimal
    payment_method: str
    reference: str | None
    payment_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime