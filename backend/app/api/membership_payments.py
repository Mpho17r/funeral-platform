from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.schemas.membership_payment import (
    MembershipPaymentCreate,
    MembershipPaymentResponse,
    MembershipPaymentUpdate,
)
from app.services.audit_service import create_audit_log
from app.services.membership_status import recalculate_membership_status

router = APIRouter(
    prefix="/membership-payments",
    tags=["Membership Payments"],
)


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business.",
        )

    try:
        return UUID(str(business_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid business ID.",
        )


def get_membership(
    db: Session,
    membership_id: UUID,
    business_id: UUID,
) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    return membership


def get_contribution(
    db: Session,
    contribution_id: UUID,
    membership_id: UUID,
    business_id: UUID,
) -> MembershipContribution:
    contribution = db.scalar(
        select(MembershipContribution).where(
            MembershipContribution.id == contribution_id,
            MembershipContribution.membership_id == membership_id,
            MembershipContribution.business_id == business_id,
        )
    )

    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership contribution not found.",
        )

    return contribution


def recalculate_contribution(
    db: Session,
    contribution: MembershipContribution,
) -> MembershipContribution:
    total_paid = db.scalar(
        select(
            func.coalesce(
                func.sum(MembershipPayment.amount),
                Decimal("0.00"),
            )
        ).where(
            MembershipPayment.contribution_id == contribution.id,
            MembershipPayment.business_id == contribution.business_id,
        )
    )

    total_paid = Decimal(str(total_paid or "0.00"))

    contribution.amount_paid = total_paid

    if total_paid >= contribution.amount_due:
        contribution.status = "paid"
        contribution.paid_at = date.today()
    elif total_paid > Decimal("0.00"):
        contribution.status = "partially_paid"
        contribution.paid_at = None
    else:
        if contribution.due_date < date.today():
            contribution.status = "overdue"
        else:
            contribution.status = "due"

        contribution.paid_at = None

    contribution.updated_at = datetime.now(timezone.utc)

    return contribution


@router.post(
    "",
    response_model=MembershipPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership_payment(
    payload: MembershipPaymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("payments.create")),
):
    business_id = get_business_id(current_user)

    membership = get_membership(
        db,
        payload.membership_id,
        business_id,
    )

    contribution = None

    if payload.contribution_id:
        contribution = get_contribution(
            db,
            payload.contribution_id,
            membership.id,
            business_id,
        )

        existing_paid = db.scalar(
            select(
                func.coalesce(
                    func.sum(MembershipPayment.amount),
                    Decimal("0.00"),
                )
            ).where(
                MembershipPayment.contribution_id == contribution.id,
                MembershipPayment.business_id == business_id,
            )
        )

        existing_paid = Decimal(str(existing_paid or "0.00"))

        new_total = existing_paid + payload.amount

        if new_total > contribution.amount_due:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Payment would exceed the contribution amount due. "
                    f"Amount due: {contribution.amount_due}, "
                    f"already paid: {existing_paid}, "
                    f"payment: {payload.amount}."
                ),
            )

    if payload.reference:
        duplicate = db.scalar(
            select(MembershipPayment).where(
                MembershipPayment.business_id == business_id,
                MembershipPayment.reference == payload.reference,
            )
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A payment with this reference already exists.",
            )

    payment = MembershipPayment(
        business_id=business_id,
        membership_id=membership.id,
        contribution_id=(
            contribution.id
            if contribution
            else None
        ),
        amount=payload.amount,
        payment_method=payload.payment_method,
        reference=payload.reference,
        payment_date=payload.payment_date,
        notes=payload.notes,
    )

    db.add(payment)
    db.flush()

    if contribution:
        recalculate_contribution(
            db,
            contribution,
        )

    recalculate_membership_status(
        db,
        membership,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.payment_created",
        entity_type="membership_payment",
        entity_id=payment.id,
        details={
            "amount": str(payment.amount),
            "payment_method": payment.payment_method,
            "reference": payment.reference,
            "payment_date": payment.payment_date.isoformat(),
            "membership_id": str(payment.membership_id),
            "contribution_id": (
                str(payment.contribution_id)
                if payment.contribution_id
                else None
            ),
        },
        notes="Membership payment created by Main Admin.",
    )

    db.commit()
    db.refresh(payment)

    return payment


@router.get(
    "",
    response_model=list[MembershipPaymentResponse],
)
def list_membership_payments(
    membership_id: UUID | None = None,
    contribution_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("payments.view")),
):
    business_id = get_business_id(current_user)

    query = select(MembershipPayment).where(
        MembershipPayment.business_id == business_id,
    )

    if membership_id:
        query = query.where(
            MembershipPayment.membership_id == membership_id,
        )

    if contribution_id:
        query = query.where(
            MembershipPayment.contribution_id == contribution_id,
        )

    query = query.order_by(
        MembershipPayment.payment_date.desc(),
        MembershipPayment.created_at.desc(),
    )

    return list(db.scalars(query).all())


