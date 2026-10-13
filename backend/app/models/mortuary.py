import uuid

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


LOCATION_KINDS = (
    "fridge",
    "cold_room",
    "preparation_room",
    "chapel_of_rest",
    "other",
)

# Places that keep remains cold. Remains must be cooled within three
# hours of arriving, so only these count towards that.
COLD_LOCATION_KINDS = ("fridge", "cold_room")

RECEIVED_FROM_TYPES = (
    "home",
    "hospital",
    "state_mortuary",
    "scene",
    "other",
)

EVENT_TYPES = (
    "received",
    "moved",
    "prepared",
    "identified",
    "temperature",
    "released",
    "note",
)

PROCEDURES = ("washed", "embalmed", "dressed", "other")


def _in(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


class MortuaryLocation(Base):
    """
    A place remains can be kept: a fridge, a cold room, a preparation
    room or a chapel of rest.

    A capacity of None means unlimited. Cold places should be given the
    number of trays they really have, because the number of remains in
    a cold place must never exceed it.
    """

    __tablename__ = "mortuary_locations"

    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_in(LOCATION_KINDS)})",
            name="ck_mortuary_locations_kind",
        ),
        CheckConstraint(
            "capacity IS NULL OR capacity > 0",
            name="ck_mortuary_locations_capacity",
        ),
        Index(
            "uq_mortuary_locations_business_name",
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

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    kind: Mapped[str] = mapped_column(String(30), nullable=False)

    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RemainsRecord(Base):
    """
    The custody record of the deceased, one per case.

    It says who has the remains now and where, how they arrived, who
    identified them and, once they leave, who they were released to.
    Every change is also written to the custody log, which is never
    edited. The case cannot be deleted while this record exists.
    """

    __tablename__ = "remains_records"

    __table_args__ = (
        UniqueConstraint("case_id", name="uq_remains_records_case"),
        UniqueConstraint(
            "business_id",
            "tag_number",
            name="uq_remains_records_business_tag",
        ),
        CheckConstraint(
            "status IN ('in_custody', 'released')",
            name="ck_remains_records_status",
        ),
        CheckConstraint(
            f"received_from_type IN ({_in(RECEIVED_FROM_TYPES)})",
            name="ck_remains_records_received_from_type",
        ),
        CheckConstraint(
            "(status = 'released' AND released_at IS NOT NULL "
            "AND current_location_id IS NULL) "
            "OR (status = 'in_custody' AND released_at IS NULL)",
            name="ck_remains_records_release_state",
        ),
        Index("ix_remains_records_status", "business_id", "status"),
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

    # No ondelete: custody history must outlive any attempt to remove
    # the case.
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id"),
        nullable=False,
    )

    tag_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_custody",
        server_default=text("'in_custody'"),
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    received_from_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    received_from: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    collected_by_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    vehicle_resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="SET NULL"),
        nullable=True,
    )

    condition_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    belongings: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    current_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mortuary_locations.id"),
        nullable=True,
        index=True,
    )

    cooled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    identified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    identified_by_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    identified_relationship: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    received_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    released_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    released_to_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    released_to_id_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    released_to_relationship: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    release_override_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CustodyEvent(Base):
    """
    One entry in the custody log: arrived, moved, prepared,
    identified, temperature taken, released, or a note.

    The log is append-only. The database refuses any update or delete
    of a row, so the history of who had the remains and where cannot be
    rewritten, only added to.
    """

    __tablename__ = "custody_events"

    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({_in(EVENT_TYPES)})",
            name="ck_custody_events_type",
        ),
        CheckConstraint(
            f"procedure IS NULL OR procedure IN ({_in(PROCEDURES)})",
            name="ck_custody_events_procedure",
        ),
        Index(
            "ix_custody_events_remains_time",
            "remains_id",
            "occurred_at",
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

    remains_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("remains_records.id"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mortuary_locations.id"),
        nullable=True,
    )

    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mortuary_locations.id"),
        nullable=True,
    )

    procedure: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    temperature_c: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True
    )

    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
