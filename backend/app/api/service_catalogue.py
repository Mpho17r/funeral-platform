from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_service import CaseService
from app.models.funeral_case import FuneralCase
from app.models.inventory import InventoryItem
from app.models.service_catalogue import (
    ServiceCatalogueItem,
    ServicePackage,
    ServicePackageItem,
)
from app.services.audit_service import create_audit_log
from app.services.inventory import InventoryError
from app.services.service_billing import sync_service_into_drafts
from app.services.stock_automation import sync_service_stock

router = APIRouter(tags=["Service catalogue"])


# ----------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------

class CatalogueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    service_type: str = Field(default="other", min_length=1, max_length=50)
    description: str | None = None
    default_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    default_quantity: int = Field(default=1, ge=1)
    price_varies: bool = False
    inventory_item_id: UUID | None = None


class CatalogueUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    service_type: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    default_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    default_quantity: int | None = Field(default=None, ge=1)
    price_varies: bool | None = None
    inventory_item_id: UUID | None = None
    is_active: bool | None = None


class PackageItemIn(BaseModel):
    catalogue_item_id: UUID
    quantity: int = Field(default=1, ge=1)


class PackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    items: list[PackageItemIn] = Field(default_factory=list, max_length=50)


class PackageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    items: list[PackageItemIn] | None = Field(default=None, max_length=50)


class AddToCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_item_id: UUID
    quantity: int | None = Field(default=None, ge=1)
    # Prices vary: leave empty to use the saved price.
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    scheduled_date: str | None = None
    provider: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class AddPackageToCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: UUID
    # Per-item price overrides, keyed by catalogue item id.
    prices: dict[UUID, Decimal] = Field(default_factory=dict)


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _biz(current_user: dict) -> UUID:
    return UUID(str(current_user["business_id"]))


def _uid(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


def _item_out(i: ServiceCatalogueItem) -> dict:
    return {
        "id": i.id,
        "name": i.name,
        "service_type": i.service_type,
        "description": i.description,
        "default_price": i.default_price,
        "default_quantity": i.default_quantity,
        "price_varies": i.price_varies,
        "inventory_item_id": i.inventory_item_id,
        "is_active": i.is_active,
    }


def _package_out(db: Session, p: ServicePackage) -> dict:
    rows = (
        db.query(ServicePackageItem, ServiceCatalogueItem)
        .join(
            ServiceCatalogueItem,
            ServiceCatalogueItem.id == ServicePackageItem.catalogue_item_id,
        )
        .filter(ServicePackageItem.package_id == p.id)
        .order_by(ServiceCatalogueItem.name)
        .all()
    )
    items = [
        {
            "catalogue_item_id": c.id,
            "name": c.name,
            "quantity": pi.quantity,
            "unit_price": c.default_price,
            "line_total": (c.default_price * pi.quantity),
            "price_varies": c.price_varies,
        }
        for pi, c in rows
    ]
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "is_active": p.is_active,
        "items": items,
        "total": sum((i["line_total"] for i in items), Decimal("0")),
    }


def _check_stock_item(db: Session, business_id: UUID, item_id: UUID | None):
    if item_id is None:
        return
    found = (
        db.query(InventoryItem.id)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.business_id == business_id,
        )
        .first()
    )
    if found is None:
        raise HTTPException(422, "Stock item not found")


def _get_item(db: Session, business_id: UUID, item_id: UUID) -> ServiceCatalogueItem:
    item = (
        db.query(ServiceCatalogueItem)
        .filter(
            ServiceCatalogueItem.id == item_id,
            ServiceCatalogueItem.business_id == business_id,
        )
        .first()
    )
    if item is None:
        raise HTTPException(404, "Catalogue item not found")
    return item


def _get_package(db: Session, business_id: UUID, package_id: UUID) -> ServicePackage:
    package = (
        db.query(ServicePackage)
        .filter(
            ServicePackage.id == package_id,
            ServicePackage.business_id == business_id,
        )
        .first()
    )
    if package is None:
        raise HTTPException(404, "Package not found")
    return package


