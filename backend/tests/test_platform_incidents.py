import json
import stat

from app.config import settings
from app.services import message_delivery, platform_incidents


def healthy_status():
    return {
        "local_backup": {"state": "ok", "message": "Local backup is current."},
        "offsite_backup": {"state": "ok", "message": "Remote backup is current."},
        "scheduler": {"state": "ok", "message": "Scheduler is running."},
    }


def setup_monitor(tmp_path, monkeypatch, health=None):
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(settings, "platform_alert_email", "ops@example.test")
    monkeypatch.setattr(
        message_delivery, "email_configured", lambda: True
    )
    monkeypatch.setattr(
        platform_incidents.platform_health,
        "read",
        lambda: health or healthy_status(),
    )


def test_new_incident_sends_one_alert_and_deduplicates(
    tmp_path, monkeypatch
):
    health = healthy_status()
    health["offsite_backup"] = {
        "state": "failed",
        "message": "Remote backup failed.",
    }
    setup_monitor(tmp_path, monkeypatch, health)

    sent = []
    monkeypatch.setattr(
        message_delivery,
        "send_email",
        lambda to, subject, body: sent.append((to, subject, body)),
    )

    first = platform_incidents.run()
    second = platform_incidents.run()

    assert first["opened"] == 1
    assert first["notifications_sent"] == 1
    assert second["opened"] == 0
    assert second["notifications_sent"] == 0
    assert len(sent) == 1
    assert sent[0][0] == "ops@example.test"

    record = json.loads(
        (tmp_path / "platform_incidents.json").read_text()
    )
    assert record["incidents"]["offsite_backup"]["status"] == "active"
    assert record["incidents"]["offsite_backup"]["notified_at"]


def test_recovery_sends_one_recovery_email(tmp_path, monkeypatch):
    health = healthy_status()
    health["scheduler"] = {
        "state": "stale",
        "message": "Scheduler heartbeat is stale.",
    }
    setup_monitor(tmp_path, monkeypatch, health)

    sent = []
    monkeypatch.setattr(
        message_delivery,
        "send_email",
        lambda to, subject, body: sent.append(subject),
    )

    platform_incidents.run()

    monkeypatch.setattr(
        platform_incidents.platform_health,
        "read",
        healthy_status,
    )

    result = platform_incidents.run()
    again = platform_incidents.run()

    assert result["recovered"] == 1
    assert result["notifications_sent"] == 1
    assert again["notifications_sent"] == 0
    assert len(sent) == 2
    assert "alert" in sent[0].lower()
    assert "recovered" in sent[1].lower()


def test_failed_alert_email_is_retried(tmp_path, monkeypatch):
    health = healthy_status()
    health["local_backup"] = {
        "state": "failed",
        "message": "Local backup failed.",
    }
    setup_monitor(tmp_path, monkeypatch, health)

    attempts = []

    def fail_email(to, subject, body):
        attempts.append(subject)
        raise message_delivery.DeliveryError("SMTP unavailable")

    monkeypatch.setattr(message_delivery, "send_email", fail_email)

    platform_incidents.run()
    record = json.loads(
        (tmp_path / "platform_incidents.json").read_text()
    )
    assert record["incidents"]["local_backup"]["notified_at"] is None

    monkeypatch.setattr(
        message_delivery,
        "send_email",
        lambda to, subject, body: attempts.append(subject),
    )
    result = platform_incidents.run()

    assert result["notifications_sent"] == 1
    assert len(attempts) == 2


def test_missing_recipient_records_incident_without_email(
    tmp_path, monkeypatch
):
    health = healthy_status()
    health["offsite_backup"] = {
        "state": "stale",
        "message": "Remote backup is stale.",
    }
    setup_monitor(tmp_path, monkeypatch, health)
    monkeypatch.setattr(settings, "platform_alert_email", "")

    def unexpected_email(*args, **kwargs):
        raise AssertionError("Email must not be attempted")

    monkeypatch.setattr(message_delivery, "send_email", unexpected_email)

    result = platform_incidents.run()

    assert result["opened"] == 1
    record = json.loads(
        (tmp_path / "platform_incidents.json").read_text()
    )
    assert record["incidents"]["offsite_backup"]["status"] == "active"
    assert record["incidents"]["offsite_backup"]["notified_at"] is None


def test_incident_file_has_restricted_permissions(tmp_path, monkeypatch):
    health = healthy_status()
    health["scheduler"] = {
        "state": "stale",
        "message": "Scheduler heartbeat is stale.",
    }
    setup_monitor(tmp_path, monkeypatch, health)
    monkeypatch.setattr(
        message_delivery,
        "send_email",
        lambda to, subject, body: None,
    )

    platform_incidents.run()

    path = tmp_path / "platform_incidents.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700


def test_recovery_email_not_sent_if_opening_alert_was_not_delivered(
    tmp_path, monkeypatch
):
    health = healthy_status()
    health["scheduler"] = {
        "state": "stale",
        "message": "Scheduler heartbeat is stale.",
    }
    setup_monitor(tmp_path, monkeypatch, health)
    monkeypatch.setattr(settings, "platform_alert_email", "")

    platform_incidents.run()

    monkeypatch.setattr(
        platform_incidents.platform_health,
        "read",
        healthy_status,
    )
    sent = []
    monkeypatch.setattr(
        message_delivery,
        "send_email",
        lambda *args: sent.append(args),
    )

    platform_incidents.run()

    assert sent == []



def test_malformed_incident_records_do_not_crash_monitor(
    tmp_path, monkeypatch
):
    setup_monitor(tmp_path, monkeypatch)
    (tmp_path / "platform_incidents.json").write_text(
        json.dumps({
            "incidents": {
                "local_backup": "not-a-record",
                "unknown_component": {"status": "active"},
                "scheduler": {"status": "invalid"},
            }
        })
    )

    result = platform_incidents.run()

    assert result["active"] == 0
    saved = json.loads(
        (tmp_path / "platform_incidents.json").read_text()
    )
    assert saved["incidents"] == {}


def test_notification_error_does_not_store_raw_exception(
    tmp_path, monkeypatch
):
    health = healthy_status()
    health["local_backup"] = {
        "state": "failed",
        "message": "Local backup failed.",
    }
    setup_monitor(tmp_path, monkeypatch, health)

    def fail_email(to, subject, body):
        raise message_delivery.DeliveryError(
            "private-host.internal connection detail"
        )

    monkeypatch.setattr(message_delivery, "send_email", fail_email)
    platform_incidents.run()

    saved = json.loads(
        (tmp_path / "platform_incidents.json").read_text()
    )
    error = saved["incidents"]["local_backup"]["notification_error"]

    assert "DeliveryError" in error
    assert "notification delivery failed" in error
    assert "private-host.internal" not in error
