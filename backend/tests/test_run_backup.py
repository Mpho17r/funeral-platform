"""Regression tests for backup naming and status-file safety."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import run_backup


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 7, 20, 0, 0, tzinfo=tz or timezone.utc)


def test_backup_collision_does_not_delete_existing_backup(
    tmp_path, monkeypatch
):
    backup_root = tmp_path / "backups"
    storage_root = tmp_path / "storage"
    backup_root.mkdir()
    storage_root.mkdir()
    (storage_root / "logo.png").write_bytes(b"sample")
    monkeypatch.setattr(run_backup, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(run_backup, "datetime", FixedDateTime)
    monkeypatch.setattr(
        run_backup.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="0123456789abcdef"),
    )
    monkeypatch.setattr(run_backup.shutil, "which", lambda _: "/usr/bin/pg_dump")

    def fake_run(command, **kwargs):
        if command[0] == "pg_dump":
            dump_path = command[command.index("--file") + 1]
            with open(dump_path, "wb") as dump:
                dump.write(b"valid-dump-placeholder")

    monkeypatch.setattr(run_backup.subprocess, "run", fake_run)

    first = run_backup.run_backup(str(backup_root), keep=14)
    assert first["ok"] is True
    existing = backup_root / (
        "funeralos-20261107-200000-01234567"
    )
    assert (existing / "database.dump").is_file()
    assert existing.stat().st_mode & 0o777 == 0o700
    assert backup_root.stat().st_mode & 0o777 == 0o700

    # Force the same generated name again. The failed second attempt must not
    # remove the first successful backup folder.
    second = run_backup.run_backup(str(backup_root), keep=14)
    assert second["ok"] is False
    assert (existing / "database.dump").is_file()
    status = json.loads((backup_root / "status.json").read_text())
    assert status["last_ok_at"] == first["finished_at"]
    assert not list(backup_root.glob(".status-*.tmp"))


def test_interrupted_status_replace_preserves_previous_status(
    tmp_path, monkeypatch
):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    previous_status = {
        "ok": True,
        "last_ok_at": "2026-11-08T00:00:00+00:00",
        "path": "backups/funeralos-previous",
    }
    status_path = backup_root / "status.json"
    status_path.write_text(json.dumps(previous_status))

    # Force the backup attempt to fail before status is written, then simulate
    # an interruption at the atomic replacement step.
    monkeypatch.setattr(run_backup.shutil, "which", lambda _: None)

    def interrupted_replace(source, destination):
        raise OSError("simulated interruption during status replacement")

    monkeypatch.setattr(run_backup.os, "replace", interrupted_replace)

    with pytest.raises(OSError, match="simulated interruption"):
        run_backup.run_backup(str(backup_root), keep=14)

    # The old known-good status remains readable and no temporary file leaks.
    assert json.loads(status_path.read_text()) == previous_status
    assert not list(backup_root.glob(".status-*.tmp"))
