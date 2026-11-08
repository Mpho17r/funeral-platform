"""Tests for independent encrypted off-site backup handling."""

import json
import subprocess
from pathlib import Path

from app import offsite_backup


def _credentials(monkeypatch):
    monkeypatch.setenv("OFFSITE_BACKUP_ENABLED", "true")
    monkeypatch.setenv("RESTIC_REPOSITORY", "s3:https://example.invalid/bucket/linda")
    monkeypatch.setenv("RESTIC_PASSWORD", "test-only-password")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-004")


def test_offsite_backup_disabled_does_not_call_restic(tmp_path, monkeypatch):
    monkeypatch.setattr(offsite_backup, "BACKUP_ROOT", tmp_path)
    monkeypatch.setenv("OFFSITE_BACKUP_ENABLED", "false")

    def unexpected(*args, **kwargs):
        raise AssertionError("Restic must not run when off-site backup is disabled")

    monkeypatch.setattr(offsite_backup.subprocess, "run", unexpected)
    result = offsite_backup.run_offsite_backup(tmp_path / "missing")

    assert result == {
        "enabled": False,
        "ok": None,
        "detail": "off-site backup disabled",
    }


def test_offsite_backup_verifies_snapshot_and_records_status(tmp_path, monkeypatch):
    _credentials(monkeypatch)
    backup_root = tmp_path / "backups"
    source = backup_root / "funeralos-20261108-020000-abcd1234"
    source.mkdir(parents=True)
    (source / "database.dump").write_bytes(b"dump")
    (source / "files.tar.gz").write_bytes(b"files")
    monkeypatch.setattr(offsite_backup, "BACKUP_ROOT", backup_root)

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "snapshots":
            return subprocess.CompletedProcess(
                command, 0,
                stdout=json.dumps([{
                    "id": "a" * 64,
                    "short_id": "a" * 8,
                    "time": "2026-11-08T02:00:00Z",
                    "paths": [str(source.resolve())],
                }]),
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(offsite_backup.subprocess, "run", fake_run)
    result = offsite_backup.run_offsite_backup(source)

    assert result["ok"] is True
    assert result["snapshot_id"] == "a" * 8
    assert [call[1] for call in calls] == ["backup", "snapshots", "forget"]
    status = json.loads((backup_root / "offsite_status.json").read_text())
    assert status["ok"] is True
    assert status["last_ok_at"] == status["finished_at"]
    assert (backup_root / "offsite_status.json").stat().st_mode & 0o777 == 0o600


def test_offsite_failure_does_not_erase_last_success(tmp_path, monkeypatch):
    _credentials(monkeypatch)
    backup_root = tmp_path / "backups"
    source = backup_root / "funeralos-20261108-020000-abcd1234"
    source.mkdir(parents=True)
    monkeypatch.setattr(offsite_backup, "BACKUP_ROOT", backup_root)
    previous = {
        "ok": True,
        "last_ok_at": "2026-11-07T02:00:00+00:00",
    }
    (backup_root / "offsite_status.json").write_text(json.dumps(previous))

    def failed_run(command, **kwargs):
        raise subprocess.CalledProcessError(
            1, command, stderr="repository unavailable"
        )

    monkeypatch.setattr(offsite_backup.subprocess, "run", failed_run)
    result = offsite_backup.run_offsite_backup(source)

    assert result["ok"] is False
    assert result["last_ok_at"] == previous["last_ok_at"]
    assert "repository unavailable" in result["error"]
