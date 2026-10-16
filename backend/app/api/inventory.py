from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase
from app.models.inventory import InventoryItem, StockMovement
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    ItemCategory,
    StockAdjustmentCreate,
    StockMovementCreate,
    StockMovementResponse,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.branch_service import BranchError, resolve_branch_id
from app.services.inventory import (
    InventoryError,
    get_case_for_stock,
    get_usable_supplier,
    lock_item,
    record_movement,
)


router = APIRouter(
    tags=["Inventory"],
)


AUDITED_ITEM_FIELDS = (
    "name",
    "category",
    "unit",
    "description",
    "supplier_id",
    "reorder_level",
    "unit_cost",
)

MOVEMENT_AUDIT_ACTIONS = {
    "receipt": "inventory.stock_received",
    "issue": "inventory.stock_issued",
    "return": "inventory.stock_returned",
    "adjustment": "inventory.stock_adjusted",
}


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def get_user_id(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


def raise_inventory_error(db: Session, error: InventoryError):
    db.rollback()

    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


def get_item_or_404(
    db: Session,
    item_id: UUID,
    business_id: UUID,
) -> InventoryItem:
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == item_id,
            InventoryItem.business_id == business_id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found",
        )

    return item


def audit_item(
    db: Session,
    *,
    item: InventoryItem,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    details = {"sku": item.sku}

    if extra:
        details.update(extra)

    create_audit_log(
        db,
        business_id=item.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="inventory_item",
        entity_id=item.id,
        details=details,
        notes=notes,
    )


def audit_movement(
    db: Session,
    *,
    item: InventoryItem,
    movement: StockMovement,
    current_user: dict,
    case_number: str | None = None,
) -> None:
    extra = {
        "movement_id": str(movement.id),
        "quantity": str(movement.quantity),
        "balance_after": str(movement.balance_after),
    }

    if case_number:
        extra["case_number"] = case_number

    audit_item(
        db,
        item=item,
        current_user=current_user,
        action=MOVEMENT_AUDIT_ACTIONS[movement.movement_type],
        notes="Stock level was changed.",
        extra=extra,
    )


# ============================================================
# ITEMS
# ============================================================

@router.post(
    "/inventory/items",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    data: InventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    business_id = get_business_id(current_user)
    user_id = get_user_id(current_user)

    try:
        branch_id = resolve_branch_id(
            db,
            business_id=business_id,
            requested=data.branch_id,
            acting_user_id=user_id,
        )

        supplier = (
            get_usable_supplier(db, business_id, data.supplier_id)
            if data.supplier_id
            else None
        )
    except (BranchError, InventoryError) as error:
        db.rollback()

        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    item = InventoryItem(
        business_id=business_id,
        branch_id=branch_id,
        supplier_id=supplier.id if supplier else None,
        sku=data.sku,
        name=data.name,
        category=data.category,
        unit=data.unit,
        description=data.description,
        quantity_on_hand=Decimal("0"),
        reorder_level=data.reorder_level,
        unit_cost=data.unit_cost,
        is_active=True,
    )

    db.add(item)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An item with that SKU already exists",
        )

    if data.opening_quantity > 0:
        record_movement(
            db,
            item=item,
            movement_type="receipt",
            quantity=data.opening_quantity,
            user_id=user_id,
            unit_cost=data.unit_cost,
            supplier_id=item.supplier_id,
            reason="Opening stock",
        )

    audit_item(
        db,
        item=item,
        current_user=current_user,
        action="inventory_item.created",
        notes="Inventory item was created.",
        extra={
            "category": item.category,
            "branch_id": str(branch_id) if branch_id else None,
            "opening_quantity": str(data.opening_quantity),
        },
    )

    db.commit()
    db.refresh(item)

    return item


@router.get(
    "/inventory/items",
    response_model=list[InventoryItemResponse],
)
def list_items(
    category: ItemCategory | None = None,
    branch_id: UUID | None = None,
    supplier_id: UUID | None = None,
    low_stock: bool = False,
    include_inactive: bool = False,
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(InventoryItem).filter(
        InventoryItem.business_id == business_id
    )

    if not include_inactive:
        query = query.filter(InventoryItem.is_active.is_(True))

    if category:
        query = query.filter(InventoryItem.category == category)

    if branch_id:
        query = query.filter(InventoryItem.branch_id == branch_id)

    if supplier_id:
        query = query.filter(InventoryItem.supplier_id == supplier_id)

    if low_stock:
        query = query.filter(
            InventoryItem.reorder_level > 0,
            InventoryItem.quantity_on_hand <= InventoryItem.reorder_level,
        )

    if search and search.strip():
        like = f"%{search.strip()}%"

        query = query.filter(
            or_(
                InventoryItem.name.ilike(like),
                InventoryItem.sku.ilike(like),
            )
        )

    return query.order_by(InventoryItem.name).all()


@router.get(
    "/inventory/items/{item_id}",
    response_model=InventoryItemResponse,
)
def get_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.view")),
):
    return get_item_or_404(
        db, item_id, get_business_id(current_user)
    )


@router.patch(
    "/inventory/items/{item_id}",
    response_model=InventoryItemResponse,
)
def update_item(
    item_id: UUID,
    data: InventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    business_id = get_business_id(current_user)

    try:
        item = lock_item(db, item_id, business_id)

        updates = data.model_dump(exclude_unset=True)

        for required in ("name", "category", "unit", "reorder_level"):
            if required in updates and updates[required] is None:
                raise InventoryError(
                    422, f"{required} cannot be null"
                )

        if updates.get("supplier_id"):
            get_usable_supplier(
                db, business_id, updates["supplier_id"]
            )
    except InventoryError as error:
        raise_inventory_error(db, error)

    old_values = snapshot_fields(item, AUDITED_ITEM_FIELDS)

    for field, value in updates.items():
        setattr(item, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(item, AUDITED_ITEM_FIELDS),
    )

    if changes:
        audit_item(
            db,
            item=item,
            current_user=current_user,
            action="inventory_item.updated",
            notes="Inventory item was updated.",
            extra={"changes": changes},
        )

    db.commit()
    db.refresh(item)

    return item


def set_item_active(
    db: Session,
    item_id: UUID,
    current_user: dict,
    *,
    active: bool,
) -> InventoryItem:
    business_id = get_business_id(current_user)

    try:
        item = lock_item(db, item_id, business_id)
    except InventoryError as error:
        raise_inventory_error(db, error)

    if item.is_active == active:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Item is already active"
                if active
                else "Item is already inactive"
            ),
        )

    item.is_active = active

    audit_item(
        db,
        item=item,
        current_user=current_user,
        action=(
            "inventory_item.reactivated"
            if active
            else "inventory_item.deactivated"
        ),
        notes=(
            "Inventory item was reactivated."
            if active
            else "Inventory item was deactivated."
        ),
    )

    db.commit()
    db.refresh(item)

    return item


