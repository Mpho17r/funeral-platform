"""Payment and membership reminders.

The system works out who should be reminded about what, writes the
message, and queues it. A person sends it (the screen offers a WhatsApp,
SMS or email link) and marks it sent, so nothing is ever sent without a
person seeing it first, and every message is on record.

Reminder rules
--------------
* ``payment_due_soon``: an unpaid contribution falls due within the next
  few days.
* ``payment_overdue``: the oldest unpaid contribution is past its due
  date, but the membership has not lapsed yet. Repeats no more often
  than every ``overdue_repeat_days``.
* ``lapse_warning``: the membership will lapse within the next few days.
  Sent once for each stretch of arrears.
* ``lapsed``: the membership lapsed recently. Sent once for each stretch
  of arrears, and only while the lapse is recent, so switching this on
  for a business with old lapsed members does not message all of them.

A member who has opted out is never queued a reminder. A member with no
usable phone number or email address is reported back so staff can fix
the record.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.communication import (
    CHANNELS,
    CommunicationMessage,
    MemberCommunicationPreference,
    MessageTemplate,
    REMINDER_KINDS,
)
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan


# South Africa is UTC+2 all year.
SAST = timezone(timedelta(hours=2))

UNPAID_STATUSES = ("due", "partially_paid", "overdue")

# Memberships in these states are not reminded about payments.
SKIPPED_MEMBERSHIP_STATUSES = ("cancelled",)

DEFAULT_CHANNEL = "whatsapp"


class CommunicationError(Exception):
    """A rule was broken; the message is safe to show to staff."""


# ------------------------------------------------------------
# Wording
# ------------------------------------------------------------

PLACEHOLDERS = {
    "member_name": "The member's first name",
    "business_name": "Your business name",
    "business_phone": "Your business phone number",
    "membership_number": "The membership number",
    "plan_name": "The plan name",
    "amount_due": "The amount still unpaid, for example R250.00",
    "due_date": "When the contribution is or was due",
    "days_overdue": "How long it has been overdue, for example 3 days",
    "lapse_date": "The day the membership lapses or lapsed",
}

DEFAULT_TEMPLATES = {
    "payment_due_soon": (
        "Contribution due soon",
        "Hello {member_name}, a friendly reminder from {business_name}: "
        "your funeral cover contribution of {amount_due} for membership "
        "{membership_number} is due on {due_date}. Thank you for keeping "
        "your cover active.",
    ),
    "payment_overdue": (
        "Contribution overdue",
        "Hello {member_name}, your contribution of {amount_due} for "
        "membership {membership_number} was due on {due_date} and is now "
        "{days_overdue} overdue. Please pay as soon as you can so your "
        "cover stays active. If you have already paid, please ignore "
        "this message. {business_name}",
    ),
    "lapse_warning": (
        "Your cover is about to lapse",
        "Hello {member_name}, your membership {membership_number} with "
        "{business_name} will lapse on {lapse_date} if the outstanding "
        "{amount_due} is not paid. Once it lapses you will no longer "
        "have funeral cover. Please contact us at {business_phone} if "
        "you need help.",
    ),
    "lapsed": (
        "Your cover has lapsed",
        "Hello {member_name}, your membership {membership_number} with "
        "{business_name} lapsed on {lapse_date} because of unpaid "
        "contributions, so your funeral cover has stopped. Please "
        "contact us at {business_phone} to find out how to reinstate it.",
    ),
}

PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")


def unknown_placeholders(text: str) -> list[str]:
    return sorted(
        {
            name
            for name in PLACEHOLDER_PATTERN.findall(text)
            if name not in PLACEHOLDERS
        }
    )


def render(text: str, values: dict[str, str]) -> str:
    """Fill the {placeholders}. Anything unknown is left empty rather
    than failing, so a message is never blocked by a typo."""

    return " ".join(
        PLACEHOLDER_PATTERN.sub(
            lambda match: values.get(match.group(1), ""),
            text,
        ).split()
    )


def format_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def format_money(value: Decimal) -> str:
    return f"R{Decimal(value):,.2f}"


def days_text(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def today_in_south_africa() -> date:
    return datetime.now(SAST).date()


# ------------------------------------------------------------
# Contact details
# ------------------------------------------------------------

def normalize_phone(phone: str | None) -> str | None:
    """Digits only, in international form, or None when it is not a
    usable number. South African numbers starting 0 become 27..."""

    if not phone:
        return None

    cleaned = phone.strip()
    digits = re.sub(r"\D", "", cleaned)

    if cleaned.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        digits = "27" + digits[1:]

    if not 8 <= len(digits) <= 15:
        return None

    return digits


def clean_email(email: str | None) -> str | None:
    if not email:
        return None

    value = email.strip()

    if "@" not in value or " " in value:
        return None

    return value


def pick_channel(
    member: Member,
    preferred: str,
) -> tuple[str, str] | None:
    """The channel and recipient to use: the member's preferred channel
    when we have the contact detail for it, otherwise whichever works."""

    phone = normalize_phone(member.phone)
    email = clean_email(member.email)

    options = {
        "whatsapp": phone,
        "sms": phone,
        "email": email,
    }

    order = [preferred] + [
        channel for channel in CHANNELS if channel != preferred
    ]

    for channel in order:
        if options.get(channel):
            return channel, options[channel]

    return None


def action_url(message: CommunicationMessage) -> str:
    """A link that opens the right app with the message filled in."""

    body = quote(message.body, safe="")

    if message.channel == "whatsapp":
        return f"https://wa.me/{message.recipient}?text={body}"

    if message.channel == "sms":
        return f"sms:+{message.recipient}?body={body}"

    subject = quote(message.subject or "", safe="")

    return f"mailto:{message.recipient}?subject={subject}&body={body}"


# ------------------------------------------------------------
# Templates and preferences
# ------------------------------------------------------------

@dataclass
class TemplateView:
    kind: str
    subject: str
    body: str
    is_active: bool
    is_default: bool


def load_templates(
    db: Session,
    business_id: UUID,
) -> dict[str, TemplateView]:
    saved = {
        row.kind: row
        for row in db.scalars(
            select(MessageTemplate).where(
                MessageTemplate.business_id == business_id
            )
        ).all()
    }

    result = {}

    for kind in REMINDER_KINDS:
        row = saved.get(kind)

        if row is not None:
            result[kind] = TemplateView(
                kind, row.subject, row.body, row.is_active, False
            )
        else:
            subject, body = DEFAULT_TEMPLATES[kind]
            result[kind] = TemplateView(kind, subject, body, True, True)

    return result


def load_preferences(
    db: Session,
    business_id: UUID,
) -> dict[UUID, MemberCommunicationPreference]:
    return {
        row.member_id: row
        for row in db.scalars(
            select(MemberCommunicationPreference).where(
                MemberCommunicationPreference.business_id == business_id
            )
        ).all()
    }


# ------------------------------------------------------------
# Working out who to remind
# ------------------------------------------------------------

@dataclass
class Candidate:
    kind: str
    member: Member
    membership: Membership
    contribution: MembershipContribution
    channel: str
    recipient: str
    subject: str
    body: str
    dedupe_key: str


@dataclass
class Skipped:
    kind: str
    member_id: UUID
    member_name: str
    membership_number: str
    reason: str  # opted_out or no_contact


@dataclass
class ReminderPlan:
    today: date
    candidates: list[Candidate] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    already_queued: int = 0
    disabled_kinds: list[str] = field(default_factory=list)


def outstanding(contribution: MembershipContribution) -> Decimal:
    return Decimal(contribution.amount_due) - Decimal(
        contribution.amount_paid
    )


def is_unpaid(contribution: MembershipContribution) -> bool:
    return (
        contribution.status in UNPAID_STATUSES
        and contribution.amount_paid < contribution.amount_due
    )


def plan_reminders(
    db: Session,
    business: Business,
    *,
    today: date | None = None,
    kinds: list[str] | None = None,
    branch_id: UUID | None = None,
    days_before: int = 3,
    warning_days: int = 7,
    overdue_repeat_days: int = 7,
    lapsed_notice_days: int = 14,
) -> ReminderPlan:
    today = today or today_in_south_africa()
    wanted = set(kinds) if kinds else set(REMINDER_KINDS)

    templates = load_templates(db, business.id)
    preferences = load_preferences(db, business.id)

    plan = ReminderPlan(today=today)

    for kind in REMINDER_KINDS:
        if kind in wanted and not templates[kind].is_active:
            plan.disabled_kinds.append(kind)
            wanted.discard(kind)

    if not wanted:
        return plan

    # Every membership that could need a reminder, with its member and
    # plan, and its unpaid contributions in due-date order.
    query = (
        select(Membership, Member, MembershipPlan)
        .join(Member, Member.id == Membership.member_id)
        .join(MembershipPlan, MembershipPlan.id == Membership.plan_id)
        .where(
            Membership.business_id == business.id,
            Membership.status.notin_(SKIPPED_MEMBERSHIP_STATUSES),
            Member.status == "active",
            Member.archived_at.is_(None),
        )
        .order_by(Membership.membership_number.asc())
    )

    if branch_id is not None:
        query = query.where(Member.branch_id == branch_id)

    rows = db.execute(query).all()

    if not rows:
        return plan

    membership_ids = [membership.id for membership, _, _ in rows]

    unpaid_by_membership: dict[UUID, list[MembershipContribution]] = {}

    for contribution in db.scalars(
        select(MembershipContribution)
        .where(
            MembershipContribution.business_id == business.id,
            MembershipContribution.membership_id.in_(membership_ids),
            MembershipContribution.status.in_(UNPAID_STATUSES),
        )
        .order_by(
            MembershipContribution.due_date.asc(),
            MembershipContribution.contribution_period.asc(),
        )
    ).all():
        if is_unpaid(contribution):
            unpaid_by_membership.setdefault(
                contribution.membership_id, []
            ).append(contribution)

    recent_overdue = {
        membership_id
        for membership_id in db.scalars(
            select(CommunicationMessage.membership_id).where(
                CommunicationMessage.business_id == business.id,
                CommunicationMessage.kind == "payment_overdue",
                CommunicationMessage.status != "cancelled",
                CommunicationMessage.created_at
                >= datetime.now(timezone.utc)
                - timedelta(days=overdue_repeat_days),
            )
        ).all()
        if membership_id is not None
    }

    existing_keys = set(
        db.scalars(
            select(CommunicationMessage.dedupe_key).where(
                CommunicationMessage.business_id == business.id,
                CommunicationMessage.dedupe_key.is_not(None),
            )
        ).all()
    )

    lapse_after = business.lapse_after_days

    def add(
        kind: str,
        member: Member,
        membership: Membership,
        membership_plan: MembershipPlan,
        contribution: MembershipContribution,
        dedupe_key: str,
        *,
        days_overdue: int = 0,
        lapse_date: date | None = None,
    ) -> None:
        if dedupe_key in existing_keys:
            plan.already_queued += 1
            return

        name = f"{member.first_name} {member.last_name}".strip()
        preference = preferences.get(member.id)

        if preference is not None and preference.opted_out:
            plan.skipped.append(
                Skipped(
                    kind, member.id, name,
                    membership.membership_number, "opted_out",
                )
            )
            return

        preferred = (
            preference.preferred_channel
            if preference is not None
            else DEFAULT_CHANNEL
        )
        choice = pick_channel(member, preferred)

        if choice is None:
            plan.skipped.append(
                Skipped(
                    kind, member.id, name,
                    membership.membership_number, "no_contact",
                )
            )
            return

        channel, recipient = choice
        template = templates[kind]

        values = {
            "member_name": member.first_name,
            "business_name": business.name,
            "business_phone": business.phone or "our office",
            "membership_number": membership.membership_number,
            "plan_name": membership_plan.name,
            "amount_due": format_money(outstanding(contribution)),
            "due_date": format_date(contribution.due_date),
            "days_overdue": days_text(days_overdue),
            "lapse_date": format_date(lapse_date) if lapse_date else "",
        }

        plan.candidates.append(
            Candidate(
                kind=kind,
                member=member,
                membership=membership,
                contribution=contribution,
                channel=channel,
                recipient=recipient,
                subject=render(template.subject, values),
                body=render(template.body, values),
                dedupe_key=dedupe_key,
            )
        )

    for membership, member, membership_plan in rows:
        unpaid = unpaid_by_membership.get(membership.id, [])

        if not unpaid:
            continue

        # Coming due: any unpaid contribution due in the next few days.
        if "payment_due_soon" in wanted:
            for contribution in unpaid:
                if (
                    today
                    <= contribution.due_date
                    <= today + timedelta(days=days_before)
                ):
                    add(
                        "payment_due_soon",
                        member,
                        membership,
                        membership_plan,
                        contribution,
                        f"payment_due_soon:{contribution.id}",
                    )

        # Past due: the oldest unpaid contribution decides.
        oldest = unpaid[0]

        if oldest.due_date >= today:
            continue

        days_in_arrears = (today - oldest.due_date).days
        lapse_date = oldest.due_date + timedelta(days=lapse_after)
        days_to_lapse = lapse_after - days_in_arrears

        if days_to_lapse > 0:
            warning_key = f"lapse_warning:{membership.id}:{oldest.due_date}"

            # A lapse warning already says what the overdue notice would,
            # so inside the warning window it replaces the notice rather
            # than sending the member two messages.
            warning_now = (
                "lapse_warning" in wanted
                and days_to_lapse <= warning_days
            )

            if (
                "payment_overdue" in wanted
                and membership.id not in recent_overdue
                and not warning_now
            ):
                add(
                    "payment_overdue",
                    member,
                    membership,
                    membership_plan,
                    oldest,
                    f"payment_overdue:{oldest.id}:{today.isoformat()}",
                    days_overdue=days_in_arrears,
                    lapse_date=lapse_date,
                )

            if "lapse_warning" in wanted and days_to_lapse <= warning_days:
                add(
                    "lapse_warning",
                    member,
                    membership,
                    membership_plan,
                    oldest,
                    warning_key,
                    days_overdue=days_in_arrears,
                    lapse_date=lapse_date,
                )

        elif (
            "lapsed" in wanted
            and (today - lapse_date).days <= lapsed_notice_days
        ):
            add(
                "lapsed",
                member,
                membership,
                membership_plan,
                oldest,
                f"lapsed:{membership.id}:{oldest.due_date}",
                days_overdue=days_in_arrears,
                lapse_date=lapse_date,
            )

    return plan


def queue_candidates(
    db: Session,
    business_id: UUID,
    user_id: UUID | None,
    candidates: list[Candidate],
) -> tuple[list[CommunicationMessage], int]:
    """Write the messages. A reminder another request queued a moment
    ago is skipped rather than duplicated."""

    created = []
    duplicates = 0

    for candidate in candidates:
        message = CommunicationMessage(
            business_id=business_id,
            member_id=candidate.member.id,
            membership_id=candidate.membership.id,
            contribution_id=candidate.contribution.id,
            kind=candidate.kind,
            channel=candidate.channel,
            recipient=candidate.recipient,
            subject=candidate.subject,
            body=candidate.body,
            status="queued",
            dedupe_key=candidate.dedupe_key,
            created_by=user_id,
        )

        try:
            with db.begin_nested():
                db.add(message)
                db.flush()
        except IntegrityError:
            duplicates += 1
            continue

        created.append(message)

    return created, duplicates
