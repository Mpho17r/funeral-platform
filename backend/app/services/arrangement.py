"""Funeral arrangement, collection and run sheet rules.

Pure business rules with no HTTP concerns, plus the run sheet builder.

The run sheet is the page the whole firm works from each morning: every
collection, wake, service, departure and burial happening that day, in
time order, with a flag against anything that will go wrong if nobody
acts. Flags are the point. They catch an unconfirmed grave, a missing
burial order, no vehicle booked for the cortege, remains not yet
identified, and collections that are overdue.

Times are stored with a timezone offset. A "day" is a calendar day in
South Africa (SAST, UTC+2).
"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.arrangement import CaseCollection, FuneralArrangement
from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.mortuary import MortuaryLocation, RemainsRecord
from app.models.resource import Resource, ResourceBooking
from app.models.user import User
from app.services.mortuary import RELEASE_PAPER_BY_DISPOSAL


BUSINESS_TZ_NAME = "Africa/Johannesburg"
BUSINESS_TZ = ZoneInfo(BUSINESS_TZ_NAME)

# A time cannot be recorded as already happened if it is further ahead
# than this.
CLOCK_SLACK = timedelta(minutes=5)

OPEN_COLLECTION_STATUSES = ("scheduled", "en_route")

ARRANGEMENT_TRANSITIONS = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"draft", "completed", "cancelled"},
    "completed": set(),
    "cancelled": {"draft"},
}

COLLECTION_TRANSITIONS = {
    "scheduled": {"en_route", "collected", "cancelled"},
    "en_route": {"scheduled", "collected", "cancelled"},
    "collected": set(),
    "cancelled": set(),
}

# The order the funeral happens in, with the words used in messages.
TIMELINE = (
    ("wake_at", "wake"),
    ("service_at", "service"),
    ("departure_at", "departure"),
    ("committal_at", "burial or cremation"),
)

KIND_ORDER = {
    "collection": 0,
    "booking": 1,
    "wake": 2,
    "service": 3,
    "departure": 4,
    "committal": 5,
}


class ArrangementError(Exception):
    """An arrangement or collection rule was violated."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def local_date(value: datetime) -> date:
    return value.astimezone(BUSINESS_TZ).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """The start and end of a South African calendar day, in UTC."""

    start = datetime.combine(day, time.min, tzinfo=BUSINESS_TZ)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=BUSINESS_TZ)

    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


# ============================================================
# ARRANGEMENT RULES
# ============================================================

def check_timeline(values: dict, *, date_of_death: date | None) -> None:
    """The wake, service, departure and burial must happen in order,
    and none can be before the person died."""

    previous_value = None
    previous_label = None

    for field, label in TIMELINE:
        value = values.get(field)

        if value is None:
            continue

        if date_of_death is not None and local_date(value) < date_of_death:
            raise ArrangementError(
                422,
                f"The {label} cannot be before the date of death "
                f"({date_of_death.isoformat()})",
            )

        if previous_value is not None and value < previous_value:
            raise ArrangementError(
                422,
                f"The {label} cannot be before the {previous_label}",
            )

        previous_value = value
        previous_label = label


def check_can_confirm(values: dict) -> None:
    """What must be known before the family can be told it is booked."""

    missing = []

    if values.get("committal_at") is None:
        missing.append("the burial or cremation time")

    if not values.get("committal_place"):
        missing.append("the cemetery or crematorium")

    if missing:
        raise ArrangementError(
            422,
            "Cannot confirm the funeral without " + " and ".join(missing),
        )


def check_arrangement_transition(
    current: str,
    target: str,
    *,
    reason: str | None,
    values: dict,
    now: datetime | None = None,
) -> None:
    if target == current:
        raise ArrangementError(
            409, f"The arrangement is already {current}"
        )

    if target not in ARRANGEMENT_TRANSITIONS[current]:
        raise ArrangementError(
            409, f"A {current} arrangement cannot become {target}"
        )

    if target == "cancelled" and not reason:
        raise ArrangementError(
            422, "A reason is required to cancel the arrangement"
        )

    if target == "confirmed":
        check_can_confirm(values)

    if target == "completed":
        committal = values.get("committal_at")
        now = now or now_utc()

        if committal is None or committal > now + CLOCK_SLACK:
            raise ArrangementError(
                422,
                "The funeral cannot be completed before the burial or "
                "cremation has happened",
            )


