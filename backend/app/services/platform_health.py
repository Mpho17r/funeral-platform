"""Read-only operational health information for Saccharum platform admins."""

import json

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.services import backup_status, scheduler_state


OFFSITE_STALE_AFTER = timedelta(hours=26)


def _unknown_offsite(message: str) -> dict:
    return {
        "state": "unknown",
        "message": message,
        "enabled": None,
        "last_ok_at": None,
        "finished_at": None,
        "snapshot_id": None,
        "error": None,
        "age_hours": None,
    }


def _offsite_status(now: datetime | None = None) -> dict:
    """Read off-site backup status and detect stale successful backups."""
    path = Path(settings.backup_dir) / "offsite_status.json"

    if not path.is_file():
        return _unknown_offsite(
            "No off-site backup status record exists yet."
        )

    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return _unknown_offsite(
            "The off-site backup record could not be read."
        )

    if not isinstance(data, dict):
        return _unknown_offsite(
            "The off-site backup record has an invalid format."
        )

    result = {
        "enabled": data.get("enabled"),
        "last_ok_at": data.get("last_ok_at"),
        "finished_at": data.get("finished_at"),
        "snapshot_id": data.get("snapshot_id"),
        "error": data.get("error"),
        "age_hours": None,
    }

    if data.get("enabled") is False:
        return {
            **result,
            "state": "disabled",
            "message": "Off-site backups are disabled.",
        }

    # A failed latest attempt must not be masked by an older success.
    if data.get("ok") is False:
        return {
            **result,
            "state": "failed",
            "message": "The latest off-site backup failed.",
        }

    if data.get("ok") is not True:
        return {
            **result,
            "state": "unknown",
            "message": "Off-site backup status is incomplete.",
        }

    last_ok_at = data.get("last_ok_at")
    if not isinstance(last_ok_at, str) or not last_ok_at.strip():
        return {
            **result,
            "state": "unknown",
            "message": "The last successful off-site backup time is missing.",
        }

    try:
        last_success = datetime.fromisoformat(
            last_ok_at.strip().replace("Z", "+00:00")
        )
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=timezone.utc)
        last_success = last_success.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return {
            **result,
            "state": "unknown",
            "message": "The last successful off-site backup time is invalid.",
        }

    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    age = checked_at - last_success

    if age < timedelta(0):
        return {
            **result,
            "state": "unknown",
            "message": "The off-site backup timestamp is in the future.",
        }

    age_hours = round(age.total_seconds() / 3600, 2)
    result["age_hours"] = age_hours

    if age > OFFSITE_STALE_AFTER:
        return {
            **result,
            "state": "stale",
            "message": "The last successful off-site backup is older than 26 hours.",
        }

    return {
        **result,
        "state": "ok",
        "message": "The latest off-site backup succeeded.",
    }


def read() -> dict:
    """Return separate local, remote and scheduler health signals."""
    try:
        local = backup_status.read()
    except Exception:  # noqa: BLE001
        local = {
            "state": "unknown",
            "message": "Local backup status could not be read.",
        }

    try:
        offsite = _offsite_status()
    except Exception:  # noqa: BLE001
        offsite = _unknown_offsite(
            "Off-site backup status could not be read."
        )

    try:
        scheduler = scheduler_state.read()
    except Exception:  # noqa: BLE001
        scheduler = {
            "state": "unknown",
            "heartbeat_at": None,
            "failing": [],
            "jobs": {},
        }

    states = [
        local.get("state"),
        offsite.get("state"),
        scheduler.get("state"),
    ]

    if any(state in ("failed", "stale", "degraded") for state in states):
        overall = "degraded"
    elif any(state in ("unknown", "never") for state in states):
        overall = "unknown"
    elif offsite.get("state") == "disabled":
        overall = "degraded"
    else:
        overall = "ok"

    # Expose operational summaries only. Raw exception messages,
    # internal snapshot identifiers and scheduler job details stay private.
    safe_local = {
        key: local.get(key)
        for key in ("state", "message", "last_backup_at", "age_hours", "size_mb")
        if key in local
    }
    safe_offsite = {
        key: offsite.get(key)
        for key in ("state", "message", "enabled", "last_ok_at",
                    "finished_at", "age_hours")
        if key in offsite
    }

    raw_jobs = scheduler.get("jobs", {})
    safe_jobs = {}
    if isinstance(raw_jobs, dict):
        for name, job in raw_jobs.items():
            if isinstance(job, dict):
                safe_jobs[name] = {
                    "ok": job.get("ok"),
                    "last_run_at": job.get("last_run_at"),
                }

    safe_scheduler = {
        "state": scheduler.get("state", "unknown"),
        "heartbeat_at": scheduler.get("heartbeat_at"),
        "failing": scheduler.get("failing", []),
        "jobs": safe_jobs,
    }

    return {
        "state": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "local_backup": safe_local,
        "offsite_backup": safe_offsite,
        "scheduler": safe_scheduler,
    }
