"""Messages to customers and contacts.

Email is sent over SMTP when the server has it. WhatsApp and SMS are one-tap
links a person opens on their phone or computer and then marks as sent: no
provider account is needed, and nothing is claimed as sent that was not.

A message freezes its wording and recipient when it is queued, so what the
history shows is what the customer was sent.
"""

from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointments import ContactMessage
from app.services import message_delivery
from app.services.communications import clean_email, normalize_phone

CHANNELS = ("whatsapp", "sms", "email")


class MessageError(ValueError):
    """The message cannot be made or sent; the text says why."""


# Wording a person can start from. Only {name} and {business} are filled in.
TEMPLATES = [
    {
        "key": "custom",
        "label": "Write my own",
        "subject": "",
        "body": "",
    },
    {
        "key": "thank_you",
        "label": "Thank you",
        "subject": "Thank you from {business}",
        "body": (
            "Hello {name},\n\nThank you for choosing {business}. "
            "If there is anything else we can do for you, please let us know.\n\n"
            "Kind regards,\n{business}"
        ),
    },
    {
        "key": "follow_up",
        "label": "Follow up",
        "subject": "Following up from {business}",
        "body": (
            "Hello {name},\n\nWe are following up from {business}. "
            "Please let us know a good time to speak.\n\nKind regards,\n{business}"
        ),
    },
    {
        "key": "payment_reminder",
        "label": "Friendly payment reminder",
        "subject": "A reminder from {business}",
        "body": (
            "Hello {name},\n\nThis is a friendly reminder about your "
            "outstanding balance with {business}. If you have already paid, "
            "please ignore this message.\n\nKind regards,\n{business}"
        ),
    },
]


def render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def templates_for(name: str | None, business: str) -> list[dict]:
    values = {"name": (name or "there").strip() or "there", "business": business}
    return [
        {
            "key": t["key"],
            "label": t["label"],
            "subject": render(t["subject"], values),
            "body": render(t["body"], values),
        }
        for t in TEMPLATES
    ]


def check_recipient(channel: str, recipient: str) -> str:
    """The recipient in its clean form for this channel, or MessageError."""
    if channel not in CHANNELS:
        raise MessageError("Choose WhatsApp, SMS or email.")

    if channel == "email":
        email = clean_email(recipient)
        if not email:
            raise MessageError("That email address does not look right.")
        return email

    phone = normalize_phone(recipient)
    if not phone:
        raise MessageError("That phone number does not look right.")
    return phone


def best_channel(phone: str | None, email: str | None, preferred: str | None = None):
    """The channel to use for a contact, or None when we have nothing usable."""
    usable = {
        "whatsapp": normalize_phone(phone),
        "sms": normalize_phone(phone),
        "email": clean_email(email),
    }
    if preferred and usable.get(preferred):
        return preferred
    for channel in ("whatsapp", "email", "sms"):
        if usable[channel]:
            return channel
    return None


def link_for(message: ContactMessage) -> str | None:
    """The one-tap link for a WhatsApp or SMS message."""
    if message.channel == "whatsapp":
        return f"https://wa.me/{message.recipient}?text={quote(message.body)}"
    if message.channel == "sms":
        return f"sms:+{message.recipient}?body={quote(message.body)}"
    return None


def queue(
    db: Session,
    *,
    business_id: UUID,
    channel: str,
    recipient: str,
    body: str,
    subject: str | None = None,
    customer_id: UUID | None = None,
    appointment_id: UUID | None = None,
    recipient_name: str | None = None,
    kind: str = "custom",
    dedupe_key: str | None = None,
    created_by: UUID | None = None,
) -> ContactMessage:
    """Add a message to the queue. The caller commits."""
    recipient = check_recipient(channel, recipient)
    body = (body or "").strip()
    if not body:
        raise MessageError("Write the message first.")
    if len(body) > 2000:
        raise MessageError("Keep the message under 2000 characters.")

    message = ContactMessage(
        business_id=business_id,
        customer_id=customer_id,
        appointment_id=appointment_id,
        recipient_name=(recipient_name or None),
        kind=kind,
        channel=channel,
        recipient=recipient,
        subject=(subject or "").strip() or None,
        body=body,
        status="queued",
        dedupe_key=dedupe_key,
        created_by=created_by,
    )
    db.add(message)
    db.flush()
    return message


def deliver_one(message: ContactMessage) -> bool:
    """Send one queued email. True when it went out; the caller commits."""
    if message.status != "queued":
        raise MessageError(f"A {message.status} message cannot be sent.")
    if message.channel != "email":
        raise MessageError(
            "Only email is sent automatically. Use the WhatsApp or SMS button."
        )

    message.delivery_attempts += 1
    message.last_attempt_at = datetime.now(timezone.utc)
    try:
        message_delivery.send_email(message.recipient, message.subject, message.body)
    except message_delivery.DeliveryError as exc:
        message.delivery_error = str(exc)
        raise MessageError(f"Could not send the email: {exc}") from exc

    message.status = "sent"
    message.sent_at = message.last_attempt_at
    message.delivered_by = "smtp"
    message.delivery_error = None
    return True


def deliver_queued(db: Session, *, limit: int = 100) -> dict[str, int]:
    """Send waiting emails (the scheduler calls this)."""
    from app.config import settings

    result = {"sent": 0, "failed": 0}
    if not message_delivery.email_configured():
        return result

    waiting = (
        db.query(ContactMessage)
        .filter(
            ContactMessage.status == "queued",
            ContactMessage.channel == "email",
            ContactMessage.delivery_attempts < settings.delivery_max_attempts,
        )
        .order_by(ContactMessage.created_at)
        .limit(limit)
        .all()
    )
    for message in waiting:
        try:
            deliver_one(message)
            result["sent"] += 1
        except MessageError:
            result["failed"] += 1
        db.commit()
    return result


def as_dict(message: ContactMessage, customer_name: str | None = None) -> dict:
    """How a message is shown on screen, with its one-tap link if any."""
    queued = message.status == "queued"
    return {
        "id": str(message.id),
        "customer_id": str(message.customer_id) if message.customer_id else None,
        "customer_name": customer_name,
        "appointment_id": str(message.appointment_id) if message.appointment_id else None,
        "recipient_name": message.recipient_name,
        "kind": message.kind,
        "channel": message.channel,
        "recipient": message.recipient,
        "subject": message.subject,
        "body": message.body,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "delivered_by": message.delivered_by,
        "delivery_error": message.delivery_error,
        "cancel_reason": message.cancel_reason,
        "link": link_for(message) if queued else None,
    }


def try_send_now(message: ContactMessage) -> None:
    """Send an email straight away when email is set up. A failure leaves it
    queued (with the reason on it) for the scheduler or a manual retry."""
    if message.channel == "email" and message_delivery.email_configured():
        try:
            deliver_one(message)
        except MessageError:
            pass
