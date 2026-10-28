"""Partner drivers: matching a car to a job, alerting the driver, paying.

A partner driver is someone with their own car who drives for funerals now
and then (taking the family to the cemetery and home again). A funeral has
car jobs; each asks for a colour, a type and sometimes a model so the cars
in a cortege match. This module finds the drivers who fit, assigns one,
sends the alert (venue, time, dress code) and keeps the pay record.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.funeral_case import FuneralCase
from app.models.transport import PartnerDriver, PartnerVehicle, TransportJob

# Two jobs closer together than this cannot be driven by the same person.
CLASH_HOURS = 4
ACTIVE = ("assigned", "accepted")


class TransportError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def norm(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value or None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_driver_link(driver: PartnerDriver) -> str:
    """Make a fresh private link. Any earlier link stops working."""
    token = secrets.token_urlsafe(24)
    driver.token_hash = hash_token(token)
    return token


def vehicle_matches(job: TransportJob, vehicle: PartnerVehicle) -> bool:
    colour = norm(job.required_colour)
    kind = norm(job.required_type)
    model = norm(job.required_model)
    if colour and norm(vehicle.colour) != colour:
        return False
    if kind and norm(vehicle.vehicle_type) != kind:
        return False
    if model:
        have = " ".join(
            x for x in (norm(vehicle.make), norm(vehicle.model)) if x
        )
        if model not in have:
            return False
    return True


def clashing_job(
    db: Session, job: TransportJob, driver_id: UUID
) -> TransportJob | None:
    window = timedelta(hours=CLASH_HOURS)
    return (
        db.query(TransportJob)
        .filter(
            TransportJob.driver_id == driver_id,
            TransportJob.id != job.id,
            TransportJob.status.in_(ACTIVE),
            TransportJob.report_time > job.report_time - window,
            TransportJob.report_time < job.report_time + window,
        )
        .first()
    )


def candidates(
    db: Session, job: TransportJob
) -> list[tuple[PartnerDriver, PartnerVehicle]]:
    """Free drivers whose car fits the job, best fit first."""

    declined = {str(x) for x in (job.declined_by or [])}
    rows = (
        db.query(PartnerDriver, PartnerVehicle)
        .join(PartnerVehicle, PartnerVehicle.driver_id == PartnerDriver.id)
        .filter(
            PartnerDriver.business_id == job.business_id,
            PartnerDriver.is_active.is_(True),
            PartnerVehicle.is_active.is_(True),
        )
        .order_by(PartnerDriver.full_name)
        .all()
    )
    found = []
    for driver, vehicle in rows:
        if str(driver.id) in declined:
            continue
        if not vehicle_matches(job, vehicle):
            continue
        if clashing_job(db, job, driver.id) is not None:
            continue
        found.append((driver, vehicle))
    return found


def alert_text(
    db: Session,
    job: TransportJob,
    driver: PartnerDriver,
    vehicle: PartnerVehicle | None,
    link: str | None = None,
) -> str:
    case = db.get(FuneralCase, job.case_id)
    when = job.report_time.astimezone(timezone(timedelta(hours=2)))
    lines = [
        f"Hello {driver.full_name.split()[0]}, you have a funeral car job.",
        f"Date: {when:%A %d %B %Y}",
        f"Report at: {when:%H:%M}",
    ]
    if case is not None:
        lines.append(f"Funeral of: {case.deceased_full_name}")
    if job.pickup_address:
        lines.append(f"Pick up: {job.pickup_address}")
    if job.venue:
        lines.append(f"Venue: {job.venue}")
    if job.destination:
        lines.append(f"Then to: {job.destination}")
    if job.dress_code:
        lines.append(f"Dress code: {job.dress_code}")
    if vehicle is not None:
        car = " ".join(
            x for x in (vehicle.colour, vehicle.make, vehicle.model) if x
        )
        lines.append(f"Your car: {car}")
    if job.instructions:
        lines.append(f"Notes: {job.instructions}")
    if job.pay_amount and Decimal(job.pay_amount) > 0:
        lines.append(f"Pay: R {Decimal(job.pay_amount):,.2f}")
    if link:
        lines.append(f"Accept or decline: {link}")
    return "\n".join(lines)


def whatsapp_link(driver: PartnerDriver, text: str) -> str | None:
    digits = "".join(c for c in (driver.phone or "") if c.isdigit())
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    return f"https://wa.me/{digits}?text={quote(text)}"


def send_alert(
    db: Session, job: TransportJob, driver: PartnerDriver, text: str
) -> bool:
    """Email the driver if possible. Phone alerts are a one-tap link."""

    from app.services import message_delivery as md

    job.alerted_at = None
    job.alert_error = None
    if not driver.email:
        job.alert_error = "No email address; send the alert by WhatsApp"
        return False
    try:
        md.send_email(driver.email, "Funeral car job", text)
    except md.DeliveryError as exc:
        job.alert_error = str(exc)[:255]
        return False
    job.alerted_at = datetime.now(timezone.utc)
    return True


def assign(
    db: Session,
    job: TransportJob,
    driver: PartnerDriver,
    vehicle: PartnerVehicle,
    *,
    force: bool = False,
) -> None:
    if job.status in ("completed", "cancelled"):
        raise TransportError(409, f"A {job.status} job cannot be assigned")
    if not driver.is_active or not vehicle.is_active:
        raise TransportError(409, "That driver or car is switched off")
    if vehicle.driver_id != driver.id:
        raise TransportError(422, "That car does not belong to this driver")
    clash = clashing_job(db, job, driver.id)
    if clash is not None and not force:
        raise TransportError(
            409,
            "This driver already has a job within "
            f"{CLASH_HOURS} hours of this one",
        )
    if not vehicle_matches(job, vehicle) and not force:
        raise TransportError(
            409, "That car does not match the colour, type or model asked for"
        )
    job.driver_id = driver.id
    job.vehicle_id = vehicle.id
    job.status = "assigned"
    job.assigned_at = datetime.now(timezone.utc)
    job.responded_at = None
    job.reminder_sent_at = None


def unassign(job: TransportJob) -> None:
    if job.status in ("completed", "cancelled"):
        raise TransportError(409, f"A {job.status} job cannot be changed")
    job.driver_id = None
    job.vehicle_id = None
    job.status = "open"
    job.assigned_at = None
    job.responded_at = None
    job.alerted_at = None
    job.alert_error = None


def auto_assign(db: Session, jobs: list[TransportJob]) -> list[TransportJob]:
    """Give each open job the first driver whose car fits. Earliest first."""

    done = []
    for job in sorted(jobs, key=lambda j: j.report_time):
        if job.status != "open":
            continue
        options = candidates(db, job)
        if not options:
            continue
        driver, vehicle = options[0]
        assign(db, job, driver, vehicle)
        db.flush()
        done.append(job)
    return done


def pay_job(db: Session, job: TransportJob, user_id, on_date=None) -> Expense:
    if job.expense_id is not None:
        raise TransportError(409, "This job has already been paid")
    if job.status != "completed":
        raise TransportError(409, "Only a completed job can be paid")
    if job.driver_id is None or not job.pay_amount or Decimal(job.pay_amount) <= 0:
        raise TransportError(409, "This job has no pay amount set")
    driver = db.get(PartnerDriver, job.driver_id)
    case = db.get(FuneralCase, job.case_id)
    expense = Expense(
        business_id=job.business_id,
        case_id=job.case_id,
        category="transport_and_fuel",
        description=(
            f"Partner driver {driver.full_name}: {job.label}"
            + (f" ({case.case_number})" if case else "")
        )[:500],
        amount=job.pay_amount,
        expense_date=on_date or datetime.now(timezone.utc).date(),
        payment_method="cash",
        created_by=user_id,
    )
    db.add(expense)
    db.flush()
    job.expense_id = expense.id
    return expense


def send_due_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Remind drivers of accepted jobs starting within the next 24 hours."""

    now = now or datetime.now(timezone.utc)
    jobs = (
        db.query(TransportJob)
        .filter(
            TransportJob.status == "accepted",
            TransportJob.reminder_sent_at.is_(None),
            TransportJob.report_time > now,
            TransportJob.report_time <= now + timedelta(hours=24),
        )
        .all()
    )
    sent = 0
    for job in jobs:
        driver = db.get(PartnerDriver, job.driver_id) if job.driver_id else None
        if driver is None:
            continue
        vehicle = db.get(PartnerVehicle, job.vehicle_id) if job.vehicle_id else None
        text = "Reminder.\n" + alert_text(db, job, driver, vehicle)
        from app.services import message_delivery as md

        try:
            if driver.email:
                md.send_email(driver.email, "Reminder: funeral car job", text)
        except md.DeliveryError:
            continue
        job.reminder_sent_at = now
        sent += 1
    db.commit()
    return sent
