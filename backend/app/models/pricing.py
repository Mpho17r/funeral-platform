"""What LINDA costs, and what each business has used.

One row of prices for the whole platform (`PlatformPricing`) and one line per
business per day of how many staff and branches it had (`UsageSnapshot`).
A month is billed on its busiest day, so removing people just before the end
of the month does not lower the bill.

Amounts are whole cents (ZAR).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
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

    # Always id 1: there is a single set of prices.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ZAR")
    base_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    included_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    included_branches: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_staff_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_branch_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Shown under the prices, e.g. "Prices include VAT."
    price_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


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
