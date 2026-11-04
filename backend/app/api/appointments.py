"""Appointments and bookings, for funeral homes and other businesses."""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.appointments import Appointment
from app.models.business import Business
from app.models.sales import Customer
from app.models.user import User
from app.services import appointments as calc
from app.services import contact_messages as messages
from app.services.audit_service import create_audit_log
from app.services.notifications import notify

router = APIRouter(prefix="/appointments", tags=["Appointments"])


class AppointmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    customer_id: UUID | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=3000)
    assigned_user_id: UUID | None = None
    allow_clash: bool = False
    send_confirmation: bool = False
    channel: str | None = None


class AppointmentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None
    customer_id: UUID | None = None
    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=3000)
    assigned_user_id: UUID | None = None
    allow_clash: bool = False


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "appointment_confirmation"
    channel: str | None = None


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appointment_reminders: bool


def _aware(value: datetime) -> datetime:
    """A time without a zone is read as South African time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=calc.TZ)
    return value


def _ids(current_user):
    return UUID(str(current_user["business_id"])), UUID(str(current_user["user_id"]))


def _out(db: Session, appt: Appointment) -> dict:
    customer = db.get(Customer, appt.customer_id) if appt.customer_id else None
    assignee = db.get(User, appt.assigned_user_id) if appt.assigned_user_id else None
    name, phone, email = calc.contact_for(db, appt)
    return {
        "id": str(appt.id),
        "title": appt.title,
        "start_at": appt.start_at.isoformat(),
        "end_at": appt.end_at.isoformat(),
        "status": appt.status,
        "customer_id": str(appt.customer_id) if appt.customer_id else None,
        "customer_name": customer.name if customer else None,
        "contact_name": appt.contact_name,
        "contact_phone": appt.contact_phone,
        "contact_email": appt.contact_email,
        "who": name,
        "who_phone": phone,
        "who_email": email,
        "location": appt.location,
        "notes": appt.notes,
        "assigned_user_id": str(appt.assigned_user_id) if appt.assigned_user_id else None,
        "assigned_user_name": assignee.full_name if assignee else None,
        "cancel_reason": appt.cancel_reason,
        "created_at": appt.created_at.isoformat(),
    }


def _get(db: Session, business_id: UUID, appt_id: UUID) -> Appointment:
    appt = (
        db.query(Appointment)
        .filter(Appointment.id == appt_id, Appointment.business_id == business_id)
        .first()
    )
    if appt is None:
        raise HTTPException(404, "Appointment not found")
    return appt


def _check_refs(db, business_id, customer_id, assigned_user_id):
    if customer_id and not (
        db.query(Customer.id)
        .filter(Customer.id == customer_id, Customer.business_id == business_id)
        .first()
    ):
        raise HTTPException(404, "Customer not found")
    if assigned_user_id and not (
        db.query(User.id)
        .filter(
            User.id == assigned_user_id,
            User.business_id == business_id,
            User.is_active.is_(True),
        )
        .first()
    ):
        raise HTTPException(404, "That person is not on your team")


def _check_free(db, business_id, user_id, start, end, allow_clash, ignore=None):
    """A person cannot be in two places, or booked on a day of leave, unless
    the booking is confirmed anyway. Both come back as 409."""
    if not user_id or allow_clash:
        return
    if calc.on_leave_then(db, business_id, user_id, start, end):
        raise HTTPException(409, "That person is on approved leave that day.")
    other = calc.find_clash(db, business_id, user_id, start, end, ignore)
    if other:
        raise HTTPException(
            409,
            f"That person already has “{other.title}” at "
            f"{calc.when_text(other.start_at)}.",
        )


def _contact_check(contact_phone, contact_email):
    if contact_phone and not messages.normalize_phone(contact_phone):
        raise HTTPException(422, "That phone number does not look right.")
    if contact_email and not messages.clean_email(contact_email):
        raise HTTPException(422, "That email address does not look right.")


@router.get("")
def list_appointments(
    start: date | None = None,
    end: date | None = None,
    status: str | None = None,
    mine: bool = False,
    upcoming: bool = False,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.view")),
):
    business_id, user_id = _ids(current_user)
    query = db.query(Appointment).filter(Appointment.business_id == business_id)

    if upcoming:
        query = query.filter(
            Appointment.end_at >= datetime.now(timezone.utc),
            Appointment.status.in_(calc.LIVE),
        )
    if start:
        query = query.filter(
            Appointment.end_at >= datetime.combine(start, time.min, tzinfo=calc.TZ)
        )
    if end:
        query = query.filter(
            Appointment.start_at
            < datetime.combine(end + timedelta(days=1), time.min, tzinfo=calc.TZ)
        )
    if status:
        query = query.filter(Appointment.status == status)
    if mine:
        query = query.filter(
            or_(Appointment.assigned_user_id == user_id, Appointment.created_by == user_id)
        )
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Appointment.title.ilike(like),
                Appointment.contact_name.ilike(like),
                Appointment.location.ilike(like),
                Appointment.customer_id.in_(
                    db.query(Customer.id).filter(
                        Customer.business_id == business_id, Customer.name.ilike(like)
                    )
                ),
            )
        )

    rows = query.order_by(Appointment.start_at).limit(500).all()
    business = db.get(Business, business_id)
    return {
        "items": [_out(db, a) for a in rows],
        "reminders_on": bool(business and business.appointment_reminders),
        "email_ready": messages.message_delivery.email_configured(),
    }


@router.post("", status_code=201)
def create_appointment(
    data: AppointmentIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    business_id, user_id = _ids(current_user)
    start = _aware(data.start_at)
    end = _aware(data.end_at) if data.end_at else start + timedelta(
        minutes=data.duration_minutes
    )
    try:
        calc.check_times(start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    _check_refs(db, business_id, data.customer_id, data.assigned_user_id)
    _contact_check(data.contact_phone, data.contact_email)
    _check_free(db, business_id, data.assigned_user_id, start, end, data.allow_clash)

    appt = Appointment(
        business_id=business_id,
        title=data.title.strip(),
        start_at=start,
        end_at=end,
        status="scheduled",
        customer_id=data.customer_id,
        contact_name=(data.contact_name or "").strip() or None,
        contact_phone=(data.contact_phone or "").strip() or None,
        contact_email=(data.contact_email or "").strip() or None,
        location=(data.location or "").strip() or None,
        notes=(data.notes or "").strip() or None,
        assigned_user_id=data.assigned_user_id,
        created_by=user_id,
    )
    db.add(appt)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="appointment.created",
        entity_type="appointment",
        entity_id=appt.id,
        details={"title": appt.title, "start_at": start.isoformat()},
        notes="Appointment booked.",
    )
    notify(
        db,
        business_id=business_id,
        user_ids=[appt.assigned_user_id],
        kind="appointment",
        title=f"Appointment: {appt.title}",
        body=calc.when_text(start),
        link="/appointments",
        actor_id=user_id,
    )

    sent = None
    note = None
    if data.send_confirmation:
        try:
            business = db.get(Business, business_id)
            message = calc.queue_message(
                db, appt, business, kind="appointment_confirmation",
                channel=data.channel, created_by=user_id,
            )
            messages.try_send_now(message)
            sent = messages.as_dict(message)
        except messages.MessageError as exc:
            note = str(exc)

    db.commit()
    db.refresh(appt)
    return {"appointment": _out(db, appt), "message": sent, "message_note": note}


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.view")),
):
    business_id, _ = _ids(current_user)
    appt = _get(db, business_id, appointment_id)
    from app.models.appointments import ContactMessage

    sent = (
        db.query(ContactMessage)
        .filter(
            ContactMessage.business_id == business_id,
            ContactMessage.appointment_id == appt.id,
        )
        .order_by(ContactMessage.created_at.desc())
        .all()
    )
    return {
        **_out(db, appt),
        "messages": [messages.as_dict(m) for m in sent],
    }


@router.patch("/{appointment_id}")
def update_appointment(
    appointment_id: UUID,
    data: AppointmentPatch,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    business_id, user_id = _ids(current_user)
    appt = _get(db, business_id, appointment_id)
    if appt.status not in calc.LIVE:
        raise HTTPException(409, f"A {appt.status.replace('_', ' ')} appointment cannot be changed.")

    sent = data.model_fields_set - {"allow_clash"}
    start = _aware(data.start_at) if "start_at" in sent and data.start_at else appt.start_at
    if "end_at" in sent and data.end_at:
        end = _aware(data.end_at)
    elif "start_at" in sent and data.start_at:
        # Moving the start keeps the length.
        end = start + (appt.end_at - appt.start_at)
    else:
        end = appt.end_at
    try:
        calc.check_times(start, end)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    assignee = data.assigned_user_id if "assigned_user_id" in sent else appt.assigned_user_id
    _check_refs(
        db, business_id,
        data.customer_id if "customer_id" in sent else None,
        data.assigned_user_id if "assigned_user_id" in sent else None,
    )
    _contact_check(
        data.contact_phone if "contact_phone" in sent else None,
        data.contact_email if "contact_email" in sent else None,
    )

    moved = start != appt.start_at or end != appt.end_at
    if moved or assignee != appt.assigned_user_id:
        _check_free(db, business_id, assignee, start, end, data.allow_clash, appt.id)

    for field in (
        "customer_id", "contact_name", "contact_phone", "contact_email",
        "location", "notes", "assigned_user_id",
    ):
        if field in sent:
            value = getattr(data, field)
            if isinstance(value, str):
                value = value.strip() or None
            setattr(appt, field, value)
    if "title" in sent and data.title:
        appt.title = data.title.strip()
    appt.start_at, appt.end_at = start, end

    create_audit_log(
        db, business_id=business_id, user_id=user_id,
        action="appointment.updated", entity_type="appointment",
        entity_id=appt.id, details={"moved": moved}, notes="Appointment changed.",
    )
    if moved:
        notify(
            db, business_id=business_id, user_ids=[appt.assigned_user_id],
            kind="appointment", title=f"Appointment moved: {appt.title}",
            body=calc.when_text(start), link="/appointments", actor_id=user_id,
        )
    db.commit()
    db.refresh(appt)
    return _out(db, appt)


def _change(db, current_user, appointment_id, new_status, allowed_from, action):
    business_id, user_id = _ids(current_user)
    appt = _get(db, business_id, appointment_id)
    if appt.status not in allowed_from:
        raise HTTPException(
            409, f"A {appt.status.replace('_', ' ')} appointment cannot be marked {new_status.replace('_', ' ')}."
        )
    appt.status = new_status
    create_audit_log(
        db, business_id=business_id, user_id=user_id, action=action,
        entity_type="appointment", entity_id=appt.id, details={"status": new_status},
        notes=f"Appointment marked {new_status.replace('_', ' ')}.",
    )
    return business_id, user_id, appt


@router.post("/{appointment_id}/confirm")
def confirm(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    _, _, appt = _change(db, current_user, appointment_id, "confirmed", ("scheduled",), "appointment.confirmed")
    db.commit()
    return _out(db, appt)


@router.post("/{appointment_id}/complete")
def complete(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    _, _, appt = _change(db, current_user, appointment_id, "completed", calc.LIVE, "appointment.completed")
    db.commit()
    return _out(db, appt)


@router.post("/{appointment_id}/no-show")
def no_show(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    business_id, _ = _ids(current_user)
    appt = _get(db, business_id, appointment_id)
    if appt.start_at > datetime.now(timezone.utc):
        raise HTTPException(409, "It has not started yet, so it cannot be a no-show.")
    _, _, appt = _change(db, current_user, appointment_id, "no_show", calc.LIVE, "appointment.no_show")
    db.commit()
    return _out(db, appt)


@router.post("/{appointment_id}/cancel")
def cancel(
    appointment_id: UUID,
    data: CancelIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    business_id, user_id, appt = _change(
        db, current_user, appointment_id, "cancelled", calc.LIVE, "appointment.cancelled"
    )
    appt.cancel_reason = data.reason.strip()
    notify(
        db, business_id=business_id, user_ids=[appt.assigned_user_id],
        kind="appointment", title=f"Appointment cancelled: {appt.title}",
        body=data.reason.strip(), link="/appointments", actor_id=user_id,
    )
    db.commit()
    return _out(db, appt)


@router.post("/{appointment_id}/message", status_code=201)
def message_contact(
    appointment_id: UUID,
    data: MessageIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    """Queue a confirmation or reminder for this appointment's contact."""
    business_id, user_id = _ids(current_user)
    if data.kind not in ("appointment_confirmation", "appointment_reminder"):
        raise HTTPException(422, "Choose a confirmation or a reminder.")
    appt = _get(db, business_id, appointment_id)
    if appt.status not in calc.LIVE:
        raise HTTPException(409, "Only a live appointment can be messaged.")
    try:
        message = calc.queue_message(
            db, appt, db.get(Business, business_id), kind=data.kind,
            channel=data.channel, created_by=user_id,
        )
        messages.try_send_now(message)
    except messages.MessageError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return messages.as_dict(message)


@router.put("/settings/reminders")
def set_reminders(
    data: SettingsIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("appointments.manage")),
):
    business_id, user_id = _ids(current_user)
    business = db.get(Business, business_id)
    business.appointment_reminders = data.appointment_reminders
    create_audit_log(
        db, business_id=business_id, user_id=user_id,
        action="appointment.reminders_changed", entity_type="business",
        entity_id=business_id, details={"on": data.appointment_reminders},
        notes="Appointment reminders turned "
        + ("on." if data.appointment_reminders else "off."),
    )
    db.commit()
    return {"appointment_reminders": business.appointment_reminders}
