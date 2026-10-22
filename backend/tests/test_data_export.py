"""Business data export and the backup job."""

import csv
import io
import json
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app.models.audit_log import AuditLog
from app.models.user import User
from tests.test_expenses_reconciliation import add_expense
from tests.test_reports import make_case, make_member


def export(client, auth_headers, user, **params):
    return client.post(
        "/data-export", params=params, headers=auth_headers(user)
    )


def open_zip(response):
    return zipfile.ZipFile(io.BytesIO(response.content))


def rows(archive, name):
    text = archive.read(f"data/{name}.csv").decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_export_contains_this_business_only(
    client, db, test_data, auth_headers
):
    mine = make_case(db, test_data["business_a"])
    theirs = make_case(db, test_data["business_b"])
    make_member(db, test_data["business_a"])
    add_expense(client, auth_headers, test_data["main_admin"])

    response = export(client, auth_headers, test_data["main_admin"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "funeralos-export-" in response.headers["content-disposition"]

    archive = open_zip(response)
    names = archive.namelist()
    assert "README.txt" in names and "manifest.json" in names

    case_numbers = {r["case_number"] for r in rows(archive, "funeral_cases")}
    assert mine.case_number in case_numbers
    assert theirs.case_number not in case_numbers
    assert rows(archive, "expenses")[0]["description"] == "Hearse diesel"
    assert rows(archive, "members")

    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["tables"]["funeral_cases"] == len(case_numbers)
    assert manifest["files_included"] is False


def test_passwords_never_leave(client, db, test_data, auth_headers):
    response = export(client, auth_headers, test_data["main_admin"])
    archive = open_zip(response)

    users = rows(archive, "users")
    assert users and "password_hash" not in users[0]
    hashes = [
        u.password_hash
        for u in db.query(User).filter(
            User.business_id == test_data["business_a"].id
        )
    ]
    blob = b"".join(archive.read(n) for n in archive.namelist())
    assert all(h.encode() not in blob for h in hashes if h)


def test_child_tables_follow_their_parent(
    client, db, test_data, auth_headers
):
    """Tables with no business_id (e.g. chat reactions) are still scoped."""
    archive = open_zip(
        export(client, auth_headers, test_data["main_admin"])
    )
    other_users = {
        str(u.id)
        for u in db.query(User).filter(
            User.business_id == test_data["business_b"].id
        )
    }
    for name in archive.namelist():
        if name.startswith("data/user_permissions"):
            leaked = {r["user_id"] for r in rows(archive, "user_permissions")}
            assert not (leaked & other_users)


def test_only_allowed_people_can_export(
    client, db, test_data, auth_headers
):
    assert export(client, auth_headers, test_data["staff"]).status_code == 403
    assert (
        export(client, auth_headers, test_data["manager"]).status_code == 403
    )
    assert (
        client.get(
            "/data-export/backup-status",
            headers=auth_headers(test_data["staff"]),
        ).status_code
        == 403
    )


def test_export_is_audited(client, db, test_data, auth_headers):
    export(client, auth_headers, test_data["main_admin"])
    entry = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == test_data["business_a"].id,
            AuditLog.action == "data.exported",
        )
        .first()
    )
    assert entry is not None
    assert entry.details["rows"] > 0


def test_uploaded_files_only_when_asked(
    client, db, test_data, auth_headers, tmp_path, monkeypatch
):
    from app.services import data_export

    root = tmp_path / "storage"
    folder = root / "documents" / str(test_data["business_a"].id)
    folder.mkdir(parents=True)
    (folder / "form.txt").write_text("hello")
    other = root / "documents" / str(test_data["business_b"].id)
    other.mkdir(parents=True)
    (other / "secret.txt").write_text("not yours")
    monkeypatch.setattr(data_export, "STORAGE_ROOT", root)

    plain = open_zip(export(client, auth_headers, test_data["main_admin"]))
    assert not [n for n in plain.namelist() if n.startswith("files/")]

    full = open_zip(
        export(
            client, auth_headers, test_data["main_admin"], include_files="true"
        )
    )
    files = [n for n in full.namelist() if n.startswith("files/")]
    assert files == ["files/documents/form.txt"]


# ---------------------------------------------------------------- backups


def test_backup_status_before_and_after(
    client, test_data, auth_headers, tmp_path, monkeypatch
):
    from app.config import settings
    from app.services import backup_status

    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    admin = auth_headers(test_data["main_admin"])

    assert client.get("/data-export/backup-status", headers=admin).json()[
        "state"
    ] == "never"

    def write(**data):
        (tmp_path / "status.json").write_text(json.dumps(data))

    now = datetime.now(timezone.utc)
    write(ok=True, finished_at=now.isoformat(), last_ok_at=now.isoformat())
    assert backup_status.read()["state"] == "ok"

    old = (now - timedelta(hours=40)).isoformat()
    write(ok=True, finished_at=old, last_ok_at=old)
    assert backup_status.read()["state"] == "stale"

    write(ok=False, finished_at=now.isoformat(), last_ok_at=old, error="boom")
    failed = backup_status.read()
    assert failed["state"] == "failed" and failed["error"] == "boom"
    assert failed["age_hours"] > 39


@pytest.mark.skipif(
    shutil.which("pg_dump") is None, reason="needs PostgreSQL client tools"
)
def test_backup_job_writes_a_readable_dump_and_prunes(
    tmp_path, monkeypatch
):
    from app import run_backup

    storage = tmp_path / "storage"
    (storage / "documents").mkdir(parents=True)
    (storage / "documents" / "a.txt").write_text("file")
    monkeypatch.setattr(run_backup, "STORAGE_ROOT", storage)

    backups = tmp_path / "backups"
    first = run_backup.run_backup(str(backups), keep=2)
    assert first["ok"], first["error"]
    assert (backups / "status.json").is_file()

    folder = next(backups.glob("funeralos-*"))
    assert (folder / "database.dump").stat().st_size > 0
    assert (folder / "files.tar.gz").stat().st_size > 0

    # With two older runs added there are three; keep=2 drops the oldest.
    for stamp in ("20200101-000000", "20200102-000000"):
        (backups / f"funeralos-{stamp}").mkdir()
    removed = run_backup.prune(backups, keep=2)
    assert len(list(backups.glob("funeralos-*"))) == 2
    assert removed == ["funeralos-20200101-000000"]
    assert (backups / "funeralos-20200102-000000").is_dir()
    assert folder.is_dir()


def test_failed_backup_is_reported_and_leaves_no_partial_folder(
    tmp_path, monkeypatch
):
    from app import run_backup

    monkeypatch.setattr(run_backup.shutil, "which", lambda name: None)
    result = run_backup.run_backup(str(tmp_path))

    assert result["ok"] is False and "pg_dump" in result["error"]
    assert not list(tmp_path.glob("funeralos-*"))
    assert json.loads((tmp_path / "status.json").read_text())["ok"] is False
