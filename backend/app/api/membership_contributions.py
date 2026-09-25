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
from app.schemas.membership_contribution import (
    MembershipContributionCreate,
    MembershipContributionResponse,
    MembershipContributionUpdate,
)
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/membership-contributions",
    tags=["Membership Contributions"],
)


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not associated with a business.",
        )

    try:
        return UUID(str(business_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
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


def calculate_initial_status(due_date: date) -> str:
    """
    Determine the initial contribution status.

    Payment-derived statuses such as partially_paid and paid
    are produced by the contribution recalculation workflow.
    """
    if due_date < date.today():
        return "overdue"

    return "due"


def recalculate_contribution(
    db: Session,
    contribution: MembershipContribution,
) -> MembershipContribution:
    """
    Recalculate contribution payment totals and status.

    The contribution status is derived from:
    - total recorded payments
    - amount due
    - due date

    This prevents contradictory states such as:
    - R200 paid against R300 due but status = paid
    - R0 paid but status = partially_paid
    - unpaid contribution past its due date but status = due
    """

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
    response_model=MembershipContributionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership_contribution(
    payload: MembershipContributionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contributions.create")),
):
    business_id = get_business_id(current_user)

    membership = get_membership(
        db,
        payload.membership_id,
        business_id,
    )

    existing = db.scalar(
        select(MembershipContribution).where(
            MembershipContribution.membership_id == payload.membership_id,
            MembershipContribution.business_id == business_id,
            MembershipContribution.contribution_period
            == payload.contribution_period,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A contribution already exists for this membership period.",
        )

    contribution = MembershipContribution(
        business_id=business_id,
        membership_id=membership.id,
        contribution_period=payload.contribution_period,
        amount_due=payload.amount_due,
        amount_paid=0,
        due_date=payload.due_date,
        status=calculate_initial_status(payload.due_date),
    )

    db.add(contribution)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.contribution_created",
        entity_type="membership_contribution",
        entity_id=contribution.id,
        details={
            "membership_id": str(contribution.membership_id),
            "contribution_period": (
                contribution.contribution_period.isoformat()
            ),
            "amount_due": str(contribution.amount_due),
            "due_date": contribution.due_date.isoformat(),
            "status": contribution.status,
        },
        notes="Membership contribution created.",
    )

    db.commit()
    db.refresh(contribution)

    return contribution


@router.get(
    "",
    response_model=list[MembershipContributionResponse],
)
def list_membership_contributions(
    membership_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contributions.view")),
):
    business_id = get_business_id(current_user)

    query = select(MembershipContribution).where(
        MembershipContribution.business_id == business_id
    )

    if membership_id:
        query = query.where(
            MembershipContribution.membership_id == membership_id
        )

    return list(
        db.scalars(
            query.order_by(
                MembershipContribution.contribution_period.desc()
            )
        ).all()
    )


@router.get(
    "/{contribution_id}",
    response_model=MembershipContributionResponse,
)
def get_membership_contribution(
    contribution_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contributions.view")),
):
    business_id = get_business_id(current_user)

    contribution = db.scalar(
        select(MembershipContribution).where(
            MembershipContribution.id == contribution_id,
            MembershipContribution.business_id == business_id,
        )
    )

    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership contribution not found.",
        )

    return contribution


@router.patch(
    "/{contribution_id}",
    response_model=MembershipContributionResponse,
)
def update_membership_contribution(
    contribution_id: UUID,
    payload: MembershipContributionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("contributions.edit")),
):
    business_id = get_business_id(current_user)

    contribution = db.scalar(
        select(MembershipContribution).where(
            MembershipContribution.id == contribution_id,
            MembershipContribution.business_id == business_id,
        )
    )

    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership contribution not found.",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        return contribution

    previous_values = {
        field: (
            str(getattr(contribution, field))
            if getattr(contribution, field) is not None
            else None
        )
        for field in updates
    }

    if "amount_due" in updates:
        new_amount_due = updates["amount_due"]

        if contribution.amount_paid > new_amount_due:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Amount due cannot be lower than "
                    "amount already paid."
                ),
            )

    if "status" in updates:
        new_status = updates["status"]

        if new_status == "paid":
            if contribution.amount_paid < contribution.amount_due:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "A contribution cannot be marked paid "
                        "before the full amount is paid."
                    ),
                )

        elif new_status == "partially_paid":
            if contribution.amount_paid <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "A contribution cannot be marked partially paid "
                        "when no payment has been recorded."
                    ),
                )

    for field, value in updates.items():
        setattr(
            contribution,
            field,
            value,
        )

    # Status and payment totals are authoritative and must always
    # be recalculated after contribution details change.
    recalculate_contribution(
        db,
        contribution,
    )

    db.flush()

    new_values = {
        field: (
            str(getattr(contribution, field))
            if getattr(contribution, field) is not None
            else None
        )
        for field in updates
    }

    # Also capture the recalculated status if status was not part
    # of the original request but changed because of the update.
    if "status" not in updates:
        previous_status = previous_values.get(
            "status",
            None,
        )

        if previous_status is None:
            previous_status = None

        new_values["status"] = contribution.status

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.contribution_updated",
        entity_type="membership_contribution",
        entity_id=contribution.id,
        details={
            "changes": {
                field: {
                    "before": previous_values.get(
                        field,
                        None,
                    ),
                    "after": new_values.get(
                        field,
                        None,
                    ),
                }
                for field in new_values
            }
        },
        notes="Membership contribution updated.",
    )

    db.commit()
    db.refresh(contribution)

    return contribution