"""
Cleaning and disinfection records for the mortuary.

R363 regulation 11(2): working surfaces and equipment must be cleaned and
disinfected immediately after each preparation. We treat a preparation
with no surfaces AND equipment record after it, more than
`GRACE_MINUTES` later, as something to chase.
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.funeral_case import FuneralCase
from app.models.mortuary import (
    CustodyEvent,
    MortuaryHygieneLog,
    RemainsRecord,
)

GRACE_MINUTES = 120
LOOKBACK_HOURS = 48
REQUIRED_AFTER_PREPARATION = ("surfaces", "equipment")

TASK_LABELS = {
    "surfaces": "Preparation surfaces",
    "equipment": "Equipment and instruments",
    "protective_clothing": "Protective clothing",
    "vehicle": "Vehicle loading space",
    "waste": "Health-care risk waste",
    "premises": "Premises (pests, odours)",
}


def cleaning_gaps(
    db: Session, *, business_id: UUID, now: datetime
) -> list[dict]:
    """Attention items for recent preparations nobody has cleaned up after."""
    since = now - timedelta(hours=LOOKBACK_HOURS)
    due_before = now - timedelta(minutes=GRACE_MINUTES)

    preparations = (
        db.query(CustodyEvent, RemainsRecord, FuneralCase)
        .join(RemainsRecord, RemainsRecord.id == CustodyEvent.remains_id)
        .join(FuneralCase, FuneralCase.id == RemainsRecord.case_id)
        .filter(
            CustodyEvent.business_id == business_id,
            CustodyEvent.event_type == "prepared",
            CustodyEvent.occurred_at >= since,
            CustodyEvent.occurred_at <= due_before,
        )
        .order_by(CustodyEvent.occurred_at)
        .all()
    )
    if not preparations:
        return []

    logs = (
        db.query(MortuaryHygieneLog.task, MortuaryHygieneLog.performed_at)
        .filter(
            MortuaryHygieneLog.business_id == business_id,
            MortuaryHygieneLog.performed_at >= since,
            MortuaryHygieneLog.task.in_(REQUIRED_AFTER_PREPARATION),
        )
        .all()
    )

    items = []
    for event, remains, case in preparations:
        missing = [
            task
            for task in REQUIRED_AFTER_PREPARATION
            if not any(
                t == task and at >= event.occurred_at for t, at in logs
            )
        ]
        if missing:
            items.append(
                {
                    "reason": "cleaning_overdue",
                    "message": "No "
                    + " or ".join(
                        TASK_LABELS[t].lower() for t in missing
                    )
                    + " cleaning record since the preparation",
                    "case_id": str(case.id),
                    "name": case.deceased_full_name,
                    "tag_number": remains.tag_number,
                }
            )
    return items
