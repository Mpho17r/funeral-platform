from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.financial_documents import (
    audit_document,
    document_response,
    fail,
    get_case_or_404,
    get_document_or_404,
    validate_type_fields,
)
from app.api.services import create_service
from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_service import CaseService
from app.models.financial_document import FinancialDocument
from app.models.inventory import InventoryItem
from app.models.service_catalogue import (
    CatalogItem,
    ServicePackage,
    ServicePackageItem,
)
from app.schemas.case_service import CaseServiceCreate, CaseServiceResponse
from app.schemas.financial_document import DocumentResponse
from app.schemas.service_catalogue import (
    AddFromCatalog,
    AddPackage,
    BillFromServices,
    CatalogItemCreate,
    CatalogItemResponse,
    CatalogItemUpdate,
    PackageCreate,
    PackageResponse,
    PackageUpdate,
)
from app.services.audit_service import create_audit_log
from app.services.financial_documents import (
    DocumentError,
    ensure_draft,
    money,
    recalculate_document,
)
from app.services.service_catalogue import (
    already_billed_ids,
    billable_services,
    line_from_service,
    sync_draft_with_services,
)

router = APIRouter(tags=["Service Catalogue"])


def _biz(user: dict) -> UUID:
    return UUID(str(user["business_id"]))


def _uid(user: dict) -> UUID:
    return UUID(str(user["user_id"]))


def _check_stock_item(db, business_id, item_id):
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


# ============================================================
# PRICE LIST
# ============================================================

