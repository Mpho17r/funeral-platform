"""Encrypted off-site backup upload using Restic and S3-compatible storage.

This module is deliberately independent of run_backup.py: a cloud outage must
never invalidate a successful local backup. Credentials are read only from the
scheduler process environment and are never written to status files or logs.
"""

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKUP_ROOT = Path(os.getenv("BACKUP_DIR", "backups"))
TAG = "linda-production"
HOST = "linda-production"


def _enabled() -> bool:
    return os.getenv("OFFSITE_BACKUP_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _required_environment() -> dict[str, str]:
    names = (
        "RESTIC_REPOSITORY",
        "RESTIC_PASSWORD",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
    )
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Off-site backup is enabled but required settings are missing: "
            + ", ".join(missing)
        )
    env = dict(os.environ)
    env["RESTIC_CACHE_DIR"] = env.get("RESTIC_CACHE_DIR", "/tmp/restic-cache")
    return env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["restic", *args],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_status(root: Path, result: dict) -> None:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    status_path = root / "offsite_status.json"
    previous = {}
    try:
        previous = json.loads(status_path.read_text())
    except (OSError, ValueError):
        pass

    if result.get("ok"):
        result["last_ok_at"] = result["finished_at"]
    else:
        result["last_ok_at"] = previous.get("last_ok_at")

    temporary = root / f".offsite-status-{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(result, indent=2))
        temporary.chmod(0o600)
        os.replace(temporary, status_path)
    finally:
        temporary.unlink(missing_ok=True)


def run_offsite_backup(backup_path: str | Path) -> dict:
    """Upload one completed local backup folder and apply remote retention.

    Returns a separate off-site result. It never raises for an upload failure,
    so callers can preserve the success state of the local backup.
    """
    if not _enabled():
        return {"enabled": False, "ok": None, "detail": "off-site backup disabled"}

    root = BACKUP_ROOT
    result = {
        "enabled": True,
        "ok": False,
        "path": None,
        "snapshot_id": None,
        "error": None,
    }

    try:
        env = _required_environment()
        source = Path(backup_path).resolve(strict=True)
        backup_root = root.resolve(strict=True)
        if source.parent != backup_root or not source.is_dir():
            raise RuntimeError(
                "Refusing off-site upload: source must be a direct backup folder"
            )
        if not source.name.startswith("funeralos-"):
            raise RuntimeError("Refusing off-site upload: unexpected backup folder")

        _run(
            ["backup", "--host", HOST, "--tag", TAG, str(source)],
            env,
        )

        snapshots = json.loads(
            _run(["snapshots", "--json", "--tag", TAG], env).stdout or "[]"
        )
        matching = [
            item for item in snapshots
            if str(source) in item.get("paths", [])
        ]
        if not matching:
            raise RuntimeError(
                "Restic upload returned, but the new snapshot could not be verified"
            )
        latest = max(matching, key=lambda item: item.get("time", ""))
        result["snapshot_id"] = latest.get("short_id") or latest.get("id")

        # Group by host and tag, not source path: every dated local folder has
        # a unique path, but all LINDA production snapshots share one policy.
        _run(
            [
                "forget",
                "--group-by", "host,tags",
                "--keep-daily", "30",
                "--keep-monthly", "12",
                "--prune",
                "--tag", TAG,
            ],
            env,
        )

        result.update(ok=True, path=str(source))
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        result["error"] = detail[:500]
    except Exception as exc:  # noqa: BLE001 - report separately from local backup
        result["error"] = str(exc)[:500]

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    try:
        _write_status(root, result)
    except OSError as exc:
        # Do not raise into the local backup path if the status volume is read-only.
        result["status_write_error"] = str(exc)[:300]
    return result
