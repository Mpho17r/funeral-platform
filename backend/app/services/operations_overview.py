"""The operations dashboard: every live funeral, where it has got to,
and the one thing to do next.

Read-only. Carries no money or membership information.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.arrangement import CaseCollection, FuneralArrangement
from app.models.case_task import CaseTask
from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.mortuary import RemainsRecord
from app.models.resource import Resource, ResourceBooking
from app.services.mortuary_overview import SAST, sa_day_bounds

LIVE_STATUSES = ("open", "confirmed", "in_progress")
SOON_DAYS = 3

STEP_LABELS = {
    "collection": "Collection",
    "remains": "In our care",
    "death_record": "Death record",
    "arrangement": "Arrangement",
    "paperwork": "Paperwork",
    "vehicle": "Vehicle",
}


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def next_action(steps: dict, *, funeral_soon: bool) -> tuple[str, str]:
    """The first thing still missing, in the order a funeral needs it.

    Returns a short code and the sentence shown to staff.
    """

    if steps["collection"] == "todo":
        return "arrange_collection", "Arrange the collection"
    if steps["collection"] == "pending":
        return "await_collection", "Collection is scheduled"
    if steps["remains"] == "todo":
        return "take_in", "Take the remains into care"
    if steps["death_record"] == "todo":
        return "death_record", "Capture the death record"
    if steps["arrangement"] == "todo":
        return "plan_arrangement", "Plan the funeral arrangement"
    if steps["arrangement"] == "draft":
        return "confirm_arrangement", "Confirm the arrangement with the family"
    if steps["paperwork"] == "todo":
        return "paperwork", "Obtain the outstanding paperwork"
    if steps["vehicle"] == "todo" and funeral_soon:
        return "book_vehicle", "Book a vehicle for the funeral"
    return "on_track", "On track"


def overview(
    db: Session,
    *,
    business_id: UUID,
    branch_id: UUID | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(SAST).date()
    day_start, day_end = sa_day_bounds(today)

    q = db.query(FuneralCase).filter(
        FuneralCase.business_id == business_id,
        FuneralCase.is_archived.is_(False),
        FuneralCase.status.in_(LIVE_STATUSES),
    )
    if branch_id is not None:
        q = q.filter(FuneralCase.branch_id == branch_id)
    cases = q.all()
    ids = [c.id for c in cases]

    def by_case(model, *conds):
        out: dict[UUID, list] = {}
        if ids:
            for row in db.query(model).filter(
                model.case_id.in_(ids), *conds
            ):
                out.setdefault(row.case_id, []).append(row)
        return out

    arrangements = {
        a.case_id: a
        for rows in by_case(FuneralArrangement).values()
        for a in rows
    }
    collections = by_case(CaseCollection)
    remains = {
        r.case_id: r for rows in by_case(RemainsRecord).values() for r in rows
    }
    death = {
        d.case_id: d for rows in by_case(DeathRecord).values() for d in rows
    }
    paper = by_case(CasePaperworkItem)
    bookings = by_case(ResourceBooking, ResourceBooking.status != "cancelled")
    tasks = by_case(CaseTask, CaseTask.completed_at.is_(None))

    vehicle_ids = {
        r.id
        for r in db.query(Resource).filter(
            Resource.business_id == business_id,
            Resource.resource_type == "vehicle",
        )
    }

    rows = []
    for case in cases:
        arr = arrangements.get(case.id)
        cols = [c for c in collections.get(case.id, []) if c.status != "cancelled"]
        rem = remains.get(case.id)
        items = paper.get(case.id, [])
        pending_paper = [i for i in items if i.status == "pending"]
        has_vehicle = any(
            b.resource_id in vehicle_ids for b in bookings.get(case.id, [])
        )

        if rem is not None:
            collection = "done"
        elif any(c.status == "collected" for c in cols):
            collection = "done"
        elif cols:
            collection = "pending"
        else:
            collection = "todo"

        steps = {
            "collection": collection,
            "remains": "done" if rem is not None else "todo",
            "death_record": "done" if case.id in death else "todo",
            "arrangement": (
                "todo" if arr is None or arr.status == "cancelled"
                else "draft" if arr.status == "draft" else "done"
            ),
            "paperwork": (
                "todo" if (pending_paper or (case.id in death and not items))
                else "done"
            ),
            "vehicle": "done" if has_vehicle else "todo",
        }

        funeral_day = case.funeral_date
        if funeral_day is None and arr is not None and arr.committal_at:
            funeral_day = arr.committal_at.astimezone(SAST).date()

        days_to = (funeral_day - today).days if funeral_day else None
        funeral_soon = days_to is not None and 0 <= days_to <= SOON_DAYS

        code, text = next_action(steps, funeral_soon=funeral_soon)
        overdue = [
            t for t in tasks.get(case.id, [])
            if t.due_date and t.due_date < today
        ]

        rows.append(
            {
                "case_id": str(case.id),
                "case_number": case.case_number,
                "name": case.deceased_full_name,
                "status": case.status,
                "funeral_date": _iso(funeral_day),
                "days_to_funeral": days_to,
                "venue": (
                    (arr.service_venue if arr and arr.service_venue else None)
                    or case.funeral_venue
                ),
                "arrangement_status": arr.status if arr else None,
                "steps": steps,
                "next_action": code,
                "next_action_text": text,
                "open_tasks": len(tasks.get(case.id, [])),
                "overdue_tasks": len(overdue),
                "urgent": (
                    code not in ("on_track", "await_collection")
                    and funeral_soon
                ) or bool(overdue),
                "_committal": arr.committal_at if arr else None,
                "_service": arr.service_at if arr else None,
                "_departure": arr.departure_at if arr else None,
            }
        )

    def sort_key(r):
        d = r["days_to_funeral"]
        return (d is None, d if d is not None else 0, r["case_number"])

    rows.sort(key=sort_key)

    # --- today's programme: every timed moment of every funeral today
    programme = []
    for r in rows:
        for label, moment in (
            ("Departure", r["_departure"]),
            ("Service", r["_service"]),
            ("Committal", r["_committal"]),
        ):
            if moment is not None and day_start <= moment < day_end:
                programme.append(
                    {
                        "at": moment.isoformat(),
                        "label": label,
                        "case_id": r["case_id"],
                        "case_number": r["case_number"],
                        "name": r["name"],
                        "venue": r["venue"],
                    }
                )
    programme.sort(key=lambda p: p["at"])

    # --- collections still to do today or overdue
    collections_due = []
    pending_cols = (
        db.query(CaseCollection, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CaseCollection.case_id)
        .filter(
            CaseCollection.business_id == business_id,
            CaseCollection.status.in_(("scheduled", "en_route")),
            CaseCollection.scheduled_at < day_end,
        )
        .order_by(CaseCollection.scheduled_at)
        .all()
    )
    for col, case in pending_cols:
        if branch_id is not None and case.branch_id != branch_id:
            continue
        collections_due.append(
            {
                "case_id": str(case.id),
                "case_number": case.case_number,
                "name": case.deceased_full_name,
                "scheduled_at": col.scheduled_at.isoformat(),
                "status": col.status,
                "overdue": col.scheduled_at < now,
                "pickup_type": col.pickup_type,
                "pickup_address": col.pickup_address,
            }
        )

    # --- vehicles
    todays_bookings = (
        db.query(ResourceBooking)
        .filter(
            ResourceBooking.business_id == business_id,
            ResourceBooking.status == "booked",
            ResourceBooking.starts_at < day_end,
            ResourceBooking.ends_at >= day_start,
        )
        .all()
    )
    busy_vehicles = {
        b.resource_id for b in todays_bookings
        if b.resource_id in vehicle_ids
    }
    active_vehicles = db.query(Resource).filter(
        Resource.business_id == business_id,
        Resource.resource_type == "vehicle",
        Resource.is_active.is_(True),
    ).count()

    for r in rows:
        for key in ("_committal", "_service", "_departure"):
            r.pop(key)

    funerals_today = [r for r in rows if r["days_to_funeral"] == 0]
    this_week = [
        r for r in rows
        if r["days_to_funeral"] is not None and 0 <= r["days_to_funeral"] <= 7
    ]
    needs_action = [
        r for r in rows if r["next_action"] not in ("on_track",)
    ]

    pipeline: dict[str, int] = {}
    for r in rows:
        pipeline[r["next_action"]] = pipeline.get(r["next_action"], 0) + 1

    return {
        "today": today.isoformat(),
        "kpis": {
            "live_cases": len(rows),
            "funerals_today": len(funerals_today),
            "funerals_this_week": len(this_week),
            "needing_action": len(needs_action),
            "urgent": sum(1 for r in rows if r["urgent"]),
            "overdue_tasks": sum(r["overdue_tasks"] for r in rows),
            "collections_due": len(collections_due),
            "vehicles_out_today": len(busy_vehicles),
            "vehicles_in_fleet": active_vehicles,
        },
        "programme": programme,
        "collections_due": collections_due,
        "pipeline": pipeline,
        "step_labels": STEP_LABELS,
        "cases": rows[:60],
    }
