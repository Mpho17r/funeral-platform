from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


BENEFIT_TYPES = (
    "monetary",
    "included_service",
    "quantity",
    "other",
)


class MembershipPlanBenefitCreate(BaseModel):
    plan_id: UUID
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    benefit_type: str = "other"
    monetary_limit: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=12,
    )
    quantity_limit: int | None = Field(
        default=None,
        ge=0,
    )
    is_included: bool = True
    is_active: bool = True

    @model_validator(mode="after")
    def validate_limits(self):
        if self.benefit_type not in BENEFIT_TYPES:
            raise ValueError(
                "Benefit type must be one of: "
                "monetary, included_service, quantity, other"
            )

        if self.benefit_type == "monetary" and self.monetary_limit is None:
            raise ValueError(
                "Monetary benefits require a monetary limit"
            )

        if self.benefit_type == "quantity" and self.quantity_limit is None:
            raise ValueError(
                "Quantity benefits require a quantity limit"
            )

        return self


class MembershipPlanBenefitUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    description: str | None = None
    benefit_type: str | None = None
    monetary_limit: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=12,
    )
    quantity_limit: int | None = Field(
        default=None,
        ge=0,
    )
    is_included: bool | None = None
    is_active: bool | None = None


class MembershipPlanBenefitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    plan_id: UUID
    name: str
    description: str | None
    benefit_type: str
    monetary_limit: Decimal | None
    quantity_limit: int | None
    is_included: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
