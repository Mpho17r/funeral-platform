"""
Stock that looks after itself.

* A service line linked to a stocked item takes the stock off automatically
  and puts it back when the line is cancelled or deleted.
* When an item runs low, the right people are told once. If the item allows
  it, an order is placed with its supplier: emailed when email is set up,
  otherwise left as "to send" for a person.
* Receiving stock (by recording a receipt) closes the open order.

Only one order per item can be open, so a low item is never ordered twice.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import (
    OPEN_ORDER_STATUSES,
    InventoryItem,
    PurchaseOrder,
    Supplier,
)
from app.services import message_delivery
from app.services.inventory import InventoryError, lock_item, record_movement
from app.services.notifications import notify, users_with_permission


# ---------------------------------------------------------- service lines


def sync_service_stock(
    db: Session, *, service, wanted: int, user_id, case_number: str | None
) -> None:
    """Make the stock issued to this service line equal `wanted`.

    Issues or returns only the difference, so editing a quantity or
    cancelling a line always leaves stock and ledger in agreement.
    """
    if service.inventory_item_id is None:
        return

    difference = wanted - service.stock_issued
    if difference == 0:
        return

    item = lock_item(db, service.inventory_item_id, service.business_id)
    reference = f"Case {case_number}: {service.service_name}"[:100]
    record_movement(
        db,
        item=item,
        movement_type="issue" if difference > 0 else "return",
        quantity=Decimal(abs(difference)),
        user_id=user_id,
        case_id=service.case_id,
        reference=reference,
        reason="Automatic, from the case's services"
        if difference > 0
        else "Automatic: service line changed or removed",
    )
    service.stock_issued = wanted


# ------------------------------------------------------------- low stock


def _alert_people(db, item, title, body, actor_id=None) -> None:
    notify(
        db,
        business_id=item.business_id,
        user_ids=users_with_permission(db, item.business_id, "inventory.manage"),
        kind="stock",
        title=title,
        body=body,
        link="/inventory",
        actor_id=actor_id,
    )


def check_low_stock(db: Session, item: InventoryItem, *, user_id=None) -> None:
    """Alert (and maybe order) when an item has just become low, and re-arm
    the alert once it has been restocked. The caller commits."""
    if not item.is_active:
        return

    if not item.is_low_stock:
        if item.low_stock_alerted_at is not None:
            item.low_stock_alerted_at = None
        return

    if item.low_stock_alerted_at is not None:
        return
    item.low_stock_alerted_at = datetime.now(timezone.utc)

    detail = (
        f"{item.quantity_on_hand} {item.unit} left "
        f"(reorder level {item.reorder_level})."
    )
    order = None
    if item.auto_order:
        order = place_order(db, item, automatic=True, user_id=None)

    if order is not None and order.status == "sent":
        detail += f" Order {order.number} was emailed to the supplier."
    elif order is not None:
        detail += (
            f" Order {order.number} is ready but still needs to be sent "
            "to the supplier."
        )
    elif item.auto_order:
        detail += " It could not be ordered automatically."
    _alert_people(db, item, f"{item.name} is running low", detail, user_id)


def scan_low_stock(db: Session) -> int:
    """Daily/periodic safety net: catch items that became low some other
    way (a changed reorder level, a manual issue, a count adjustment)."""
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.is_active.is_(True))
        .all()
    )
    changed = 0
    for item in items:
        before = item.low_stock_alerted_at
        check_low_stock(db, item)
        if item.low_stock_alerted_at != before:
            changed += 1
    db.commit()
    return changed


# ---------------------------------------------------------------- orders


def next_number(db: Session, business_id) -> str:
    year = datetime.now(timezone.utc).year
    count = (
        db.query(func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.business_id == business_id)
        .execution_options(all_branches=True)
        .scalar()
    )
    return f"PO-{year}-{count + 1:04d}"


def open_order(db: Session, item_id) -> PurchaseOrder | None:
    return (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.item_id == item_id,
            PurchaseOrder.status.in_(OPEN_ORDER_STATUSES),
        )
        .execution_options(all_branches=True)
        .first()
    )


def _order_email(item, supplier, order) -> tuple[str, str]:
    subject = f"Order {order.number}: {item.name}"
    body = (
        f"Hello {supplier.contact_person or supplier.name},\n\n"
        f"Please supply the following:\n\n"
        f"  {order.quantity} {item.unit} of {item.name} (SKU {item.sku})\n\n"
        f"Order reference: {order.number}\n"
        "Please confirm availability and delivery.\n\nThank you."
    )
    return subject, body


def place_order(
    db: Session,
    item: InventoryItem,
    *,
    automatic: bool,
    user_id,
    quantity: Decimal | None = None,
) -> PurchaseOrder | None:
    """Create an order for an item. Returns None when it cannot be placed
    (no supplier, no quantity, or an order is already open). Manual callers
    pass a quantity and get a clear error from `require_orderable` first."""
    supplier = db.get(Supplier, item.supplier_id) if item.supplier_id else None
    qty = quantity if quantity is not None else item.reorder_quantity
    if (
        supplier is None
        or not supplier.is_active
        or not qty
        or qty <= 0
        or open_order(db, item.id) is not None
    ):
        return None

    order = PurchaseOrder(
        business_id=item.business_id,
        branch_id=item.branch_id,
        number=next_number(db, item.business_id),
        item_id=item.id,
        supplier_id=supplier.id,
        quantity=qty,
        status="to_send",
        automatic=automatic,
        created_by=user_id,
    )

    if supplier.email and message_delivery.email_configured():
        subject, body = _order_email(item, supplier, order)
        try:
            message_delivery.send_email(supplier.email, subject, body)
            order.status = "sent"
            order.sent_at = datetime.now(timezone.utc)
        except message_delivery.DeliveryError as exc:
            order.send_error = str(exc)
    elif not supplier.email:
        order.send_error = "The supplier has no email address."
    else:
        order.send_error = "Email sending is not set up."

    db.add(order)
    db.flush()
    return order


def require_orderable(db: Session, item: InventoryItem, quantity) -> None:
    if item.supplier_id is None:
        raise InventoryError(422, "Choose a supplier for this item first")
    qty = quantity if quantity is not None else item.reorder_quantity
    if not qty or qty <= 0:
        raise InventoryError(422, "Say how many to order")
    if open_order(db, item.id) is not None:
        raise InventoryError(409, "This item already has an open order")


def close_open_orders_on_receipt(db: Session, item_id) -> None:
    """Stock arrived: the item's open order is fulfilled."""
    order = open_order(db, item_id)
    if order is not None:
        order.status = "received"
        order.received_at = datetime.now(timezone.utc)