@router.get("/service-catalog", response_model=list[CatalogItemResponse])
def list_catalog(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    query = db.query(CatalogItem).filter(
        CatalogItem.business_id == _biz(current_user)
    )
    if not include_inactive:
        query = query.filter(CatalogItem.is_active.is_(True))
    return query.order_by(CatalogItem.service_type, CatalogItem.name).all()


@router.post(
    "/service-catalog",
    response_model=CatalogItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_item(
    data: CatalogItemCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.catalog")),
):
    business_id = _biz(current_user)
    _check_stock_item(db, business_id, data.inventory_item_id)

    item = CatalogItem(
        business_id=business_id,
        name=data.name.strip(),
        service_type=data.service_type.strip(),
        description=data.description,
        unit_price=data.unit_price,
        default_quantity=data.default_quantity,
        price_varies=data.price_varies,
        is_standard=data.is_standard,
        inventory_item_id=data.inventory_item_id,
        provider=data.provider,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A service with that name already exists")

    create_audit_log(
        db,
        business_id=business_id,
        user_id=_uid(current_user),
        action="catalog.item_created",
        entity_type="service_catalog_item",
        entity_id=item.id,
        details={"name": item.name, "unit_price": str(item.unit_price)},
        notes="A service was added to the price list.",
    )
    db.commit()
    db.refresh(item)
    return item


def _get_item(db, business_id, item_id) -> CatalogItem:
    item = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.id == item_id,
            CatalogItem.business_id == business_id,
        )
        .first()
    )
    if item is None:
        raise HTTPException(404, "Service not found in the price list")
    return item


@router.patch(
    "/service-catalog/{item_id}", response_model=CatalogItemResponse
)
def update_catalog_item(
    item_id: UUID,
    data: CatalogItemUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.catalog")),
):
    business_id = _biz(current_user)
    item = _get_item(db, business_id, item_id)
    changes = data.model_dump(exclude_unset=True)
    if "inventory_item_id" in changes:
        _check_stock_item(db, business_id, changes["inventory_item_id"])
    for key, value in changes.items():
        if key in ("name", "service_type") and value is not None:
            value = value.strip()
        setattr(item, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A service with that name already exists")

    create_audit_log(
        db,
        business_id=business_id,
        user_id=_uid(current_user),
        action="catalog.item_updated",
        entity_type="service_catalog_item",
        entity_id=item.id,
        details={k: str(v) for k, v in changes.items()},
        notes="A price list service was changed.",
    )
    db.commit()
    db.refresh(item)
    return item


# ============================================================
# PACKAGES
# ============================================================

def _package_response(db, package: ServicePackage) -> dict:
    rows = (
        db.query(ServicePackageItem, CatalogItem)
        .join(CatalogItem, CatalogItem.id == ServicePackageItem.catalog_item_id)
        .filter(ServicePackageItem.package_id == package.id)
        .order_by(CatalogItem.service_type, CatalogItem.name)
        .all()
    )
    items = []
    total = Decimal("0")
    for line, item in rows:
        line_total = money(Decimal(line.quantity) * Decimal(item.unit_price))
        total += line_total
        items.append(
            {
                "catalog_item_id": item.id,
                "name": item.name,
                "quantity": line.quantity,
                "unit_price": item.unit_price,
                "line_total": line_total,
            }
        )
    return {
        "id": package.id,
        "name": package.name,
        "description": package.description,
        "is_active": package.is_active,
        "total": money(total),
        "items": items,
    }


def _set_package_items(db, package, business_id, lines):
    ids = [line.catalog_item_id for line in lines]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "A service appears twice in the package")
    if ids:
        found = {
            row[0]
            for row in db.query(CatalogItem.id)
            .filter(
                CatalogItem.id.in_(ids),
                CatalogItem.business_id == business_id,
            )
            .all()
        }
        if found != set(ids):
            raise HTTPException(422, "A package service is not in the price list")
    db.query(ServicePackageItem).filter(
        ServicePackageItem.package_id == package.id
    ).delete()
    for line in lines:
        db.add(
            ServicePackageItem(
                business_id=business_id,
                package_id=package.id,
                catalog_item_id=line.catalog_item_id,
                quantity=line.quantity,
            )
        )
    db.flush()


@router.get("/service-packages", response_model=list[PackageResponse])
def list_packages(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    packages = (
        db.query(ServicePackage)
        .filter(
            ServicePackage.business_id == _biz(current_user),
            ServicePackage.is_active.is_(True),
        )
        .order_by(ServicePackage.name)
        .all()
    )
    return [_package_response(db, p) for p in packages]


@router.post(
    "/service-packages",
    response_model=PackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_package(
    data: PackageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.catalog")),
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
    _set_package_items(db, package, business_id, data.items)
    db.commit()
    db.refresh(package)
    return _package_response(db, package)


@router.patch("/service-packages/{package_id}", response_model=PackageResponse)
def update_package(
    package_id: UUID,
    data: PackageUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.catalog")),
):
    business_id = _biz(current_user)
    package = _get_package(db, business_id, package_id)
    changes = data.model_dump(exclude_unset=True)
    items = data.items
    changes.pop("items", None)
    for key, value in changes.items():
        setattr(package, key, value.strip() if key == "name" and value else value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A package with that name already exists")
    if items is not None:
        _set_package_items(db, package, business_id, items)
    db.commit()
    db.refresh(package)
    return _package_response(db, package)


def _get_package(db, business_id, package_id) -> ServicePackage:
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


# ============================================================
# ADD TO A CASE
# ============================================================

def _add_item_to_case(
    db, current_user, case_id, item: CatalogItem, *,
    quantity=None, unit_price=None, scheduled_date=None, notes=None,
):
    return create_service(
        case_id,
        CaseServiceCreate(
            service_type=item.service_type,
            service_name=item.name,
            description=item.description,
            quantity=quantity or item.default_quantity,
            unit_price=(
                unit_price if unit_price is not None else item.unit_price
            ),
            scheduled_date=scheduled_date,
            provider=item.provider,
            notes=notes,
            inventory_item_id=item.inventory_item_id,
            catalog_item_id=item.id,
        ),
        db,
        current_user,
    )


def _on_case(db, business_id, case_id) -> set:
    rows = (
        db.query(CaseService.catalog_item_id)
        .filter(
            CaseService.case_id == case_id,
            CaseService.business_id == business_id,
            CaseService.catalog_item_id.isnot(None),
            CaseService.status != "cancelled",
        )
        .all()
    )
    return {r[0] for r in rows}


@router.post(
    "/cases/{case_id}/services/from-catalog",
    response_model=CaseServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_from_catalog(
    case_id: UUID,
    data: AddFromCatalog,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    item = _get_item(db, business_id, data.catalog_item_id)
    if not item.is_active:
        raise HTTPException(409, "That service is no longer offered")
    return _add_item_to_case(
        db, current_user, case_id, item,
        quantity=data.quantity,
        unit_price=data.unit_price,
        scheduled_date=data.scheduled_date,
        notes=data.notes,
    )


@router.post(
    "/cases/{case_id}/services/from-package",
    response_model=list[CaseServiceResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_package(
    case_id: UUID,
    data: AddPackage,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    package = _get_package(db, business_id, data.package_id)
    get_case_or_404(db, case_id, business_id)
    present = _on_case(db, business_id, case_id)
    rows = (
        db.query(ServicePackageItem, CatalogItem)
        .join(CatalogItem, CatalogItem.id == ServicePackageItem.catalog_item_id)
        .filter(ServicePackageItem.package_id == package.id)
        .all()
    )
    added = []
    for line, item in rows:
        if item.id in present or not item.is_active:
            continue
        added.append(
            _add_item_to_case(
                db, current_user, case_id, item, quantity=line.quantity
            )
        )
    return added


@router.post(
    "/cases/{case_id}/services/apply-standard",
    response_model=list[CaseServiceResponse],
    status_code=status.HTTP_201_CREATED,
)
def add_standard_services(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.manage")),
):
    business_id = _biz(current_user)
    get_case_or_404(db, case_id, business_id)
    present = _on_case(db, business_id, case_id)
    items = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.business_id == business_id,
            CatalogItem.is_standard.is_(True),
            CatalogItem.is_active.is_(True),
        )
        .order_by(CatalogItem.service_type, CatalogItem.name)
        .all()
    )
    return [
        _add_item_to_case(db, current_user, case_id, item)
        for item in items
        if item.id not in present
    ]


# ============================================================
# QUOTE / INVOICE FROM SERVICES
# ============================================================

@router.post(
    "/cases/{case_id}/financial-documents/from-services",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def bill_from_services(
    case_id: UUID,
    data: BillFromServices,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = _biz(current_user)
    case = get_case_or_404(db, case_id, business_id)
    if case.is_archived:
        raise HTTPException(409, "Archived cases cannot receive new documents")

    validate_type_fields(
        data.document_type, valid_until=data.valid_until, due_date=data.due_date
    )

    services = billable_services(db, case.id, business_id)
    done = already_billed_ids(db, case.id, business_id, data.document_type)
    todo = [s for s in services if s.id not in done]
    if not todo:
        raise HTTPException(
            409,
            "Every service on this case is already on a "
            f"{data.document_type}, or there are no services yet",
        )

    document = FinancialDocument(
        business_id=business_id,
        case_id=case.id,
        document_type=data.document_type,
        status="draft",
        discount=Decimal("0.00"),
        tax=Decimal("0.00"),
        valid_until=data.valid_until,
        due_date=data.due_date,
        notes=data.notes,
        created_by=_uid(current_user),
    )
    db.add(document)
    db.flush()

    for position, service in enumerate(todo):
        db.add(line_from_service(document, service, position))
    db.flush()

    document.discount = money(data.discount)
    document.tax = money(data.tax)
    try:
        recalculate_document(db, document)
    except DocumentError as error:
        fail(db, error)

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.created",
        notes="Draft built automatically from the case's services.",
        extra={"total": str(document.total), "line_count": len(todo)},
    )
    db.commit()
    db.refresh(document)
    return document_response(db, document)


@router.post(
    "/financial-documents/{document_id}/sync-services",
    response_model=DocumentResponse,
)
def sync_services(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = _biz(current_user)
    document = get_document_or_404(db, document_id, business_id, lock=True)
    try:
        ensure_draft(document)
        result = sync_draft_with_services(db, document)
    except DocumentError as error:
        fail(db, error)

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.synced",
        notes="Draft was refreshed from the case's services.",
        extra=result,
    )
    db.commit()
    db.refresh(document)
    return document_response(db, document)
