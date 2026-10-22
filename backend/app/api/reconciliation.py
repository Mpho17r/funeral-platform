"""Daily reconciliation: counted money against what the books expect."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.reconciliation import Reconciliation
from app.schemas.case_payment import PAYMENT_METHODS
from app.services.audit_service import create_audit_log
from app.services.notifications import notify, users_with_permission
from app.services.finance_books import (
    day_position,
    expected_for,
    money,
    open_days,
)

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


class ReconcileRequest(BaseModel):
    recon_date: date
    payment_method: str
    counted_amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("payment_method")
    @classmethod
    def method_known(cls, value: str) -> str:
        if value not in PAYMENT_METHODS:
            raise ValueError("Unknown payment method")
        return value


def _business(current_user: dict) -> UUID:
    return UUID(str(current_user["business_id"]))


@router.get("")
def position(
    day: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reconciliation.view")),
):
    business_id = _business(current_user)
    today = date.today()
    chosen = day or today

    return {
        **day_position(db, business_id, chosen),
        "open_days": open_days(db, business_id, today),
    }


@router.get("/history")
def history(
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reconciliation.view")),
):
    rows = (
        db.query(Reconciliation)
        .filter(Reconciliation.business_id == _business(current_user))
        .order_by(
            Reconciliation.recon_date.desc(),
            Reconciliation.payment_method,
        )
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "date": r.recon_date.isoformat(),
                "payment_method": r.payment_method,
                "expected_amount": float(r.expected_amount),
                "counted_amount": float(r.counted_amount),
                "variance": float(r.variance),
                "notes": r.notes,
                "reconciled_at": r.reconciled_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.post("", status_code=status.HTTP_200_OK)
def reconcile(
    payload: ReconcileRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reconciliation.manage")),
):
    business_id = _business(current_user)
    user_id = UUID(str(current_user["user_id"]))

    if payload.recon_date > date.today():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A day cannot be reconciled before it has happened",
        )

    receipts, spent, expected = expected_for(
        db, business_id, payload.recon_date, payload.payment_method
    )
    counted = money(payload.counted_amount)
    variance = counted - expected

    if variance != 0 and not (payload.notes and payload.notes.strip()):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Add a note explaining the difference",
        )

    record = (
        db.query(Reconciliation)
        .filter(
            Reconciliation.business_id == business_id,
            Reconciliation.recon_date == payload.recon_date,
            Reconciliation.payment_method == payload.payment_method,
        )
        .first()
    )

    previous = None
    if record is None:
        record = Reconciliation(
            business_id=business_id,
            recon_date=payload.recon_date,
            payment_method=payload.payment_method,
        )
        db.add(record)
        action = "reconciliation.created"
    else:
        previous = {
            "expected": str(record.expected_amount),
            "counted": str(record.counted_amount),
            "variance": str(record.variance),
        }
        action = "reconciliation.updated"

    record.receipts_total = receipts
    record.expenses_total = spent
    record.expected_amount = expected
    record.counted_amount = counted
    record.variance = variance
    record.notes = payload.notes.strip() if payload.notes else None
    record.reconciled_by = user_id
    record.reconciled_at = datetime.now(timezone.utc)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action=action,
        entity_type="reconciliation",
        entity_id=record.id,
        details={
            "date": payload.recon_date.isoformat(),
            "payment_method": payload.payment_method,
            "expected": str(expected),
            "counted": str(counted),
            "variance": str(variance),
            "previous": previous,
        },
        notes="Day's money was reconciled.",
    )
    if variance != 0:
        notify(
            db,
            business_id=business_id,
            user_ids=users_with_permission(
                db, business_id, "reconciliation.manage"
            ),
            kind="reconciliation_difference",
            title=(
                f"{payload.payment_method.upper()} on "
                f"{payload.recon_date.isoformat()} is "
                f"R {abs(variance):,.2f} "
                f"{'over' if variance > 0 else 'short'}"
            ),
            body=record.notes,
            link="/reconciliation",
            actor_id=user_id,
        )
    db.commit()

    return day_position(db, business_id, payload.recon_date)
