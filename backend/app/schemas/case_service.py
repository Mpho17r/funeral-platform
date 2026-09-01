from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseServiceCreate(BaseModel):
    service_type: str = Field(..., min_length=1, max_length=50)
    service_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="pending", max_length=50)
    quantity: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    scheduled_date: date | None = None
    provider: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CaseServiceUpdate(BaseModel):
    service_type: str | None = Field(default=None, min_length=1, max_length=50)
    service_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, max_length=50)
    quantity: int | None = Field(default=None, ge=1)
    unit_price: Decimal | None = Field(default=None, ge=0)
    scheduled_date: date | None = None
    provider: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CaseServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    service_type: str
    service_name: str
    description: str | None
    status: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    scheduled_date: date | None
    provider: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
