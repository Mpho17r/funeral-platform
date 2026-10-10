from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase
from app.models.resource import Resource, ResourceBooking
from app.schemas.resource import (
    AvailabilityResponse,
    ResourceBookingCreate,
    ResourceBookingResponse,
    ResourceBookingUpdate,
    ResourceCreate,
    ResourceResponse,
    ResourceSignalCase,
    ResourceSignalsResponse,
    ResourceType,
    ResourceUpdate,
)
from app.services.audit_service import build_audit_changes, create_audit_log
from app.services.resource_scheduling import (
    ACTIVE_BOOKING_STATUS,
    SchedulingError,
    ensure_bookable,
    find_resource_conflicts,
    load_driver,
    lock_resource,
    validate_window,
)


router = APIRouter(
    tags=["Resources"],
)


BOOKABLE_CASE_STATUSES = {"open", "confirmed", "in_progress"}


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def get_resource_or_404(
    db: Session,
    resource_id: UUID,
    business_id: UUID,
) -> Resource:
    resource = (
        db.query(Resource)
        .filter(
            Resource.id == resource_id,
            Resource.business_id == business_id,
        )
        .first()
    )

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    return resource


def get_booking_or_404(
    db: Session,
    booking_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> ResourceBooking:
    query = db.query(ResourceBooking).filter(
        ResourceBooking.id == booking_id,
        ResourceBooking.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    booking = query.first()

    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource booking not found",
        )

    return booking


def get_case_or_404(
    db: Session,
    case_id: UUID,
    business_id: UUID,
) -> FuneralCase:
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


def raise_scheduling_error(error: SchedulingError):
    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


RESOURCE_AUDIT_FIELDS = (
    "name",
    "identifier",
    "capacity",
    "location",
    "notes",
)

BOOKING_AUDIT_FIELDS = (
    "driver_user_id",
    "starts_at",
    "ends_at",
    "purpose",
    "notes",
)


# ============================================================
# RESOURCE CATALOGUE
# ============================================================

@router.post(
    "/resources",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    data: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("resources.manage")),
):
    business_id = get_business_id(current_user)

    resource = Resource(
        business_id=business_id,
        resource_type=data.resource_type,
        name=data.name,
        identifier=data.identifier,
        capacity=data.capacity,
        location=data.location,
        notes=data.notes,
        is_active=True,
    )

    db.add(resource)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A resource of this type with that identifier "
                "already exists"
            ),
        )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="resource.created",
        entity_type="resource",
        entity_id=resource.id,
        details={
            "resource_type": resource.resource_type,
        },
        notes="Resource was created.",
    )

    db.commit()
    db.refresh(resource)

    return resource


@router.get(
    "/resources",
    response_model=list[ResourceResponse],
)
def list_resources(
    resource_type: ResourceType | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("resources.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(Resource).filter(
        Resource.business_id == business_id,
    )

    if resource_type is not None:
        query = query.filter(Resource.resource_type == resource_type)

    if not include_inactive:
        query = query.filter(Resource.is_active.is_(True))

    return query.order_by(Resource.resource_type, Resource.name).all()


@router.get(
    "/resources/{resource_id}",
    response_model=ResourceResponse,
)
def get_resource(
    resource_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("resources.view")),
):
    business_id = get_business_id(current_user)

    return get_resource_or_404(db, resource_id, business_id)


@router.patch(
    "/resources/{resource_id}",
    response_model=ResourceResponse,
)
def update_resource(
    resource_id: UUID,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("resources.manage")),
):
    business_id = get_business_id(current_user)

    resource = get_resource_or_404(db, resource_id, business_id)

    updates = data.model_dump(exclude_unset=True)

    old_values = {
        field: getattr(resource, field)
        for field in RESOURCE_AUDIT_FIELDS
    }

    for field, value in updates.items():
        setattr(resource, field, value)

    new_values = {
        field: getattr(resource, field)
        for field in RESOURCE_AUDIT_FIELDS
    }

    changes = build_audit_changes(old_values, new_values)

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=current_user["user_id"],
            action="resource.updated",
            entity_type="resource",
            entity_id=resource.id,
            details={"changes": changes},
            notes="Resource was updated.",
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A resource of this type with that identifier "
                "already exists"
            ),
        )

    db.refresh(resource)

    return resource


