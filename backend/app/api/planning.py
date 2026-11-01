"""Recurring money items and monthly budgets (general businesses)."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.planning import Budget, RecurringItem
from app.services import planning as calc
from app.services.audit_service import create_audit_log
from app.services.finance_books import GENERAL_EXPENSE_CATEGORIES, INCOME_CATEGORIES

router = APIRouter(prefix="/planning", tags=["Planning"])

FREQUENCIES = ("weekly", "monthly", "yearly")


class RecurringIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    category: str
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    frequency: str
    start_date: date
    end_date: date | None = None


class RecurringPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, min_length=1, max_length=500)
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=12)
    active: bool | None = None
    end_date: date | None = None


class BudgetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 0 removes the budget for the category.
    amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)


def _out(i: RecurringItem) -> dict:
    return {
        "id": str(i.id),
        "kind": i.kind,
        "category": i.category,
        "description": i.description,
        "amount": float(i.amount),
        "frequency": i.frequency,
        "next_date": i.next_date.isoformat(),
        "end_date": i.end_date.isoformat() if i.end_date else None,
        "active": i.active,
        "last_recorded_on": i.last_recorded_on.isoformat() if i.last_recorded_on else None,
    }


@router.get("/recurring")
def list_recurring(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.view")),
):
    rows = (
        db.query(RecurringItem)
        .filter(RecurringItem.business_id == user["business_id"])
        .order_by(RecurringItem.active.desc(), RecurringItem.next_date)
        .all()
    )
    return {"total": len(rows), "items": [_out(r) for r in rows]}


@router.post("/recurring", status_code=201)
def add_recurring(
    data: RecurringIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.manage")),
):
    if data.kind not in ("income", "expense"):
        raise HTTPException(422, "Kind must be income or expense")
    allowed = INCOME_CATEGORIES if data.kind == "income" else GENERAL_EXPENSE_CATEGORIES
    if data.category not in allowed:
        raise HTTPException(422, "Unknown category")
    if data.frequency not in FREQUENCIES:
        raise HTTPException(422, "Frequency must be weekly, monthly or yearly")
    if data.end_date and data.end_date < data.start_date:
        raise HTTPException(422, "The end date is before the start date")

    item = RecurringItem(
        business_id=user["business_id"],
        created_by=user["user_id"],
        kind=data.kind,
        category=data.category,
        description=data.description.strip(),
        amount=data.amount,
        frequency=data.frequency,
        next_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(item)
    db.flush()
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="recurring.added",
        entity_type="recurring",
        entity_id=item.id,
        details={"amount": str(item.amount), "frequency": item.frequency},
        notes="A recurring item was added.",
    )
    # Anything already due (a start date in the past) is recorded now.
    calc.record_due(db)
    db.commit()
    db.refresh(item)
    return _out(item)


@router.patch("/recurring/{item_id}")
def change_recurring(
    item_id: UUID,
    data: RecurringPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.manage")),
):
    item = (
        db.query(RecurringItem)
        .filter(RecurringItem.id == item_id, RecurringItem.business_id == user["business_id"])
        .first()
    )
    if item is None:
        raise HTTPException(404, "Recurring item not found")
    # Entries already recorded are never changed; this only affects the future.
    for field in data.model_fields_set:
        setattr(item, field, getattr(data, field))
    db.commit()
    return _out(item)


@router.get("/budgets")
def budgets(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.view")),
):
    return {
        "categories": list(GENERAL_EXPENSE_CATEGORIES),
        "items": calc.budget_status(db, user["business_id"]),
    }


@router.put("/budgets/{category}")
def set_budget(
    category: str,
    data: BudgetIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("income.manage")),
):
    if category not in GENERAL_EXPENSE_CATEGORIES:
        raise HTTPException(422, "Unknown category")
    row = (
        db.query(Budget)
        .filter(Budget.business_id == user["business_id"], Budget.category == category)
        .first()
    )
    if data.amount == 0:
        if row:
            db.delete(row)
    elif row:
        row.amount = data.amount
    else:
        db.add(Budget(business_id=user["business_id"], category=category, amount=data.amount))
    db.commit()
    return {"items": calc.budget_status(db, user["business_id"])}
