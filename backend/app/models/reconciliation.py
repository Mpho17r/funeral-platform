import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
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


class Reconciliation(Base):
    """
    One day's money for one payment method: what the books say should
    be there, what was actually counted or banked, and the difference.
    The expected figure is frozen when the day is reconciled.
    """

    __tablename__ = "reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "recon_date",
            "payment_method",
            name="uq_reconciliations_day_method",
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
    recon_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    receipts_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    expenses_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    expected_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    counted_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    variance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