def _set_resource_active(
    *,
    resource_id: UUID,
    active: bool,
    db: Session,
    current_user: dict,
) -> Resource:
    business_id = get_business_id(current_user)

    resource = get_resource_or_404(db, resource_id, business_id)

    if resource.is_active == active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Resource is already active"
                if active
                else "Resource is already inactive"
            ),
        )

    resource.is_active = active

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action=(
            "resource.reactivated" if active else "resource.deactivated"
        ),
        entity_type="resource",
        entity_id=resource.id,
        details={"resource_type": resource.resource_type},
        notes=(
            "Resource was reactivated."
            if active
            else "Resource was deactivated."
        ),
    )

    db.commit()
    db.refresh(resource)

    return resource


@router.post(
    "/resources/{resource_id}/deactivate",
    response_model=ResourceResponse,
)
def deactivate_resource(
    resource_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("resources.manage")),
):
    return _set_resource_active(
        resource_id=resource_id,
        active=False,
        db=db,
        current_user=current_user,
    )


@router.post(
    "/resources/{resource_id}/reactivate",
    response_model=ResourceResponse,
)
def reactivate_resource(
    resource_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("resources.manage")),
):
    return _set_resource_active(
        resource_id=resource_id,
        active=True,
        db=db,
        current_user=current_user,
    )


# ============================================================
# AVAILABILITY
# GET /resources/{id}/availability
# ============================================================

@router.get(
    "/resources/{resource_id}/availability",
    response_model=AvailabilityResponse,
)
def check_availability(
    resource_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.view")
    ),
):
    business_id = get_business_id(current_user)

    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Datetime must include a timezone offset",
        )

    resource = get_resource_or_404(db, resource_id, business_id)

    try:
        validate_window(starts_at, ends_at)
    except SchedulingError as error:
        raise_scheduling_error(error)

    conflicts = find_resource_conflicts(
        db,
        business_id=business_id,
        resource_id=resource.id,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    return AvailabilityResponse(
        resource_id=resource.id,
        starts_at=starts_at,
        ends_at=ends_at,
        is_available=resource.is_active and not conflicts,
        conflicts=conflicts,
    )


# ============================================================
# BOOKINGS
# ============================================================

@router.post(
    "/cases/{case_id}/resource-bookings",
    response_model=ResourceBookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    case_id: UUID,
    data: ResourceBookingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.manage")
    ),
):
    business_id = get_business_id(current_user)

    case = get_case_or_404(db, case_id, business_id)

    if case.is_archived or case.status not in BOOKABLE_CASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Resources can only be booked for live cases "
                "(open, confirmed or in progress)"
            ),
        )

    try:
        # Lock order is always resource first, then driver, so
        # concurrent bookings cannot deadlock.
        resource = lock_resource(
            db,
            business_id=business_id,
            resource_id=data.resource_id,
        )

        if data.driver_user_id is not None:
            load_driver(
                db,
                business_id=business_id,
                driver_user_id=data.driver_user_id,
            )

        ensure_bookable(
            db,
            business_id=business_id,
            resource=resource,
            driver_user_id=data.driver_user_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
        )
    except SchedulingError as error:
        db.rollback()
        raise_scheduling_error(error)

    booking = ResourceBooking(
        business_id=business_id,
        case_id=case.id,
        resource_id=resource.id,
        driver_user_id=data.driver_user_id,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        purpose=data.purpose,
        notes=data.notes,
        status=ACTIVE_BOOKING_STATUS,
        created_by=current_user["user_id"],
    )

    db.add(booking)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="resource_booking.created",
        entity_type="resource_booking",
        entity_id=booking.id,
        details={
            "case_id": str(case.id),
            "resource_id": str(resource.id),
            "resource_type": resource.resource_type,
            "driver_user_id": (
                str(data.driver_user_id)
                if data.driver_user_id
                else None
            ),
            "starts_at": data.starts_at.isoformat(),
            "ends_at": data.ends_at.isoformat(),
        },
        notes="Resource booking was created.",
    )

    db.commit()
    db.refresh(booking)

    return booking


