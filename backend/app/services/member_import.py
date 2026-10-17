"""Bring an existing member list (from a spreadsheet) into FuneralOS.

The flow is deliberately two-step: a *check* reads the file and reports,
row by row, what would happen without saving anything; the *import*
saves the rows that passed. Nothing here guesses: a row that is unclear
is reported, not silently fixed.
"""

import csv
import io
import re
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan
from app.schemas.member import MemberCreate


MAX_ROWS = 2000
MAX_BYTES = 2 * 1024 * 1024

# What staff see in the template, and the other names we accept for the
# same column, so a spreadsheet exported from elsewhere still lines up.
COLUMNS = (
    "member_number",
    "first_name",
    "last_name",
    "id_number",
    "date_of_birth",
    "phone",
    "email",
    "address",
    "join_date",
    "status",
    "plan",
    "membership_number",
    "start_date",
    "next_due_date",
)

REQUIRED = ("member_number", "first_name", "last_name")

ALIASES = {
    "member_no": "member_number",
    "member_no.": "member_number",
    "member_num": "member_number",
    "member_#": "member_number",
    "name": "first_name",
    "firstname": "first_name",
    "first": "first_name",
    "surname": "last_name",
    "lastname": "last_name",
    "last": "last_name",
    "id": "id_number",
    "id_no": "id_number",
    "idnumber": "id_number",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "cell": "phone",
    "cellphone": "phone",
    "mobile": "phone",
    "telephone": "phone",
    "e-mail": "email",
    "email_address": "email",
    "physical_address": "address",
    "joined": "join_date",
    "date_joined": "join_date",
    "plan_name": "plan",
    "cover": "plan",
    "policy_number": "membership_number",
    "policy_no": "membership_number",
    "policy": "membership_number",
    "membership_no": "membership_number",
    "policy_start": "start_date",
    "membership_start": "start_date",
    "next_due": "next_due_date",
    "due_date": "next_due_date",
}

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")


class ImportFileError(Exception):
    """The file as a whole cannot be read."""


@dataclass
class RowResult:
    line: int
    values: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    payload: MemberCreate | None = None
    plan_id: UUID | None = None
    membership: dict | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    writer.writerow(
        [
            "M-0001", "Thandi", "Nkosi", "", "1985-03-14",
            "0821234567", "thandi@example.com", "12 Main Road, Soweto",
            "2023-02-01", "active", "Family Plan", "P-0001",
            "2023-02-01", "2026-11-01",
        ]
    )
    return buffer.getvalue()


def _decode(raw: bytes) -> str:
    if len(raw) > MAX_BYTES:
        raise ImportFileError("The file is larger than 2 MB. Split it up.")

    if not raw.strip():
        raise ImportFileError("The file is empty.")

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ImportFileError("The file could not be read as text. Save it as CSV.")


def _header_key(name: str) -> str:
    key = re.sub(r"\s+", "_", (name or "").strip().lower())
    return ALIASES.get(key, key)


def _parse_date(value: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"'{value}' is not a date. Use YYYY-MM-DD or DD/MM/YYYY."
    )


def _next_month(start: date) -> date:
    year = start.year + (1 if start.month == 12 else 0)
    month = 1 if start.month == 12 else start.month + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def read_rows(raw: bytes) -> list[dict]:
    text = _decode(raw)

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]

    if not rows:
        raise ImportFileError("The file has no rows.")

    headers = [_header_key(h) for h in rows[0]]
    missing = [c for c in REQUIRED if c not in headers]

    if missing:
        raise ImportFileError(
            "The first row must be the column names. Missing: "
            + ", ".join(missing)
            + "."
        )

    unknown = [h for h in headers if h and h not in COLUMNS]
    body = rows[1:]

    if not body:
        raise ImportFileError("The file has column names but no members.")

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

    if unknown:
        result[0]["_unknown_columns"] = unknown

    return result


