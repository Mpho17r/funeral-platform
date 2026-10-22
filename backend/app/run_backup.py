"""
Back up FuneralOS: the whole database plus every uploaded file.

Run it by hand or from a scheduler (see docs/BACKUPS_AND_RECOVERY.md):

    python -m app.run_backup

Each run makes a dated folder inside BACKUP_DIR holding
  database.dump   a full PostgreSQL dump (restore with pg_restore)
  files.tar.gz    everything in the storage folder (documents, photos, logos)
checks the dump can be read back, records the result in status.json, and
deletes the oldest backups beyond BACKUP_KEEP. Exit code 0 means success.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import settings

STORAGE_ROOT = Path("storage")
PREFIX = "funeralos-"


def _pg_env():
    url = make_url(settings.database_url)
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    args = [
        "--host", url.host or "localhost",
        "--port", str(url.port or 5432),
        "--username", url.username or "postgres",
    ]
    return url.database, args, env


def _size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


def prune(root: Path, keep: int) -> list[str]:
    """Delete the oldest backup folders beyond `keep`."""
    folders = sorted(
        (p for p in root.iterdir() if p.is_dir() and p.name.startswith(PREFIX)),
        key=lambda p: p.name,
    )
    removed = []
    for old in folders[: max(0, len(folders) - max(1, keep))]:
        shutil.rmtree(old)
        removed.append(old.name)
    return removed


def run_backup(
    backup_dir: str | None = None, keep: int | None = None
) -> dict:
    root = Path(backup_dir or settings.backup_dir)
    root.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    target = root / f"{PREFIX}{started.strftime('%Y%m%d-%H%M%S')}"
    result = {"ok": False, "path": str(target), "error": None}

    try:
        if shutil.which("pg_dump") is None:
            raise RuntimeError(
                "pg_dump was not found. Install the PostgreSQL client tools."
            )

        target.mkdir()
        database, args, env = _pg_env()
        dump = target / "database.dump"

        subprocess.run(
            ["pg_dump", *args, "--format=custom", "--file", str(dump),
             database],
            env=env, check=True, capture_output=True, text=True,
        )
        # A backup that cannot be read back is not a backup.
        subprocess.run(
            ["pg_restore", "--list", str(dump)],
            check=True, capture_output=True, text=True,
        )

        with tarfile.open(target / "files.tar.gz", "w:gz") as tar:
            if STORAGE_ROOT.is_dir():
                tar.add(STORAGE_ROOT, arcname="storage")

        result.update(ok=True, size_mb=_size_mb(target))
        prune(root, keep if keep is not None else settings.backup_keep)
    except subprocess.CalledProcessError as exc:
        result["error"] = (exc.stderr or str(exc)).strip()[:500]
        shutil.rmtree(target, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001 - recorded, then reported
        result["error"] = str(exc)[:500]
        shutil.rmtree(target, ignore_errors=True)

    result["finished_at"] = datetime.now(timezone.utc).isoformat()

    # After a failure, still remember when the last good backup was made.
    if result["ok"]:
        result["last_ok_at"] = result["finished_at"]
    else:
        try:
            before = json.loads((root / "status.json").read_text())
            result["last_ok_at"] = before.get("last_ok_at")
        except (OSError, ValueError):
            result["last_ok_at"] = None

    (root / "status.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    outcome = run_backup()
    if outcome["ok"]:
        print(f"Backup saved to {outcome['path']} ({outcome['size_mb']} MB)")
        sys.exit(0)
    print(f"Backup FAILED: {outcome['error']}", file=sys.stderr)
    sys.exit(1)
