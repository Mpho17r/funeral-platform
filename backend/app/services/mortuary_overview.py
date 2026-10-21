"""The mortuary dashboard: occupancy, temperatures, who is where, and
what each set of remains still needs before it can leave.

Read-only. Nothing here carries money or membership information.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.mortuary import (
    COLD_LOCATION_KINDS,
    CustodyEvent,
    MortuaryLocation,
    MortuaryTemperatureReading,
    RemainsRecord,
)
from app.services.mortuary import (
    cooling_status,
    now_utc,
    release_blockers,
)

SAST = timezone(timedelta(hours=2))

# Remains must be at 5 degrees C or colder (Regulation R363).
MAX_SAFE_TEMPERATURE = Decimal("5.0")
LONG_STAY_DAYS = 14
MAX_HOURS = 24 * 7


def _num(value) -> float | None:
    return None if value is None else float(value)


def sa_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=SAST)
    return start.astimezone(timezone.utc), (
        start + timedelta(days=1)
    ).astimezone(timezone.utc)


def stage_of(remains, *, prepared: bool, blockers: list[str]) -> str:
    """Where remains are in the journey, in order."""

    if remains.identified_at is None:
        return "awaiting_identification"
    if not prepared:
        return "awaiting_preparation"
    if blockers:
        return "awaiting_paperwork"
    return "ready_for_release"


def record_temperature(
    db: Session,
    *,
    business_id: UUID,
    location: MortuaryLocation,
    temperature_c: Decimal,
    recorded_by: UUID,
    recorded_at: datetime | None = None,
    notes: str | None = None,
) -> MortuaryTemperatureReading:
    reading = MortuaryTemperatureReading(
        business_id=business_id,
        location_id=location.id,
        temperature_c=temperature_c,
        recorded_by=recorded_by,
        recorded_at=recorded_at or now_utc(),
        notes=notes or None,
    )
    db.add(reading)
    db.flush()
    return reading


def temperature_series(
    db: Session,
    *,
    business_id: UUID,
    hours: int,
    now: datetime,
    location_ids: list[UUID] | None = None,
) -> dict:
    since = now - timedelta(hours=hours)

    query = db.query(MortuaryTemperatureReading).filter(
        MortuaryTemperatureReading.business_id == business_id,
        MortuaryTemperatureReading.recorded_at >= since,
        MortuaryTemperatureReading.recorded_at <= now,
    )
    if location_ids is not None:
        query = query.filter(
            MortuaryTemperatureReading.location_id.in_(location_ids)
        )

    readings = query.order_by(MortuaryTemperatureReading.recorded_at).all()

    # One point per hour: the average of that hour's readings.
    buckets: dict[datetime, list[Decimal]] = {}
    for r in readings:
        hour = r.recorded_at.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        buckets.setdefault(hour, []).append(r.temperature_c)

    points = [
        {
            "at": hour.isoformat(),
            "temperature_c": round(
                float(sum(values) / len(values)), 1
            ),
        }
        for hour, values in sorted(buckets.items())
    ]

    temps = [r.temperature_c for r in readings]

    return {
        "hours": hours,
        "max_safe_c": float(MAX_SAFE_TEMPERATURE),
        "points": points,
        "readings": len(readings),
        "average_c": (
            round(float(sum(temps) / len(temps)), 1) if temps else None
        ),
        "min_c": _num(min(temps)) if temps else None,
        "max_c": _num(max(temps)) if temps else None,
        "out_of_range": sum(
            1 for t in temps if t > MAX_SAFE_TEMPERATURE
        ),
    }


def overview(
    db: Session,
    *,
    business_id: UUID,
    branch_id: UUID | None = None,
    hours: int = 24,
    now: datetime | None = None,
) -> dict:
    now = now or now_utc()
    hours = max(1, min(hours, MAX_HOURS))

    q = db.query(MortuaryLocation).filter(
        MortuaryLocation.business_id == business_id,
        MortuaryLocation.is_active.is_(True),
        MortuaryLocation.kind.in_(COLD_LOCATION_KINDS),
    )
    if branch_id is not None:
        q = q.filter(MortuaryLocation.branch_id == branch_id)
    locations = q.order_by(MortuaryLocation.name).all()
    loc_ids = [loc.id for loc in locations]

    # Everyone currently in our care (anywhere), with their case.
    rows = (
        db.query(RemainsRecord, FuneralCase)
        .join(FuneralCase, FuneralCase.id == RemainsRecord.case_id)
        .filter(
            RemainsRecord.business_id == business_id,
            RemainsRecord.status == "in_custody",
        )
        .all()
    )
    if branch_id is not None:
        rows = [(r, c) for r, c in rows if c.branch_id == branch_id]

    case_ids = [c.id for _, c in rows]
    remains_ids = [r.id for r, _ in rows]

    prepared_ids = {
        e[0]
        for e in db.query(CustodyEvent.remains_id).filter(
            CustodyEvent.remains_id.in_(remains_ids),
            CustodyEvent.event_type == "prepared",
        )
    } if remains_ids else set()

    death_records = {
        d.case_id: d
        for d in db.query(DeathRecord).filter(
            DeathRecord.case_id.in_(case_ids)
        )
    } if case_ids else {}

    paperwork: dict[UUID, list] = {}
    if case_ids:
        for item in db.query(CasePaperworkItem).filter(
            CasePaperworkItem.case_id.in_(case_ids)
        ):
            paperwork.setdefault(item.case_id, []).append(item)

    # Latest temperature per cold place (from the log).
    latest: dict[UUID, MortuaryTemperatureReading] = {}
    if loc_ids:
        for r in (
            db.query(MortuaryTemperatureReading)
            .filter(MortuaryTemperatureReading.location_id.in_(loc_ids))
            .order_by(MortuaryTemperatureReading.recorded_at)
        ):
            latest[r.location_id] = r

    occupants: dict[UUID, list] = {}
    stages = {
        "awaiting_identification": 0,
        "awaiting_preparation": 0,
        "awaiting_paperwork": 0,
        "ready_for_release": 0,
    }
    attention: list[dict] = []
    today_start, today_end = sa_day_bounds(now.astimezone(SAST).date())
    admissions_today = []
    ready_list = []

    for remains, case in rows:
        blockers = release_blockers(
            remains=remains,
            death_record=death_records.get(case.id),
            paperwork_items=paperwork.get(case.id, []),
        )
        stage = stage_of(
            remains, prepared=remains.id in prepared_ids,
            blockers=blockers,
        )
        stages[stage] += 1

        cooling = cooling_status(remains, now=now)
        days = (now - remains.received_at).days

        entry = {
            "remains_id": str(remains.id),
            "case_id": str(case.id),
            "case_number": case.case_number,
            "name": case.deceased_full_name,
            "tag_number": remains.tag_number,
            "received_at": remains.received_at.isoformat(),
            "stage": stage,
            "days_in_care": days,
            "cooling_overdue": cooling["cooling_overdue"],
            "blockers": blockers,
            "funeral_date": (
                case.funeral_date.isoformat() if case.funeral_date else None
            ),
        }

        if remains.current_location_id:
            occupants.setdefault(
                remains.current_location_id, []
            ).append(entry)

        if today_start <= remains.received_at < today_end:
            admissions_today.append(entry)
        if stage == "ready_for_release":
            ready_list.append(entry)

        if cooling["cooling_overdue"]:
            attention.append(
                {**entry, "reason": "cooling_overdue",
                 "message": "Not yet cooled; the 3 hour limit has passed"}
            )
        elif days >= LONG_STAY_DAYS:
            attention.append(
                {**entry, "reason": "long_stay",
                 "message": f"In our care for {days} days"}
            )
        elif stage == "awaiting_identification" and days >= 1:
            attention.append(
                {**entry, "reason": "not_identified",
                 "message": "Still not formally identified"}
            )

    units = []
    capacity_total = 0
    occupied_total = 0

    for loc in locations:
        here = occupants.get(loc.id, [])
        reading = latest.get(loc.id)
        too_warm = (
            reading is not None
            and reading.temperature_c > MAX_SAFE_TEMPERATURE
        )

        if too_warm:
            status = "out_of_range"
            attention.append(
                {
                    "reason": "temperature",
                    "message": (
                        f"{loc.name} read {reading.temperature_c}°C "
                        f"(above {MAX_SAFE_TEMPERATURE}°C)"
                    ),
                    "location_id": str(loc.id),
                    "name": loc.name,
                }
            )
        elif loc.capacity is not None and len(here) >= loc.capacity:
            status = "full"
        elif here:
            status = "occupied"
        else:
            status = "available"

        if loc.capacity is not None:
            capacity_total += loc.capacity
        occupied_total += len(here)

        units.append(
            {
                "id": str(loc.id),
                "name": loc.name,
                "zone": loc.kind,
                "capacity": loc.capacity,
                "occupied": len(here),
                "status": status,
                "temperature_c": (
                    _num(reading.temperature_c) if reading else None
                ),
                "temperature_at": (
                    reading.recorded_at.isoformat() if reading else None
                ),
                "occupants": here,
            }
        )

    awaiting_placement = [
        {
            "remains_id": str(r.id),
            "case_id": str(c.id),
            "name": c.deceased_full_name,
            "tag_number": r.tag_number,
        }
        for r, c in rows
        if r.current_location_id not in set(loc_ids)
    ]

    return {
        "occupancy": {
            "occupied": occupied_total,
            "capacity": capacity_total,
            "percent": (
                round(100 * occupied_total / capacity_total, 1)
                if capacity_total
                else None
            ),
            "unlimited_places": sum(
                1 for loc in locations if loc.capacity is None
            ),
        },
        "in_care": len(rows),
        "pending_releases": len(ready_list),
        "ready_for_release": ready_list[:10],
        "admissions_today": len(admissions_today),
        "admissions_today_list": admissions_today,
        "stages": stages,
        "temperature": temperature_series(
            db,
            business_id=business_id,
            hours=hours,
            now=now,
            location_ids=loc_ids,
        ),
        "units": units,
        "not_in_a_cold_place": awaiting_placement,
        "attention": attention[:20],
    }
