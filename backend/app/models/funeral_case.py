import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FuneralCase(Base):
    __tablename__ = "funeral_cases"

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

    case_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    deceased_full_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    date_of_death: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    next_of_kin_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    next_of_kin_phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    funeral_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    funeral_venue: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="open",
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
