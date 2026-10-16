
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)

from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.case_service import CaseService
from app.models.funeral_case import FuneralCase

from app.schemas.case_financial import (
    CaseFinancialCreate,
    CaseFinancialResponse,
    CaseFinancialUpdate,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Financials"],
)


# Fields whose changes are recorded in the audit trail. This includes
# the calculated fields so the history shows how a balance moved.
AUDITED_FINANCIAL_FIELDS = (
    "subtotal",
    "discount",
    "tax",
    "total",
    "amount_paid",
    "balance",
    "credit",
    "status",
    "notes",
)


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User business information is missing",
        )

    try:
        return UUID(str(business_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid business information",
        )


def calculate_status(
    total: Decimal,
    amount_paid: Decimal,
) -> str:
    """
    Determine the automatic financial status.

    draft:
        No financial value and no payment.

    unpaid:
        Total exists but nothing has been paid.

    partially_paid:
        Some payment has been made but the full total
        has not been paid.

    paid:
        Amount paid exactly equals total.

    overpaid:
        Amount paid is greater than total.
    """

    total = total or Decimal("0.00")
    amount_paid = amount_paid or Decimal("0.00")

    total = total.quantize(Decimal("0.01"))
    amount_paid = amount_paid.quantize(Decimal("0.01"))

    if total == Decimal("0.00") and amount_paid == Decimal("0.00"):
        return "draft"

    if amount_paid == Decimal("0.00"):
        return "unpaid"

    if amount_paid < total:
        return "partially_paid"

    if amount_paid == total:
        return "paid"

    return "overpaid"


def calculate_totals(
    subtotal: Decimal,
    discount: Decimal,
    tax: Decimal,
    amount_paid: Decimal,
):
    """
    Calculate financial totals.

    total   = subtotal - discount + tax
    balance = amount still owed
    credit  = amount paid above total
    """

    subtotal = subtotal or Decimal("0.00")
    discount = discount or Decimal("0.00")
    tax = tax or Decimal("0.00")
    amount_paid = amount_paid or Decimal("0.00")

    total = subtotal - discount + tax

    if total < Decimal("0.00"):
        total = Decimal("0.00")

    total = total.quantize(Decimal("0.01"))

    difference = total - amount_paid

    if difference >= Decimal("0.00"):
        balance = difference
        credit = Decimal("0.00")
    else:
        balance = Decimal("0.00")
        credit = abs(difference)

    return (
        total.quantize(Decimal("0.01")),
        balance.quantize(Decimal("0.01")),
        credit.quantize(Decimal("0.01")),
    )


def calculate_payment_total(
    db: Session,
    case_id: UUID,
    business_id: UUID,
) -> Decimal:
    """
    Calculate amount paid from actual payment records.

    Payment records are the source of truth for amount_paid.
    """

    payments = (
        db.query(CasePayment.amount)
        .filter(
            CasePayment.case_id == case_id,
            CasePayment.business_id == business_id,
        )
        .all()
    )

    amount_paid = sum(
        (amount for (amount,) in payments),
        Decimal("0.00"),
    )

    return amount_paid.quantize(Decimal("0.01"))


def recalculate_financial(
    db: Session,
    financial: CaseFinancial,
):
    """
    Recalculate the complete financial record.

    This is the single source of truth for:

    - amount_paid
    - total
    - balance
    - credit
    - status
    """

    # --------------------------------------------------------
    # Get actual payments
    # --------------------------------------------------------

    amount_paid = calculate_payment_total(
        db=db,
        case_id=financial.case_id,
        business_id=financial.business_id,
    )

    # --------------------------------------------------------
    # Calculate total, balance and credit
    # --------------------------------------------------------

    total, balance, credit = calculate_totals(
        financial.subtotal,
        financial.discount,
        financial.tax,
        amount_paid,
    )

    # --------------------------------------------------------
    # Calculate automatic status
    # --------------------------------------------------------

    financial_status = calculate_status(
        total=total,
        amount_paid=amount_paid,
    )

    # --------------------------------------------------------
    # Update financial record
    # --------------------------------------------------------

    financial.amount_paid = amount_paid
    financial.total = total
    financial.balance = balance
    financial.credit = credit
    financial.status = financial_status

    return financial


# ============================================================
# CREATE FINANCIAL RECORD
# POST /cases/{case_id}/financial
# ============================================================

@router.post(
    "/{case_id}/financial",
    response_model=CaseFinancialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_financial(
    case_id: UUID,
    payload: CaseFinancialCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.manage")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify case
    # --------------------------------------------------------

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    # --------------------------------------------------------
    # Check existing financial record
    # --------------------------------------------------------

    existing = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.case_id == case_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Financial record already exists for this case",
        )

    # --------------------------------------------------------
    # Create initial financial record
    # --------------------------------------------------------

    financial = CaseFinancial(
        business_id=business_id,
        case_id=case_id,
        status="draft",
        subtotal=payload.subtotal,
        discount=payload.discount,
        tax=payload.tax,
        total=Decimal("0.00"),
        amount_paid=Decimal("0.00"),
        balance=Decimal("0.00"),
        credit=Decimal("0.00"),
        notes=payload.notes,
    )

    db.add(financial)

    # Flush so the financial object exists in the session.
    db.flush()

    # --------------------------------------------------------
    # Calculate everything from the actual data
    # --------------------------------------------------------

    recalculate_financial(
        db=db,
        financial=financial,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="case.financial_created",
        entity_type="case_financial",
        entity_id=financial.id,
        details={
            "case_id": str(case_id),
            "subtotal": str(financial.subtotal),
            "discount": str(financial.discount),
            "tax": str(financial.tax),
            "total": str(financial.total),
        },
        notes="Case financial record was created.",
    )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()
    db.refresh(financial)

    return financial


# ============================================================
# GET FINANCIAL RECORD FOR CASE
# GET /cases/{case_id}/financial
# ============================================================

@router.get(
    "/{case_id}/financial",
    response_model=CaseFinancialResponse,
)
def get_case_financial(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.view")),
):
    business_id = get_business_id(current_user)

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.case_id == case_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if not financial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial record not found",
        )

    # --------------------------------------------------------
    # Always synchronize financial data
    # --------------------------------------------------------

    recalculate_financial(
        db=db,
        financial=financial,
    )

    db.commit()
    db.refresh(financial)

    return financial


# ============================================================
# GET FINANCIAL RECORD BY ID
# GET /cases/financial/{financial_id}
# ============================================================

@router.get(
    "/financial/{financial_id}",
    response_model=CaseFinancialResponse,
)
def get_financial(
    financial_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.view")),
):
    business_id = get_business_id(current_user)

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.id == financial_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if not financial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial record not found",
        )

    # --------------------------------------------------------
    # Always synchronize financial data
    # --------------------------------------------------------

    recalculate_financial(
        db=db,
        financial=financial,
    )

    db.commit()
    db.refresh(financial)

    return financial


