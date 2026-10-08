import uuid

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


RESOURCE_TYPES = ("vehicle", "venue", "equipment")

BOOKING_STATUSES = ("booked", "completed", "cancelled")


class Resource(Base):
    """
    A physical resource the business owns or uses:
    a vehicle, a venue or a piece of equipment.

    Resources are never hard-deleted. They are deactivated so that
    historical bookings keep their meaning.
    """

    __tablename__ = "resources"

    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('vehicle', 'venue', 'equipment')",
            name="ck_resources_resource_type",
        ),
        Index(
            "uq_resources_business_type_identifier",
            "business_id",
            "resource_type",
            "identifier",
            unique=True,
            postgresql_where="identifier IS NOT NULL",
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

    resource_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Registration number, asset tag or similar. Unique per business
    # and resource type when provided.
    identifier: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Seats, hall capacity, etc. Optional.
    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
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


class ResourceBooking(Base):
    """
    Reserves a resource (and optionally a driver) for a case over a
    time window.

    Overlapping active ("booked") bookings for the same resource, or
    for the same driver, are rejected by the API.
    """

    __tablename__ = "resource_bookings"

    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_resource_bookings_window",
        ),
        CheckConstraint(
            "status IN ('booked', 'completed', 'cancelled')",
            name="ck_resource_bookings_status",
        ),
        Index(
            "ix_resource_bookings_resource_window",
            "resource_id",
            "starts_at",
            "ends_at",
        ),
        Index(
            "ix_resource_bookings_driver_window",
            "driver_user_id",
            "starts_at",
            "ends_at",
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

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Only meaningful for vehicle bookings.
    driver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    purpose: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="booked",
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
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