def _set_package_items(
    db: Session, package: ServicePackage, items: list[PackageItemIn]
) -> None:
    seen: set[UUID] = set()
    for entry in items:
        if entry.catalogue_item_id in seen:
            raise HTTPException(422, "An item can be in a package only once")
        seen.add(entry.catalogue_item_id)
        _get_item(db, package.business_id, entry.catalogue_item_id)

    db.query(ServicePackageItem).filter(
        ServicePackageItem.package_id == package.id
    ).delete()
    db.flush()
    for entry in items:
        db.add(
            ServicePackageItem(
                business_id=package.business_id,
                package_id=package.id,
                catalogue_item_id=entry.catalogue_item_id,
                quantity=entry.quantity,
            )
        )


def add_item_to_case(
    db: Session,
    *,
    case: FuneralCase,
    item: ServiceCatalogueItem,
    current_user: dict,
    quantity: int | None = None,
    unit_price: Decimal | None = None,
    scheduled_date=None,
    provider: str | None = None,
    notes: str | None = None,
) -> CaseService:
    """Create a case service from a catalogue item.

    Stock is issued and draft quotes/invoices are updated as a result.
    """

    qty = quantity or item.default_quantity
    price = Decimal(str(unit_price if unit_price is not None else item.default_price))

    service = CaseService(
        business_id=case.business_id,
        case_id=case.id,
        service_type=item.service_type,
        service_name=item.name,
        description=item.description,
        status="pending",
        quantity=qty,
        unit_price=price,
        total_price=(price * qty).quantize(Decimal("0.01")),
        scheduled_date=scheduled_date,
        provider=provider,
        notes=notes,
        inventory_item_id=item.inventory_item_id,
    )
    db.add(service)
    db.flush()

    if service.inventory_item_id is not None:
        try:
            sync_service_stock(
                db,
                service=service,
                wanted=qty,
                user_id=_uid(current_user),
                case_number=case.case_number,
            )
        except InventoryError as error:
            db.rollback()
            raise HTTPException(error.status_code, error.detail)

    sync_service_into_drafts(db, service)

    create_audit_log(
        db,
        business_id=case.business_id,
        user_id=_uid(current_user),
        action="case.service_created",
        entity_type="case_service",
        entity_id=service.id,
        details={
            "case_id": str(case.id),
            "from_catalogue": str(item.id),
            "quantity": qty,
            "unit_price": str(price),
        },
        notes="Case service was added from the catalogue.",
    )
    return service


def _get_case(db: Session, business_id: UUID, case_id: UUID) -> FuneralCase:
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )
    if case is None:
        raise HTTPException(404, "Funeral case not found")
    if case.is_archived:
        raise HTTPException(409, "Archived cases cannot be changed")
    return case


def _service_out(s: CaseService) -> dict:
    return {
        "id": s.id,
        "service_name": s.service_name,
        "service_type": s.service_type,
        "quantity": s.quantity,
        "unit_price": s.unit_price,
        "total_price": s.total_price,
    }


# ----------------------------------------------------------------
# Catalogue
# ----------------------------------------------------------------