@router.get(
    "/cases/{case_id}/resource-bookings",
    response_model=list[ResourceBookingResponse],
)
def list_case_bookings(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.view")
    ),
):
    business_id = get_business_id(current_user)

    get_case_or_404(db, case_id, business_id)

    return (
        db.query(ResourceBooking)
        .filter(
            ResourceBooking.case_id == case_id,
            ResourceBooking.business_id == business_id,
        )
        .order_by(ResourceBooking.starts_at)
        .all()
    )


@router.get(
    "/resource-bookings",
    response_model=list[ResourceBookingResponse],
)
def list_bookings(
    resource_id: UUID | None = None,
    driver_user_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.view")
    ),
):
    business_id = get_business_id(current_user)

    query = db.query(ResourceBooking).filter(
        ResourceBooking.business_id == business_id,
    )

    if resource_id is not None:
        query = query.filter(ResourceBooking.resource_id == resource_id)

    if driver_user_id is not None:
        query = query.filter(
            ResourceBooking.driver_user_id == driver_user_id
        )

    if status_filter is not None:
        query = query.filter(ResourceBooking.status == status_filter)

    if from_ is not None:
        query = query.filter(ResourceBooking.ends_at > from_)

    if to is not None:
        query = query.filter(ResourceBooking.starts_at < to)

    return query.order_by(ResourceBooking.starts_at).all()


@router.get(
    "/resource-bookings/{booking_id}",
    response_model=ResourceBookingResponse,
)
def get_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.view")
    ),
):
    business_id = get_business_id(current_user)

    return get_booking_or_404(db, booking_id, business_id)


@router.patch(
    "/resource-bookings/{booking_id}",
    response_model=ResourceBookingResponse,
)
def update_booking(
    booking_id: UUID,
    data: ResourceBookingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.manage")
    ),
):
    business_id = get_business_id(current_user)

    booking = get_booking_or_404(db, booking_id, business_id)

    if booking.status != ACTIVE_BOOKING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active bookings can be changed",
        )

    updates = data.model_dump(exclude_unset=True)

    new_driver = updates.get("driver_user_id", booking.driver_user_id)
    new_start = updates.get("starts_at", booking.starts_at)
    new_end = updates.get("ends_at", booking.ends_at)

    try:
        resource = lock_resource(
            db,
            business_id=business_id,
            resource_id=booking.resource_id,
        )

        # Re-read under the lock so we validate the latest state.
        db.refresh(booking)

        if booking.status != ACTIVE_BOOKING_STATUS:
            raise SchedulingError(
                409,
                "Only active bookings can be changed",
            )

        if new_driver is not None:
            load_driver(
                db,
                business_id=business_id,
                driver_user_id=new_driver,
            )

        scheduling_changed = any(
            field in updates
            for field in ("driver_user_id", "starts_at", "ends_at")
        )

        if scheduling_changed:
            ensure_bookable(
                db,
                business_id=business_id,
                resource=resource,
                driver_user_id=new_driver,
                starts_at=new_start,
                ends_at=new_end,
                exclude_booking_id=booking.id,
            )
    except SchedulingError as error:
        db.rollback()
        raise_scheduling_error(error)

    old_values = {
        field: getattr(booking, field)
        for field in BOOKING_AUDIT_FIELDS
    }

    for field, value in updates.items():
        setattr(booking, field, value)

    new_values = {
        field: getattr(booking, field)
        for field in BOOKING_AUDIT_FIELDS
    }

    changes = build_audit_changes(old_values, new_values)

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=current_user["user_id"],
            action="resource_booking.updated",
            entity_type="resource_booking",
            entity_id=booking.id,
            details={
                "case_id": str(booking.case_id),
                "changes": changes,
            },
            notes="Resource booking was updated.",
        )

    db.commit()
    db.refresh(booking)

    return booking


