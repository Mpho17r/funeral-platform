"""Subscription usage snapshot cadence remains hourly."""

from app.run_scheduler import build_jobs


def test_usage_snapshot_job_runs_hourly():
    job = next(job for job in build_jobs() if job.name == "usage")
    assert job.every_minutes == 60
