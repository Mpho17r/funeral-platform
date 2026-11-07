"""Scheduler due-time and retry behaviour."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.run_scheduler import Job, is_due

TZ = ZoneInfo("Africa/Johannesburg")


def test_daily_job_runs_when_nothing_has_run_today():
    job = Job("backup", lambda: "ok", daily_hour=2, window_hours=22)
    now = datetime(2026, 11, 7, 2, 30, tzinfo=TZ)

    assert is_due(job, None, now, TZ)


def test_successful_daily_job_does_not_run_twice():
    job = Job("backup", lambda: "ok", daily_hour=2, window_hours=22)
    last = datetime(2026, 11, 7, 2, 10, tzinfo=TZ)
    now = datetime(2026, 11, 7, 3, 30, tzinfo=TZ)

    assert not is_due(job, last, now, TZ, last_ok=True)


def test_failed_daily_job_waits_before_retrying():
    job = Job("backup", lambda: "ok", daily_hour=2, window_hours=22)
    last = datetime(2026, 11, 7, 2, 10, tzinfo=TZ)
    now = datetime(2026, 11, 7, 2, 45, tzinfo=TZ)

    assert not is_due(job, last, now, TZ, last_ok=False)


def test_failed_daily_job_retries_after_one_hour():
    job = Job("backup", lambda: "ok", daily_hour=2, window_hours=22)
    last = datetime(2026, 11, 7, 2, 10, tzinfo=TZ)
    now = datetime(2026, 11, 7, 3, 10, tzinfo=TZ)

    assert is_due(job, last, now, TZ, last_ok=False)


def test_failed_daily_job_still_runs_on_next_day():
    job = Job("backup", lambda: "ok", daily_hour=2, window_hours=22)
    last = datetime(2026, 11, 6, 2, 10, tzinfo=TZ)
    now = datetime(2026, 11, 7, 2, 5, tzinfo=TZ)

    assert is_due(job, last, now, TZ, last_ok=False)


def test_daily_job_does_not_retry_outside_its_window():
    job = Job("backup", lambda: "ok", daily_hour=2, window_hours=22)
    last = datetime(2026, 11, 7, 23, 10, tzinfo=TZ)
    now = datetime(2026, 11, 8, 0, 10, tzinfo=TZ)

    assert not is_due(job, last, now, TZ, last_ok=False)


def test_interval_jobs_keep_their_existing_retry_interval():
    job = Job("delivery", lambda: "ok", every_minutes=10)
    last = datetime(2026, 11, 7, 2, 10, tzinfo=TZ)

    assert not is_due(
        job, last, datetime(2026, 11, 7, 2, 19, tzinfo=TZ), TZ,
        last_ok=False,
    )
    assert is_due(
        job, last, datetime(2026, 11, 7, 2, 20, tzinfo=TZ), TZ,
        last_ok=False,
    )