def _finish_booking(
    *,
    booking_id: UUID,
    new_status: str,
    action: str,
    note: str,
    db: Session,
    current_user: dict,
) -> ResourceBooking:
    business_id = get_business_id(current_user)

    booking = get_booking_or_404(
        db,
        booking_id,
        business_id,
        lock=True,
    )

    if booking.status != ACTIVE_BOOKING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Booking is already {booking.status}",
        )

    booking.status = new_status

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action=action,
        entity_type="resource_booking",
        entity_id=booking.id,
        details={
            "case_id": str(booking.case_id),
            "resource_id": str(booking.resource_id),
        },
        notes=note,
    )

    db.commit()
    db.refresh(booking)

    return booking


@router.post(
    "/resource-bookings/{booking_id}/cancel",
    response_model=ResourceBookingResponse,
)
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.manage")
    ),
):
    return _finish_booking(
        booking_id=booking_id,
        new_status="cancelled",
        action="resource_booking.cancelled",
        note="Resource booking was cancelled.",
        db=db,
        current_user=current_user,
    )


@router.post(
    "/resource-bookings/{booking_id}/complete",
    response_model=ResourceBookingResponse,
)
def complete_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.manage")
    ),
):
    return _finish_booking(
        booking_id=booking_id,
        new_status="completed",
        action="resource_booking.completed",
        note="Resource booking was completed.",
        db=db,
        current_user=current_user,
    )


# ============================================================
# OPERATIONAL SIGNALS
# GET /resource-signals
#
# Deterministic gaps for upcoming funerals: what has no vehicle,
# no venue, or no driver. Feeds the dashboard "what is at risk".
# ============================================================

@router.get(
    "/resource-signals",
    response_model=ResourceSignalsResponse,
)
def get_resource_signals(
    window_days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("resource_bookings.view")
    ),
):
    business_id = get_business_id(current_user)

    today = date.today()
    horizon = today + timedelta(days=window_days)

    upcoming_cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(BOOKABLE_CASE_STATUSES),
            FuneralCase.funeral_date.isnot(None),
            FuneralCase.funeral_date >= today,
            FuneralCase.funeral_date <= horizon,
        )
        .order_by(FuneralCase.funeral_date, FuneralCase.case_number)
        .all()
    )

    def has_active_booking(case_id: UUID, resource_type: str) -> bool:
        return db.query(
            exists().where(
                ResourceBooking.business_id == business_id,
                ResourceBooking.case_id == case_id,
                ResourceBooking.status == ACTIVE_BOOKING_STATUS,
                ResourceBooking.resource_id == Resource.id,
                Resource.resource_type == resource_type,
            )
        ).scalar()

    without_vehicle = []
    without_venue = []

    for case in upcoming_cases:
        entry = ResourceSignalCase(
            case_id=case.id,
            case_number=case.case_number,
            funeral_date=case.funeral_date.isoformat(),
        )

        if not has_active_booking(case.id, "vehicle"):
            without_vehicle.append(entry)

        if not has_active_booking(case.id, "venue"):
            without_venue.append(entry)

    window_start = datetime.now(timezone.utc)
    window_end = window_start + timedelta(days=window_days)

    vehicle_bookings_without_driver = (
        db.query(ResourceBooking)
        .join(Resource, Resource.id == ResourceBooking.resource_id)
        .filter(
            ResourceBooking.business_id == business_id,
            ResourceBooking.status == ACTIVE_BOOKING_STATUS,
            ResourceBooking.driver_user_id.is_(None),
            Resource.resource_type == "vehicle",
            ResourceBooking.ends_at > window_start,
            ResourceBooking.starts_at < window_end,
        )
        .count()
    )

    return ResourceSignalsResponse(
        window_days=window_days,
        funerals_without_vehicle=without_vehicle,
        funerals_without_venue=without_venue,
        vehicle_bookings_without_driver=vehicle_bookings_without_driver,
    )
