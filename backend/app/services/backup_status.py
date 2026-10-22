"""What the backup job last did, for the Settings screen."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

# A daily job that is more than a day and a bit overdue needs attention.
STALE_AFTER_HOURS = 26


def status_file() -> Path:
    return Path(settings.backup_dir) / "status.json"


def read() -> dict:
    path = status_file()
    if not path.is_file():
        return {
            "state": "never",
            "message": "No backup has run yet.",
            "last_backup_at": None,
            "age_hours": None,
        }

    try:
        data = json.loads(path.read_text())
        finished = datetime.fromisoformat(data["finished_at"])
        last_ok = data.get("last_ok_at")
        last_ok = datetime.fromisoformat(last_ok) if last_ok else None
    except (ValueError, KeyError, OSError):
        return {
            "state": "unknown",
            "message": "The backup record could not be read.",
            "last_backup_at": None,
            "age_hours": None,
        }

    reference = last_ok
    age = (
        (datetime.now(timezone.utc) - reference).total_seconds() / 3600
        if reference
        else None
    )

    if not data.get("ok"):
        state, message = "failed", "The last backup failed."
    elif age is None or age > STALE_AFTER_HOURS:
        state, message = "stale", "The last backup is out of date."
    else:
        state, message = "ok", "Backups are running."

    return {
        "state": state,
        "message": message,
        "last_backup_at": reference.isoformat() if reference else None,
        "age_hours": round(age, 1) if age is not None else None,
        "size_mb": data.get("size_mb"),
        "error": data.get("error"),
    }
