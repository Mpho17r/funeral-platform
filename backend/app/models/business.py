import uuid

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Business(Base):

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    # ========================================================
    # BRANDING
    # ========================================================

    logo_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    primary_color: Mapped[str] = mapped_column(
        String(20),
        default="#000000",
        nullable=False,
    )

    secondary_color: Mapped[str] = mapped_column(
        String(20),
        default="#64748b",
        nullable=False,
    )

    watermark_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    watermark_opacity: Mapped[float] = mapped_column(
        default=0.05,
        nullable=False,
    )

    theme_preference: Mapped[str] = mapped_column(
        String(20),
        default="system",
        nullable=False,
    )

    # ========================================================
    # MEMBERSHIP COVER POLICY
    # ========================================================

    grace_period_days: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    cover_during_arrears: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    lapse_after_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        nullable=False,
    )

    reinstatement_policy: Mapped[str] = mapped_column(
        String(30),
        default="automatic",
        nullable=False,
    )

    # Possible values:
    #
    # automatic
    # manual
    # not_allowed

        # ========================================================
    # STAFF ATTENDANCE POLICY
    # ========================================================

    tea_break_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        nullable=False,
    )

    lunch_break_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )

    idle_timeout_minutes: Mapped[int] = mapped_column(
        Integer,
        default=15,
        nullable=False,
    )

    break_expiry_behavior: Mapped[str] = mapped_column(
        String(30),
        default="notify_and_keep_active",
        nullable=False,
    )

    break_warning_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    break_warning_minutes: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )

    break_expiry_notification_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )


    # ========================================================
    # BUSINESS CONTACT DETAILS
    # ========================================================

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

    # ========================================================
    # STATUS
    # ========================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ========================================================
    # TIMESTAMPS
    # ========================================================

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
