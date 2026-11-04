"""Appointments: who is free, what to tell the customer, and reminders."""

from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.appointments import Appointment
from app.models.business import Business
from app.models.sales import Customer
from app.services import contact_messages as messages
from app.services import leave as leave_service

TZ = ZoneInfo("Africa/Johannesburg")
LIVE = ("scheduled", "confirmed")
MAX_HOURS = 24


def local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TZ)


def when_text(start: datetime) -> str:
    start = local(start)
    return f"{start:%A} {start.day} {start:%B} at {start:%H:%M}"


def find_clash(
    db: Session,
    business_id: UUID,
    user_id: UUID,
    start: datetime,
    end: datetime,
    ignore: UUID | None = None,
) -> Appointment | None:
    """Another live appointment for the same person at the same time."""
    query = db.query(Appointment).filter(
        Appointment.business_id == business_id,
        Appointment.assigned_user_id == user_id,
        Appointment.status.in_(LIVE),
        Appointment.start_at < end,
        Appointment.end_at > start,
    )
    if ignore:
        query = query.filter(Appointment.id != ignore)
    return query.order_by(Appointment.start_at).first()


def on_leave_then(
    db: Session, business_id: UUID, user_id: UUID, start: datetime, end: datetime
) -> bool:
    """Is the person on approved leave on the day(s) of the appointment?"""
    day = local(start).date()
    last = local(end).date()
    while day <= last:
        if user_id in leave_service.on_leave(db, business_id, day):
            return True
        day += timedelta(days=1)
    return False


def check_times(start: datetime, end: datetime) -> None:
    if end <= start:
        raise ValueError("The end must be after the start.")
    if end - start > timedelta(hours=MAX_HOURS):
        raise ValueError("An appointment can be up to 24 hours long.")


def contact_for(db: Session, appt: Appointment):
    """(name, phone, email) to reach, from the customer or typed contact."""
    customer = db.get(Customer, appt.customer_id) if appt.customer_id else None
    return (
        (customer.name if customer else None) or appt.contact_name,
        (customer.phone if customer else None) or appt.contact_phone,
        (customer.email if customer else None) or appt.contact_email,
    )


def confirmation_text(appt: Appointment, name: str | None, business: Business):
    where = f" at {appt.location}" if appt.location else ""
    contact = f" on {business.phone}" if business.phone else ""
    subject = f"Your appointment on {local(appt.start_at):%d %B}"
    body = (
        f"Hello {name or 'there'},\n\n"
        f"Your appointment with {business.name} is booked for "
        f"{when_text(appt.start_at)}{where}.\n\n"
        f"If you need to change it, please contact us{contact}.\n\n"
        f"Kind regards,\n{business.name}"
    )
    return subject, body


def reminder_text(appt: Appointment, name: str | None, business: Business):
    where = f" at {appt.location}" if appt.location else ""
    contact = f" on {business.phone}" if business.phone else ""
    subject = f"Reminder: your appointment {when_text(appt.start_at)}"
    body = (
        f"Hello {name or 'there'},\n\n"
        f"A reminder that you have an appointment with {business.name} on "
        f"{when_text(appt.start_at)}{where}.\n\n"
        f"If you can no longer make it, please let us know{contact}.\n\n"
        f"Kind regards,\n{business.name}"
    )
    return subject, body


def queue_message(
    db: Session,
    appt: Appointment,
    business: Business,
    *,
    kind: str,
    channel: str | None = None,
    created_by: UUID | None = None,
    dedupe_key: str | None = None,
):
    """Queue a confirmation or reminder for the appointment's contact."""
    name, phone, email = contact_for(db, appt)
    picked = messages.best_channel(phone, email, channel)
    if picked is None:
        raise messages.MessageError(
            "This appointment has no usable phone number or email."
        )
    recipient = email if picked == "email" else phone
    build = confirmation_text if kind == "appointment_confirmation" else reminder_text
    subject, body = build(appt, name, business)
    return messages.queue(
        db,
        business_id=appt.business_id,
        channel=picked,
        recipient=recipient,
        subject=subject,
        body=body,
        customer_id=appt.customer_id,
        appointment_id=appt.id,
        recipient_name=name,
        kind=kind,
        dedupe_key=dedupe_key,
        created_by=created_by,
    )


def plan_reminders(db: Session, now: datetime | None = None) -> int:
    """Queue a reminder for appointments in the next 24 hours.

    Only for businesses that switched reminders on, only once per
    appointment time, and only when there is a way to reach the contact.
    """
    now = now or datetime.now(timezone.utc)
    queued = 0
    businesses = (
        db.query(Business).filter(Business.appointment_reminders.is_(True)).all()
    )
    for business in businesses:
        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.business_id == business.id,
                Appointment.status.in_(LIVE),
                Appointment.start_at > now,
                Appointment.start_at <= now + timedelta(hours=24),
            )
            .all()
        )
        for appt in upcoming:
            key = f"appt-reminder:{appt.id}:{appt.start_at.isoformat()}"
            exists = (
                db.query(messages.ContactMessage.id)
                .filter(
                    messages.ContactMessage.business_id == business.id,
                    messages.ContactMessage.dedupe_key == key,
                )
                .first()
            )
            if exists:
                continue
            try:
                queue_message(
                    db, appt, business, kind="appointment_reminder", dedupe_key=key
                )
                queued += 1
            except messages.MessageError:
                continue
        db.commit()
    return queued