# ============================================================
# COLLECTION RULES
# ============================================================

def check_collection_time(
    scheduled_at: datetime, *, date_of_death: date | None
) -> None:
    if date_of_death is not None and local_date(scheduled_at) < date_of_death:
        raise ArrangementError(
            422,
            "A collection cannot be scheduled before the date of death "
            f"({date_of_death.isoformat()})",
        )


def check_collection_transition(
    collection: CaseCollection,
    target: str,
    *,
    reason: str | None,
    collected_at: datetime | None,
    now: datetime | None = None,
) -> datetime | None:
    """Validate a status change. Returns the time to record as the
    collection time when the target is 'collected'."""

    current = collection.status
    now = now or now_utc()

    if target == current:
        raise ArrangementError(
            409, f"The collection is already {current}"
        )

    if target not in COLLECTION_TRANSITIONS[current]:
        raise ArrangementError(
            409, f"A {current} collection cannot become {target}"
        )

    if target == "cancelled" and not reason:
        raise ArrangementError(
            422, "A reason is required to cancel the collection"
        )

    if target == "en_route":
        if collection.vehicle_resource_id is None:
            raise ArrangementError(
                422, "Assign a vehicle before sending the collection out"
            )

        if collection.driver_user_id is None:
            raise ArrangementError(
                422, "Assign a driver before sending the collection out"
            )

    if target == "collected":
        at = collected_at or now

        if at > now + CLOCK_SLACK:
            raise ArrangementError(
                422, "The collection time cannot be in the future"
            )

        return at

    return None


def check_vehicle_and_driver(
    db: Session,
    *,
    business_id: UUID,
    vehicle_resource_id: UUID | None,
    driver_user_id: UUID | None,
) -> None:
    if vehicle_resource_id is not None:
        vehicle = (
            db.query(Resource)
            .filter(
                Resource.id == vehicle_resource_id,
                Resource.business_id == business_id,
            )
            .first()
        )

        if vehicle is None:
            raise ArrangementError(404, "Vehicle not found")

        if vehicle.resource_type != "vehicle":
            raise ArrangementError(422, "That resource is not a vehicle")

        if not vehicle.is_active:
            raise ArrangementError(422, "That vehicle is inactive")

    if driver_user_id is not None:
        driver = (
            db.query(User)
            .filter(
                User.id == driver_user_id,
                User.business_id == business_id,
            )
            .first()
        )

        if driver is None:
            raise ArrangementError(404, "Driver not found")

        if not driver.is_active:
            raise ArrangementError(422, "That driver is inactive")


# ============================================================
# RUN SHEET
# ============================================================

def _flag(code: str, severity: str, message: str) -> dict:
    return {"code": code, "severity": severity, "message": message}


