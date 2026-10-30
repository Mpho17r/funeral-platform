from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.inventory import InventoryItem, PurchaseOrder, Supplier
from app.services.audit_service import create_audit_log
from app.services.inventory import InventoryError, lock_item, record_movement
from app.services import stock_automation as auto

router = APIRouter(tags=["Purchase orders"])


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )


def _out(db: Session, o: PurchaseOrder) -> dict:
    item = db.get(InventoryItem, o.item_id)
    supplier = db.get(Supplier, o.supplier_id)
    return {
        "id": o.id,
        "number": o.number,
        "item_id": o.item_id,
        "item_name": item.name if item else None,
        "unit": item.unit if item else None,
        "supplier_id": o.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "quantity": o.quantity,
        "status": o.status,
        "automatic": o.automatic,
        "send_error": o.send_error,
        "created_at": o.created_at,
        "sent_at": o.sent_at,
        "received_at": o.received_at,
    }


def _get(db, order_id, business_id) -> PurchaseOrder:
    order = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.id == order_id,
            PurchaseOrder.business_id == business_id,
        )
        .first()
    )
    if order is None:
        raise HTTPException(404, "Order not found")
    return order


def _audit(db, order, user, action, notes):
    create_audit_log(
        db,
        business_id=order.business_id,
        user_id=user["user_id"],
        action=action,
        entity_type="purchase_order",
        entity_id=order.id,
        details={"number": order.number, "status": order.status},
        notes=notes,
    )


@router.get("/inventory/orders")
def list_orders(
    status: str | None = None,
    archived: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.view")),
):
    query = db.query(PurchaseOrder).filter(
        PurchaseOrder.business_id == current_user["business_id"],
        PurchaseOrder.archived_at.is_not(None)
        if archived
        else PurchaseOrder.archived_at.is_(None),
    )
    if status:
        query = query.filter(PurchaseOrder.status == status)
    rows = query.order_by(PurchaseOrder.created_at.desc()).limit(200).all()
    return [_out(db, o) for o in rows]


@router.post("/inventory/items/{item_id}/order", status_code=201)
def order_now(
    item_id: UUID,
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    """Order an item from its supplier now (emails it when email is set up)."""
    try:
        item = lock_item(db, item_id, current_user["business_id"])
        auto.require_orderable(db, item, data.quantity)
    except InventoryError as error:
        db.rollback()
        raise HTTPException(error.status_code, error.detail)

    order = auto.place_order(
        db,
        item,
        automatic=False,
        user_id=current_user["user_id"],
        quantity=data.quantity,
    )
    _audit(db, order, current_user, "inventory.order_placed", "Order placed.")
    db.commit()
    return _out(db, order)


@router.post("/inventory/orders/{order_id}/mark-sent")
def mark_sent(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    """A person sent a 'to send' order to the supplier themselves."""
    order = _get(db, order_id, current_user["business_id"])
    if order.status != "to_send":
        raise HTTPException(409, f"A {order.status} order cannot be marked sent")
    order.status = "sent"
    order.sent_at = datetime.now(timezone.utc)
    _audit(db, order, current_user, "inventory.order_sent", "Marked as sent.")
    db.commit()
    return _out(db, order)


@router.post("/inventory/orders/{order_id}/receive")
def receive(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.stock")),
):
    """The goods arrived: record the receipt and close the order."""
    order = _get(db, order_id, current_user["business_id"])
    if order.status not in ("to_send", "sent"):
        raise HTTPException(409, f"A {order.status} order cannot be received")
    try:
        item = lock_item(db, order.item_id, order.business_id)
        record_movement(
            db,
            item=item,
            movement_type="receipt",
            quantity=order.quantity,
            user_id=current_user["user_id"],
            supplier_id=order.supplier_id,
            reference=order.number,
            reason=None,
        )
    except InventoryError as error:
        db.rollback()
        raise HTTPException(error.status_code, error.detail)
    # record_movement closes the open order; make sure this one is closed.
    order = _get(db, order_id, current_user["business_id"])
    _audit(db, order, current_user, "inventory.order_received", "Stock received.")
    db.commit()
    return _out(db, order)


@router.post("/inventory/orders/{order_id}/cancel")
def cancel(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("inventory.manage")),
):
    order = _get(db, order_id, current_user["business_id"])
    if order.status not in ("to_send", "sent"):
        raise HTTPException(409, f"A {order.status} order cannot be cancelled")
    order.status = "cancelled"
    # The low-stock alert stays "already raised" until the item is
    # restocked, so the scheduler does not simply re-order what a person
    # just cancelled. They can still order by hand.
    _audit(db, order, current_user, "inventory.order_cancelled", "Cancelled.")
    db.commit()
    return _out(db, order)
