"""Track platform health incidents and notify the Saccharum operator."""

import json
import os
import uuid

from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.services import message_delivery, platform_health


COMPONENTS = {
    "local_backup": "Local backups",
    "offsite_backup": "Off-site backups",
    "scheduler": "Background scheduler",
}


def _path() -> Path:
    return Path(settings.backup_dir) / "platform_incidents.json"


def _load() -> dict:
    try:
        data = json.loads(_path().read_text())
        if isinstance(data, dict) and isinstance(data.get("incidents"), dict):
            # Ignore malformed records so one damaged entry cannot
            # prevent the scheduled monitor from running.
            incidents = {
                key: value
                for key, value in data["incidents"].items()
                if key in COMPONENTS
                and isinstance(value, dict)
                and value.get("status") in {"active", "resolved"}
            }
            return {"incidents": incidents}
    except (OSError, ValueError):
        pass
    return {"incidents": {}}


def _save(data: dict) -> None:
    target = _path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.parent.chmod(0o700)

    temporary = target.parent / f".platform-incidents-{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(data, indent=2))
        temporary.chmod(0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _send(subject: str, body: str) -> None:
    recipient = settings.platform_alert_email.strip()
    if not recipient or not message_delivery.email_configured():
        return

    message_delivery.send_email(recipient, subject, body)


def run() -> dict:
    """Update incidents and send only transition-based notifications."""
    now = datetime.now(timezone.utc).isoformat()
    health = platform_health.read()
    data = _load()
    incidents = data.setdefault("incidents", {})

    opened = 0
    recovered = 0
    notifications_sent = 0

    for key, label in COMPONENTS.items():
        component = health.get(key, {})
        state = component.get("state", "unknown")
        message = component.get("message") or "No additional details available."
        incident = incidents.get(key)

        if state != "ok":
            if not incident or incident.get("status") != "active":
                incident = {
                    "status": "active",
                    "state": state,
                    "opened_at": now,
                    "updated_at": now,
                    "notified_at": None,
                    "recovery_notified_at": None,
                    "notification_error": None,
                }
                incidents[key] = incident
                opened += 1
            else:
                incident["state"] = state
                incident["updated_at"] = now

            if not incident.get("notified_at"):
                try:
                    _send(
                        f"LINDA platform alert: {label}",
                        (
                            f"LINDA operational alert\n\n"
                            f"Component: {label}\n"
                            f"State: {state}\n"
                            f"Details: {message}\n"
                            f"Detected at: {now}\n\n"
                            "This incident remains open until the component recovers."
                        ),
                    )
                    if (
                        settings.platform_alert_email.strip()
                        and message_delivery.email_configured()
                    ):
                        incident["notified_at"] = now
                        incident["notification_error"] = None
                        notifications_sent += 1
                except Exception as exc:  # noqa: BLE001
                    incident["notification_error"] = (
                        f"{type(exc).__name__}: notification delivery failed"
                    )[:300]
        elif incident and incident.get("status") == "active":
            incident["status"] = "resolved"
            incident["resolved_at"] = now
            incident["updated_at"] = now
            recovered += 1

        # A recovery notice is sent only if the opening alert was delivered.
        if (
            incident
            and incident.get("status") == "resolved"
            and incident.get("notified_at")
            and not incident.get("recovery_notified_at")
        ):
            try:
                _send(
                    f"LINDA platform recovered: {label}",
                    (
                        f"LINDA operational recovery\n\n"
                        f"Component: {label}\n"
                        f"Current state: ok\n"
                        f"Recovered at: {now}\n\n"
                        "The incident is now resolved."
                    ),
                )
                if (
                    settings.platform_alert_email.strip()
                    and message_delivery.email_configured()
                ):
                    incident["recovery_notified_at"] = now
                    incident["notification_error"] = None
                    notifications_sent += 1
            except Exception as exc:  # noqa: BLE001
                incident["notification_error"] = (
                    f"{type(exc).__name__}: notification delivery failed"
                )[:300]

    data["updated_at"] = now
    _save(data)

    return {
        "opened": opened,
        "recovered": recovered,
        "notifications_sent": notifications_sent,
        "active": sum(
            1 for item in incidents.values()
            if item.get("status") == "active"
        ),
    }


def read() -> dict:
    """Return a safe incident summary for authenticated platform operators."""
    data = _load()
    incidents = []

    for key, label in COMPONENTS.items():
        record = data["incidents"].get(key)
        if not record:
            continue

        incidents.append({
            "component": key,
            "label": label,
            "status": record.get("status"),
            "state": record.get("state"),
            "opened_at": record.get("opened_at"),
            "updated_at": record.get("updated_at"),
            "resolved_at": record.get("resolved_at"),
            "alert_notified": bool(record.get("notified_at")),
            "recovery_notified": bool(record.get("recovery_notified_at")),
        })

    incidents.sort(
        key=lambda item: (
            item["status"] != "active",
            item["opened_at"] or "",
        ),
        reverse=False,
    )

    return {
        "active": sum(item["status"] == "active" for item in incidents),
        "total": len(incidents),
        "incidents": incidents,
    }
