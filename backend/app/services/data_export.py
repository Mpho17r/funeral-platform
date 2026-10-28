"""
A complete, portable copy of one business's data.

The export is a ZIP of CSV files, one per table, plus a manifest and a
plain-language README. It is built from the database schema itself, so a
table added later is exported automatically. Tables are filtered to the
one business; tables without their own business_id (for example group
members) are reached through the record they belong to.

Never exported: password hashes. Uploaded files are added only when asked.
"""

import csv
import io
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.orm import Session

from app.database import Base

# Columns that must never leave the system.
EXCLUDED_COLUMNS = {"password_hash", "token_hash"}

# Shared reference data, not this business's data.
SKIPPED_TABLES = {"permissions", "role_permissions", "alembic_version"}

# Uploaded files live here, in a folder per business.
FILE_FOLDERS = ("documents", "chat", "branding", "avatars", "task_files")
STORAGE_ROOT = Path("storage")

README = """FuneralOS data export
=====================

Exported: {when}
Business: {business}

What is inside
--------------
- data/        One CSV file per kind of record (open them in Excel).
- files/       Uploaded documents, photos and logos (only if you asked for them).
- manifest.json  How many rows each file holds.

Notes
-----
- Dates and times are in UTC. Amounts are in rands.
- Ids (long codes) link records together, for example case_id on a payment
  points at the id of a funeral case.
- Passwords are never included.
- Keep this file safe: it contains personal information about families and
  members. Delete copies you no longer need.
"""


def _business_filter(table: Table, business_id: UUID, tables: dict, depth=0):
    """A WHERE clause limiting this table to one business, or None."""
    if table.name == "businesses":
        return table.c.id == business_id
    if "business_id" in table.c:
        return table.c.business_id == business_id
    if depth >= 3:
        return None
    # Reach the business through a parent record this table points at.
    for column in table.c:
        for fk in column.foreign_keys:
            parent = fk.column.table
            if parent.name in SKIPPED_TABLES or parent is table:
                continue
            parent_filter = _business_filter(
                parent, business_id, tables, depth + 1
            )
            if parent_filter is not None:
                return column.in_(
                    select(fk.column).where(parent_filter)
                )
    return None


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def build_export(
    db: Session,
    *,
    business_id: UUID,
    business_name: str,
    exported_by: str,
    include_files: bool = False,
):
    """Returns an open temporary file holding the ZIP (position 0)."""
    tables = Base.metadata.tables
    out = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(tables):
            if name in SKIPPED_TABLES:
                continue
            table = tables[name]
            condition = _business_filter(table, business_id, tables)
            if condition is None:
                continue

            columns = [c for c in table.c if c.name not in EXCLUDED_COLUMNS]
            rows = db.execute(select(*columns).where(condition))

            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer)
            writer.writerow([c.name for c in columns])
            total = 0
            for row in rows:
                writer.writerow([_cell(v) for v in row])
                total += 1

            if total == 0:
                continue
            counts[name] = total
            # BOM so Excel reads accents (names) correctly.
            archive.writestr(f"data/{name}.csv", "﻿" + buffer.getvalue())

        file_count = 0
        if include_files:
            for folder in FILE_FOLDERS:
                root = STORAGE_ROOT / folder / str(business_id)
                if not root.is_dir():
                    continue
                for path in sorted(root.rglob("*")):
                    if path.is_file():
                        archive.write(
                            path, f"files/{folder}/{path.relative_to(root)}"
                        )
                        file_count += 1

        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "exported_at": now.isoformat(),
                    "exported_by": exported_by,
                    "business_id": str(business_id),
                    "tables": counts,
                    "files_included": include_files,
                    "file_count": file_count,
                },
                indent=2,
            ),
        )
        archive.writestr(
            "README.txt",
            README.format(
                when=now.strftime("%d %B %Y %H:%M UTC"),
                business=business_name,
            ),
        )

    out.seek(0)
    return out, counts, file_count
