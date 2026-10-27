"""
The one process that runs FuneralOS's recurring work.

    python -m app.run_scheduler          # keep running (use this in production)
    python -m app.run_scheduler --once   # check what is due, run it, exit

It replaces setting up four separate cron entries:

  every  5 minutes   move funerals along as arrangements are confirmed
  every 30 minutes   mortuary alerts and licence renewal reminders
  daily at 07:00     payment reminders for businesses that turned them on
  daily at 02:00     backup of the database and uploaded files

Times are South African time (SCHEDULER_TIMEZONE). If the computer was off
at the usual time, a daily job runs when it comes back, inside a window that
keeps reminders from going out late at night. One failing job never stops the
others. Run exactly ONE copy of this process.
"""

import logging
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from app.config import settings
from app.services import scheduler_state

log = logging.getLogger("funeralos.scheduler")

TICK_SECONDS = 30


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable[[], str]
    every_minutes: int | None = None  # repeat on an interval, or
    daily_hour: int | None = None     # once a day from this local hour
    window_hours: int = 24            # how long after that hour it may still run


def is_due(job: Job, last_run: datetime | None, now: datetime, tz) -> bool:
    """Should this job run now? `now` must be timezone-aware."""
    if job.every_minutes is not None:
        return last_run is None or now - last_run >= timedelta(
            minutes=job.every_minutes
        )

    local = now.astimezone(tz)
    start = local.replace(
        hour=job.daily_hour, minute=0, second=0, microsecond=0
    )
    if not (start <= local < start + timedelta(hours=job.window_hours)):
        return False
    return last_run is None or last_run.astimezone(tz).date() < local.date()


# ----------------------------------------------------------------- the jobs


def _lifecycle() -> str:
    from app.database import SessionLocal
    from app.jobs.sync_case_lifecycle import run

    db = SessionLocal()
    try:
        return f"{run(db)} status change(s)"
    finally:
        db.close()


def _mortuary() -> str:
    from app.database import SessionLocal
    from app.services.mortuary_alerts import run_all

    db = SessionLocal()
    try:
        results = run_all(db)
    finally:
        db.close()
    return f"{sum(n for n in results.values() if n > 0)} alert(s) sent"


def _reminders() -> str:
    from app.database import SessionLocal
    from app.services.auto_reminders import run_all

    from app.services.transport import send_due_reminders

    db = SessionLocal()
    try:
        results = run_all(db)
        drivers = send_due_reminders(db)
    finally:
        db.close()
    queued = sum(n for n in results.values() if n > 0)
    return f"{queued} reminder(s) queued, {drivers} driver reminder(s) sent"


def _stock() -> str:
    from app.database import SessionLocal
    from app.services.stock_automation import scan_low_stock

    db = SessionLocal()
    try:
        return f"{scan_low_stock(db)} low-stock alert(s)"
    finally:
        db.close()


def _delivery() -> str:
    from app.database import SessionLocal
    from app.services.message_delivery import deliver_queued

    db = SessionLocal()
    try:
        result = deliver_queued(db)
    finally:
        db.close()
    return f"{result['sent']} sent, {result['failed']} failed"


def _backup() -> str:
    from app.run_backup import run_backup

    result = run_backup()
    if not result["ok"]:
        raise RuntimeError(result["error"] or "backup failed")
    return f"{result['size_mb']} MB"


def build_jobs() -> list[Job]:
    jobs = [
        Job("lifecycle", _lifecycle, every_minutes=5),
        Job("mortuary_alerts", _mortuary, every_minutes=30),
        # Reminders only go out in daytime, even after a late restart.
        Job("reminders", _reminders,
            daily_hour=settings.scheduler_reminders_hour, window_hours=8),
        Job("delivery", _delivery, every_minutes=10),
        Job("stock", _stock, every_minutes=60),
    ]
    if settings.scheduler_backups_enabled:
        jobs.append(
            Job("backup", _backup,
                daily_hour=settings.scheduler_backup_hour, window_hours=22)
        )
    return jobs


# ------------------------------------------------------------------ running


def tick(jobs: list[Job], now: datetime | None = None) -> dict[str, str]:
    """Run whatever is due. Returns what ran, for logs and tests."""
    now = now or datetime.now(timezone.utc)
    tz = ZoneInfo(settings.scheduler_timezone)
    state = scheduler_state.load()
    ran: dict[str, str] = {}

    for job in jobs:
        entry = state.setdefault("jobs", {}).get(job.name, {})
        last = (
            datetime.fromisoformat(entry["last_run_at"])
            if entry.get("last_run_at")
            else None
        )
        if not is_due(job, last, now, tz):
            continue

        try:
            detail = job.run()
            entry = {"last_run_at": now.isoformat(), "ok": True,
                     "detail": detail}
            log.info("%s: %s", job.name, detail)
        except Exception as exc:  # noqa: BLE001 - one job must not stop the rest
            entry = {"last_run_at": now.isoformat(), "ok": False,
                     "detail": str(exc)[:300]}
            log.exception("%s failed", job.name)
        state["jobs"][job.name] = entry
        ran[job.name] = entry["detail"]

    state["heartbeat_at"] = now.isoformat()
    scheduler_state.save(state)
    return ran


def main(argv: list[str]) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    jobs = build_jobs()

    if "--once" in argv:
        print(tick(jobs))
        return 0

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log.info("Scheduler started with %d jobs", len(jobs))
    while not stopping:
        tick(jobs)
        for _ in range(TICK_SECONDS):
            if stopping:
                break
            time.sleep(1)
    log.info("Scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