def build_run_sheet(
    db: Session,
    *,
    business_id: UUID,
    day: date,
    branch_id: UUID | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or now_utc()
    start, end = day_bounds(day)

    case_query = db.query(FuneralCase).filter(
        FuneralCase.business_id == business_id,
        FuneralCase.is_archived.is_(False),
    )

    if branch_id is not None:
        case_query = case_query.filter(FuneralCase.branch_id == branch_id)

    case_ids_query = case_query.with_entities(FuneralCase.id)

    # ---- fetch ----------------------------------------------------

    collections = (
        db.query(CaseCollection)
        .filter(
            CaseCollection.business_id == business_id,
            CaseCollection.case_id.in_(case_ids_query),
            CaseCollection.status != "cancelled",
            CaseCollection.scheduled_at >= start,
            CaseCollection.scheduled_at < end,
        )
        .all()
    )

    overdue = (
        db.query(CaseCollection)
        .filter(
            CaseCollection.business_id == business_id,
            CaseCollection.case_id.in_(case_ids_query),
            CaseCollection.status.in_(OPEN_COLLECTION_STATUSES),
            CaseCollection.scheduled_at < now,
        )
        .all()
    )
    overdue = [
        collection
        for collection in overdue
        if not (start <= collection.scheduled_at < end)
    ]

    arrangements = [
        arrangement
        for arrangement in (
            db.query(FuneralArrangement)
            .filter(
                FuneralArrangement.business_id == business_id,
                FuneralArrangement.case_id.in_(case_ids_query),
                FuneralArrangement.status != "cancelled",
            )
            .all()
        )
        if any(
            (value := getattr(arrangement, field)) is not None
            and start <= value < end
            for field, _ in TIMELINE
        )
    ]

    bookings = (
        db.query(ResourceBooking, Resource, User)
        .join(Resource, Resource.id == ResourceBooking.resource_id)
        .outerjoin(User, User.id == ResourceBooking.driver_user_id)
        .filter(
            ResourceBooking.business_id == business_id,
            ResourceBooking.case_id.in_(case_ids_query),
            ResourceBooking.status != "cancelled",
            ResourceBooking.starts_at < end,
            ResourceBooking.ends_at > start,
        )
        .all()
    )

    case_ids = (
        {c.case_id for c in collections}
        | {c.case_id for c in overdue}
        | {a.case_id for a in arrangements}
        | {b.case_id for b, _, _ in bookings}
    )

    cases = {
        case.id: case
        for case in db.query(FuneralCase)
        .filter(FuneralCase.id.in_(case_ids))
        .all()
    }

    disposal = {
        record.case_id: record.disposal_method
        for record in db.query(DeathRecord)
        .filter(DeathRecord.case_id.in_(case_ids))
        .all()
    }

    paperwork: dict[tuple[UUID, str], str] = {}
    has_paperwork: set[UUID] = set()

    for item in (
        db.query(CasePaperworkItem)
        .filter(CasePaperworkItem.case_id.in_(case_ids))
        .all()
    ):
        paperwork[(item.case_id, item.item_type)] = item.status
        has_paperwork.add(item.case_id)

    remains = {
        record.case_id: record
        for record in db.query(RemainsRecord)
        .filter(RemainsRecord.case_id.in_(case_ids))
        .all()
    }

    location_names = {
        location.id: location.name
        for location in db.query(MortuaryLocation)
        .filter(MortuaryLocation.business_id == business_id)
        .all()
    }

    vehicle_names = {
        resource.id: resource.name
        for resource in db.query(Resource)
        .filter(
            Resource.business_id == business_id,
            Resource.resource_type == "vehicle",
        )
        .all()
    }

    driver_names = {
        user.id: user.full_name
        for user in db.query(User)
        .filter(User.business_id == business_id)
        .all()
    }

    vehicle_booked_cases = {
        booking.case_id
        for booking, resource, _ in bookings
        if resource.resource_type == "vehicle"
    }

    # ---- build ----------------------------------------------------

    items: list[dict] = []

    def base(case: FuneralCase) -> dict:
        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "deceased_full_name": case.deceased_full_name,
            "flags": [],
        }

    def collection_item(collection: CaseCollection) -> dict:
        case = cases[collection.case_id]
        flags = []

        if (
            collection.status in OPEN_COLLECTION_STATUSES
            and collection.scheduled_at < now
        ):
            flags.append(
                _flag(
                    "collection_overdue",
                    "danger",
                    "This collection was due and has not been made",
                )
            )

        if collection.status in OPEN_COLLECTION_STATUSES:
            if (
                collection.vehicle_resource_id is None
                and collection.case_id not in vehicle_booked_cases
            ):
                flags.append(
                    _flag(
                        "no_vehicle",
                        "warning",
                        "No vehicle assigned to this collection",
                    )
                )

            if collection.driver_user_id is None:
                flags.append(
                    _flag(
                        "no_driver",
                        "warning",
                        "No driver assigned to this collection",
                    )
                )

        return {
            **base(case),
            "id": f"collection-{collection.id}",
            "kind": "collection",
            "at": collection.scheduled_at,
            "title": "Collect the deceased",
            "location": collection.pickup_type.replace("_", " "),
            "address": collection.pickup_address,
            "contact_name": collection.pickup_contact_name,
            "contact_phone": collection.pickup_contact_phone,
            "vehicle": vehicle_names.get(collection.vehicle_resource_id),
            "driver": driver_names.get(collection.driver_user_id),
            "status": collection.status,
            "flags": flags,
        }

    for collection in collections:
        items.append(collection_item(collection))

    overdue_items = [collection_item(c) for c in overdue]
    overdue_items.sort(key=lambda item: item["at"])

    for arrangement in arrangements:
        case = cases[arrangement.case_id]
        method = disposal.get(case.id, "burial")

        events = []

        for field, kind, title, location, address in (
            (
                "wake_at",
                "wake",
                "Wake",
                arrangement.wake_venue,
                arrangement.wake_address,
            ),
            (
                "service_at",
                "service",
                "Funeral service",
                arrangement.service_venue,
                arrangement.service_address,
            ),
            (
                "departure_at",
                "departure",
                "Cortege departs",
                arrangement.departure_point,
                None,
            ),
            (
                "committal_at",
                "committal",
                "Cremation" if method == "cremation" else (
                    "Repatriation" if method == "repatriation" else "Burial"
                ),
                arrangement.committal_place,
                None,
            ),
        ):
            value = getattr(arrangement, field)

            if value is None or not (start <= value < end):
                continue

            events.append(
                {
                    **base(case),
                    "id": f"{kind}-{arrangement.id}",
                    "kind": kind,
                    "at": value,
                    "title": title,
                    "location": location,
                    "address": address,
                    "status": arrangement.status,
                    "flags": [],
                }
            )

        if not events:
            continue

        # Gaps are reported once, on the departure if it is today,
        # otherwise on the burial, so a crowded day is not noisy.
        anchor = next(
            (e for e in events if e["kind"] == "departure"),
            next((e for e in events if e["kind"] == "committal"), events[0]),
        )

        if arrangement.status == "draft":
            anchor["flags"].append(
                _flag(
                    "not_confirmed",
                    "warning",
                    "The family has not confirmed these arrangements",
                )
            )

        paper = RELEASE_PAPER_BY_DISPOSAL.get(method)

        if paper is not None:
            key, label = paper
            state = paperwork.get((case.id, key))

            if state is None and case.id not in has_paperwork:
                anchor["flags"].append(
                    _flag(
                        "paperwork_not_started",
                        "warning",
                        "The paperwork checklist has not been started",
                    )
                )
            elif state == "pending":
                anchor["flags"].append(
                    _flag(
                        f"{key}_missing",
                        "danger",
                        f"The {label} has not been obtained",
                    )
                )

        record = remains.get(case.id)

        if record is None:
            anchor["flags"].append(
                _flag(
                    "no_remains_record",
                    "warning",
                    "No remains record exists for this case",
                )
            )
        elif record.status == "in_custody":
            where = location_names.get(record.current_location_id)

            anchor["flags"].append(
                _flag(
                    "remains_in_custody",
                    "warning",
                    "Remains are still in custody"
                    + (f" at {where}" if where else "")
                    + ": release them before the cortege leaves",
                )
            )

            if record.identified_at is None:
                anchor["flags"].append(
                    _flag(
                        "not_identified",
                        "danger",
                        "The remains have not been formally identified",
                    )
                )

        committal = next(
            (e for e in events if e["kind"] == "committal"), None
        )

        if (
            committal is not None
            and method == "burial"
            and not arrangement.grave_confirmed
        ):
            committal["flags"].append(
                _flag(
                    "grave_not_confirmed",
                    "warning",
                    "The grave has not been confirmed with the cemetery",
                )
            )

        departure = next(
            (e for e in events if e["kind"] == "departure"), None
        )

        if departure is not None and case.id not in vehicle_booked_cases:
            departure["flags"].append(
                _flag(
                    "no_vehicle",
                    "danger",
                    "No vehicle is booked for the cortege",
                )
            )

        items.extend(events)

    for booking, resource, driver in bookings:
        case = cases[booking.case_id]

        items.append(
            {
                **base(case),
                "id": f"booking-{booking.id}",
                "kind": "booking",
                "at": max(booking.starts_at, start),
                "ends_at": min(booking.ends_at, end),
                "title": booking.purpose or resource.name,
                "location": resource.name,
                "vehicle": (
                    resource.name
                    if resource.resource_type == "vehicle"
                    else None
                ),
                "driver": driver.full_name if driver else None,
                "status": booking.status,
            }
        )

    items.sort(key=lambda item: (item["at"], KIND_ORDER[item["kind"]]))

    flagged = sum(1 for item in items if item["flags"])

    return {
        "date": day,
        "timezone": BUSINESS_TZ_NAME,
        "branch_id": branch_id,
        "summary": {
            "collections": sum(1 for i in items if i["kind"] == "collection"),
            "funerals": len({i["case_id"] for i in items if i["kind"] in ("service", "departure", "committal")}),
            "items": len(items),
            "flagged_items": flagged,
            "overdue_collections": len(overdue_items),
        },
        "items": items,
        "overdue_collections": overdue_items,
    }
