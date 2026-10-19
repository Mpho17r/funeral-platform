"""Queue reminders every day for businesses that switched it on.

Nothing is sent. The same rules as the Reminders page decide who is
due, the messages land in the queue, and a person still sends each one.
Running it twice in a day is safe: a reminder already queued is skipped.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.services.audit_service import create_audit_log
from app.services.communications import (
    plan_reminders,
    queue_candidates,
    today_in_south_africa,
)


def run_for_business(
    db: Session,
    business: Business,
    *,
    today: date | None = None,
) -> int:
    """Queue today's reminders for one business. Returns how many."""

    plan = plan_reminders(db, business, today=today)
    created, _ = queue_candidates(
        db, business.id, None, plan.candidates
    )

    counts: dict[str, int] = {}
    for message in created:
        counts[message.kind] = counts.get(message.kind, 0) + 1

    business.auto_reminders_last_run_at = datetime.now(timezone.utc)
    business.auto_reminders_last_count = len(created)

    create_audit_log(
        db,
        business_id=business.id,
        user_id=None,
        action="communication.reminders_auto_generated",
        entity_type="communication_message",
        details={
            "created": len(created),
            "counts": counts,
            "skipped": len(plan.skipped),
            "date": plan.today.isoformat(),
        },
        notes="Reminders were queued automatically.",
    )

    return len(created)


def run_all(db: Session, *, today: date | None = None) -> dict[str, int]:
    """Every business with automatic reminders on. One business failing
    never stops the others."""

    results: dict[str, int] = {}
    today = today or today_in_south_africa()

    businesses = db.scalars(
        select(Business).where(Business.auto_reminders_enabled.is_(True))
    ).all()

    for business in businesses:
        try:
            results[str(business.id)] = run_for_business(
                db, business, today=today
            )
            db.commit()
        except Exception:
            db.rollback()
            results[str(business.id)] = -1

    return results
