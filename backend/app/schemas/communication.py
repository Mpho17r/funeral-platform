from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


Channel = Literal["whatsapp", "sms", "email"]
ReminderKind = Literal[
    "payment_due_soon",
    "payment_overdue",
    "lapse_warning",
    "lapsed",
]
MessageKind = Literal[
    "payment_due_soon",
    "payment_overdue",
    "lapse_warning",
    "lapsed",
    "custom",
]
MessageStatus = Literal["queued", "sent", "cancelled"]


def _strip(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()

    return stripped or None


# ============================================================
# TEMPLATES
# ============================================================

class TemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=1000)
    is_active: bool = True

    @field_validator("subject", "body", mode="after")
    @classmethod
    def not_blank(cls, value):
        stripped = value.strip()

        if not stripped:
            raise ValueError("Cannot be blank")

        return stripped


class TemplateResponse(BaseModel):
    kind: ReminderKind
    subject: str
    body: str
    is_active: bool
    # True while the built-in wording is in use.
    is_default: bool


class PlaceholderInfo(BaseModel):
    name: str
    description: str


class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]
    placeholders: list[PlaceholderInfo]


# ============================================================
# PREFERENCES
# ============================================================

class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_channel: Channel | None = None
    opted_out: bool | None = None
    opt_out_reason: str | None = None

    @field_validator("opt_out_reason", mode="after")
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class PreferenceResponse(BaseModel):
    member_id: UUID
    preferred_channel: Channel
    opted_out: bool
    opted_out_at: datetime | None
    opt_out_reason: str | None


# ============================================================
# REMINDER RUN
# ============================================================

class ReminderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kinds: list[ReminderKind] | None = None
    branch_id: UUID | None = None
    days_before: int = Field(default=3, ge=0, le=30)
    warning_days: int = Field(default=7, ge=1, le=60)
    overdue_repeat_days: int = Field(default=7, ge=1, le=60)
    lapsed_notice_days: int = Field(default=14, ge=1, le=90)


class ReminderItem(BaseModel):
    kind: ReminderKind
    member_id: UUID
    member_name: str
    membership_id: UUID
    membership_number: str
    channel: Channel
    recipient: str
    subject: str
    body: str


class SkippedItem(BaseModel):
    kind: ReminderKind
    member_id: UUID
    member_name: str
    membership_number: str
    reason: Literal["opted_out", "no_contact"]


class ReminderPlanResponse(BaseModel):
    date: str
    items: list[ReminderItem]
    skipped: list[SkippedItem]
    already_queued: int
    disabled_kinds: list[ReminderKind]
    counts: dict[str, int]


class ReminderGenerateResponse(ReminderPlanResponse):
    created: int


# ============================================================
# MESSAGES
# ============================================================

class CustomMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    channel: Channel | None = None
    subject: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("subject", mode="after")
    @classmethod
    def blank_subject(cls, value):
        return _strip(value)

    @field_validator("body", mode="after")
    @classmethod
    def not_blank(cls, value):
        stripped = value.strip()

        if not stripped:
            raise ValueError("Cannot be blank")

        return stripped


class MessageCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None

    @field_validator("reason", mode="after")
    @classmethod
    def blank_is_none(cls, value):
        return _strip(value)


class MessageResponse(BaseModel):
    id: UUID
    member_id: UUID
    member_name: str | None
    membership_id: UUID | None
    membership_number: str | None
    kind: MessageKind
    channel: Channel
    recipient: str
    subject: str | None
    body: str
    status: MessageStatus
    # A link that opens WhatsApp, the messages app or the mail app with
    # this message filled in.
    action_url: str
    created_at: datetime
    sent_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    delivery_attempts: int = 0
    delivery_error: str | None = None
    delivered_by: str | None = None


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    counts: dict[str, int]
