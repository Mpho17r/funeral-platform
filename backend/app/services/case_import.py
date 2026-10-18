"""Bring in funerals already in progress (or recently done) from the old
system, so staff can carry on in FuneralOS without re-typing them.

Same two-step shape as the other imports: check first, save nothing; then
import the rows that passed. Cases are saved as records: no tasks,
documents or invoices are invented for them.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.funeral_case import FuneralCase
from app.models.membership import Membership
from app.services.case_lifecycle import ALLOWED_CASE_STATUSES
from app.services.member_import import ImportFileError, _decode, _parse_date

MAX_ROWS = 2000

COLUMNS = (
    "case_number",
    "deceased_full_name",
    "date_of_birth",
    "date_of_death",
    "funeral_date",
    "funeral_venue",
    "next_of_kin_name",
    "next_of_kin_phone",
    "status",
    "membership_number",
    "notes",
)

REQUIRED = ("case_number", "deceased_full_name")

ALIASES = {
    "case_no": "case_number",
    "case_no.": "case_number",
    "file_number": "case_number",
    "file_no": "case_number",
    "deceased": "deceased_full_name",
    "deceased_name": "deceased_full_name",
    "name": "deceased_full_name",
    "full_name": "deceased_full_name",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "dod": "date_of_death",
    "death_date": "date_of_death",
    "date_died": "date_of_death",
    "burial_date": "funeral_date",
    "service_date": "funeral_date",
    "venue": "funeral_venue",
    "cemetery": "funeral_venue",
    "kin": "next_of_kin_name",
    "next_of_kin": "next_of_kin_name",
    "kin_name": "next_of_kin_name",
    "kin_phone": "next_of_kin_phone",
    "kin_cell": "next_of_kin_phone",
    "contact_phone": "next_of_kin_phone",
    "policy_number": "membership_number",
    "policy_no": "membership_number",
    "membership_no": "membership_number",
    "note": "notes",
    "comment": "notes",
}

STATUS_WORDS = {
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "done": "completed",
    "complete": "completed",
    "finished": "completed",
    "canceled": "cancelled",
}


@dataclass
class CaseRow:
    line: int
    values: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    writer.writerow(
        [
            "C-0001", "Themba Nkosi", "1948-06-02", "2026-10-10",
            "2026-10-18", "Westpark Cemetery", "Thandi Nkosi",
            "0821234567", "confirmed", "P-0001", "Family wants a Saturday",
        ]
    )
    return buffer.getvalue()


def _key(name: str) -> str:
    key = re.sub(r"\s+", "_", (name or "").strip().lower())
    return ALIASES.get(key, key)


def read_rows(raw: bytes) -> list[dict]:
    text = _decode(raw)

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    rows = [
        r for r in csv.reader(io.StringIO(text), dialect)
        if any(c.strip() for c in r)
    ]

    if not rows:
        raise ImportFileError("The file has no rows.")

    headers = [_key(h) for h in rows[0]]
    missing = [c for c in REQUIRED if c not in headers]

    if missing:
        raise ImportFileError(
            "The first row must be the column names. Missing: "
            + ", ".join(missing)
            + "."
        )

    body = rows[1:]

    if not body:
        raise ImportFileError("The file has column names but no cases.")

    if len(body) > MAX_ROWS:
        raise ImportFileError(
            f"The file has {len(body)} rows; the limit is {MAX_ROWS} at a time."
        )

    result = []

    for index, cells in enumerate(body, start=2):
        values = {}
        for column, cell in zip(headers, cells):
            if column in COLUMNS and column not in values:
                values[column] = cell.strip()
        values["_line"] = index
        result.append(values)

    unknown = [h for h in headers if h and h not in COLUMNS]
    if unknown:
        result[0]["_unknown_columns"] = unknown

    return result


def check_rows(
    db: Session, business_id: UUID, raw_rows: list[dict]
) -> tuple[list[CaseRow], list[str]]:
    unknown = raw_rows[0].get("_unknown_columns", []) if raw_rows else []

    taken = {
        n for (n,) in db.query(FuneralCase.case_number).filter(
            FuneralCase.business_id == business_id
        )
    }
    memberships = {
        n: i for n, i in db.query(Membership.membership_number, Membership.id)
        .filter(Membership.business_id == business_id)
    }

    seen: set[str] = set()
    results: list[CaseRow] = []
    today = date.today()

    for raw in raw_rows:
        line = raw.pop("_line")
        raw.pop("_unknown_columns", None)
        row = CaseRow(line=line, values=raw)
        results.append(row)

        def get(name):
            return (raw.get(name) or "").strip()

        number = get("case_number")
        name = get("deceased_full_name")

        if not number:
            row.errors.append("Case number is empty.")
        elif len(number) > 50:
            row.errors.append("Case number is longer than 50 characters.")
        elif number in taken:
            row.errors.append(f"Case number {number} already exists.")
        elif number in seen:
            row.errors.append(f"Case number {number} appears twice in this file.")
        if number:
            seen.add(number)

        if not name:
            row.errors.append("Deceased name is empty.")
        elif len(name) > 200:
            row.errors.append("Deceased name is longer than 200 characters.")

        dates = {}
        for column in ("date_of_birth", "date_of_death", "funeral_date"):
            if get(column):
                try:
                    dates[column] = _parse_date(get(column))
                except ValueError as error:
                    label = column.replace("_", " ").capitalize()
                    row.errors.append(f"{label}: {error}")

        dob = dates.get("date_of_birth")
        dod = dates.get("date_of_death")
        funeral = dates.get("funeral_date")

        if dod and dod > today:
            row.errors.append("The date of death is in the future.")
        if dob and dob > today:
            row.errors.append("The date of birth is in the future.")
        if dob and dod and dob > dod:
            row.errors.append("The date of birth is after the date of death.")
        if dod and funeral and funeral < dod:
            row.errors.append("The funeral date is before the date of death.")

        if not dod:
            row.warnings.append(
                "No date of death; cover will be judged from the funeral "
                "date or today."
            )

        status_value = get("status").lower()
        status_value = STATUS_WORDS.get(status_value, status_value)
        status_value = status_value.replace(" ", "_")

        if not status_value:
            status_value = "open"
        elif status_value not in ALLOWED_CASE_STATUSES:
            row.errors.append(
                f"Unknown status '{get('status')}'. Use: "
                + ", ".join(sorted(ALLOWED_CASE_STATUSES))
                + "."
            )

        membership_id = None
        if get("membership_number"):
            membership_id = memberships.get(get("membership_number"))
            if membership_id is None:
                row.errors.append(
                    f"No membership numbered {get('membership_number')}. "
                    "Import the members first, or leave this blank."
                )

        for column, limit in (
            ("next_of_kin_name", 200),
            ("next_of_kin_phone", 30),
            ("funeral_venue", 255),
        ):
            if len(get(column)) > limit:
                row.errors.append(
                    f"{column.replace('_', ' ').capitalize()} is longer "
                    f"than {limit} characters."
                )

        if row.ok:
            row.data = dict(
                case_number=number,
                deceased_full_name=name,
                date_of_birth=dob,
                date_of_death=dod,
                funeral_date=funeral,
                funeral_venue=get("funeral_venue") or None,
                next_of_kin_name=get("next_of_kin_name") or None,
                next_of_kin_phone=get("next_of_kin_phone") or None,
                status=status_value,
                membership_id=membership_id,
                notes=get("notes") or None,
            )

    return results, unknown
