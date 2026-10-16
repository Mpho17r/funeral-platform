"""Mortuary and custody rules.

Pure business rules with no HTTP concerns. They protect the three
things that go wrong in a mortuary: remains left warm, a cold place
overfilled, and the wrong person released to the wrong family.

- Remains must be cooled to 5 degrees C within three hours of
  arriving (Regulation R363, 10(6)(b)), so the system tracks a cooling
  deadline from the moment of arrival.
- The number of remains in a cold place may not exceed its trays
  (R363, 11(2)(g)), so a place with a capacity refuses to overfill.
- Remains are released only against their tag number, only once they
  have been identified, and only with the paperwork the way they are
  being laid to rest needs. A manager may override paperwork gaps with
  a written reason. The tag check can never be overridden.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.mortuary import (
    COLD_LOCATION_KINDS,
    MortuaryLocation,
    RemainsRecord,
)


COOLING_LIMIT = timedelta(hours=3)

# The paperwork item that must be in place before the remains leave,
# by the way they will be laid to rest.
RELEASE_PAPER_BY_DISPOSAL = {
    "burial": ("burial_order", "burial order"),
    "cremation": ("cremation_permit", "cremation permit"),
    "repatriation": ("export_permit", "export permit"),
}


class MortuaryError(Exception):
    """A mortuary rule was violated."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def default_tag(case_number: str) -> str:
    """A tag that is unique because case numbers are."""

    return f"T-{case_number}"


def is_cold(location: MortuaryLocation | None) -> bool:
    return location is not None and location.kind in COLD_LOCATION_KINDS


def cooling_status(
    remains: RemainsRecord,
    *,
    now: datetime | None = None,
) -> dict:
    """Whether the remains have been cooled, and if not, by when."""

    now = now or now_utc()

    if remains.status == "released":
        return {
            "cooled": remains.cooled_at is not None,
            "cooling_due_at": None,
            "cooling_overdue": False,
        }

    if remains.cooled_at is not None:
        return {
            "cooled": True,
            "cooling_due_at": None,
            "cooling_overdue": False,
        }

    due = remains.received_at + COOLING_LIMIT

    return {
        "cooled": False,
        "cooling_due_at": due,
        "cooling_overdue": now > due,
    }


def occupancy(db: Session, location_id: UUID) -> int:
    """How many remains are in a place right now."""

    return (
        db.query(func.count(RemainsRecord.id))
        .filter(
            RemainsRecord.current_location_id == location_id,
            RemainsRecord.status == "in_custody",
        )
        .scalar()
    )


def get_placeable_location(
    db: Session,
    business_id: UUID,
    location_id: UUID,
) -> MortuaryLocation:
    """A place remains may be put in, locked so two arrivals cannot
    take the last tray at the same moment."""

    location = (
        db.query(MortuaryLocation)
        .filter(
            MortuaryLocation.id == location_id,
            MortuaryLocation.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if location is None:
        raise MortuaryError(422, "Mortuary location not found")

    if not location.is_active:
        raise MortuaryError(
            409,
            f"{location.name} is inactive and cannot receive remains",
        )

    if location.capacity is not None:
        taken = occupancy(db, location.id)

        if taken >= location.capacity:
            raise MortuaryError(
                409,
                f"{location.name} is full "
                f"({taken} of {location.capacity})",
            )

    return location


def release_blockers(
    *,
    remains: RemainsRecord,
    death_record,
    paperwork_items,
) -> list[str]:
    """Everything that stands between these remains and release.

    A manager may override these with a written reason. They are
    returned together so staff can see the whole list at once.
    """

    blockers: list[str] = []

    if remains.identified_at is None:
        blockers.append("The remains have not been formally identified")

    if death_record is None:
        blockers.append("No death record has been captured for the case")

        return blockers

    if (
        death_record.manner_of_death == "unnatural"
        and death_record.forensic_status != "released"
    ):
        blockers.append(
            "Forensic pathology has not released the remains"
        )

    paper = RELEASE_PAPER_BY_DISPOSAL.get(death_record.disposal_method)

    if paper is not None:
        item_type, label = paper

        item = next(
            (
                entry
                for entry in paperwork_items
                if entry.item_type == item_type
            ),
            None,
        )

        if item is None or item.status == "pending":
            blockers.append(f"The {label} has not been obtained")

    return blockers
