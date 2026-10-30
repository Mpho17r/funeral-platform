import uuid

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


ITEM_CATEGORIES = (
    "coffin",
    "casket",
    "flowers",
    "clothing",
    "consumable",
    "stationery",
    "other",
)

MOVEMENT_TYPES = ("receipt", "issue", "return", "adjustment")


def _now():
    return datetime.now(timezone.utc)


class Supplier(Base):
    """
    Someone the business buys stock or services from.

    Suppliers are never hard-deleted. They are deactivated so that
    historical stock receipts keep their meaning.
    """

    __tablename__ = "suppliers"

    __table_args__ = (
        Index(
            "uq_suppliers_business_name",
            "business_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        nullable=False,
    )


class InventoryItem(Base):
    """
    A stocked item: a coffin model, a flower arrangement, a
    consumable.

    The quantity on hand is changed only by recording a StockMovement
    (see app.services.inventory), never edited directly, so the stock
    figure can always be explained from the ledger.
    """

    __tablename__ = "inventory_items"

    __table_args__ = (
        CheckConstraint(
            "category IN ('coffin', 'casket', 'flowers', 'clothing', "
            "'consumable', 'stationery', 'other')",
            name="ck_inventory_items_category",
        ),
        CheckConstraint(
            "quantity_on_hand >= 0",
            name="ck_inventory_items_quantity_non_negative",
        ),
        CheckConstraint(
            "reorder_level >= 0",
            name="ck_inventory_items_reorder_non_negative",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_inventory_items_cost_non_negative",
        ),
        Index(
            "uq_inventory_items_business_sku",
            "business_id",
            "sku",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The branch holding this stock. See Resource.branch_id.
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id"),
        nullable=True,
        index=True,
    )

    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )
    unit: Mapped[str] = mapped_column(
        String(30), nullable=False, default="each"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )

    # At or below this level (when above zero) the item is low stock.
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )

    # Ordering: how much to buy when stock runs low, and whether the
    # system may email the supplier by itself.
    reorder_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    auto_order: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        server_default=text("false"),
    )
    # Set when the low-stock alert went out; cleared once restocked, so
    # people are told once per time the item runs low.
    low_stock_alerted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Cost of one unit. Follows the latest receipt that gave a cost.
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    @property
    def is_low_stock(self) -> bool:
        """At or below a reorder level that has been set."""

        return (
            self.reorder_level > 0
            and self.quantity_on_hand <= self.reorder_level
        )


class StockMovement(Base):
    """
    One entry in an item's stock ledger.

    Append-only: a movement is never edited or deleted. A mistake is
    put right with a further movement. quantity is signed (receipts
    and returns add, issues remove, adjustments either way) and
    balance_after records the stock level once it was applied.
    """

    __tablename__ = "stock_movements"

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('receipt', 'issue', 'return', "
            "'adjustment')",
            name="ck_stock_movements_type",
        ),
        CheckConstraint(
            "quantity <> 0",
            name="ck_stock_movements_quantity_not_zero",
        ),
        CheckConstraint(
            "balance_after >= 0",
            name="ck_stock_movements_balance_non_negative",
        ),
        Index(
            "ix_stock_movements_item_created",
            "item_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id"),
        nullable=False,
    )

    movement_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id"),
        nullable=True,
    )

    # The case the stock was used for (or came back from).
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id"),
        nullable=True,
        index=True,
    )

    # Supplier invoice or delivery note number, free text.
    reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


ORDER_STATUSES = ("to_send", "sent", "received", "cancelled")
OPEN_ORDER_STATUSES = ("to_send", "sent")


class PurchaseOrder(Base):
    """
    An order for one stocked item from its supplier.

    `to_send` means the system could not email it (no supplier email or
    email not set up) and a person must send it. `sent` means it went out
    (by email, or a person marked it sent). Only one order per item can be
    open at a time, so a low item is never ordered twice.
    """

    __tablename__ = "purchase_orders"

    __table_args__ = (
        CheckConstraint(
            "status IN ('to_send', 'sent', 'received', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
        CheckConstraint(
            "quantity > 0", name="ck_purchase_orders_quantity"
        ),
        Index(
            "uq_purchase_orders_one_open_per_item",
            "item_id",
            unique=True,
            postgresql_where=text("status IN ('to_send', 'sent')"),
        ),
    )

    # Received and cancelled orders are archived after a while.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Same branch as the item, so branch limits apply to orders too.
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )
    number: Mapped[str] = mapped_column(String(30), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    automatic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        server_default=text("false"),
    )
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
