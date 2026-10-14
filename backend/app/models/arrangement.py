import uuid

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


ARRANGEMENT_STATUSES = ("draft", "confirmed", "completed", "cancelled")
VENUE_TYPES = ("church", "home", "chapel", "hall", "graveside", "other")
COLLECTION_STATUSES = ("scheduled", "en_route", "collected", "cancelled")
PICKUP_TYPES = ("home", "hospital", "scene", "mortuary", "other")


def _in(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


class FuneralArrangement(Base):
    """
    When and where the funeral happens, one per case: the wake, the
    service, the cortege leaving, and the burial or cremation itself.

    Moves from draft to confirmed once the family has agreed the
    details, then to completed after the committal. Cancelled
    arrangements can be reopened as drafts.
    """

    __tablename__ = "funeral_arrangements"

    __table_args__ = (
        UniqueConstraint("case_id", name="uq_funeral_arrangements_case"),
        CheckConstraint(
            f"status IN ({_in(ARRANGEMENT_STATUSES)})",
            name="ck_funeral_arrangements_status",
        ),
        CheckConstraint(
            "service_venue_type IS NULL OR "
            f"service_venue_type IN ({_in(VENUE_TYPES)})",
            name="ck_funeral_arrangements_venue_type",
        ),
        Index(
            "ix_funeral_arrangements_committal",
            "business_id",
            "committal_at",
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
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )

    # The wake or night vigil before the funeral.
    wake_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wake_venue: Mapped[str | None] = mapped_column(String(255))
    wake_address: Mapped[str | None] = mapped_column(Text)

    # The funeral service.
    service_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    service_venue_type: Mapped[str | None] = mapped_column(String(20))
    service_venue: Mapped[str | None] = mapped_column(String(255))
    service_address: Mapped[str | None] = mapped_column(Text)
    officiant: Mapped[str | None] = mapped_column(String(150))

    # The cortege leaving for the cemetery or crematorium.
    departure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    departure_point: Mapped[str | None] = mapped_column(String(255))

    # The burial or cremation itself.
    committal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    committal_place: Mapped[str | None] = mapped_column(String(255))
    committal_section: Mapped[str | None] = mapped_column(String(100))
    grave_number: Mapped[str | None] = mapped_column(String(50))
    grave_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    notes: Mapped[str | None] = mapped_column(Text)

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CaseCollection(Base):
    """
    A call-out to collect the deceased from where they died.

    This is the job that comes before the remains are taken into care.
    Only one collection per case can be open (scheduled or on the way)
    at a time, so a family is never sent two vehicles.
    """

    __tablename__ = "case_collections"

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_in(COLLECTION_STATUSES)})",
            name="ck_case_collections_status",
        ),
        CheckConstraint(
            f"pickup_type IN ({_in(PICKUP_TYPES)})",
            name="ck_case_collections_pickup_type",
        ),
        CheckConstraint(
            "(status = 'collected') = (collected_at IS NOT NULL)",
            name="ck_case_collections_collected_at",
        ),
        Index(
            "uq_case_collections_one_open",
            "case_id",
            unique=True,
            postgresql_where=text("status IN ('scheduled', 'en_route')"),
        ),
        Index(
            "ix_case_collections_schedule",
            "business_id",
            "scheduled_at",
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

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    pickup_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="home"
    )
    pickup_address: Mapped[str | None] = mapped_column(Text)
    pickup_contact_name: Mapped[str | None] = mapped_column(String(150))
    pickup_contact_phone: Mapped[str | None] = mapped_column(String(30))

    vehicle_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="SET NULL"),
        nullable=True,
    )
    driver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    en_route_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
