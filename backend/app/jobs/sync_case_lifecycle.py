"""One-shot job to advance funeral case statuses from linked arrangements.

Run from backend/:
    python -m app.jobs.sync_case_lifecycle

Schedule this command with the production host's cron/scheduled-job feature
(e.g. every 5 minutes). It uses the configured DATABASE_URL and does not
connect to the test database unless DATABASE_URL explicitly points there.
"""

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.arrangement import FuneralArrangement
from app.models.funeral_case import FuneralCase
from app.services.automatic_case_lifecycle import (
    sync_case_status_from_arrangement,
)


def run(db: Session) -> int:
    pairs = (
        db.query(FuneralCase, FuneralArrangement)
        .join(
            FuneralArrangement,
            (FuneralArrangement.case_id == FuneralCase.id)
            & (FuneralArrangement.business_id == FuneralCase.business_id),
        )
        .filter(
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.notin_(("completed", "closed", "cancelled")),
            FuneralArrangement.status.in_(("confirmed", "completed")),
        )
        .all()
    )

    changed_count = 0
    for case, arrangement in pairs:
        changes = sync_case_status_from_arrangement(
            db,
            case=case,
            arrangement=arrangement,
            user_id=None,
        )
        if changes:
            db.commit()
            changed_count += len(changes)

    return changed_count


def main() -> None:
    db = SessionLocal()
    try:
        changed = run(db)
        print(f"FuneralOS automatic case lifecycle: {changed} status transition(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
