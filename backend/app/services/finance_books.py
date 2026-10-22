"""Expenses summary and the daily reconciliation position."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case_payment import CasePayment
from app.models.expense import Expense
from app.models.membership_payment import MembershipPayment
from app.models.reconciliation import Reconciliation

ZERO = Decimal("0.00")

EXPENSE_CATEGORIES = (
    "coffins_and_stock",
    "transport_and_fuel",
    "mortuary",
    "staff",
    "venue_and_catering",
    "utilities",
    "maintenance",
    "supplies",
    "marketing",
    "other",
)

LOOKBACK_DAYS = 14


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def receipts_by_method(
    db: Session, business_id: UUID, start: date, end: date
) -> dict[tuple[date, str], Decimal]:
    """Money received per (day, method), cases and memberships together."""
    totals: dict[tuple[date, str], Decimal] = defaultdict(lambda: ZERO)

    for model in (CasePayment, MembershipPayment):
        rows = (
            db.query(
                model.payment_date,
                model.payment_method,
                func.sum(model.amount),
            )
            .filter(
                model.business_id == business_id,
                model.payment_date >= start,
                model.payment_date <= end,
            )
            .group_by(model.payment_date, model.payment_method)
            .all()
        )
        for day, method, total in rows:
            totals[(day, method)] += money(total)

    return totals


def expenses_by_method(
    db: Session, business_id: UUID, start: date, end: date
) -> dict[tuple[date, str], Decimal]:
    totals: dict[tuple[date, str], Decimal] = defaultdict(lambda: ZERO)

    rows = (
        db.query(
            Expense.expense_date,
            Expense.payment_method,
            func.sum(Expense.amount),
        )
        .filter(
            Expense.business_id == business_id,
            Expense.status == "recorded",
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .group_by(Expense.expense_date, Expense.payment_method)
        .all()
    )
    for day, method, total in rows:
        totals[(day, method)] += money(total)

    return totals


def expected_for(
    db: Session, business_id: UUID, day: date, method: str
) -> tuple[Decimal, Decimal, Decimal]:
    """(receipts, expenses, expected) for one day and method."""
    receipts = receipts_by_method(db, business_id, day, day)[(day, method)]
    spent = expenses_by_method(db, business_id, day, day)[(day, method)]
    return receipts, spent, receipts - spent


def serialize_record(record: Reconciliation | None, current_expected):
    if record is None:
        return None

    return {
        "id": str(record.id),
        "counted_amount": float(record.counted_amount),
        "expected_amount": float(record.expected_amount),
        "variance": float(record.variance),
        "notes": record.notes,
        "reconciled_at": record.reconciled_at.isoformat(),
        # The books moved after this was reconciled (a late payment or
        # expense) so the day needs another look.
        "needs_review": money(record.expected_amount)
        != money(current_expected),
    }


def day_position(db: Session, business_id: UUID, day: date) -> dict:
    receipts = receipts_by_method(db, business_id, day, day)
    spent = expenses_by_method(db, business_id, day, day)
    records = {
        r.payment_method: r
        for r in db.query(Reconciliation).filter(
            Reconciliation.business_id == business_id,
            Reconciliation.recon_date == day,
        )
    }

    methods = sorted(
        {m for (d, m) in receipts if d == day}
        | {m for (d, m) in spent if d == day}
        | set(records)
    )

    rows = []
    for method in methods:
        r_in = receipts[(day, method)]
        r_out = spent[(day, method)]
        expected = r_in - r_out
        rows.append(
            {
                "payment_method": method,
                "receipts": float(r_in),
                "expenses": float(r_out),
                "expected": float(expected),
                "record": serialize_record(records.get(method), expected),
            }
        )

    return {"date": day.isoformat(), "methods": rows}


def open_days(db: Session, business_id: UUID, today: date) -> list[dict]:
    """Recent days with money movement that are not fully reconciled."""
    start = today - timedelta(days=LOOKBACK_DAYS)
    receipts = receipts_by_method(db, business_id, start, today)
    spent = expenses_by_method(db, business_id, start, today)
    records = {
        (r.recon_date, r.payment_method): r
        for r in db.query(Reconciliation).filter(
            Reconciliation.business_id == business_id,
            Reconciliation.recon_date >= start,
            Reconciliation.recon_date <= today,
        )
    }

    keys = set(receipts) | set(spent)
    by_day: dict[date, dict] = {}

    for day, method in keys:
        expected = receipts[(day, method)] - spent[(day, method)]
        record = records.get((day, method))
        if record is None:
            state = "open"
        elif money(record.expected_amount) != money(expected):
            state = "needs_review"
        else:
            continue

        entry = by_day.setdefault(
            day, {"date": day.isoformat(), "open": 0, "needs_review": 0,
                  "expected": ZERO}
        )
        entry[state] += 1
        entry["expected"] += expected

    days = sorted(by_day.values(), key=lambda d: d["date"], reverse=True)
    for d in days:
        d["expected"] = float(d["expected"])
    return days


def expense_summary(
    db: Session, business_id: UUID, today: date
) -> dict:
    month_start = today.replace(day=1)

    live = (
        Expense.business_id == business_id,
        Expense.status == "recorded",
    )

    def total(*conditions):
        return money(
            db.query(func.sum(Expense.amount)).filter(*live, *conditions)
            .scalar()
        )

    by_category = (
        db.query(Expense.category, func.sum(Expense.amount))
        .filter(*live, Expense.expense_date >= month_start)
        .group_by(Expense.category)
        .all()
    )

    trend = []
    cursor = month_start
    months = []
    for _ in range(6):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    for start in reversed(months):
        nxt = (start + timedelta(days=32)).replace(day=1)
        trend.append(
            {
                "month": start.isoformat(),
                "total": float(
                    total(Expense.expense_date >= start,
                          Expense.expense_date < nxt)
                ),
            }
        )

    return {
        "today": float(total(Expense.expense_date == today)),
        "month": float(total(Expense.expense_date >= month_start)),
        "by_category": sorted(
            (
                {"category": c, "total": float(money(t))}
                for c, t in by_category
            ),
            key=lambda row: row["total"],
            reverse=True,
        ),
        "trend": trend,
    }
