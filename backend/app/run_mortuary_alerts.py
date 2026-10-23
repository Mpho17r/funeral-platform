"""Scheduled job: tell the mortuary team what needs attention.

    python -m app.run_mortuary_alerts

Run it every 30 minutes (cron, launchd or your host's scheduler). Each
problem is sent once per day, so running it often does not repeat itself.
"""

from app.database import SessionLocal
from app.services.mortuary_alerts import run_all


def main() -> None:
    db = SessionLocal()
    try:
        results = run_all(db)
    finally:
        db.close()

    failed = sum(1 for n in results.values() if n < 0)
    sent = sum(n for n in results.values() if n > 0)
    print(f"Businesses: {len(results)}, alerts sent: {sent}, failed: {failed}")


if __name__ == "__main__":
    main()
