import uuid

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


CLAIM_STATUSES = (
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "paid",
    "cancelled",
)

# A case may only have one claim in any of these states.
LIVE_CLAIM_STATUSES = (
    "submitted",
    "under_review",
    "approved",
    "paid",
)


class MembershipClaim(Base):
    """
    A claim against a membership, raised from a funeral case.

    The claim stores snapshots of the coverage decision at submission
    and at decision time so the basis of every decision stays auditable
    even if the membership or plan changes later.
    """

    __tablename__ = "membership_claims"

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "claim_number",
            name="uq_membership_claims_business_claim_number",
        ),
        CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', "
            "'rejected', 'paid', 'cancelled')",
            name="ck_membership_claims_status",
        ),
        CheckConstraint(
            "claimed_amount > 0",
            name="ck_membership_claims_claimed_amount",
        ),
        CheckConstraint(
            "approved_amount IS NULL OR approved_amount >= 0",
            name="ck_membership_claims_approved_amount",
        ),
        Index(
            "uq_membership_claims_one_live_per_case",
            "case_id",
            unique=True,
            postgresql_where=(
                "status IN ('submitted', 'under_review', "
                "'approved', 'paid')"
            ),
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

    claim_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    covered_dependent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("covered_dependents.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="submitted",
        index=True,
    )

    claimed_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    approved_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    submission_coverage: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    decision_coverage: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    override_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    paid_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    payment_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    payout_allocations: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
