"""Bring in the people attached to a policy: covered dependents and
beneficiaries. Both are matched to a policy by membership number.

Same two-step shape as the other imports: a check that saves nothing,
then an import of the rows that passed.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.models.covered_dependent import CoveredDependent
from app.models.membership import Membership
from app.models.membership_beneficiary import MembershipBeneficiary
from app.schemas.covered_dependent import (
    COVERED_DEPENDENT_RELATIONSHIPS,
    COVERED_DEPENDENT_STATUSES,
)
from app.services.identity import normalise_identity_number
from app.services.member_import import ImportFileError, _decode, _parse_date

MAX_ROWS = 3000

COLUMNS = {
    "dependents": (
        "membership_number", "first_name", "last_name", "relationship",
        "id_number", "date_of_birth", "phone", "status",
        "cover_start_date", "cover_end_date",
    ),
    "beneficiaries": (
        "membership_number", "first_name", "last_name", "relationship",
        "id_number", "phone", "email", "share_percent", "notes",
    ),
}

REQUIRED = {
    "dependents": ("membership_number", "first_name", "last_name", "relationship"),
    "beneficiaries": (
        "membership_number", "first_name", "last_name", "relationship",
        "share_percent",
    ),
}

ALIASES = {
    "policy_number": "membership_number",
    "policy_no": "membership_number",
    "policy": "membership_number",
    "membership_no": "membership_number",
    "name": "first_name",
    "firstname": "first_name",
    "surname": "last_name",
    "lastname": "last_name",
    "relation": "relationship",
    "id": "id_number",
    "id_no": "id_number",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "cell": "phone",
    "mobile": "phone",
    "e-mail": "email",
    "share": "share_percent",
    "percent": "share_percent",
    "percentage": "share_percent",
    "cover_start": "cover_start_date",
    "start_date": "cover_start_date",
    "cover_end": "cover_end_date",
    "end_date": "cover_end_date",
    "note": "notes",
    "comment": "notes",
}

RELATIONSHIP_WORDS = {
    "wife": "spouse", "husband": "spouse", "married": "spouse",
    "son": "child", "daughter": "child", "kid": "child",
    "stepchild": "child", "stepson": "child", "stepdaughter": "child",
    "mother": "parent", "father": "parent", "mom": "parent",
    "mum": "parent", "dad": "parent", "mother-in-law": "parent",
    "father-in-law": "parent",
    "brother": "sibling", "sister": "sibling",
    "grandmother": "grandparent", "grandfather": "grandparent",
    "granny": "grandparent", "gran": "grandparent",
    "grandson": "grandchild", "granddaughter": "grandchild",
    "fiance": "partner", "fiancee": "partner", "girlfriend": "partner",
    "boyfriend": "partner",
}

STATUS_WORDS = {"inactive": "removed", "dead": "deceased", "died": "deceased"}

HUNDRED = Decimal("100")
EMAIL = TypeAdapter(EmailStr)


@dataclass
class PersonRow:
    line: int
    values: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def template_csv(kind: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS[kind])

    if kind == "dependents":
        writer.writerow(
            ["P-0001", "Sipho", "Nkosi", "child", "", "2012-04-09", "",
             "active", "2023-02-01", ""]
        )
    else:
        writer.writerow(
            ["P-0001", "Thandi", "Nkosi", "spouse", "", "0821234567",
             "thandi@example.com", "100", ""]
        )

    return buffer.getvalue()


def _key(name: str) -> str:
    key = re.sub(r"\s+", "_", (name or "").strip().lower())
    return ALIASES.get(key, key)


def read_rows(kind: str, raw: bytes) -> list[dict]:
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
    missing = [c for c in REQUIRED[kind] if c not in headers]

    if missing:
        raise ImportFileError(
            "The first row must be the column names. Missing: "
            + ", ".join(missing)
            + "."
        )

    body = rows[1:]

    if not body:
        raise ImportFileError("The file has column names but no people.")

    if len(body) > MAX_ROWS:
        raise ImportFileError(
            f"The file has {len(body)} rows; the limit is {MAX_ROWS} at a time."
        )

    result = []

    for index, cells in enumerate(body, start=2):
        values = {}
        for column, cell in zip(headers, cells):
            if column in COLUMNS[kind] and column not in values:
                values[column] = cell.strip()
        values["_line"] = index
        result.append(values)

    unknown = [h for h in headers if h and h not in COLUMNS[kind]]
    if unknown:
        result[0]["_unknown_columns"] = unknown

    return result


def _percent(value: str) -> Decimal:
    try:
        number = Decimal(value.replace("%", "").replace(",", ".").strip())
    except InvalidOperation:
        raise ValueError(f"'{value}' is not a percentage.")

    if number <= 0 or number > HUNDRED:
        raise ValueError("The share must be more than 0 and at most 100.")

    return number.quantize(Decimal("0.01"))


def check_rows(
    db: Session, business_id: UUID, kind: str, raw_rows: list[dict]
) -> tuple[list[PersonRow], list[str], list[str]]:
    """Returns (rows, ignored columns, policy-level warnings)."""

    unknown = raw_rows[0].get("_unknown_columns", []) if raw_rows else []

    memberships = {
        m.membership_number: m
        for m in db.query(Membership).filter(
            Membership.business_id == business_id
        )
    }

    if kind == "dependents":
        existing = {
            (d.membership_id, d.first_name.lower(), d.last_name.lower(),
             d.date_of_birth)
            for d in db.query(CoveredDependent).filter(
                CoveredDependent.business_id == business_id
            )
        }
    else:
        existing = set()
        allocated: dict[UUID, Decimal] = {}
        for b in db.query(MembershipBeneficiary).filter(
            MembershipBeneficiary.business_id == business_id,
            MembershipBeneficiary.is_active.is_(True),
        ):
            allocated[b.membership_id] = (
                allocated.get(b.membership_id, Decimal("0"))
                + Decimal(str(b.share_percent))
            )

    seen: set = set()
    touched: dict[UUID, str] = {}
    results: list[PersonRow] = []
    today = date.today()

    for raw in raw_rows:
        line = raw.pop("_line")
        raw.pop("_unknown_columns", None)
        row = PersonRow(line=line, values=raw)
        results.append(row)

        def get(name):
            return (raw.get(name) or "").strip()

        number = get("membership_number")
        membership = memberships.get(number) if number else None

        if not number:
            row.errors.append("Membership number is empty.")
        elif membership is None:
            row.errors.append(
                f"No membership numbered {number}. Import the members first."
            )

        for column in ("first_name", "last_name"):
            if not get(column):
                row.errors.append(
                    f"{column.replace('_', ' ').capitalize()} is empty."
                )
            elif len(get(column)) > 100:
                row.errors.append(
                    f"{column.replace('_', ' ').capitalize()} is too long."
                )

        relationship = get("relationship").lower()
        relationship = RELATIONSHIP_WORDS.get(relationship, relationship)

        if not relationship:
            row.errors.append("Relationship is empty.")
        elif kind == "dependents" and (
            relationship not in COVERED_DEPENDENT_RELATIONSHIPS
        ):
            row.errors.append(
                f"Unknown relationship '{get('relationship')}'. Use: "
                + ", ".join(COVERED_DEPENDENT_RELATIONSHIPS)
                + "."
            )
        elif len(relationship) > 50:
            row.errors.append("Relationship is too long.")

        id_number = None
        try:
            id_number = normalise_identity_number(get("id_number") or None)
        except ValueError as error:
            row.errors.append(f"ID number: {error}")

        if len(get("phone")) > 30:
            row.errors.append("Phone number is too long.")

        data = dict(
            first_name=get("first_name"),
            last_name=get("last_name"),
            relationship=relationship,
            id_number=id_number,
            phone=get("phone") or None,
        )

        if kind == "dependents":
            dob = None
            if get("date_of_birth"):
                try:
                    dob = _parse_date(get("date_of_birth"))
                    if dob > today:
                        row.errors.append("The date of birth is in the future.")
                except ValueError as error:
                    row.errors.append(f"Date of birth: {error}")

            state = get("status").lower()
            state = STATUS_WORDS.get(state, state) or "active"
            if state not in COVERED_DEPENDENT_STATUSES:
                row.errors.append(
                    f"Unknown status '{get('status')}'. Use: "
                    + ", ".join(COVERED_DEPENDENT_STATUSES)
                    + "."
                )

            start = end = None
            if get("cover_start_date"):
                try:
                    start = _parse_date(get("cover_start_date"))
                except ValueError as error:
                    row.errors.append(f"Cover start date: {error}")
            elif membership is not None:
                start = membership.start_date
                row.warnings.append(
                    "No cover start date; used the policy start date."
                )

            if get("cover_end_date"):
                try:
                    end = _parse_date(get("cover_end_date"))
                except ValueError as error:
                    row.errors.append(f"Cover end date: {error}")

            if start and end and end < start:
                row.errors.append("Cover ends before it starts.")

            data.update(
                date_of_birth=dob, status=state,
                cover_start_date=start, cover_end_date=end,
            )

            if membership is not None and row.ok:
                person = (
                    membership.id, data["first_name"].lower(),
                    data["last_name"].lower(), dob,
                )
                if person in existing:
                    row.errors.append(
                        "This person is already covered on this policy."
                    )
                elif person in seen:
                    row.errors.append(
                        "This person appears twice on this policy in the file."
                    )
                seen.add(person)

        else:
            email = None
            if get("email"):
                try:
                    email = str(EMAIL.validate_python(get("email")))
                except ValidationError:
                    row.errors.append(f"'{get('email')}' is not an email address.")

            share = None
            if get("share_percent"):
                try:
                    share = _percent(get("share_percent"))
                except ValueError as error:
                    row.errors.append(f"Share: {error}")
            else:
                row.errors.append("Share is empty.")

            data.update(
                email=email, share_percent=share, notes=get("notes") or None
            )

            if membership is not None and share is not None and row.ok:
                total = allocated.get(membership.id, Decimal("0")) + share

                if total > HUNDRED:
                    row.errors.append(
                        f"Shares on policy {number} would total {total}%, "
                        "which is more than 100%."
                    )
                else:
                    allocated[membership.id] = total
                    touched[membership.id] = number

        if membership is not None:
            data["membership_id"] = membership.id

        if row.ok:
            row.data = data

    policy_notes = []
    if kind == "beneficiaries":
        for membership_id, number in touched.items():
            total = allocated[membership_id]
            if total != HUNDRED:
                policy_notes.append(
                    f"Policy {number}: shares total {total}%. A claim cannot "
                    "be paid until they total 100%."
                )

    return results, unknown, policy_notes
