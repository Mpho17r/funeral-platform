"""Resource scheduling rules.

Keeps conflict detection out of the HTTP layer so the same rules can
later be reused by dispatch, portals and automation.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.resource import Resource, ResourceBooking
from app.models.user import User


ACTIVE_BOOKING_STATUS = "booked"


class SchedulingError(Exception):
    """A booking cannot be made. Carries an HTTP-friendly status."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def find_resource_conflicts(
    db: Session,
    *,
    business_id: UUID,
    resource_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_booking_id: UUID | None = None,
) -> list[ResourceBooking]:
    """Active bookings that overlap the window for one resource.

    Windows are half-open: a booking ending exactly when another
    starts does not conflict.
    """

    query = db.query(ResourceBooking).filter(
        ResourceBooking.business_id == business_id,
        ResourceBooking.resource_id == resource_id,
        ResourceBooking.status == ACTIVE_BOOKING_STATUS,
        ResourceBooking.starts_at < ends_at,
        ResourceBooking.ends_at > starts_at,
    )

    if exclude_booking_id is not None:
        query = query.filter(ResourceBooking.id != exclude_booking_id)

    return query.order_by(ResourceBooking.starts_at).all()


def find_driver_conflicts(
    db: Session,
    *,
    business_id: UUID,
    driver_user_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_booking_id: UUID | None = None,
) -> list[ResourceBooking]:
    """Active bookings that overlap the window for one driver."""

    query = db.query(ResourceBooking).filter(
        ResourceBooking.business_id == business_id,
        ResourceBooking.driver_user_id == driver_user_id,
        ResourceBooking.status == ACTIVE_BOOKING_STATUS,
        ResourceBooking.starts_at < ends_at,
        ResourceBooking.ends_at > starts_at,
    )

    if exclude_booking_id is not None:
        query = query.filter(ResourceBooking.id != exclude_booking_id)

    return query.order_by(ResourceBooking.starts_at).all()


def validate_window(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise SchedulingError(
            422,
            "Booking must end after it starts",
        )


def lock_resource(
    db: Session,
    *,
    business_id: UUID,
    resource_id: UUID,
) -> Resource:
    """Load and row-lock a resource so concurrent bookings serialize."""

    resource = (
        db.query(Resource)
        .filter(
            Resource.id == resource_id,
            Resource.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if resource is None:
        raise SchedulingError(404, "Resource not found")

    return resource


def load_driver(
    db: Session,
    *,
    business_id: UUID,
    driver_user_id: UUID,
) -> User:
    """Load and row-lock a driver, which must be an active user of
    the same business."""

    driver = (
        db.query(User)
        .filter(
            User.id == driver_user_id,
            User.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if driver is None:
        raise SchedulingError(404, "Driver not found")

    if not driver.is_active:
        raise SchedulingError(409, "Driver account is inactive")

    return driver


def ensure_bookable(
    db: Session,
    *,
    business_id: UUID,
    resource: Resource,
    driver_user_id: UUID | None,
    starts_at: datetime,
    ends_at: datetime,
    exclude_booking_id: UUID | None = None,
) -> None:
    """Raise SchedulingError if the booking cannot be made.

    The resource (and driver, if any) must already be row-locked by
    the caller.
    """

    validate_window(starts_at, ends_at)

    if not resource.is_active:
        raise SchedulingError(409, "Resource is inactive")

    if driver_user_id is not None and resource.resource_type != "vehicle":
        raise SchedulingError(
            422,
            "A driver can only be assigned to a vehicle booking",
        )

    resource_conflicts = find_resource_conflicts(
        db,
        business_id=business_id,
        resource_id=resource.id,
        starts_at=starts_at,
        ends_at=ends_at,
        exclude_booking_id=exclude_booking_id,
    )

    if resource_conflicts:
        raise SchedulingError(
            409,
            "Resource is already booked for an overlapping time",
        )

    if driver_user_id is not None:
        driver_conflicts = find_driver_conflicts(
            db,
            business_id=business_id,
            driver_user_id=driver_user_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_booking_id=exclude_booking_id,
        )

        if driver_conflicts:
            raise SchedulingError(
                409,
                "Driver is already booked for an overlapping time",
            )