@router.post(
    "/inventory/items/{item_id}/deactivate",
    response_model=InventoryItemResponse,
)
def deactivate_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    return set_item_active(db, item_id, current_user, active=False)


@router.post(
    "/inventory/items/{item_id}/reactivate",
    response_model=InventoryItemResponse,
)
def reactivate_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    return set_item_active(db, item_id, current_user, active=True)


# ============================================================
# MOVEMENTS
# ============================================================

@router.post(
    "/inventory/items/{item_id}/movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_movement(
    item_id: UUID,
    data: StockMovementCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.stock")),
):
    business_id = get_business_id(current_user)

    case_number = None

    try:
        item = lock_item(db, item_id, business_id)

        if data.supplier_id:
            if data.movement_type != "receipt":
                raise InventoryError(
                    422, "Only a receipt can name a supplier"
                )

            get_usable_supplier(db, business_id, data.supplier_id)

        if data.unit_cost is not None and data.movement_type != "receipt":
            raise InventoryError(
                422, "Only a receipt can carry a unit cost"
            )

        if data.case_id:
            if data.movement_type == "receipt":
                raise InventoryError(
                    422, "A receipt cannot be linked to a case"
                )

            case_number = get_case_for_stock(
                db, business_id, data.case_id
            ).case_number

        movement = record_movement(
            db,
            item=item,
            movement_type=data.movement_type,
            quantity=data.quantity,
            user_id=get_user_id(current_user),
            unit_cost=data.unit_cost,
            supplier_id=data.supplier_id,
            case_id=data.case_id,
            reference=data.reference,
            reason=data.reason,
        )
    except InventoryError as error:
        raise_inventory_error(db, error)

    audit_movement(
        db,
        item=item,
        movement=movement,
        current_user=current_user,
        case_number=case_number,
    )

    db.commit()
    db.refresh(movement)

    return movement


@router.post(
    "/inventory/items/{item_id}/adjustments",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_adjustment(
    item_id: UUID,
    data: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    """Correct the stock level after a count or a loss. Adjustments
    are for managers: they change the stock without a delivery or a
    case behind them, so a reason is always recorded."""

    business_id = get_business_id(current_user)

    try:
        item = lock_item(db, item_id, business_id)

        movement = record_movement(
            db,
            item=item,
            movement_type="adjustment",
            quantity=data.quantity,
            user_id=get_user_id(current_user),
            reason=data.reason,
        )
    except InventoryError as error:
        raise_inventory_error(db, error)

    audit_movement(
        db,
        item=item,
        movement=movement,
        current_user=current_user,
    )

    db.commit()
    db.refresh(movement)

    return movement


@router.get(
    "/inventory/items/{item_id}/movements",
    response_model=list[StockMovementResponse],
)
def list_item_movements(
    item_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.view")),
):
    business_id = get_business_id(current_user)

    get_item_or_404(db, item_id, business_id)

    return (
        db.query(StockMovement)
        .filter(
            StockMovement.business_id == business_id,
            StockMovement.item_id == item_id,
        )
        .order_by(
            StockMovement.created_at.desc(),
            StockMovement.id.desc(),
        )
        .limit(limit)
        .all()
    )


@router.get(
    "/cases/{case_id}/stock",
    response_model=list[StockMovementResponse],
)
def list_case_stock(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.view")),
):
    """Stock issued to, and returned from, one case."""

    business_id = get_business_id(current_user)

    case = (
        db.query(FuneralCase.id)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return (
        db.query(StockMovement)
        .filter(
            StockMovement.business_id == business_id,
            StockMovement.case_id == case_id,
        )
        .order_by(
            StockMovement.created_at.desc(),
            StockMovement.id.desc(),
        )
        .all()
    )
