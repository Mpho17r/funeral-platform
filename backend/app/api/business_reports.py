"""Reports for a general business: profit and loss, sales by customer,
tax charged, and a spreadsheet download. Cash basis: money counts when it
is received or paid; invoices are shown alongside."""

import csv
import io
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.expense import Expense
from app.models.income import IncomeEntry
from app.models.sales import Customer, SalePayment, SalesDocument
from app.services.finance_books import money

router = APIRouter(prefix="/business-reports", tags=["Business reports"])

ZERO = Decimal("0.00")


def _range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = date.today()
    start = date_from or today.replace(day=1)
    end = date_to or today
    if start > end:
        raise HTTPException(422, "The start date is after the end date")
    if (end - start).days > 800:
        raise HTTPException(422, "Choose a range of about two years or less")
    return start, end


def _month_key(d: date) -> str:
    return d.replace(day=1).isoformat()


def build(db: Session, business_id: UUID, start: date, end: date) -> dict:
    income_rows = (
        db.query(IncomeEntry.income_date, IncomeEntry.category, IncomeEntry.amount)
        .filter(
            IncomeEntry.business_id == business_id,
            IncomeEntry.status == "recorded",
            IncomeEntry.income_date >= start,
            IncomeEntry.income_date <= end,
        )
        .all()
    )
    expense_rows = (
        db.query(Expense.expense_date, Expense.category, Expense.amount)
        .filter(
            Expense.business_id == business_id,
            Expense.status == "recorded",
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .all()
    )

    months: dict[str, dict] = {}
    income_by: dict[str, Decimal] = {}
    expense_by: dict[str, Decimal] = {}

    def month(d: date) -> dict:
        return months.setdefault(
            _month_key(d), {"month": _month_key(d), "income": ZERO, "expenses": ZERO}
        )

    for d, cat, amount in income_rows:
        month(d)["income"] += money(amount)
        income_by[cat] = income_by.get(cat, ZERO) + money(amount)
    for d, cat, amount in expense_rows:
        month(d)["expenses"] += money(amount)
        expense_by[cat] = expense_by.get(cat, ZERO) + money(amount)

    income = sum(income_by.values(), ZERO)
    spent = sum(expense_by.values(), ZERO)

    # ------- sales (invoices issued in the range, and what was paid)
    invoices = (
        db.query(SalesDocument)
        .filter(
            SalesDocument.business_id == business_id,
            SalesDocument.document_type == "invoice",
            SalesDocument.status == "issued",
            SalesDocument.issue_date >= start,
            SalesDocument.issue_date <= end,
        )
        .all()
    )
    invoiced = sum((money(i.total) for i in invoices), ZERO)
    tax_charged = sum((money(i.tax) for i in invoices), ZERO)

    paid_rows = (
        db.query(SalePayment.invoice_id, func.sum(SalePayment.amount))
        .join(SalesDocument, SalesDocument.id == SalePayment.invoice_id)
        .filter(
            SalePayment.business_id == business_id,
            SalePayment.status == "recorded",
            SalePayment.paid_on >= start,
            SalePayment.paid_on <= end,
        )
        .group_by(SalePayment.invoice_id)
        .all()
    )
    paid_by_invoice = {i: money(v) for i, v in paid_rows}
    collected = sum(paid_by_invoice.values(), ZERO)

    owner_of = {
        i: c
        for i, c in db.query(SalesDocument.id, SalesDocument.customer_id).filter(
            SalesDocument.id.in_(list(paid_by_invoice) or [None])
        )
    }

    customers: dict[UUID, dict] = {}

    def cust(cid: UUID) -> dict:
        return customers.setdefault(
            cid, {"customer_id": str(cid), "invoiced": ZERO, "paid": ZERO}
        )

    for inv in invoices:
        cust(inv.customer_id)["invoiced"] += money(inv.total)
    for inv_id, amount in paid_by_invoice.items():
        if inv_id in owner_of:
            cust(owner_of[inv_id])["paid"] += amount

    names = {
        c.id: c.name
        for c in db.query(Customer).filter(Customer.id.in_(list(customers) or [None]))
    }
    top = sorted(customers.values(), key=lambda r: -(r["invoiced"] + r["paid"]))
    top_customers = [
        {
            "customer_id": r["customer_id"],
            "customer_name": names.get(UUID(r["customer_id"]), ""),
            "invoiced": float(r["invoiced"]),
            "paid": float(r["paid"]),
        }
        for r in top
    ]

    trend = [
        {
            "month": m["month"],
            "income": float(m["income"]),
            "expenses": float(m["expenses"]),
            "profit": float(m["income"] - m["expenses"]),
        }
        for m in sorted(months.values(), key=lambda m: m["month"])
    ]

    def ranked(values: dict[str, Decimal]) -> list[dict]:
        return sorted(
            ({"category": c, "total": float(v)} for c, v in values.items()),
            key=lambda r: -r["total"],
        )

    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "income": float(income),
        "expenses": float(spent),
        "profit": float(income - spent),
        "result": "profit" if income >= spent else "loss",
        "income_by_category": ranked(income_by),
        "expenses_by_category": ranked(expense_by),
        "trend": trend,
        "sales": {
            "invoices_issued": len(invoices),
            "invoiced": float(invoiced),
            "collected": float(collected),
            "tax_charged": float(tax_charged),
        },
        "top_customers": top_customers,
    }


@router.get("/overview")
def overview(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.view")),
):
    start, end = _range(date_from, date_to)
    return build(db, user["business_id"], start, end)


@router.get("/export")
def export(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.view")),
):
    """A CSV the accountant can open in Excel."""

    start, end = _range(date_from, date_to)
    data = build(db, user["business_id"], start, end)

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Profit and loss", data["date_from"], "to", data["date_to"]])
    w.writerow([])
    w.writerow(["Money received", f'{data["income"]:.2f}'])
    for r in data["income_by_category"]:
        w.writerow(["", r["category"], f'{r["total"]:.2f}'])
    w.writerow(["Money spent", f'{data["expenses"]:.2f}'])
    for r in data["expenses_by_category"]:
        w.writerow(["", r["category"], f'{r["total"]:.2f}'])
    w.writerow([data["result"].capitalize(), f'{data["profit"]:.2f}'])
    w.writerow([])
    w.writerow(["Month", "Received", "Spent", "Profit"])
    for t in data["trend"]:
        w.writerow([t["month"], f'{t["income"]:.2f}', f'{t["expenses"]:.2f}', f'{t["profit"]:.2f}'])
    w.writerow([])
    s = data["sales"]
    w.writerow(["Sales"])
    w.writerow(["Invoices issued", s["invoices_issued"]])
    w.writerow(["Invoiced", f'{s["invoiced"]:.2f}'])
    w.writerow(["Collected", f'{s["collected"]:.2f}'])
    w.writerow(["Tax charged on invoices", f'{s["tax_charged"]:.2f}'])
    w.writerow([])
    w.writerow(["Customer", "Invoiced", "Paid"])
    for c in data["top_customers"]:
        w.writerow([c["customer_name"], f'{c["invoiced"]:.2f}', f'{c["paid"]:.2f}'])

    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="report-{start.isoformat()}-to-{end.isoformat()}.csv"'
            )
        },
    )
