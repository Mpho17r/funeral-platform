"""Stock rules.

Pure business rules with no HTTP concerns. Stock only ever changes by
recording a movement here, with the item row locked, so the quantity on
hand always equals the sum of its ledger and can never go negative.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.funeral_case import FuneralCase
from app.models.inventory import (
    InventoryItem,
    StockMovement,
    Supplier,
)


TWO_PLACES = Decimal("0.01")


class InventoryError(Exception):
    """A stock rule was violated."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def money(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES)


def lock_item(
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
        .with_for_update()
        .first()
    )

    if item is None:
        raise InventoryError(404, "Inventory item not found")

    return item


def get_usable_supplier(
    db: Session,
    business_id: UUID,
    supplier_id: UUID,
) -> Supplier:
    """A supplier that may be attached to new stock: same business and
    still active."""

    supplier = (
        db.query(Supplier)
        .filter(
            Supplier.id == supplier_id,
            Supplier.business_id == business_id,
        )
        .first()
    )

    if supplier is None:
        raise InventoryError(422, "Supplier not found")

    if not supplier.is_active:
        raise InventoryError(
            409,
            f"Supplier {supplier.name} is inactive",
        )

    return supplier


def get_case_for_stock(
    db: Session,
    business_id: UUID,
    case_id: UUID,
) -> FuneralCase:
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if case is None:
        raise InventoryError(422, "Case not found")

    if case.is_archived:
        raise InventoryError(
            409,
            "Stock cannot be recorded against an archived case",
        )

    return case


def record_movement(
    db: Session,
    *,
    item: InventoryItem,
    movement_type: str,
    quantity: Decimal,
    user_id: UUID | None,
    unit_cost: Decimal | None = None,
    supplier_id: UUID | None = None,
    case_id: UUID | None = None,
    reference: str | None = None,
    reason: str | None = None,
) -> StockMovement:
    """Apply one movement to a locked item and add it to the ledger.

    quantity is what the caller means: always positive for receipts,
    issues and returns, and a signed non-zero change for adjustments.
    The caller commits.
    """

    if not item.is_active:
        raise InventoryError(
            409,
            f"{item.name} is inactive. Reactivate it before "
            "recording stock.",
        )

    quantity = money(quantity)

    if movement_type == "issue":
        if quantity <= 0:
            raise InventoryError(
                422, "Quantity to issue must be above zero"
            )

        change = -quantity
    elif movement_type in ("receipt", "return"):
        if quantity <= 0:
            raise InventoryError(
                422, f"Quantity to {movement_type} must be above zero"
            )

        change = quantity
    elif movement_type == "adjustment":
        if quantity == 0:
            raise InventoryError(
                422, "An adjustment cannot be zero"
            )

        if not reason or not reason.strip():
            raise InventoryError(
                422, "A reason is required for a stock adjustment"
            )

        change = quantity
    else:
        raise InventoryError(422, "Unknown movement type")

    balance = item.quantity_on_hand + change

    if balance < 0:
        raise InventoryError(
            409,
            f"Not enough {item.name} in stock: {item.quantity_on_hand} "
            f"{item.unit} on hand, {abs(change)} requested.",
        )

    item.quantity_on_hand = balance

    if movement_type == "receipt" and unit_cost is not None:
        item.unit_cost = money(unit_cost)

    movement = StockMovement(
        business_id=item.business_id,
        item_id=item.id,
        movement_type=movement_type,
        quantity=change,
        balance_after=balance,
        unit_cost=(
            money(unit_cost) if unit_cost is not None else None
        ),
        supplier_id=supplier_id,
        case_id=case_id,
        reference=reference,
        reason=reason.strip() if reason else None,
        created_by=user_id,
    )

    db.add(movement)
    db.flush()

    from app.services.stock_automation import (
        check_low_stock,
        close_open_orders_on_receipt,
    )

    if movement_type == "receipt":
        close_open_orders_on_receipt(db, item.id)
    check_low_stock(db, item, user_id=user_id)

    return movement
