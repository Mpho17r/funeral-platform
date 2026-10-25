"""What the scheduler last did, so monitoring can tell it is alive."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings

# The scheduler checks in every half minute; this long without a check-in
# means it has stopped.
STALE_AFTER = timedelta(minutes=10)


def path() -> Path:
    return Path(settings.backup_dir) / "scheduler.json"


def load() -> dict:
    try:
        return json.loads(path().read_text())
    except (OSError, ValueError):
        return {"heartbeat_at": None, "jobs": {}}


def save(state: dict) -> None:
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(target)


def read(now: datetime | None = None) -> dict:
    state = load()
    beat = state.get("heartbeat_at")
    if not beat:
        return {"state": "never", "jobs": state.get("jobs", {})}

    now = now or datetime.now(timezone.utc)
    age = now - datetime.fromisoformat(beat)
    failing = [
        name for name, job in state.get("jobs", {}).items()
        if job.get("ok") is False
    ]

    if age > STALE_AFTER:
        label = "stale"
    elif failing:
        label = "degraded"
    else:
        label = "ok"

    return {
        "state": label,
        "heartbeat_at": beat,
        "failing": failing,
        "jobs": state.get("jobs", {}),
    }
