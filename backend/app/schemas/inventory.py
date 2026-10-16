from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


ItemCategory = Literal[
    "coffin",
    "casket",
    "flowers",
    "clothing",
    "consumable",
    "stationery",
    "other",
]

# Movement types a caller may ask for. Adjustments have their own
# permission, so they are a separate request.
StockMovementType = Literal["receipt", "issue", "return"]


def _strip(value):
    if value is None:
        return None

    stripped = value.strip()

    if not stripped:
        raise ValueError("Cannot be blank")

    return stripped


def _clean_sku(value):
    if value is None:
        return None

    cleaned = value.strip().upper()

    if not cleaned or " " in cleaned:
        raise ValueError("SKU cannot be blank or contain spaces")

    return cleaned


# ============================================================
# SUPPLIERS
# ============================================================

class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        return _strip(value)


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_person: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        return _strip(value)


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================
# ITEMS
# ============================================================

Quantity = Decimal


class InventoryItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    category: ItemCategory
    unit: str = Field(default="each", min_length=1, max_length=30)
    description: str | None = None
    supplier_id: UUID | None = None
    branch_id: UUID | None = None
    reorder_level: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )

    # Stock already on the shelf. Recorded as an opening receipt so
    # the ledger explains the quantity from day one.
    opening_quantity: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=12, decimal_places=2
    )

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, value):
        return _clean_sku(value)

    @field_validator("name", "unit")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class InventoryItemUpdate(BaseModel):
    """The SKU, quantity and branch are not editable here: stock
    changes through movements and the branch through a transfer."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: ItemCategory | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = None
    supplier_id: UUID | None = None
    reorder_level: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )

    @field_validator("name", "unit")
    @classmethod
    def strip_text(cls, value):
        return _strip(value)


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    branch_id: UUID | None
    supplier_id: UUID | None
    sku: str
    name: str
    category: str
    unit: str
    description: str | None
    quantity_on_hand: Decimal
    reorder_level: Decimal
    unit_cost: Decimal | None
    is_low_stock: bool = False
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================
# MOVEMENTS
# ============================================================

class StockMovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movement_type: StockMovementType
    quantity: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2
    )
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    supplier_id: UUID | None = None
    case_id: UUID | None = None
    reference: str | None = Field(default=None, max_length=100)
    reason: str | None = None


class StockAdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Signed: positive adds stock, negative removes it.
    quantity: Decimal = Field(
        ..., max_digits=12, decimal_places=2
    )
    reason: str = Field(..., min_length=1)

    @field_validator("quantity")
    @classmethod
    def not_zero(cls, value):
        if value == 0:
            raise ValueError("An adjustment cannot be zero")

        return value

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value):
        return _strip(value)


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    item_id: UUID
    movement_type: str
    quantity: Decimal
    balance_after: Decimal
    unit_cost: Decimal | None
    supplier_id: UUID | None
    case_id: UUID | None
    reference: str | None
    reason: str | None
    created_by: UUID | None
    created_at: datetime