def check_rows(
    db: Session, business_id: UUID, raw_rows: list[dict]
) -> tuple[list[RowResult], list[str]]:
    """Validate every row. Returns the results and any ignored columns."""

    unknown = raw_rows[0].get("_unknown_columns", []) if raw_rows else []

    plans = {
        p.name.strip().lower(): p
        for p in db.query(MembershipPlan).filter(
            MembershipPlan.business_id == business_id
        )
    }
    taken_numbers = {
        n for (n,) in db.query(Member.member_number).filter(
            Member.business_id == business_id
        )
    }
    taken_ids = {
        n for (n,) in db.query(Member.id_number).filter(
            Member.business_id == business_id,
            Member.id_number.isnot(None),
            Member.archived_at.is_(None),
        )
    }
    taken_policies = {
        n for (n,) in db.query(Membership.membership_number).filter(
            Membership.business_id == business_id
        )
    }

    seen_numbers: set[str] = set()
    seen_ids: set[str] = set()
    seen_policies: set[str] = set()
    results: list[RowResult] = []

    for raw in raw_rows:
        line = raw.pop("_line")
        raw.pop("_unknown_columns", None)
        row = RowResult(line=line, values=raw)
        results.append(row)

        def get(name):
            return (raw.get(name) or "").strip()

        for name in REQUIRED:
            if not get(name):
                row.errors.append(f"{name.replace('_', ' ').capitalize()} is empty.")

        data = {}
        for name in (
            "member_number", "first_name", "last_name", "id_number",
            "phone", "email", "address",
        ):
            if get(name):
                data[name] = get(name)

        for name in ("date_of_birth", "join_date"):
            if get(name):
                try:
                    data[name] = _parse_date(get(name))
                except ValueError as error:
                    row.errors.append(f"{name.replace('_', ' ').capitalize()}: {error}")

        if get("status"):
            data["status"] = get("status")

        if not row.errors:
            try:
                row.payload = MemberCreate(**data)
            except ValidationError as error:
                for item in error.errors():
                    where = ".".join(str(p) for p in item["loc"])
                    row.errors.append(
                        f"{where.replace('_', ' ').capitalize()}: "
                        f"{item['msg'].removeprefix('Value error, ')}"
                    )

        number = get("member_number")
        if number:
            if number in taken_numbers:
                row.errors.append(f"Member number {number} already exists.")
            elif number in seen_numbers:
                row.errors.append(f"Member number {number} appears twice in this file.")
            seen_numbers.add(number)

        if row.payload and row.payload.id_number:
            ident = row.payload.id_number
            if ident in taken_ids:
                row.errors.append("A member with this ID number already exists.")
            elif ident in seen_ids:
                row.errors.append("This ID number appears twice in this file.")
            seen_ids.add(ident)

        # Optional policy details: only when a plan is given.
        plan_name = get("plan")
        policy_number = get("membership_number")
        start_raw = get("start_date")
        due_raw = get("next_due_date")

        if plan_name or policy_number or start_raw or due_raw:
            plan = plans.get(plan_name.lower()) if plan_name else None

            if not plan_name:
                row.errors.append("A policy needs a plan name.")
            elif plan is None:
                row.errors.append(f"No plan called '{plan_name}'. Create it first.")
            elif not plan.is_active:
                row.errors.append(f"Plan '{plan.name}' is not active.")

            if not policy_number:
                row.errors.append("A policy needs a membership number.")
            elif policy_number in taken_policies:
                row.errors.append(f"Membership number {policy_number} already exists.")
            elif policy_number in seen_policies:
                row.errors.append(f"Membership number {policy_number} appears twice in this file.")
            seen_policies.add(policy_number)

            start = due = None
            try:
                start = _parse_date(start_raw) if start_raw else (
                    row.payload.join_date if row.payload else None
                )
                if start_raw == "" and start:
                    row.warnings.append("No start date; used the join date.")
            except ValueError as error:
                row.errors.append(f"Start date: {error}")

            try:
                due = _parse_date(due_raw) if due_raw else None
            except ValueError as error:
                row.errors.append(f"Next due date: {error}")

            if start and not due:
                due = _next_month(start)
                row.warnings.append("No next due date; set one month after the start.")

            if plan and start and policy_number:
                row.plan_id = plan.id
                row.membership = {
                    "membership_number": policy_number,
                    "start_date": start,
                    "next_due_date": due,
                }

    return results, unknown
