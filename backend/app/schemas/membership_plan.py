from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MembershipPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    monthly_contribution: Decimal = Field(
        ge=0,
        decimal_places=2,
        max_digits=12,
    )
    is_active: bool = True
    waiting_natural_months: int = Field(default=0, ge=0, le=60)
    waiting_accidental_months: int = Field(default=0, ge=0, le=60)
    waiting_suicide_months: int = Field(default=0, ge=0, le=60)
    waiting_upgrade_months: int = Field(default=0, ge=0, le=60)


class MembershipPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    monthly_contribution: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=12,
    )
    is_active: bool | None = None
    waiting_natural_months: int | None = Field(default=None, ge=0, le=60)
    waiting_accidental_months: int | None = Field(
        default=None, ge=0, le=60
    )
    waiting_suicide_months: int | None = Field(default=None, ge=0, le=60)
    waiting_upgrade_months: int | None = Field(default=None, ge=0, le=60)


class MembershipPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    description: str | None
    monthly_contribution: Decimal
    is_active: bool
    waiting_natural_months: int
    waiting_accidental_months: int
    waiting_suicide_months: int
    waiting_upgrade_months: int
    created_at: datetime
    updated_at: datetime
