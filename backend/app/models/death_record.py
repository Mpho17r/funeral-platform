import uuid

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeathRecord(Base):
    """
    The facts about the death itself, one per case.

    Kept apart from the case so access to health and identity details
    (cause of death, ID number, informant) can be controlled and
    audited on its own.
    """

    __tablename__ = "death_records"

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            name="uq_death_records_case",
        ),
        CheckConstraint(
            "manner_of_death IN ('pending', 'natural', 'unnatural')",
            name="ck_death_records_manner",
        ),
        CheckConstraint(
            "unnatural_cause IS NULL OR unnatural_cause IN "
            "('accident', 'suicide', 'homicide', 'undetermined')",
            name="ck_death_records_unnatural_cause",
        ),
        CheckConstraint(
            "unnatural_cause IS NULL OR manner_of_death = 'unnatural'",
            name="ck_death_records_cause_needs_unnatural",
        ),
        CheckConstraint(
            "forensic_status IN ('not_applicable', 'referred', "
            "'post_mortem_done', 'released')",
            name="ck_death_records_forensic_status",
        ),
        CheckConstraint(
            "disposal_method IN ('burial', 'cremation', "
            "'repatriation')",
            name="ck_death_records_disposal_method",
        ),
        CheckConstraint(
            "deceased_id_type IN ('sa_id', 'passport', 'other')",
            name="ck_death_records_id_type",
        ),
        CheckConstraint(
            "place_of_death_type IS NULL OR place_of_death_type IN "
            "('home', 'hospital', 'public_place', 'other')",
            name="ck_death_records_place_type",
        ),
        CheckConstraint(
            "forensic_status = 'not_applicable' OR "
            "manner_of_death <> 'natural'",
            name="ck_death_records_forensic_not_natural",
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

    deceased_id_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="sa_id"
    )

    deceased_id_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    time_of_death: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )

    place_of_death_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    place_of_death: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    manner_of_death: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # Only for an unnatural death. Decides which cover waiting period
    # applies, so it is kept apart from the free-text cause.
    unnatural_cause: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    cause_of_death: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    certifier_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    forensic_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_applicable"
    )

    police_case_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    infectious_remains: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    disposal_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="burial"
    )

    informant_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    informant_relationship: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    informant_phone: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    informant_id_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CasePaperworkItem(Base):
    """
    One piece of paperwork a case needs: a form, permit or certificate.

    Standard items come from the checklist for the case; custom items
    cover anything particular to one family or one authority.
    """

    __tablename__ = "case_paperwork_items"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'obtained', 'not_applicable')",
            name="ck_case_paperwork_items_status",
        ),
        # A standard item appears once per case. Custom items may
        # repeat.
        Index(
            "uq_case_paperwork_items_standard",
            "case_id",
            "item_type",
            unique=True,
            postgresql_where=text("item_type <> 'custom'"),
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

    item_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )

    label: Mapped[str] = mapped_column(String(150), nullable=False)

    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    reference_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    obtained_on: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    obtained_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("case_documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