# ============================================================
# UPDATE FINANCIAL RECORD
# PATCH /cases/financial/{financial_id}
# ============================================================

@router.patch(
    "/financial/{financial_id}",
    response_model=CaseFinancialResponse,
)
def update_financial(
    financial_id: UUID,
    payload: CaseFinancialUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.manage")),
):
    business_id = get_business_id(current_user)

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.id == financial_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if not financial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial record not found",
        )

    # --------------------------------------------------------
    # Apply allowed updates
    # --------------------------------------------------------

    updates = payload.model_dump(
        exclude_unset=True,
    )

    # Status and amount_paid are calculated automatically.
    updates.pop("status", None)
    updates.pop("amount_paid", None)
    updates.pop("total", None)
    updates.pop("balance", None)
    updates.pop("credit", None)

    old_values = snapshot_fields(
        financial,
        AUDITED_FINANCIAL_FIELDS,
    )

    for field, value in updates.items():
        setattr(financial, field, value)

    # --------------------------------------------------------
    # Recalculate everything
    # --------------------------------------------------------

    recalculate_financial(
        db=db,
        financial=financial,
    )

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    changes = build_audit_changes(
        old_values,
        snapshot_fields(financial, AUDITED_FINANCIAL_FIELDS),
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="case.financial_updated",
            entity_type="case_financial",
            entity_id=financial.id,
            details={
                "case_id": str(financial.case_id),
                "changes": changes,
            },
            notes="Case financial record was updated.",
        )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()
    db.refresh(financial)

    return financial


# ============================================================
# RECALCULATE FINANCIAL RECORD FROM SERVICES
# POST /cases/{case_id}/financial/recalculate
# ============================================================

@router.post(
    "/{case_id}/financial/recalculate",
    response_model=CaseFinancialResponse,
)
def recalculate_case_financial(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.manage")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify case
    # --------------------------------------------------------

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    # --------------------------------------------------------
    # Get financial record
    # --------------------------------------------------------

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.case_id == case_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if not financial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial record not found",
        )

    # --------------------------------------------------------
    # Calculate subtotal from services
    # --------------------------------------------------------

    services = (
        db.query(CaseService)
        .filter(
            CaseService.case_id == case_id,
            CaseService.business_id == business_id,
        )
        .all()
    )

    subtotal = sum(
        (
            service.total_price or Decimal("0.00")
            for service in services
        ),
        Decimal("0.00"),
    )

    old_values = snapshot_fields(
        financial,
        AUDITED_FINANCIAL_FIELDS,
    )

    financial.subtotal = subtotal.quantize(
        Decimal("0.01")
    )

    # --------------------------------------------------------
    # Recalculate complete financial record
    # --------------------------------------------------------

    recalculate_financial(
        db=db,
        financial=financial,
    )

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    changes = build_audit_changes(
        old_values,
        snapshot_fields(financial, AUDITED_FINANCIAL_FIELDS),
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="case.financial_recalculated",
            entity_type="case_financial",
            entity_id=financial.id,
            details={
                "case_id": str(case_id),
                "changes": changes,
            },
            notes="Case financial record was recalculated from services.",
        )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()
    db.refresh(financial)

    return financial


# ============================================================
# DELETE FINANCIAL RECORD
# DELETE /cases/financial/{financial_id}
# ============================================================

@router.delete(
    "/financial/{financial_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_financial(
    financial_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.manage")),
):
    business_id = get_business_id(current_user)

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.id == financial_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if not financial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial record not found",
        )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="case.financial_deleted",
        entity_type="case_financial",
        entity_id=financial.id,
        details={
            "case_id": str(financial.case_id),
            "total": str(financial.total),
            "amount_paid": str(financial.amount_paid),
            "balance": str(financial.balance),
            "status": financial.status,
        },
        notes="Case financial record was deleted.",
    )

    db.delete(financial)
    db.commit()

    return None
