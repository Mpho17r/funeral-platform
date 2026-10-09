
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.financial_document import PaymentReceipt
from app.models.funeral_case import FuneralCase
from app.schemas.case_payment import (
    CasePaymentCreate,
    CasePaymentResponse,
    CasePaymentUpdate,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Payments"],
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
            detail="Invalid business ID",
        )


def recalculate_financials(
    db: Session,
    case_id: UUID,
    business_id: UUID,
):
    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.case_id == case_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    if not financial:
        return None

    # --------------------------------------------------------
    # Calculate total payments
    # --------------------------------------------------------

    payments_total = (
        db.query(CasePayment.amount)
        .filter(
            CasePayment.case_id == case_id,
            CasePayment.business_id == business_id,
        )
        .all()
    )

    amount_paid = sum(
        (amount for (amount,) in payments_total),
        Decimal("0.00"),
    )

    amount_paid = amount_paid.quantize(Decimal("0.01"))

    # --------------------------------------------------------
    # Calculate financial total
    # --------------------------------------------------------

    subtotal = financial.subtotal or Decimal("0.00")
    discount = financial.discount or Decimal("0.00")
    tax = financial.tax or Decimal("0.00")

    total = subtotal - discount + tax

    if total < Decimal("0.00"):
        total = Decimal("0.00")

    total = total.quantize(Decimal("0.01"))

    # --------------------------------------------------------
    # Calculate balance and credit
    # --------------------------------------------------------

    if amount_paid > total:
        balance = Decimal("0.00")
        credit = amount_paid - total

    elif amount_paid == total:
        balance = Decimal("0.00")
        credit = Decimal("0.00")

    else:
        balance = total - amount_paid
        credit = Decimal("0.00")

    balance = balance.quantize(Decimal("0.01"))
    credit = credit.quantize(Decimal("0.01"))

    # --------------------------------------------------------
    # Determine automatic financial status
    # --------------------------------------------------------

    if total == Decimal("0.00") and amount_paid == Decimal("0.00"):
        financial_status = "draft"

    elif amount_paid == Decimal("0.00"):
        financial_status = "unpaid"

    elif amount_paid < total:
        financial_status = "partially_paid"

    elif amount_paid == total:
        financial_status = "paid"

    else:
        financial_status = "overpaid"

    # --------------------------------------------------------
    # Update financial record
    # --------------------------------------------------------

    financial.amount_paid = amount_paid
    financial.total = total
    financial.balance = balance
    financial.credit = credit
    financial.status = financial_status

    return financial


def ensure_no_receipt(db: Session, payment: CasePayment) -> None:
    """A receipted payment is part of the permanent financial record."""

    receipt = (
        db.query(PaymentReceipt.receipt_number)
        .filter(PaymentReceipt.payment_id == payment.id)
        .first()
    )

    if receipt is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Receipt {receipt[0]} has been issued for this "
                f"payment, so it can no longer be changed or deleted"
            ),
        )


def is_duplicate_payment_reference(exc: IntegrityError) -> bool:
    """
    Check whether the IntegrityError was caused by our
    unique payment reference constraint.
    """

    return "uq_case_payments_business_reference" in str(exc.orig)


# ============================================================
# CREATE PAYMENT
# POST /cases/{case_id}/payments
# ============================================================

@router.post(
    "/{case_id}/payments",
    response_model=CasePaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    case_id: UUID,
    payment_data: CasePaymentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("payments.create")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify case belongs to current business
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
            detail="Funeral case not found",
        )

    # --------------------------------------------------------
    # Verify financial record exists
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
            detail="Financial record not found for this case",
        )

    # --------------------------------------------------------
    # Create payment
    # --------------------------------------------------------

    payment = CasePayment(
        business_id=business_id,
        case_id=case_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        reference=payment_data.reference,
        payment_date=payment_data.payment_date,
        notes=payment_data.notes,
    )

    db.add(payment)

    # --------------------------------------------------------
    # Flush so PostgreSQL constraints are checked now
    # --------------------------------------------------------

    try:
        db.flush()

    except IntegrityError as exc:
        db.rollback()

        if is_duplicate_payment_reference(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment reference '{payment_data.reference}' "
                    "already exists for this business"
                ),
            )

        raise

    # --------------------------------------------------------
    # Recalculate financials
    # --------------------------------------------------------

    recalculate_financials(
        db=db,
        case_id=case_id,
        business_id=business_id,
    )

    # --------------------------------------------------------
    # Commit transaction
    # --------------------------------------------------------

    db.commit()

    db.refresh(payment)

    return payment


# ============================================================
# LIST PAYMENTS
# GET /cases/{case_id}/payments
# ============================================================

@router.get(
    "/{case_id}/payments",
    response_model=list[CasePaymentResponse],
)
def list_case_payments(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("payments.view")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify case belongs to current business
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
            detail="Funeral case not found",
        )

    # --------------------------------------------------------
    # Get payments
    # --------------------------------------------------------

    payments = (
        db.query(CasePayment)
        .filter(
            CasePayment.case_id == case_id,
            CasePayment.business_id == business_id,
        )
        .order_by(CasePayment.payment_date.desc())
        .all()
    )

    return payments


# ============================================================
# GET SINGLE PAYMENT
# GET /cases/payments/{payment_id}
# ============================================================

@router.get(
    "/payments/{payment_id}",
    response_model=CasePaymentResponse,
)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("payments.view")),
):
    business_id = get_business_id(current_user)

    payment = (
        db.query(CasePayment)
        .filter(
            CasePayment.id == payment_id,
            CasePayment.business_id == business_id,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return payment


# ============================================================
# UPDATE PAYMENT
# PATCH /cases/payments/{payment_id}
# ============================================================

@router.patch(
    "/payments/{payment_id}",
    response_model=CasePaymentResponse,
)
def update_payment(
    payment_id: UUID,
    payment_data: CasePaymentUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("payments.edit")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Find payment
    # --------------------------------------------------------

    payment = (
        db.query(CasePayment)
        .filter(
            CasePayment.id == payment_id,
            CasePayment.business_id == business_id,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    ensure_no_receipt(db, payment)

    # --------------------------------------------------------
    # Apply updates
    # --------------------------------------------------------

    updates = payment_data.model_dump(
        exclude_unset=True
    )

    for field, value in updates.items():
        setattr(payment, field, value)

    # --------------------------------------------------------
    # Check database constraints
    # --------------------------------------------------------

    try:
        db.flush()

    except IntegrityError as exc:
        db.rollback()

        if is_duplicate_payment_reference(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment reference '{payment.reference}' "
                    "already exists for this business"
                ),
            )

        raise

    # --------------------------------------------------------
    # Recalculate financials
    # --------------------------------------------------------

    recalculate_financials(
        db=db,
        case_id=payment.case_id,
        business_id=business_id,
    )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()

    db.refresh(payment)

    return payment


# ============================================================
# DELETE PAYMENT
# DELETE /cases/payments/{payment_id}
# ============================================================

@router.delete(
    "/payments/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("payments.delete")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Find payment
    # --------------------------------------------------------

    payment = (
        db.query(CasePayment)
        .filter(
            CasePayment.id == payment_id,
            CasePayment.business_id == business_id,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    ensure_no_receipt(db, payment)

    # Save case ID before deletion
    case_id = payment.case_id

    # --------------------------------------------------------
    # Delete payment
    # --------------------------------------------------------

    db.delete(payment)

    db.flush()

    # --------------------------------------------------------
    # Recalculate financials
    # --------------------------------------------------------

    recalculate_financials(
        db=db,
        case_id=case_id,
        business_id=business_id,
    )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()

    return None