@router.get(
    "/{payment_id}",
    response_model=MembershipPaymentResponse,
)
def get_membership_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("payments.view")),
):
    business_id = get_business_id(current_user)

    payment = db.scalar(
        select(MembershipPayment).where(
            MembershipPayment.id == payment_id,
            MembershipPayment.business_id == business_id,
        )
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership payment not found.",
        )

    return payment


@router.patch(
    "/{payment_id}",
    response_model=MembershipPaymentResponse,
)
def update_membership_payment(
    payment_id: UUID,
    payload: MembershipPaymentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("payments.edit")),
):
    business_id = get_business_id(current_user)

    payment = db.scalar(
        select(MembershipPayment).where(
            MembershipPayment.id == payment_id,
            MembershipPayment.business_id == business_id,
        )
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership payment not found.",
        )

    updates = payload.model_dump(
        exclude_unset=True,
    )

    previous_values = {
        field: (
            str(getattr(payment, field))
            if getattr(payment, field) is not None
            else None
        )
        for field in updates
    }

    old_contribution = None

    if payment.contribution_id:
        old_contribution = db.scalar(
            select(MembershipContribution).where(
                MembershipContribution.id == payment.contribution_id,
                MembershipContribution.business_id == business_id,
            )
        )

    new_amount = updates.get(
        "amount",
        payment.amount,
    )

    new_reference = updates.get(
        "reference",
        payment.reference,
    )

    if new_reference:
        duplicate = db.scalar(
            select(MembershipPayment).where(
                MembershipPayment.business_id == business_id,
                MembershipPayment.reference == new_reference,
                MembershipPayment.id != payment.id,
            )
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A payment with this reference already exists.",
            )

    if old_contribution:
        other_paid = db.scalar(
            select(
                func.coalesce(
                    func.sum(MembershipPayment.amount),
                    Decimal("0.00"),
                )
            ).where(
                MembershipPayment.contribution_id
                == old_contribution.id,
                MembershipPayment.business_id
                == business_id,
                MembershipPayment.id != payment.id,
            )
        )

        other_paid = Decimal(
            str(other_paid or "0.00")
        )

        new_total = other_paid + new_amount

        if new_total > old_contribution.amount_due:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Updated payment would exceed "
                    "the contribution amount due."
                ),
            )

    for field, value in updates.items():
        setattr(
            payment,
            field,
            value,
        )

    payment.updated_at = datetime.now(
        timezone.utc
    )

    db.flush()

    if old_contribution:
        recalculate_contribution(
            db,
            old_contribution,
        )

    membership = get_membership(
        db,
        payment.membership_id,
        business_id,
    )

    recalculate_membership_status(
        db,
        membership,
    )

    new_values = {
        field: (
            str(getattr(payment, field))
            if getattr(payment, field) is not None
            else None
        )
        for field in updates
    }

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.payment_updated",
        entity_type="membership_payment",
        entity_id=payment.id,
        details={
            "changes": {
                field: {
                    "before": previous_values[field],
                    "after": new_values[field],
                }
                for field in updates
            }
        },
        notes="Membership payment updated by Main Admin.",
    )

    db.commit()
    db.refresh(payment)

    return payment

@router.delete(
    "/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_membership_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("payments.delete")),
):
    business_id = get_business_id(current_user)

    payment = db.scalar(
        select(MembershipPayment).where(
            MembershipPayment.id == payment_id,
            MembershipPayment.business_id == business_id,
        )
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership payment not found.",
        )

    contribution = None

    if payment.contribution_id:
        contribution = db.scalar(
            select(MembershipContribution).where(
                MembershipContribution.id == payment.contribution_id,
                MembershipContribution.business_id == business_id,
            )
        )

    membership = get_membership(
        db,
        payment.membership_id,
        business_id,
    )

    payment_details = {
        "amount": str(payment.amount),
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "payment_date": str(payment.payment_date),
        "membership_id": str(payment.membership_id),
        "contribution_id": (
            str(payment.contribution_id)
            if payment.contribution_id
            else None
        ),
    }

    db.delete(payment)
    db.flush()

    if contribution:
        recalculate_contribution(
            db,
            contribution,
        )

    recalculate_membership_status(
        db,
        membership,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.payment_deleted",
        entity_type="membership_payment",
        entity_id=payment_id,
        details=payment_details,
        notes="Membership payment deleted by Main Admin.",
    )

    db.commit()

    return None
