import uuid

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Branch(Base):
    """
    One location of a funeral business.

    Company -> branches -> staff, resources, cases and members.

    Every business has exactly one main branch, which cannot be
    deactivated. Branches are deactivated rather than deleted so the
    history of cases and records that belonged to them stays intact.
    """

    __tablename__ = "branches"

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "code",
            name="uq_branches_business_code",
        ),
        # Branch names are unique per business, ignoring case.
        Index(
            "uq_branches_business_name",
            "business_id",
            text("lower(name)"),
            unique=True,
        ),
        # Only one main branch per business.
        Index(
            "uq_branches_one_main_per_business",
            "business_id",
            unique=True,
            postgresql_where="is_main",
        ),
        CheckConstraint(
            "NOT (is_main AND NOT is_active)",
            name="ck_branches_main_is_active",
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

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # Short code such as "SWT", used on screens and later in numbering.
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_main: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
