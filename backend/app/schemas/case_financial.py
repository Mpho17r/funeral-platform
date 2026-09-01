from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseFinancialCreate(BaseModel):
    status: str = "draft"

    subtotal: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )

    discount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )

    tax: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )

    notes: str | None = None


class CaseFinancialUpdate(BaseModel):
    status: str | None = None

    subtotal: Decimal | None = Field(
        default=None,
        ge=0,
    )

    discount: Decimal | None = Field(
        default=None,
        ge=0,
    )

    tax: Decimal | None = Field(
        default=None,
        ge=0,
    )

    notes: str | None = None


class CaseFinancialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID

    status: str

    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal

    amount_paid: Decimal
    balance: Decimal
    credit: Decimal

    notes: str | None

    created_at: datetime
    updated_at: datetime
