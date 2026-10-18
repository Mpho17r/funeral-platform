"""Bring in payments already taken under the old system.

Same two-step shape as the member import: a check that saves nothing,
then an import of the rows that passed. Each payment is matched to a
policy by membership number and, when a month is given, applied to that
month's contribution (created if the month does not exist yet) so that
arrears and cover come out right afterwards.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.models.membership_plan import MembershipPlan
from app.schemas.membership_payment import PAYMENT_METHODS
from app.services.member_import import (
    ImportFileError,
    _decode,
    _parse_date,
)


MAX_ROWS = 5000

COLUMNS = (
    "membership_number",
    "payment_date",
    "amount",
    "payment_method",
    "reference",
    "month",
    "notes",
)

REQUIRED = ("membership_number", "payment_date", "amount")

ALIASES = {
    "policy_number": "membership_number",
    "policy_no": "membership_number",
    "policy": "membership_number",
    "membership_no": "membership_number",
    "date": "payment_date",
    "paid_on": "payment_date",
    "date_paid": "payment_date",
    "value": "amount",
    "amount_paid": "amount",
    "method": "payment_method",
    "type": "payment_method",
    "ref": "reference",
    "receipt": "reference",
    "receipt_no": "reference",
    "period": "month",
    "contribution_month": "month",
    "for_month": "month",
    "note": "notes",
    "comment": "notes",
}

METHOD_WORDS = {
    "debit order": "debit_order",
    "debit-order": "debit_order",
    "debitorder": "debit_order",
    "stop order": "debit_order",
    "bank transfer": "eft",
    "transfer": "eft",
    "deposit": "eft",
    "credit card": "card",
    "debit card": "card",
}


@dataclass
class PaymentRow:
    line: int
    values: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    membership_id: UUID | None = None
    plan_amount: Decimal | None = None
    amount: Decimal | None = None
    paid_on: date | None = None
    method: str = "other"
    reference: str | None = None
    notes: str | None = None
    period: date | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def template_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    writer.writerow(
        ["P-0001", "2026-09-28", "150.00", "eft", "RCPT-1001", "2026-10", ""]
    )
    return buffer.getvalue()


def _key(name: str) -> str:
    key = re.sub(r"\s+", "_", (name or "").strip().lower())
    return ALIASES.get(key, key)


def _parse_month(value: str) -> date:
    value = value.strip()

    for fmt in ("%Y-%m", "%m/%Y", "%b %Y", "%B %Y", "%Y/%m"):
        try:
            return datetime.strptime(value, fmt).date().replace(day=1)
        except ValueError:
            continue

    try:
        return _parse_date(value).replace(day=1)
    except ValueError:
        raise ValueError(
            f"'{value}' is not a month. Use YYYY-MM, e.g. 2026-10."
        )


def _parse_amount(value: str) -> Decimal:
    cleaned = re.sub(r"(?i)\b(zar|r)\b", "", value)
    cleaned = cleaned.replace("R", "").replace(" ", "").replace(",", ".")

    # "1.234.50" style: keep only the last separator as the decimal point.
    if cleaned.count(".") > 1:
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail

    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"'{value}' is not an amount.")

    if amount <= 0:
        raise ValueError("The amount must be more than zero.")

    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("The amount can have at most two decimal places.")

    return amount


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
        raise ImportFileError("The file has column names but no payments.")

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
) -> tuple[list[PaymentRow], list[str]]:
    unknown = raw_rows[0].get("_unknown_columns", []) if raw_rows else []

    memberships = {
        m.membership_number: (m, plan)
        for m, plan in db.query(Membership, MembershipPlan)
        .join(MembershipPlan, MembershipPlan.id == Membership.plan_id)
        .filter(Membership.business_id == business_id)
    }

    refs = {
        r for (r,) in db.query(MembershipPayment.reference).filter(
            MembershipPayment.business_id == business_id,
            MembershipPayment.reference.isnot(None),
        )
    }
    triples = {
        (mid, d, a)
        for mid, d, a in db.query(
            MembershipPayment.membership_id,
            MembershipPayment.payment_date,
            MembershipPayment.amount,
        ).filter(MembershipPayment.business_id == business_id)
    }

    # What each month already holds, so a row cannot overpay it.
    contributions = {
        (c.membership_id, c.contribution_period): c
        for c in db.query(MembershipContribution).filter(
            MembershipContribution.business_id == business_id
        )
    }
    running: dict[tuple, Decimal] = {}

    seen_refs: set[str] = set()
    seen_triples: set[tuple] = set()
    results: list[PaymentRow] = []

    for raw in raw_rows:
        line = raw.pop("_line")
        raw.pop("_unknown_columns", None)
        row = PaymentRow(line=line, values=raw)
        results.append(row)

        def get(name):
            return (raw.get(name) or "").strip()

        number = get("membership_number")
        found = memberships.get(number) if number else None

        if not number:
            row.errors.append("Membership number is empty.")
        elif found is None:
            row.errors.append(
                f"No membership numbered {number}. Import the members first."
            )
        else:
            row.membership_id = found[0].id
            row.plan_amount = found[1].monthly_contribution

        if get("payment_date"):
            try:
                row.paid_on = _parse_date(get("payment_date"))
                if row.paid_on > date.today():
                    row.errors.append("The payment date is in the future.")
            except ValueError as error:
                row.errors.append(f"Payment date: {error}")
        else:
            row.errors.append("Payment date is empty.")

        if get("amount"):
            try:
                row.amount = _parse_amount(get("amount"))
            except ValueError as error:
                row.errors.append(f"Amount: {error}")
        else:
            row.errors.append("Amount is empty.")

        method = get("payment_method").lower()
        method = METHOD_WORDS.get(method, method).replace(" ", "_")
        if not method:
            row.method = "other"
            row.warnings.append("No payment method; recorded as 'other'.")
        elif method in PAYMENT_METHODS:
            row.method = method
        else:
            row.method = "other"
            row.warnings.append(
                f"Unknown payment method '{get('payment_method')}'; "
                "recorded as 'other'."
            )

        row.reference = get("reference") or None
        row.notes = get("notes") or None

        if get("month"):
            try:
                row.period = _parse_month(get("month"))
            except ValueError as error:
                row.errors.append(f"Month: {error}")
        else:
            row.warnings.append(
                "No month given; the payment is recorded but not applied "
                "to any month, so it will not clear arrears."
            )

        if row.reference:
            if row.reference in refs:
                row.errors.append(
                    f"Reference {row.reference} is already recorded."
                )
            elif row.reference in seen_refs:
                row.errors.append(
                    f"Reference {row.reference} appears twice in this file."
                )
            seen_refs.add(row.reference)
        elif row.membership_id and row.paid_on and row.amount:
            triple = (row.membership_id, row.paid_on, row.amount)
            if triple in triples:
                row.errors.append(
                    "A payment of this amount on this date is already "
                    "recorded. Add a reference if it is a different payment."
                )
            elif triple in seen_triples:
                row.errors.append(
                    "The same payment appears twice. Add a reference to "
                    "tell them apart."
                )
            seen_triples.add(triple)

        # Would this overpay the month?
        if row.ok and row.period and row.membership_id and row.amount:
            slot = (row.membership_id, row.period)
            existing = contributions.get(slot)
            due = existing.amount_due if existing else row.plan_amount
            paid = running.get(
                slot, existing.amount_paid if existing else Decimal("0.00")
            )

            if paid + row.amount > due:
                row.errors.append(
                    f"This would overpay {row.period:%Y-%m}: {due} due, "
                    f"{paid} already paid. Leave the month blank or "
                    "correct the amount."
                )
            else:
                running[slot] = paid + row.amount

    return results, unknown
