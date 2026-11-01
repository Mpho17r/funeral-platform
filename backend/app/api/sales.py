"""Customers, quotes, invoices, payments and bills for a general business."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.expense import Expense
from app.models.income import IncomeEntry
from app.models.sales import (
    Customer,
    SalePayment,
    SalesDocument,
    SalesLine,
    SupplierBill,
)
from app.services import sales as calc
from app.services.audit_service import create_audit_log
from app.services.finance_books import GENERAL_EXPENSE_CATEGORIES

router = APIRouter(tags=["Sales"])


# ------------------------------------------------------------ schemas

class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    tax_number: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class CustomerPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    tax_number: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class DocumentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    document_type: str
    lines: list[LineIn] = Field(default_factory=list)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    due_date: date | None = None
    valid_until: date | None = None
    notes: str | None = None


class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None
    lines: list[LineIn] | None = None
    discount: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None
    valid_until: date | None = None
    notes: str | None = None


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class IssueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_date: date | None = None


class PaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    method: str = "cash"
    reference: str | None = Field(default=None, max_length=255)
    paid_on: date | None = None


class BillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=500)
    category: str = "other"
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    bill_date: date
    due_date: date | None = None
    reference: str | None = Field(default=None, max_length=255)


class BillPayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paid_on: date | None = None
    method: str = "eft"


# ------------------------------------------------------------ helpers

def _customer(db: Session, user: dict, customer_id: UUID) -> Customer:
    c = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.business_id == user["business_id"])
        .first()
    )
    if c is None:
        raise HTTPException(404, "Customer not found")
    return c


def _document(db: Session, user: dict, doc_id: UUID) -> SalesDocument:
    d = (
        db.query(SalesDocument)
        .filter(
            SalesDocument.id == doc_id,
            SalesDocument.business_id == user["business_id"],
        )
        .first()
    )
    if d is None:
        raise HTTPException(404, "Document not found")
    return d


def _customer_out(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "address": c.address,
        "tax_number": c.tax_number,
        "notes": c.notes,
        "archived": c.archived_at is not None,
    }


def _payment_out(p: SalePayment) -> dict:
    return {
        "id": str(p.id),
        "amount": float(p.amount),
        "method": p.method,
        "reference": p.reference,
        "paid_on": p.paid_on.isoformat(),
        "status": p.status,
        "void_reason": p.void_reason,
    }


def _doc_out(db: Session, d: SalesDocument, detail: bool = False) -> dict:
    paid = calc.paid_amount(db, d.id) if d.document_type == "invoice" else calc.ZERO
    customer = db.get(Customer, d.customer_id)
    out = {
        "id": str(d.id),
        "customer_id": str(d.customer_id),
        "customer_name": customer.name if customer else "",
        "document_type": d.document_type,
        "status": d.status,
        "number": d.number,
        "issue_date": d.issue_date.isoformat() if d.issue_date else None,
        "due_date": d.due_date.isoformat() if d.due_date else None,
        "valid_until": d.valid_until.isoformat() if d.valid_until else None,
        "subtotal": float(d.subtotal),
        "discount": float(d.discount),
        "tax": float(d.tax),
        "total": float(d.total),
        "notes": d.notes,
        "source_quote_id": str(d.source_quote_id) if d.source_quote_id else None,
        "void_reason": d.void_reason,
        **calc.payment_state(d, paid, date.today()),
    }
    if detail:
        out["lines"] = [
            {
                "id": str(l.id),
                "description": l.description,
                "quantity": float(l.quantity),
                "unit_price": float(l.unit_price),
                "line_total": float(l.line_total),
            }
            for l in d.lines
        ]
        out["payments"] = [
            _payment_out(p)
            for p in db.query(SalePayment)
            .filter(SalePayment.invoice_id == d.id)
            .order_by(SalePayment.paid_on, SalePayment.created_at)
            .all()
        ]
        out["customer"] = _customer_out(customer) if customer else None
    return out


def _set_lines(d: SalesDocument, lines: list[LineIn]) -> None:
    d.lines.clear()
    for i, l in enumerate(lines):
        d.lines.append(
            SalesLine(
                position=i,
                description=l.description.strip(),
                quantity=l.quantity,
                unit_price=l.unit_price,
                line_total=calc.cents(l.quantity * l.unit_price),
            )
        )


def _audit(db, user, action, entity_id, notes, **details):
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action=action,
        entity_type="sales",
        entity_id=entity_id,
        details=details or None,
        notes=notes,
    )


# ---------------------------------------------------------- customers

@router.get("/customers")
def list_customers(
    search: str | None = None,
    include_archived: bool = False,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("customers.view")),
):
    q = db.query(Customer).filter(Customer.business_id == user["business_id"])
    if not include_archived:
        q = q.filter(Customer.archived_at.is_(None))
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.filter(
            or_(Customer.name.ilike(like), Customer.phone.ilike(like), Customer.email.ilike(like))
        )
    total = q.count()
    rows = q.order_by(func.lower(Customer.name)).limit(limit).all()

    owed: dict = {}
    if rows:
        for inv in (
            db.query(SalesDocument)
            .filter(
                SalesDocument.business_id == user["business_id"],
                SalesDocument.document_type == "invoice",
                SalesDocument.status == "issued",
                SalesDocument.customer_id.in_([c.id for c in rows]),
            )
            .all()
        ):
            bal = max(inv.total - calc.paid_amount(db, inv.id), calc.ZERO)
            owed[inv.customer_id] = owed.get(inv.customer_id, calc.ZERO) + bal

    return {
        "total": total,
        "items": [
            {**_customer_out(c), "owes": float(owed.get(c.id, 0))} for c in rows
        ],
    }


@router.post("/customers", status_code=201)
def create_customer(
    data: CustomerIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("customers.manage")),
):
    c = Customer(
        business_id=user["business_id"],
        created_by=user["user_id"],
        **{k: (v.strip() if isinstance(v, str) else v) for k, v in data.model_dump().items()},
    )
    db.add(c)
    db.flush()
    _audit(db, user, "customer.created", c.id, "A customer was added.", name=c.name)
    db.commit()
    return _customer_out(c)


@router.get("/customers/{customer_id}")
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("customers.view")),
):
    c = _customer(db, user, customer_id)
    docs = (
        db.query(SalesDocument)
        .filter(SalesDocument.customer_id == c.id)
        .order_by(SalesDocument.created_at.desc())
        .all()
    )
    items = [_doc_out(db, d) for d in docs]
    owes = sum(i["balance"] for i in items if i["state"] in ("unpaid", "partial"))
    billed = sum(i["total"] for i in items if i["document_type"] == "invoice" and i["status"] == "issued")
    paid = sum(i["paid"] for i in items if i["document_type"] == "invoice" and i["status"] == "issued")
    return {
        **_customer_out(c),
        "owes": owes,
        "billed": billed,
        "paid": paid,
        "documents": items,
    }


@router.patch("/customers/{customer_id}")
def update_customer(
    customer_id: UUID,
    data: CustomerPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("customers.manage")),
):
    c = _customer(db, user, customer_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "name" and not (value or "").strip():
            raise HTTPException(422, "A customer needs a name")
        setattr(c, key, value.strip() if isinstance(value, str) else value)
    _audit(db, user, "customer.updated", c.id, "A customer was changed.")
    db.commit()
    return _customer_out(c)


@router.post("/customers/{customer_id}/archive")
def archive_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("customers.manage")),
):
    from datetime import datetime, timezone

    c = _customer(db, user, customer_id)
    c.archived_at = None if c.archived_at else datetime.now(timezone.utc)
    _audit(db, user, "customer.archived", c.id, "A customer was archived or restored.")
    db.commit()
    return _customer_out(c)


# ---------------------------------------------------------- documents

@router.get("/sales/documents")
def list_documents(
    document_type: str | None = None,
    status: str | None = None,
    customer_id: UUID | None = None,
    state: str | None = Query(None, description="unpaid | partial | paid | overdue"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.view")),
):
    q = db.query(SalesDocument).filter(SalesDocument.business_id == user["business_id"])
    if document_type:
        q = q.filter(SalesDocument.document_type == document_type)
    if status:
        q = q.filter(SalesDocument.status == status)
    if customer_id:
        q = q.filter(SalesDocument.customer_id == customer_id)
    rows = q.order_by(SalesDocument.created_at.desc()).limit(limit).all()
    items = [_doc_out(db, d) for d in rows]
    if state == "overdue":
        items = [i for i in items if i["days_overdue"] > 0]
    elif state:
        items = [i for i in items if i["state"] == state]
    return {"total": len(items), "items": items}


@router.post("/sales/documents", status_code=201)
def create_document(
    data: DocumentIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    if data.document_type not in ("quote", "invoice"):
        raise HTTPException(422, "Document type must be quote or invoice")
    c = _customer(db, user, data.customer_id)
    d = SalesDocument(
        business_id=user["business_id"],
        customer_id=c.id,
        document_type=data.document_type,
        discount=calc.cents(data.discount),
        due_date=data.due_date,
        valid_until=data.valid_until,
        notes=data.notes,
        created_by=user["user_id"],
    )
    _set_lines(d, data.lines)
    calc.recalculate(db, d)
    db.add(d)
    db.flush()
    _audit(db, user, "sales.draft_created", d.id, f"A {d.document_type} draft was made.")
    db.commit()
    db.refresh(d)
    return _doc_out(db, d, detail=True)


@router.get("/sales/documents/{doc_id}")
def get_document(
    doc_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.view")),
):
    return _doc_out(db, _document(db, user, doc_id), detail=True)


@router.patch("/sales/documents/{doc_id}")
def update_document(
    doc_id: UUID,
    data: DocumentPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.status != "draft":
        raise HTTPException(409, "Only a draft can be changed. Void it and start again.")
    fields = data.model_dump(exclude_unset=True)
    if "customer_id" in fields and data.customer_id:
        d.customer_id = _customer(db, user, data.customer_id).id
    if "lines" in fields and data.lines is not None:
        _set_lines(d, data.lines)
    if "discount" in fields and data.discount is not None:
        d.discount = calc.cents(data.discount)
    for key in ("due_date", "valid_until", "notes"):
        if key in fields:
            setattr(d, key, fields[key])
    calc.recalculate(db, d)
    db.commit()
    db.refresh(d)
    return _doc_out(db, d, detail=True)


@router.delete("/sales/documents/{doc_id}", status_code=204)
def delete_draft(
    doc_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.status != "draft":
        raise HTTPException(409, "Only a draft can be deleted. Void it instead.")
    db.delete(d)
    db.commit()


@router.post("/sales/documents/{doc_id}/issue")
def issue_document(
    doc_id: UUID,
    data: IssueIn | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.status != "draft":
        raise HTTPException(409, "This is already issued")
    if not d.lines:
        raise HTTPException(422, "Add at least one line before issuing")
    calc.recalculate(db, d)
    today = date.today()
    d.number = calc.next_number(db, d.business_id, d.document_type)
    d.issue_date = today
    d.status = "issued"
    if d.document_type == "invoice":
        due = (data.due_date if data else None) or d.due_date
        d.due_date = due or calc.default_due_date(today)
    _audit(db, user, "sales.issued", d.id, f"{d.number} was issued.", total=str(d.total))
    db.commit()
    db.refresh(d)
    return _doc_out(db, d, detail=True)


@router.post("/sales/documents/{doc_id}/accept")
def accept_quote(
    doc_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.document_type != "quote" or d.status != "issued":
        raise HTTPException(409, "Only an issued quote can be accepted")
    d.status = "accepted"
    _audit(db, user, "sales.quote_accepted", d.id, f"{d.number} was accepted.")
    db.commit()
    return _doc_out(db, d, detail=True)


@router.post("/sales/documents/{doc_id}/decline")
def decline_quote(
    doc_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.document_type != "quote" or d.status != "issued":
        raise HTTPException(409, "Only an issued quote can be declined")
    d.status = "declined"
    _audit(db, user, "sales.quote_declined", d.id, f"{d.number} was declined.")
    db.commit()
    return _doc_out(db, d, detail=True)


@router.post("/sales/documents/{doc_id}/convert", status_code=201)
def convert_quote(
    doc_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    q = _document(db, user, doc_id)
    if q.document_type != "quote" or q.status not in ("issued", "accepted"):
        raise HTTPException(409, "Only an issued or accepted quote can become an invoice")
    already = (
        db.query(SalesDocument.id)
        .filter(SalesDocument.source_quote_id == q.id, SalesDocument.status != "void")
        .first()
    )
    if already:
        raise HTTPException(409, "This quote already has an invoice")
    inv = SalesDocument(
        business_id=q.business_id,
        customer_id=q.customer_id,
        document_type="invoice",
        source_quote_id=q.id,
        discount=q.discount,
        notes=q.notes,
        created_by=user["user_id"],
    )
    for i, l in enumerate(q.lines):
        inv.lines.append(
            SalesLine(
                position=i,
                description=l.description,
                quantity=l.quantity,
                unit_price=l.unit_price,
                line_total=l.line_total,
            )
        )
    calc.recalculate(db, inv)
    db.add(inv)
    if q.status == "issued":
        q.status = "accepted"
    db.flush()
    _audit(db, user, "sales.converted", inv.id, f"{q.number} became an invoice draft.")
    db.commit()
    db.refresh(inv)
    return _doc_out(db, inv, detail=True)


@router.post("/sales/documents/{doc_id}/void")
def void_document(
    doc_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.status == "void":
        raise HTTPException(409, "Already voided")
    if d.status == "draft":
        raise HTTPException(409, "A draft is deleted, not voided")
    if d.document_type == "invoice" and calc.paid_amount(db, d.id) > 0:
        raise HTTPException(409, "Cancel the payments on this invoice first")
    d.status = "void"
    d.void_reason = data.reason.strip()
    _audit(db, user, "sales.voided", d.id, f"{d.number} was voided.", reason=d.void_reason)
    db.commit()
    return _doc_out(db, d, detail=True)


# ----------------------------------------------------------- payments

@router.post("/sales/documents/{doc_id}/payments", status_code=201)
def add_payment(
    doc_id: UUID,
    data: PaymentIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    d = _document(db, user, doc_id)
    if d.document_type != "invoice" or d.status != "issued":
        raise HTTPException(409, "Payments go on an issued invoice")
    if data.method not in calc.PAYMENT_METHODS:
        raise HTTPException(422, "Unknown payment method")
    balance = d.total - calc.paid_amount(db, d.id)
    if data.amount > balance:
        raise HTTPException(
            422, f"This is more than the {balance} still owed on the invoice"
        )
    when = data.paid_on or date.today()
    customer = db.get(Customer, d.customer_id)
    income = IncomeEntry(
        business_id=d.business_id,
        category="sales",
        description=f"Payment on {d.number} - {customer.name if customer else ''}"[:500],
        amount=data.amount,
        income_date=when,
        reference=data.reference or d.number,
        created_by=user["user_id"],
    )
    db.add(income)
    db.flush()
    p = SalePayment(
        business_id=d.business_id,
        invoice_id=d.id,
        amount=data.amount,
        method=data.method,
        reference=data.reference,
        paid_on=when,
        income_entry_id=income.id,
        created_by=user["user_id"],
    )
    db.add(p)
    db.flush()
    _audit(db, user, "sales.payment_recorded", d.id, f"A payment was recorded on {d.number}.", amount=str(data.amount))
    db.commit()
    return _doc_out(db, d, detail=True)


@router.post("/sales/payments/{payment_id}/void")
def void_payment(
    payment_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.manage")),
):
    p = (
        db.query(SalePayment)
        .filter(SalePayment.id == payment_id, SalePayment.business_id == user["business_id"])
        .first()
    )
    if p is None:
        raise HTTPException(404, "Payment not found")
    if p.status == "voided":
        raise HTTPException(409, "Already cancelled")
    p.status = "voided"
    p.void_reason = data.reason.strip()
    if p.income_entry_id:
        entry = db.get(IncomeEntry, p.income_entry_id)
        if entry and entry.status == "recorded":
            entry.status = "voided"
            entry.void_reason = f"Payment cancelled: {p.void_reason}"
    d = db.get(SalesDocument, p.invoice_id)
    _audit(db, user, "sales.payment_voided", p.invoice_id, "A payment was cancelled.", reason=p.void_reason)
    db.commit()
    return _doc_out(db, d, detail=True)


# -------------------------------------------------------- receivables

def _bucket(days: int) -> str:
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    return "over_60"


@router.get("/sales/receivables")
def receivables(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("sales.view")),
):
    """Who owes the business money, oldest first, with ageing."""

    today = date.today()
    invoices = (
        db.query(SalesDocument)
        .filter(
            SalesDocument.business_id == user["business_id"],
            SalesDocument.document_type == "invoice",
            SalesDocument.status == "issued",
        )
        .all()
    )
    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "over_60": 0.0}
    items = []
    by_customer: dict = {}
    for inv in invoices:
        out = _doc_out(db, inv)
        if out["balance"] <= 0:
            continue
        buckets[_bucket(out["days_overdue"])] += out["balance"]
        items.append(out)
        row = by_customer.setdefault(
            out["customer_id"],
            {"customer_id": out["customer_id"], "customer_name": out["customer_name"], "owes": 0.0, "overdue": 0.0},
        )
        row["owes"] += out["balance"]
        if out["days_overdue"] > 0:
            row["overdue"] += out["balance"]
    items.sort(key=lambda i: (-i["days_overdue"], i["due_date"] or ""))
    outstanding = sum(buckets.values())
    return {
        "outstanding": outstanding,
        "overdue": outstanding - buckets["current"],
        "buckets": buckets,
        "customers": sorted(by_customer.values(), key=lambda r: -r["owes"]),
        "invoices": items,
    }


# --------------------------------------------------------------- bills

def _bill_out(b: SupplierBill, today: date) -> dict:
    late = (
        (today - b.due_date).days
        if b.status == "unpaid" and b.due_date and b.due_date < today
        else 0
    )
    return {
        "id": str(b.id),
        "supplier_name": b.supplier_name,
        "description": b.description,
        "category": b.category,
        "amount": float(b.amount),
        "bill_date": b.bill_date.isoformat(),
        "due_date": b.due_date.isoformat() if b.due_date else None,
        "reference": b.reference,
        "status": b.status,
        "paid_on": b.paid_on.isoformat() if b.paid_on else None,
        "days_overdue": late,
        "void_reason": b.void_reason,
    }


def _bill(db: Session, user: dict, bill_id: UUID) -> SupplierBill:
    b = (
        db.query(SupplierBill)
        .filter(SupplierBill.id == bill_id, SupplierBill.business_id == user["business_id"])
        .first()
    )
    if b is None:
        raise HTTPException(404, "Bill not found")
    return b


@router.get("/bills")
def list_bills(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bills.view")),
):
    today = date.today()
    q = db.query(SupplierBill).filter(SupplierBill.business_id == user["business_id"])
    if status:
        q = q.filter(SupplierBill.status == status)
    rows = q.order_by(SupplierBill.due_date.asc().nulls_last(), SupplierBill.created_at.desc()).limit(500).all()
    items = [_bill_out(b, today) for b in rows]
    unpaid = [i for i in items if i["status"] == "unpaid"]
    return {
        "total": len(items),
        "owed": sum(i["amount"] for i in unpaid),
        "overdue": sum(i["amount"] for i in unpaid if i["days_overdue"] > 0),
        "items": items,
    }


@router.post("/bills", status_code=201)
def add_bill(
    data: BillIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bills.manage")),
):
    if data.category not in GENERAL_EXPENSE_CATEGORIES:
        raise HTTPException(422, "Unknown category")
    b = SupplierBill(
        business_id=user["business_id"],
        created_by=user["user_id"],
        supplier_name=data.supplier_name.strip(),
        description=data.description.strip(),
        category=data.category,
        amount=data.amount,
        bill_date=data.bill_date,
        due_date=data.due_date,
        reference=data.reference,
    )
    db.add(b)
    db.flush()
    _audit(db, user, "bill.added", b.id, "A supplier bill was added.", amount=str(b.amount))
    db.commit()
    return _bill_out(b, date.today())


@router.post("/bills/{bill_id}/pay")
def pay_bill(
    bill_id: UUID,
    data: BillPayIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bills.manage")),
):
    b = _bill(db, user, bill_id)
    if b.status != "unpaid":
        raise HTTPException(409, "This bill is not waiting to be paid")
    when = data.paid_on or date.today()
    expense = Expense(
        business_id=b.business_id,
        category=b.category,
        description=f"{b.supplier_name}: {b.description}"[:500],
        amount=b.amount,
        expense_date=when,
        payment_method=data.method,
        reference=b.reference,
        created_by=user["user_id"],
    )
    db.add(expense)
    db.flush()
    b.status = "paid"
    b.paid_on = when
    b.expense_id = expense.id
    _audit(db, user, "bill.paid", b.id, "A supplier bill was paid.", amount=str(b.amount))
    db.commit()
    return _bill_out(b, date.today())


@router.post("/bills/{bill_id}/void")
def void_bill(
    bill_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bills.manage")),
):
    b = _bill(db, user, bill_id)
    if b.status == "void":
        raise HTTPException(409, "Already cancelled")
    if b.expense_id:
        expense = db.get(Expense, b.expense_id)
        if expense and expense.status == "recorded":
            expense.status = "voided"
            expense.void_reason = f"Bill cancelled: {data.reason.strip()}"
    b.status = "void"
    b.void_reason = data.reason.strip()
    _audit(db, user, "bill.voided", b.id, "A supplier bill was cancelled.")
    db.commit()
    return _bill_out(b, date.today())
