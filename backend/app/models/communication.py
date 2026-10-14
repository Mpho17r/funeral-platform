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


CHANNELS = ("whatsapp", "sms", "email")

MESSAGE_STATUSES = ("queued", "sent", "cancelled")

# Reminder kinds the system generates, plus free-form messages that
# staff write themselves.
REMINDER_KINDS = (
    "payment_due_soon",
    "payment_overdue",
    "lapse_warning",
    "lapsed",
)
MESSAGE_KINDS = REMINDER_KINDS + ("custom",)


def _in(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


class MessageTemplate(Base):
    """
    The wording of one kind of reminder for one business.

    Without a saved row the built-in wording is used, so a business only
    has a row once it has changed something.
    """

    __tablename__ = "message_templates"

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "kind",
            name="uq_message_templates_business_kind",
        ),
        CheckConstraint(
            f"kind IN ({_in(REMINDER_KINDS)})",
            name="ck_message_templates_kind",
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

    kind: Mapped[str] = mapped_column(String(30), nullable=False)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # A switched-off template stops that kind of reminder from being
    # generated at all.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
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


class MemberCommunicationPreference(Base):
    """
    How a member wants to be contacted, and whether they have asked us
    to stop. A member without a row has the defaults: WhatsApp, and not
    opted out.
    """

    __tablename__ = "member_communication_preferences"

    __table_args__ = (
        CheckConstraint(
            f"preferred_channel IN ({_in(CHANNELS)})",
            name="ck_member_comm_prefs_channel",
        ),
        CheckConstraint(
            "opted_out = (opted_out_at IS NOT NULL)",
            name="ck_member_comm_prefs_opt_out_time",
        ),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    preferred_channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="whatsapp"
    )

    opted_out: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    opted_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opt_out_reason: Mapped[str | None] = mapped_column(Text)

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
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


class CommunicationMessage(Base):
    """
    One message to one member, ready to send.

    The system writes the wording and the recipient; a person sends it
    (the screen gives a one-tap WhatsApp, SMS or email link) and then
    marks it sent. The wording and recipient are frozen when the message
    is created, so the record shows exactly what the member was told.

    Reminders carry a dedupe key, so running the generator twice never
    queues the same reminder twice.
    """

    __tablename__ = "communication_messages"

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_in(MESSAGE_STATUSES)})",
            name="ck_communication_messages_status",
        ),
        CheckConstraint(
            f"channel IN ({_in(CHANNELS)})",
            name="ck_communication_messages_channel",
        ),
        CheckConstraint(
            f"kind IN ({_in(MESSAGE_KINDS)})",
            name="ck_communication_messages_kind",
        ),
        CheckConstraint(
            "(status = 'sent') = (sent_at IS NOT NULL)",
            name="ck_communication_messages_sent_at",
        ),
        Index(
            "uq_communication_messages_dedupe",
            "business_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
        Index(
            "ix_communication_messages_queue",
            "business_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_communication_messages_member",
            "member_id",
            "created_at",
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

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )

    membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
    )

    contribution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_contributions.id", ondelete="SET NULL"),
        nullable=True,
    )

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    # The phone number or email address as it was when queued.
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)

    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )

    dedupe_key: Mapped[str | None] = mapped_column(String(150))

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
