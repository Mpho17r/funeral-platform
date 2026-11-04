"""Appointments and bookings, messages to customers, and the business's
document library. Used by funeral homes and general businesses alike."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
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

APPOINTMENT_STATUSES = ("scheduled", "confirmed", "completed", "cancelled", "no_show")
MESSAGE_CHANNELS = ("whatsapp", "sms", "email")
MESSAGE_STATUSES = ("queued", "sent", "cancelled")
MESSAGE_KINDS = ("custom", "appointment_confirmation", "appointment_reminder")
DOCUMENT_CATEGORIES = (
    "contract", "receipt", "invoice", "licence", "policy", "identity", "other",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _business() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def _user(nullable=True) -> Mapped[uuid.UUID | None]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=nullable,
    )


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_in(APPOINTMENT_STATUSES)})", name="ck_appointments_status"
        ),
        CheckConstraint("end_at > start_at", name="ck_appointments_times"),
        Index("ix_appointments_business_start", "business_id", "start_at"),
        Index("ix_appointments_assignee_start", "assigned_user_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    business_id: Mapped[uuid.UUID] = _business()
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="scheduled")

    # A general business picks a customer; anyone can type a contact instead
    # (a funeral home meets families who are not customers).
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_email: Mapped[str | None] = mapped_column(String(255))

    location: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    assigned_user_id: Mapped[uuid.UUID | None] = _user()
    created_by: Mapped[uuid.UUID | None] = _user()
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class ContactMessage(Base):
    """One message to a customer or contact, ready to send.

    The wording and recipient are frozen when it is queued. Email goes out
    over SMTP when the server has it; WhatsApp and SMS are one-tap links a
    person sends and then marks sent.
    """

    __tablename__ = "contact_messages"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_in(MESSAGE_STATUSES)})", name="ck_contact_messages_status"
        ),
        CheckConstraint(
            f"channel IN ({_in(MESSAGE_CHANNELS)})", name="ck_contact_messages_channel"
        ),
        CheckConstraint(
            f"kind IN ({_in(MESSAGE_KINDS)})", name="ck_contact_messages_kind"
        ),
        Index(
            "uq_contact_messages_dedupe", "business_id", "dedupe_key", unique=True,
            postgresql_where="dedupe_key IS NOT NULL",
        ),
        Index("ix_contact_messages_queue", "business_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    business_id: Mapped[uuid.UUID] = _business()
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"),
        index=True,
    )
    recipient_name: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="custom")
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    dedupe_key: Mapped[str | None] = mapped_column(String(150))
    created_by: Mapped[uuid.UUID | None] = _user()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_by: Mapped[uuid.UUID | None] = _user()
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_error: Mapped[str | None] = mapped_column(Text)
    delivered_by: Mapped[str | None] = mapped_column(String(20))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class BusinessDocument(Base):
    """A file the business keeps: a contract, a licence, a receipt."""

    __tablename__ = "business_documents"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({_in(DOCUMENT_CATEGORIES)})",
            name="ck_business_documents_category",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    business_id: Mapped[uuid.UUID] = _business()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    expires_on: Mapped[date | None] = mapped_column(Date, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = _user()
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
