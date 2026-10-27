from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.funeral_case import FuneralCase
from app.models.transport import PartnerDriver, PartnerVehicle, TransportJob
from app.services import portal as portal_svc
from app.services import transport as svc
from app.services.audit_service import create_audit_log

router = APIRouter(tags=["Transport"])

VEHICLE_TYPES = (
    "sedan", "suv", "minibus", "limousine", "hearse", "bakkie", "van", "other",
)


# ----------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------

class DriverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    area: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class DriverUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    area: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    is_active: bool | None = None


class VehicleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    make: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    vehicle_type: str = Field(default="sedan", max_length=50)
    colour: str = Field(min_length=1, max_length=50)
    registration: str | None = Field(default=None, max_length=30)
    seats: int = Field(default=4, ge=1, le=60)


class VehicleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    make: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    vehicle_type: str | None = Field(default=None, max_length=50)
    colour: str | None = Field(default=None, min_length=1, max_length=50)
    registration: str | None = Field(default=None, max_length=30)
    seats: int | None = Field(default=None, ge=1, le=60)
    is_active: bool | None = None


class JobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="Family car", min_length=1, max_length=100)
    count: int = Field(default=1, ge=1, le=30)
    required_colour: str | None = Field(default=None, max_length=50)
    required_type: str | None = Field(default=None, max_length=50)
    required_model: str | None = Field(default=None, max_length=100)
    report_time: datetime
    pickup_address: str | None = None
    venue: str | None = Field(default=None, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    dress_code: str | None = Field(default=None, max_length=255)
    instructions: str | None = None
    pay_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=100)
    required_colour: str | None = Field(default=None, max_length=50)
    required_type: str | None = Field(default=None, max_length=50)
    required_model: str | None = Field(default=None, max_length=100)
    report_time: datetime | None = None
    pickup_address: str | None = None
    venue: str | None = Field(default=None, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    dress_code: str | None = Field(default=None, max_length=255)
    instructions: str | None = None
    pay_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class AssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver_id: UUID
    vehicle_id: UUID
    force: bool = False


class AutoAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID | None = None
    day: date | None = None


class Respond(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _biz(user: dict) -> UUID:
    return UUID(str(user["business_id"]))


def _uid(user: dict) -> UUID:
    return UUID(str(user["user_id"]))


def _fail(db: Session, error: svc.TransportError):
    db.rollback()
    raise HTTPException(error.status_code, error.detail)


def _vehicle_out(v: PartnerVehicle) -> dict:
    return {
        "id": v.id, "driver_id": v.driver_id, "make": v.make, "model": v.model,
        "vehicle_type": v.vehicle_type, "colour": v.colour,
        "registration": v.registration, "seats": v.seats, "is_active": v.is_active,
    }


def _driver_out(db: Session, d: PartnerDriver) -> dict:
    cars = (
        db.query(PartnerVehicle)
        .filter(PartnerVehicle.driver_id == d.id)
        .order_by(PartnerVehicle.colour)
        .all()
    )
    return {
        "id": d.id, "full_name": d.full_name, "phone": d.phone, "email": d.email,
        "area": d.area, "notes": d.notes, "is_active": d.is_active,
        "has_link": d.token_hash is not None,
        "vehicles": [_vehicle_out(v) for v in cars],
    }


def _job_out(db: Session, j: TransportJob) -> dict:
    driver = db.get(PartnerDriver, j.driver_id) if j.driver_id else None
    vehicle = db.get(PartnerVehicle, j.vehicle_id) if j.vehicle_id else None
    case = db.get(FuneralCase, j.case_id)
    return {
        "id": j.id, "case_id": j.case_id,
        "case_number": case.case_number if case else None,
        "deceased_full_name": case.deceased_full_name if case else None,
        "label": j.label, "required_colour": j.required_colour,
        "required_type": j.required_type, "required_model": j.required_model,
        "report_time": j.report_time, "pickup_address": j.pickup_address,
        "venue": j.venue, "destination": j.destination,
        "dress_code": j.dress_code, "instructions": j.instructions,
        "pay_amount": j.pay_amount, "status": j.status,
        "driver_id": j.driver_id, "driver_name": driver.full_name if driver else None,
        "driver_phone": driver.phone if driver else None,
        "vehicle_id": j.vehicle_id,
        "vehicle": (
            " ".join(x for x in (vehicle.colour, vehicle.make, vehicle.model) if x)
            if vehicle else None
        ),
        "alerted_at": j.alerted_at, "alert_error": j.alert_error,
        "responded_at": j.responded_at, "paid": j.expense_id is not None,
    }


def _driver_or_404(db, business_id, driver_id) -> PartnerDriver:
    d = db.query(PartnerDriver).filter(
        PartnerDriver.id == driver_id, PartnerDriver.business_id == business_id
    ).first()
    if d is None:
        raise HTTPException(404, "Driver not found")
    return d


def _job_or_404(db, business_id, job_id) -> TransportJob:
    j = db.query(TransportJob).filter(
        TransportJob.id == job_id, TransportJob.business_id == business_id
    ).first()
    if j is None:
        raise HTTPException(404, "Job not found")
    return j


def _audit(db, user, action, entity_type, entity_id, details, notes):
    create_audit_log(
        db, business_id=_biz(user), user_id=_uid(user), action=action,
        entity_type=entity_type, entity_id=entity_id, details=details, notes=notes,
    )


def _alert_after_assign(db: Session, job: TransportJob) -> dict:
    driver = db.get(PartnerDriver, job.driver_id)
    vehicle = db.get(PartnerVehicle, job.vehicle_id)
    text = svc.alert_text(db, job, driver, vehicle)
    sent = svc.send_alert(db, job, driver, text)
    return {"emailed": sent, "text": text, "whatsapp": svc.whatsapp_link(driver, text)}


# ----------------------------------------------------------------
# Drivers and cars
# ----------------------------------------------------------------

@router.get("/transport/drivers")
def list_drivers(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.view")),
):
    q = db.query(PartnerDriver).filter(PartnerDriver.business_id == _biz(user))
    if not include_inactive:
        q = q.filter(PartnerDriver.is_active.is_(True))
    return [_driver_out(db, d) for d in q.order_by(PartnerDriver.full_name)]


@router.post("/transport/drivers", status_code=201)
def create_driver(
    data: DriverIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    d = PartnerDriver(business_id=_biz(user), **data.model_dump())
    db.add(d)
    db.flush()
    _audit(db, user, "transport.driver_created", "partner_driver", d.id,
           {"name": d.full_name}, "Partner driver registered.")
    db.commit()
    return _driver_out(db, d)


@router.patch("/transport/drivers/{driver_id}")
def update_driver(
    driver_id: UUID,
    data: DriverUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    d = _driver_or_404(db, _biz(user), driver_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if k in ("full_name", "is_active") and v is None:
            continue
        setattr(d, k, v)
    _audit(db, user, "transport.driver_updated", "partner_driver", d.id,
           {"fields": list(data.model_dump(exclude_unset=True))}, "Partner driver updated.")
    db.commit()
    return _driver_out(db, d)


@router.post("/transport/drivers/{driver_id}/vehicles", status_code=201)
def add_vehicle(
    driver_id: UUID,
    data: VehicleIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    d = _driver_or_404(db, _biz(user), driver_id)
    body = data.model_dump()
    body["colour"] = body["colour"].strip().lower()
    body["vehicle_type"] = body["vehicle_type"].strip().lower()
    v = PartnerVehicle(business_id=d.business_id, driver_id=d.id, **body)
    db.add(v)
    db.commit()
    return _vehicle_out(v)


@router.patch("/transport/vehicles/{vehicle_id}")
def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    v = db.query(PartnerVehicle).filter(
        PartnerVehicle.id == vehicle_id, PartnerVehicle.business_id == _biz(user)
    ).first()
    if v is None:
        raise HTTPException(404, "Car not found")
    for k, val in data.model_dump(exclude_unset=True).items():
        if k in ("colour", "vehicle_type") and val is not None:
            val = val.strip().lower()
        if k in ("colour", "vehicle_type", "seats", "is_active") and val is None:
            continue
        setattr(v, k, val)
    db.commit()
    return _vehicle_out(v)


@router.post("/transport/drivers/{driver_id}/link", status_code=201)
def make_driver_link(
    driver_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    """A private page where the driver sees their jobs and replies.
    The secret is shown once; making a new one cancels the old."""
    d = _driver_or_404(db, _biz(user), driver_id)
    token = svc.new_driver_link(d)
    _audit(db, user, "transport.driver_link_created", "partner_driver", d.id,
           {}, "Private driver link created.")
    db.commit()
    return {"path": f"/driver/{token}", "token": token}


# ----------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------

@router.get("/transport/jobs")
def list_jobs(
    case_id: UUID | None = None,
    day: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.view")),
):
    q = db.query(TransportJob).filter(TransportJob.business_id == _biz(user))
    if case_id:
        q = q.filter(TransportJob.case_id == case_id)
    if day:
        start = datetime.combine(day, time.min, tzinfo=timezone(timedelta(hours=2)))
        q = q.filter(TransportJob.report_time >= start,
                     TransportJob.report_time < start + timedelta(days=1))
    if status:
        q = q.filter(TransportJob.status == status)
    return [_job_out(db, j) for j in q.order_by(TransportJob.report_time).limit(500)]


@router.post("/cases/{case_id}/transport-jobs", status_code=201)
def create_jobs(
    case_id: UUID,
    data: JobIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    case = db.query(FuneralCase).filter(
        FuneralCase.id == case_id, FuneralCase.business_id == _biz(user)
    ).first()
    if case is None:
        raise HTTPException(404, "Funeral case not found")
    if case.is_archived:
        raise HTTPException(409, "Archived cases cannot be changed")
    body = data.model_dump(exclude={"count"})
    for key in ("required_colour", "required_type"):
        body[key] = svc.norm(body[key])
    jobs = []
    for _ in range(data.count):
        j = TransportJob(business_id=case.business_id, case_id=case.id, **body)
        db.add(j)
        jobs.append(j)
    db.flush()
    _audit(db, user, "transport.jobs_created", "funeral_case", case.id,
           {"count": data.count, "colour": body["required_colour"]},
           "Car jobs were created for a funeral.")
    db.commit()
    return [_job_out(db, j) for j in jobs]


@router.patch("/transport/jobs/{job_id}")
def update_job(
    job_id: UUID,
    data: JobUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    j = _job_or_404(db, _biz(user), job_id)
    if j.status in ("completed", "cancelled"):
        raise HTTPException(409, f"A {j.status} job cannot be changed")
    for k, v in data.model_dump(exclude_unset=True).items():
        if k in ("label", "report_time", "pay_amount") and v is None:
            continue
        if k in ("required_colour", "required_type"):
            v = svc.norm(v)
        setattr(j, k, v)
    db.commit()
    return _job_out(db, j)


@router.get("/transport/jobs/{job_id}/candidates")
def job_candidates(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.view")),
):
    j = _job_or_404(db, _biz(user), job_id)
    return [
        {"driver_id": d.id, "driver_name": d.full_name, "phone": d.phone,
         "vehicle": _vehicle_out(v)}
        for d, v in svc.candidates(db, j)
    ]


@router.post("/transport/jobs/{job_id}/assign")
def assign_job(
    job_id: UUID,
    data: AssignIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    biz = _biz(user)
    j = _job_or_404(db, biz, job_id)
    d = _driver_or_404(db, biz, data.driver_id)
    v = db.query(PartnerVehicle).filter(
        PartnerVehicle.id == data.vehicle_id, PartnerVehicle.business_id == biz
    ).first()
    if v is None:
        raise HTTPException(404, "Car not found")
    try:
        svc.assign(db, j, d, v, force=data.force)
    except svc.TransportError as e:
        _fail(db, e)
    alert = _alert_after_assign(db, j)
    _audit(db, user, "transport.job_assigned", "transport_job", j.id,
           {"driver": d.full_name, "forced": data.force}, "Driver assigned to a car job.")
    db.commit()
    return {**_job_out(db, j), "alert": alert}


@router.post("/transport/jobs/{job_id}/unassign")
def unassign_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    j = _job_or_404(db, _biz(user), job_id)
    try:
        svc.unassign(j)
    except svc.TransportError as e:
        _fail(db, e)
    _audit(db, user, "transport.job_unassigned", "transport_job", j.id, {}, "Driver removed from a car job.")
    db.commit()
    return _job_out(db, j)


@router.get("/transport/jobs/{job_id}/alert")
def job_alert(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.view")),
):
    j = _job_or_404(db, _biz(user), job_id)
    if j.driver_id is None:
        raise HTTPException(409, "Assign a driver first")
    d = db.get(PartnerDriver, j.driver_id)
    v = db.get(PartnerVehicle, j.vehicle_id) if j.vehicle_id else None
    text = svc.alert_text(db, j, d, v)
    return {"text": text, "whatsapp": svc.whatsapp_link(d, text)}


@router.post("/transport/jobs/{job_id}/resend")
def resend_alert(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    j = _job_or_404(db, _biz(user), job_id)
    if j.driver_id is None or j.status not in svc.ACTIVE:
        raise HTTPException(409, "There is no driver to alert")
    alert = _alert_after_assign(db, j)
    db.commit()
    return {**_job_out(db, j), "alert": alert}


@router.post("/transport/auto-assign")
def auto_assign(
    data: AutoAssignIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    """Match every open job to a free driver whose car fits."""
    q = db.query(TransportJob).filter(
        TransportJob.business_id == _biz(user), TransportJob.status == "open"
    )
    if data.case_id:
        q = q.filter(TransportJob.case_id == data.case_id)
    if data.day:
        start = datetime.combine(data.day, time.min, tzinfo=timezone(timedelta(hours=2)))
        q = q.filter(TransportJob.report_time >= start,
                     TransportJob.report_time < start + timedelta(days=1))
    jobs = q.all()
    done = svc.auto_assign(db, jobs)
    for j in done:
        _alert_after_assign(db, j)
    _audit(db, user, "transport.auto_assigned", "transport_job", None,
           {"assigned": len(done), "open": len(jobs)}, "Open car jobs were matched automatically.")
    db.commit()
    return {"assigned": len(done), "still_open": len(jobs) - len(done),
            "jobs": [_job_out(db, j) for j in jobs]}


@router.post("/transport/jobs/{job_id}/complete")
def complete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    j = _job_or_404(db, _biz(user), job_id)
    if j.status not in ("assigned", "accepted"):
        raise HTTPException(409, "Only an assigned job can be completed")
    j.status = "completed"
    j.completed_at = datetime.now(timezone.utc)
    db.commit()
    return _job_out(db, j)


@router.post("/transport/jobs/{job_id}/cancel")
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    j = _job_or_404(db, _biz(user), job_id)
    if j.status in ("completed", "cancelled"):
        raise HTTPException(409, f"This job is already {j.status}")
    j.status = "cancelled"
    _audit(db, user, "transport.job_cancelled", "transport_job", j.id, {}, "Car job cancelled.")
    db.commit()
    return _job_out(db, j)


@router.post("/transport/jobs/{job_id}/pay")
def pay_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("transport.manage")),
):
    """Record what the driver is paid as an expense on the case."""
    j = _job_or_404(db, _biz(user), job_id)
    try:
        expense = svc.pay_job(db, j, _uid(user))
    except svc.TransportError as e:
        _fail(db, e)
    _audit(db, user, "transport.job_paid", "transport_job", j.id,
           {"amount": str(expense.amount)}, "Partner driver pay recorded as an expense.")
    db.commit()
    return _job_out(db, j)


# ----------------------------------------------------------------
# The driver's own page (no sign-in; the private link is the key)
# ----------------------------------------------------------------

def _driver_by_token(db: Session, request: Request, token: str) -> PartnerDriver:
    ip = request.client.host if request.client else "unknown"
    if portal_svc.too_many_failures(ip):
        raise HTTPException(429, "Too many attempts. Try again later.")
    d = db.query(PartnerDriver).filter(
        PartnerDriver.token_hash == svc.hash_token(token),
        PartnerDriver.is_active.is_(True),
    ).first()
    if d is None:
        portal_svc.record_failure(ip)
        raise HTTPException(404, "This link is not valid")
    return d


@router.get("/driver-portal/{token}")
def driver_page(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    d = _driver_by_token(db, request, token)
    now = datetime.now(timezone.utc) - timedelta(hours=6)
    jobs = (
        db.query(TransportJob)
        .filter(
            TransportJob.driver_id == d.id,
            TransportJob.status.in_(("assigned", "accepted")),
            TransportJob.report_time >= now,
        )
        .order_by(TransportJob.report_time)
        .all()
    )
    out = []
    for j in jobs:
        v = db.get(PartnerVehicle, j.vehicle_id) if j.vehicle_id else None
        case = db.get(FuneralCase, j.case_id)
        out.append({
            "id": j.id, "status": j.status, "label": j.label,
            "report_time": j.report_time,
            "deceased_full_name": case.deceased_full_name if case else None,
            "pickup_address": j.pickup_address, "venue": j.venue,
            "destination": j.destination, "dress_code": j.dress_code,
            "instructions": j.instructions, "pay_amount": j.pay_amount,
            "car": " ".join(x for x in (v.colour, v.make, v.model) if x) if v else None,
        })
    return {"driver": d.full_name, "jobs": out}


@router.post("/driver-portal/{token}/jobs/{job_id}/respond")
def driver_respond(
    token: str,
    job_id: UUID,
    data: Respond,
    request: Request,
    db: Session = Depends(get_db),
):
    d = _driver_by_token(db, request, token)
    j = db.query(TransportJob).filter(
        TransportJob.id == job_id, TransportJob.driver_id == d.id,
        TransportJob.status.in_(("assigned", "accepted")),
    ).first()
    if j is None:
        raise HTTPException(404, "Job not found")
    j.responded_at = datetime.now(timezone.utc)
    if data.accept:
        j.status = "accepted"
    else:
        # Back to the pool, and this driver is not offered it again.
        j.declined_by = [*(j.declined_by or []), str(d.id)]
        svc.unassign(j)
    db.commit()
    return {"status": j.status}
