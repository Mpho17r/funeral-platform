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


class MembershipPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    description: str | None
    monthly_contribution: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
