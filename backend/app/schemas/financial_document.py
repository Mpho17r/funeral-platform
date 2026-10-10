from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DocumentType = Literal["quote", "invoice"]


# ============================================================
# LINES
# ============================================================

class LineCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(
        default=Decimal("1"), gt=0, decimal_places=2
    )
    unit_price: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    case_service_id: UUID | None = None


class LineUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)


class LineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    position: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    case_service_id: UUID | None


# ============================================================
# DOCUMENTS
# ============================================================

class DocumentCreate(BaseModel):
    document_type: DocumentType
    discount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    tax: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    valid_until: date | None = None
    due_date: date | None = None
    notes: str | None = None
    lines: list[LineCreate] = Field(default_factory=list, max_length=200)


class DocumentUpdate(BaseModel):
    discount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    tax: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    valid_until: date | None = None
    due_date: date | None = None
    notes: str | None = None


class DocumentVoid(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    document_type: str
    number: str | None
    status: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    valid_until: date | None
    due_date: date | None
    source_quote_id: UUID | None
    issued_at: datetime | None
    issued_by: UUID | None
    accepted_at: datetime | None
    voided_at: datetime | None
    voided_by: UUID | None
    void_reason: str | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[LineResponse] = Field(default_factory=list)


# ============================================================
# RECEIPTS
# ============================================================

class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    payment_id: UUID
    receipt_number: str
    case_number: str
    amount: Decimal
    payment_method: str
    payment_reference: str | None
    payment_date: date
    issued_by: UUID | None
    issued_at: datetime
