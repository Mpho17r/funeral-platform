"""Daily job: queue reminders for every business that turned it on.

    python -m app.run_reminders

Run it once a day from cron or your host's scheduler, for example at
07:00 South African time.
"""

from app.database import SessionLocal
from app.services.auto_reminders import run_all


def main() -> None:
    db = SessionLocal()

    try:
        results = run_all(db)
    finally:
        db.close()

    failed = sum(1 for count in results.values() if count < 0)
    queued = sum(count for count in results.values() if count > 0)

    print(
        f"Businesses: {len(results)}, reminders queued: {queued}, "
        f"failed: {failed}"
    )


if __name__ == "__main__":
    main()
