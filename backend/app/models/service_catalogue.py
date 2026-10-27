import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ServiceCatalogueItem(Base):
    """A service or product the business sells, saved once and reused.

    Adding it to a case copies the name, price and stock link onto a case
    service, so the price on a case can still be changed for that family.
    """

    __tablename__ = "service_catalogue_items"
    __table_args__ = (
        CheckConstraint(
            "default_price >= 0", name="ck_catalogue_price_non_negative"
        ),
        CheckConstraint(
            "default_quantity >= 1", name="ck_catalogue_quantity_positive"
        ),
        UniqueConstraint("business_id", "name", name="uq_catalogue_business_name"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="other"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    default_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    # True when the price normally changes from case to case; the screen
    # then asks for the price instead of silently using the default.
    price_varies: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class ServicePackage(Base):
    """A named bundle of catalogue items, e.g. "Standard funeral"."""

    __tablename__ = "service_packages"
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_package_business_name"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class ServicePackageItem(Base):
    __tablename__ = "service_package_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_package_item_quantity"),
        UniqueConstraint(
            "package_id", "catalogue_item_id", name="uq_package_item"
        ),
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
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    catalogue_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_catalogue_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
