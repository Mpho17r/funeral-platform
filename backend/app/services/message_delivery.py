"""
Sending queued messages for real.

Email goes out over SMTP when the server is configured (SMTP_HOST). SMS and
WhatsApp need a provider account, so for now those stay queued for the
one-tap manual send; the screen and `/communications/delivery` say so.

Rules that always hold:
  * a member who opted out is never contacted; their message is cancelled;
  * a failed attempt leaves the message queued with the reason, so a person
    can still send it by hand, and after `delivery_max_attempts` tries the
    scheduler stops retrying it;
  * a sent message records who or what sent it (`delivered_by`).
"""

import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.models.communication import (
    CommunicationMessage,
    MemberCommunicationPreference,
)


class DeliveryError(Exception):
    pass


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def automatic_channels() -> list[str]:
    return ["email"] if email_configured() else []


def send_email(to: str, subject: str | None, body: str) -> None:
    """Send one email. Raises DeliveryError with a plain reason."""
    if not email_configured():
        raise DeliveryError("Email sending is not set up")

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject or "Message"
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise DeliveryError(f"{type(exc).__name__}: {exc}"[:300]) from exc


def deliver_one(db: Session, message: CommunicationMessage) -> bool:
    """Try to send one queued message. Returns True when it went out.

    The caller commits.
    """
    if message.status != "queued":
        raise DeliveryError(f"A {message.status} message cannot be sent")

    pref = db.get(MemberCommunicationPreference, message.member_id)
    if pref is not None and pref.opted_out:
        message.status = "cancelled"
        message.cancelled_at = datetime.now(timezone.utc)
        message.cancel_reason = "Member opted out of messages"
        return False

    if message.channel != "email":
        raise DeliveryError(
            "Only email is sent automatically. Send this one with the "
            "WhatsApp or SMS button."
        )

    message.delivery_attempts += 1
    message.last_attempt_at = datetime.now(timezone.utc)
    try:
        send_email(message.recipient, message.subject, message.body)
    except DeliveryError as exc:
        message.delivery_error = str(exc)
        raise

    message.status = "sent"
    message.sent_at = message.last_attempt_at
    message.delivered_by = "smtp"
    message.delivery_error = None
    return True


def deliver_queued(
    db: Session, *, business_id=None, limit: int = 100
) -> dict[str, int]:
    """Send queued email messages that still have attempts left."""
    result = {"sent": 0, "failed": 0, "skipped": 0}
    if not email_configured():
        return result

    query = db.query(CommunicationMessage).filter(
        CommunicationMessage.status == "queued",
        CommunicationMessage.channel == "email",
        CommunicationMessage.delivery_attempts < settings.delivery_max_attempts,
    )
    if business_id is not None:
        query = query.filter(CommunicationMessage.business_id == business_id)

    for message in query.order_by(CommunicationMessage.created_at).limit(limit):
        try:
            if deliver_one(db, message):
                result["sent"] += 1
            else:
                result["skipped"] += 1
        except DeliveryError:
            result["failed"] += 1
        db.commit()
    return result
