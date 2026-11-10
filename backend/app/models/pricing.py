"""What LINDA costs, and what each business has used.

Plans with their prices (`PricingPlan`), shared settings such as VAT
(`PlatformPricing`) and one line per
business per day of how many staff and branches it had (`UsageSnapshot`).
A month is billed on its busiest day, so removing people just before the end
of the month does not lower the bill.

Amounts are whole cents (ZAR).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformPricing(Base):
    __tablename__ = "platform_pricing"

    # Always id 1: settings shared by every plan.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ZAR")
    # Platform VAT remains configurable and defaults to zero until Saccharum is registered.
    vat_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Shown under the prices.
    price_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class PricingPlan(Base):
    """One plan a business can pick, e.g. funeral "Beginner". Prices exclude VAT."""

    __tablename__ = "pricing_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    business_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(160), nullable=True)
    base_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    included_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    included_branches: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_staff_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_branch_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UsageSnapshot(Base):
    __tablename__ = "usage_snapshots"
    __table_args__ = (
        UniqueConstraint("business_id", "day", name="uq_usage_snapshot_day"),
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
    day: Mapped[date] = mapped_column(Date, nullable=False)
    staff: Mapped[int] = mapped_column(Integer, nullable=False)
    branches: Mapped[int] = mapped_column(Integer, nullable=False)
