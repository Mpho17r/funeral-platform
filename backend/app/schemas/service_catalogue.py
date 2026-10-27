from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.financial_document import DocumentType


class CatalogItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    service_type: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    unit_price: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    default_quantity: int = Field(default=1, ge=1, le=1000)
    price_varies: bool = False
    is_standard: bool = False
    inventory_item_id: UUID | None = None
    provider: str | None = Field(default=None, max_length=255)


class CatalogItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    service_type: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    default_quantity: int | None = Field(default=None, ge=1, le=1000)
    price_varies: bool | None = None
    is_standard: bool | None = None
    inventory_item_id: UUID | None = None
    provider: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class CatalogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    service_type: str
    description: str | None
    unit_price: Decimal
    default_quantity: int
    price_varies: bool
    is_standard: bool
    inventory_item_id: UUID | None
    provider: str | None
    is_active: bool


class PackageLine(BaseModel):
    catalog_item_id: UUID
    quantity: int = Field(default=1, ge=1, le=1000)


class PackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    items: list[PackageLine] = Field(default_factory=list, max_length=100)


class PackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None
    items: list[PackageLine] | None = Field(default=None, max_length=100)


class PackageItemResponse(BaseModel):
    catalog_item_id: UUID
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class PackageResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    total: Decimal
    items: list[PackageItemResponse]


class AddFromCatalog(BaseModel):
    catalog_item_id: UUID
    quantity: int | None = Field(default=None, ge=1, le=1000)
    # Prices vary: the usual price can be overridden for this case.
    unit_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    scheduled_date: date | None = None
    notes: str | None = None


class AddPackage(BaseModel):
    package_id: UUID


class BillFromServices(BaseModel):
    document_type: DocumentType
    discount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    tax: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    valid_until: date | None = None
    due_date: date | None = None
    notes: str | None = None