@router.get("/service-catalogue")
def list_catalogue(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    q = db.query(ServiceCatalogueItem).filter(
        ServiceCatalogueItem.business_id == _biz(current_user)
    )
    if not include_inactive:
        q = q.filter(ServiceCatalogueItem.is_active.is_(True))
    return [_item_out(i) for i in q.order_by(ServiceCatalogueItem.service_type, ServiceCatalogueItem.name)]


@router.post("/service-catalogue", status_code=201)
def create_catalogue_item(
    data: CatalogueCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    _check_stock_item(db, business_id, data.inventory_item_id)
    item = ServiceCatalogueItem(
        business_id=business_id,
        name=data.name.strip(),
        service_type=data.service_type.strip().lower(),
        description=data.description,
        default_price=data.default_price,
        default_quantity=data.default_quantity,
        price_varies=data.price_varies,
        inventory_item_id=data.inventory_item_id,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A catalogue item with that name already exists")
    create_audit_log(
        db,
        business_id=business_id,
        user_id=_uid(current_user),
        action="catalogue.item_created",
        entity_type="service_catalogue_item",
        entity_id=item.id,
        details={"name": item.name, "price": str(item.default_price)},
        notes="Catalogue item created.",
    )
    db.commit()
    return _item_out(item)


@router.patch("/service-catalogue/{item_id}")
def update_catalogue_item(
    item_id: UUID,
    data: CatalogueUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    item = _get_item(db, business_id, item_id)
    changes = data.model_dump(exclude_unset=True)
    if "inventory_item_id" in changes:
        _check_stock_item(db, business_id, changes["inventory_item_id"])
    for field, value in changes.items():
        if field == "name" and value is not None:
            value = value.strip()
        if field == "service_type" and value is not None:
            value = value.strip().lower()
        setattr(item, field, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A catalogue item with that name already exists")
    create_audit_log(
        db,
        business_id=business_id,
        user_id=_uid(current_user),
        action="catalogue.item_updated",
        entity_type="service_catalogue_item",
        entity_id=item.id,
        details={k: str(v) for k, v in changes.items()},
        notes="Catalogue item updated.",
    )
    db.commit()
    return _item_out(item)


# ----------------------------------------------------------------
# Packages
# ----------------------------------------------------------------

@router.get("/service-packages")
def list_packages(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    q = db.query(ServicePackage).filter(
        ServicePackage.business_id == _biz(current_user)
    )
    if not include_inactive:
        q = q.filter(ServicePackage.is_active.is_(True))
    return [_package_out(db, p) for p in q.order_by(ServicePackage.name)]


@router.post("/service-packages", status_code=201)
def create_package(
    data: PackageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    package = ServicePackage(
        business_id=business_id,
        name=data.name.strip(),
        description=data.description,
    )
    db.add(package)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A package with that name already exists")
    _set_package_items(db, package, data.items)
    db.commit()
    return _package_out(db, package)


@router.patch("/service-packages/{package_id}")
def update_package(
    package_id: UUID,
    data: PackageUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    package = _get_package(db, _biz(current_user), package_id)
    changes = data.model_dump(exclude_unset=True)
    items = changes.pop("items", None)
    for field, value in changes.items():
        setattr(package, field, value.strip() if field == "name" and value else value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A package with that name already exists")
    if items is not None:
        _set_package_items(db, package, data.items or [])
    db.commit()
    return _package_out(db, package)


# ----------------------------------------------------------------
# Adding to a case
# ----------------------------------------------------------------

@router.post("/cases/{case_id}/services/from-catalogue", status_code=201)
def add_catalogue_item_to_case(
    case_id: UUID,
    data: AddToCase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    case = _get_case(db, business_id, case_id)
    item = _get_item(db, business_id, data.catalogue_item_id)
    if not item.is_active:
        raise HTTPException(409, "That catalogue item is switched off")

    from datetime import date as _date

    scheduled = None
    if data.scheduled_date:
        try:
            scheduled = _date.fromisoformat(data.scheduled_date)
        except ValueError:
            raise HTTPException(422, "scheduled_date must be YYYY-MM-DD")

    service = add_item_to_case(
        db,
        case=case,
        item=item,
        current_user=current_user,
        quantity=data.quantity,
        unit_price=data.unit_price,
        scheduled_date=scheduled,
        provider=data.provider,
        notes=data.notes,
    )
    db.commit()
    return _service_out(service)


@router.post("/cases/{case_id}/services/from-package", status_code=201)
def add_package_to_case(
    case_id: UUID,
    data: AddPackageToCase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    case = _get_case(db, business_id, case_id)
    package = _get_package(db, business_id, data.package_id)
    if not package.is_active:
        raise HTTPException(409, "That package is switched off")

    rows = (
        db.query(ServicePackageItem, ServiceCatalogueItem)
        .join(
            ServiceCatalogueItem,
            ServiceCatalogueItem.id == ServicePackageItem.catalogue_item_id,
        )
        .filter(ServicePackageItem.package_id == package.id)
        .all()
    )
    if not rows:
        raise HTTPException(409, "That package has no items")

    created = []
    for pi, item in rows:
        created.append(
            add_item_to_case(
                db,
                case=case,
                item=item,
                current_user=current_user,
                quantity=pi.quantity,
                unit_price=data.prices.get(item.id),
            )
        )
    db.commit()
    return {
        "package": package.name,
        "services": [_service_out(s) for s in created],
    }
