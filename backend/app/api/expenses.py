"""Business expenses: record, correct, and void (never delete)."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.expense import Expense
from app.models.funeral_case import FuneralCase
from app.models.inventory import Supplier
from app.schemas.case_payment import PAYMENT_METHODS
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.finance_books import EXPENSE_CATEGORIES, expense_summary

router = APIRouter(prefix="/expenses", tags=["Expenses"])

AUDITED = (
    "category",
    "description",
    "amount",
    "expense_date",
    "payment_method",
    "reference",
    "notes",
    "case_id",
    "supplier_id",
)


def _validate_category(value):
    if value is not None and value not in EXPENSE_CATEGORIES:
        raise ValueError("Unknown expense category")
    return value


def _validate_method(value):
    if value is not None and value not in PAYMENT_METHODS:
        raise ValueError("Unknown payment method")
    return value


class ExpenseCreate(BaseModel):
    category: str
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    expense_date: date
    payment_method: str = "cash"
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    case_id: UUID | None = None
    supplier_id: UUID | None = None
    branch_id: UUID | None = None

    @field_validator("category")
    @classmethod
    def _category(cls, v):
        return _validate_category(v)

    @field_validator("payment_method")
    @classmethod
    def _method(cls, v):
        return _validate_method(v)


class ExpenseUpdate(BaseModel):
    category: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    amount: Decimal | None = Field(
        default=None, gt=0, decimal_places=2, max_digits=12
    )
    expense_date: date | None = None
    payment_method: str | None = None
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    case_id: UUID | None = None
    supplier_id: UUID | None = None

    @field_validator("category")
    @classmethod
    def _category(cls, v):
        return _validate_category(v)

    @field_validator("payment_method")
    @classmethod
    def _method(cls, v):
        return _validate_method(v)


class VoidRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def _business(current_user: dict) -> UUID:
    return UUID(str(current_user["business_id"]))


def _out(e: Expense, db: Session | None = None) -> dict:
    return {
        "id": str(e.id),
        "category": e.category,
        "description": e.description,
        "amount": float(e.amount),
        "expense_date": e.expense_date.isoformat(),
        "payment_method": e.payment_method,
        "reference": e.reference,
        "notes": e.notes,
        "case_id": str(e.case_id) if e.case_id else None,
        "supplier_id": str(e.supplier_id) if e.supplier_id else None,
        "branch_id": str(e.branch_id) if e.branch_id else None,
        "status": e.status,
        "void_reason": e.void_reason,
        "voided_at": e.voided_at.isoformat() if e.voided_at else None,
        "created_at": e.created_at.isoformat(),
    }


def _check_links(db, business_id, case_id, supplier_id):
    if case_id and not db.query(FuneralCase.id).filter(
        FuneralCase.id == case_id, FuneralCase.business_id == business_id
    ).first():
        raise HTTPException(404, "Funeral case not found")
    if supplier_id and not db.query(Supplier.id).filter(
        Supplier.id == supplier_id, Supplier.business_id == business_id
    ).first():
        raise HTTPException(404, "Supplier not found")


def _get(db, business_id, expense_id) -> Expense:
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.business_id == business_id)
        .first()
    )
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


@router.get("/categories")
def categories(
    current_user: dict = Depends(require_permission("expenses.view")),
):
    return {"categories": list(EXPENSE_CATEGORIES)}


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("expenses.view")),
):
    return expense_summary(db, _business(current_user), date.today())


@router.get("")
def list_expenses(
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
    case_id: UUID | None = None,
    include_voided: bool = False,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("expenses.view")),
):
    business_id = _business(current_user)
    query = db.query(Expense).filter(Expense.business_id == business_id)

    if not include_voided:
        query = query.filter(Expense.status == "recorded")
    if start:
        query = query.filter(Expense.expense_date >= start)
    if end:
        query = query.filter(Expense.expense_date <= end)
    if category:
        query = query.filter(Expense.category == category)
    if case_id:
        query = query.filter(Expense.case_id == case_id)

    total = (
        query.filter(Expense.status == "recorded")
        .with_entities(func.sum(Expense.amount))
        .scalar()
    )
    rows = (
        query.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"total": float(total or 0), "items": [_out(e) for e in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("expenses.manage")),
):
    business_id = _business(current_user)
    _check_links(db, business_id, payload.case_id, payload.supplier_id)

    expense = Expense(
        business_id=business_id,
        created_by=UUID(str(current_user["user_id"])),
        **payload.model_dump(),
    )
    db.add(expense)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="expense.created",
        entity_type="expense",
        entity_id=expense.id,
        details={
            "amount": str(expense.amount),
            "category": expense.category,
            "payment_method": expense.payment_method,
        },
        notes="Expense was recorded.",
    )
    db.commit()
    db.refresh(expense)
    return _out(expense)


@router.get("/{expense_id}")
def get_expense(
    expense_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("expenses.view")),
):
    return _out(_get(db, _business(current_user), expense_id))


@router.patch("/{expense_id}")
def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("expenses.manage")),
):
    business_id = _business(current_user)
    expense = _get(db, business_id, expense_id)

    if expense.status == "voided":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A voided expense cannot be edited"
        )

    changes = payload.model_dump(exclude_unset=True)
    for required in ("category", "description", "amount", "expense_date",
                     "payment_method"):
        if required in changes and changes[required] is None:
            raise HTTPException(422, f"{required} cannot be empty")

    _check_links(
        db, business_id, changes.get("case_id"), changes.get("supplier_id")
    )

    before = snapshot_fields(expense, AUDITED)
    for field, value in changes.items():
        setattr(expense, field, value)
    diff = build_audit_changes(before, snapshot_fields(expense, AUDITED))

    if diff:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="expense.updated",
            entity_type="expense",
            entity_id=expense.id,
            details={"changes": diff},
            notes="Expense was edited.",
        )
    db.commit()
    db.refresh(expense)
    return _out(expense)


@router.post("/{expense_id}/void")
def void_expense(
    expense_id: UUID,
    payload: VoidRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("expenses.manage")),
):
    business_id = _business(current_user)
    expense = _get(db, business_id, expense_id)

    if expense.status == "voided":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This expense is already voided"
        )

    expense.status = "voided"
    expense.void_reason = payload.reason.strip()
    expense.voided_at = datetime.now(timezone.utc)
    expense.voided_by = UUID(str(current_user["user_id"]))

    create_audit_log(
        db,
        business_id=business_id,
        user_id=expense.voided_by,
        action="expense.voided",
        entity_type="expense",
        entity_id=expense.id,
        details={"amount": str(expense.amount), "reason": expense.void_reason},
        notes="Expense was voided.",
    )
    db.commit()
    db.refresh(expense)
    return _out(expense)
