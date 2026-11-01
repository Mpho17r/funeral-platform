"""Sales quotes and invoices for a general business: totals, numbers,
what has been paid and what is still owed."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sales import SalePayment, SalesDocument
from app.services.tax import automatic_tax

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
PREFIX = {"quote": "QUO", "invoice": "INV"}
DEFAULT_TERMS_DAYS = 30

PAYMENT_METHODS = ("cash", "card", "eft", "mobile", "other")


def cents(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def recalculate(db: Session, doc: SalesDocument) -> None:
    """Totals follow the lines. Tax is automatic when the business has it
    switched on; otherwise there is none."""

    subtotal = sum((cents(l.line_total) for l in doc.lines), ZERO)
    discount = min(cents(doc.discount), subtotal)
    tax = automatic_tax(db, doc.business_id, subtotal, discount)
    doc.subtotal = subtotal
    doc.discount = discount
    doc.tax = ZERO if tax is None else tax
    doc.total = subtotal - discount + doc.tax


def next_number(db: Session, business_id: UUID, kind: str) -> str:
    year = date.today().year
    taken = (
        db.query(func.count(SalesDocument.id))
        .filter(
            SalesDocument.business_id == business_id,
            SalesDocument.document_type == kind,
            SalesDocument.number.isnot(None),
        )
        .scalar()
    )
    n = taken + 1
    while True:
        number = f"{PREFIX[kind]}-{year}-{n:05d}"
        exists = (
            db.query(SalesDocument.id)
            .filter(
                SalesDocument.business_id == business_id,
                SalesDocument.number == number,
            )
            .first()
        )
        if not exists:
            return number
        n += 1


def default_due_date(issued: date) -> date:
    return issued + timedelta(days=DEFAULT_TERMS_DAYS)


def paid_amount(db: Session, invoice_id: UUID) -> Decimal:
    value = (
        db.query(func.sum(SalePayment.amount))
        .filter(
            SalePayment.invoice_id == invoice_id,
            SalePayment.status == "recorded",
        )
        .scalar()
    )
    return cents(value)


def payment_state(doc: SalesDocument, paid: Decimal, today: date) -> dict:
    """Where an invoice stands: unpaid, partial or paid, and how late."""

    balance = max(cents(doc.total) - paid, ZERO)
    if doc.document_type != "invoice" or doc.status != "issued":
        return {"paid": float(paid), "balance": float(balance), "state": None, "days_overdue": 0}

    if balance <= 0:
        state = "paid"
    elif paid > 0:
        state = "partial"
    else:
        state = "unpaid"

    late = 0
    if balance > 0 and doc.due_date and doc.due_date < today:
        late = (today - doc.due_date).days
    return {
        "paid": float(paid),
        "balance": float(balance),
        "state": state,
        "days_overdue": late,
    }
