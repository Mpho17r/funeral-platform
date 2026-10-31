"""Money in and out for a general business, and what is left over."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.expense import Expense
from app.models.income import IncomeEntry
from app.services.audit_service import create_audit_log
from app.services.finance_books import (
    GENERAL_EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    money,
)

router = APIRouter(prefix="/money", tags=["Money"])


class IncomeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    income_date: date
    reference: str | None = Field(default=None, max_length=255)
    branch_id: UUID | None = None


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def _out(e: IncomeEntry) -> dict:
    return {
        "id": str(e.id),
        "category": e.category,
        "description": e.description,
        "amount": float(e.amount),
        "income_date": e.income_date.isoformat(),
        "reference": e.reference,
        "status": e.status,
        "void_reason": e.void_reason,
    }


@router.get("/categories")
def categories(user: dict = Depends(require_permission("income.view"))):
    return {
        "income": list(INCOME_CATEGORIES),
        "expenses": list(GENERAL_EXPENSE_CATEGORIES),
    }


@router.get("/income")
def list_income(
    start: date | None = None,
    end: date | None = None,
    include_voided: bool = False,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.view")),
):
    query = db.query(IncomeEntry).filter(IncomeEntry.business_id == user["business_id"])
    if not include_voided:
        query = query.filter(IncomeEntry.status == "recorded")
    if start:
        query = query.filter(IncomeEntry.income_date >= start)
    if end:
        query = query.filter(IncomeEntry.income_date <= end)
    total = (
        query.filter(IncomeEntry.status == "recorded")
        .with_entities(func.sum(IncomeEntry.amount))
        .scalar()
    )
    rows = query.order_by(IncomeEntry.income_date.desc(), IncomeEntry.created_at.desc()).limit(limit).all()
    return {"total": float(total or 0), "items": [_out(e) for e in rows]}


@router.post("/income", status_code=201)
def add_income(
    data: IncomeIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.manage")),
):
    if data.category not in INCOME_CATEGORIES:
        raise HTTPException(422, "Unknown income category")
    entry = IncomeEntry(
        business_id=user["business_id"],
        branch_id=data.branch_id,
        category=data.category,
        description=data.description.strip(),
        amount=data.amount,
        income_date=data.income_date,
        reference=data.reference,
        created_by=user["user_id"],
    )
    db.add(entry)
    db.flush()
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="income.recorded",
        entity_type="income",
        entity_id=entry.id,
        details={"amount": str(entry.amount), "category": entry.category},
        notes="Money received was recorded.",
    )
    db.commit()
    return _out(entry)


@router.post("/income/{entry_id}/void")
def void_income(
    entry_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.manage")),
):
    entry = (
        db.query(IncomeEntry)
        .filter(IncomeEntry.id == entry_id, IncomeEntry.business_id == user["business_id"])
        .first()
    )
    if entry is None:
        raise HTTPException(404, "Entry not found")
    if entry.status == "voided":
        raise HTTPException(409, "This entry is already voided")
    entry.status = "voided"
    entry.void_reason = data.reason.strip()
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="income.voided",
        entity_type="income",
        entity_id=entry.id,
        details={"amount": str(entry.amount), "reason": entry.void_reason},
        notes="Money received was voided.",
    )
    db.commit()
    return _out(entry)


def _month_start(d: date) -> date:
    return d.replace(day=1)


def profit_and_loss(db: Session, business_id: UUID, today: date, months: int = 6) -> dict:
    """Income, expenses and what is left, this month and month by month."""

    def sums(model, date_col, start: date, end: date):
        rows = (
            db.query(model.category, func.sum(model.amount))
            .filter(
                model.business_id == business_id,
                model.status == "recorded",
                date_col >= start,
                date_col < end,
            )
            .group_by(model.category)
            .all()
        )
        return {c: money(v) for c, v in rows}

    starts = []
    cursor = _month_start(today)
    for _ in range(months):
        starts.append(cursor)
        cursor = _month_start(cursor - timedelta(days=1))
    starts.reverse()

    trend = []
    for start in starts:
        end = _month_start(start + timedelta(days=32))
        income = sum(sums(IncomeEntry, IncomeEntry.income_date, start, end).values(), Decimal("0"))
        spent = sum(sums(Expense, Expense.expense_date, start, end).values(), Decimal("0"))
        trend.append({
            "month": start.isoformat(),
            "income": float(income),
            "expenses": float(spent),
            "profit": float(income - spent),
        })

    this = starts[-1]
    end = _month_start(this + timedelta(days=32))
    income_by = sums(IncomeEntry, IncomeEntry.income_date, this, end)
    spent_by = sums(Expense, Expense.expense_date, this, end)
    income = sum(income_by.values(), Decimal("0"))
    spent = sum(spent_by.values(), Decimal("0"))
    return {
        "month": this.isoformat(),
        "income": float(income),
        "expenses": float(spent),
        "profit": float(income - spent),
        "result": "profit" if income >= spent else "loss",
        "income_by_category": sorted(
            ({"category": c, "total": float(v)} for c, v in income_by.items()),
            key=lambda r: -r["total"],
        ),
        "expenses_by_category": sorted(
            ({"category": c, "total": float(v)} for c, v in spent_by.items()),
            key=lambda r: -r["total"],
        ),
        "trend": trend,
    }


@router.get("/summary")
def summary(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.view")),
):
    return profit_and_loss(db, user["business_id"], date.today(), months)
