from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit
from app.schemas.membership_plan_benefit import (
    BENEFIT_TYPES,
    MembershipPlanBenefitCreate,
    MembershipPlanBenefitResponse,
    MembershipPlanBenefitUpdate,
)
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/membership-plan-benefits",
    tags=["Membership Plan Benefits"],
)


def get_business_id(current_user: dict) -> UUID:
    return UUID(str(current_user["business_id"]))


def get_plan_for_business(
    db: Session,
    plan_id: UUID,
    business_id: UUID,
) -> MembershipPlan:
    plan = db.scalar(
        select(MembershipPlan).where(
            MembershipPlan.id == plan_id,
            MembershipPlan.business_id == business_id,
        )
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    return plan


def get_benefit_for_business(
    db: Session,
    benefit_id: UUID,
    business_id: UUID,
) -> MembershipPlanBenefit:
    benefit = db.scalar(
        select(MembershipPlanBenefit).where(
            MembershipPlanBenefit.id == benefit_id,
            MembershipPlanBenefit.business_id == business_id,
        )
    )

    if not benefit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan benefit not found",
        )

    return benefit


def validate_benefit_limits(
    benefit_type: str,
    monetary_limit,
    quantity_limit,
) -> None:
    if benefit_type not in BENEFIT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Benefit type must be one of: "
                "monetary, included_service, quantity, other"
            ),
        )

    if benefit_type == "monetary" and monetary_limit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monetary benefits require a monetary limit",
        )

    if benefit_type == "quantity" and quantity_limit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity benefits require a quantity limit",
        )


@router.post(
    "",
    response_model=MembershipPlanBenefitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_benefit(
    payload: MembershipPlanBenefitCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("membership_plans.manage")),
):
    business_id = get_business_id(current_user)

    get_plan_for_business(
        db,
        payload.plan_id,
        business_id,
    )

    validate_benefit_limits(
        payload.benefit_type,
        payload.monetary_limit,
        payload.quantity_limit,
    )

    benefit = MembershipPlanBenefit(
        business_id=business_id,
        plan_id=payload.plan_id,
        name=payload.name.strip(),
        description=payload.description,
        benefit_type=payload.benefit_type,
        monetary_limit=payload.monetary_limit,
        quantity_limit=payload.quantity_limit,
        is_included=payload.is_included,
        is_active=payload.is_active,
    )

    db.add(benefit)

    try:
        db.flush()

        create_audit_log(
            db=db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="membership_plan_benefit.created",
            entity_type="membership_plan_benefit",
            entity_id=benefit.id,
            details={
                "plan_id": str(benefit.plan_id),
                "name": benefit.name,
                "benefit_type": benefit.benefit_type,
                "monetary_limit": (
                    str(benefit.monetary_limit)
                    if benefit.monetary_limit is not None
                    else None
                ),
                "quantity_limit": benefit.quantity_limit,
                "is_included": benefit.is_included,
                "is_active": benefit.is_active,
            },
            notes="Membership plan benefit created by Main Admin.",
        )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create membership plan benefit",
        )

    db.refresh(benefit)
    return benefit


@router.get(
    "",
    response_model=list[MembershipPlanBenefitResponse],
)
def list_benefits(
    plan_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("membership_plans.view")),
):
    business_id = get_business_id(current_user)

    query = select(MembershipPlanBenefit).where(
        MembershipPlanBenefit.business_id == business_id,
    )

    if plan_id is not None:
        query = query.where(
            MembershipPlanBenefit.plan_id == plan_id,
        )

    query = query.order_by(
        MembershipPlanBenefit.created_at.asc()
    )

    return list(db.scalars(query).all())


@router.get(
    "/{benefit_id}",
    response_model=MembershipPlanBenefitResponse,
)
def get_benefit(
    benefit_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("membership_plans.view")),
):
    business_id = get_business_id(current_user)

    return get_benefit_for_business(
        db,
        benefit_id,
        business_id,
    )


@router.patch(
    "/{benefit_id}",
    response_model=MembershipPlanBenefitResponse,
)
def update_benefit(
    benefit_id: UUID,
    payload: MembershipPlanBenefitUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("membership_plans.manage")),
):
    business_id = get_business_id(current_user)

    benefit = get_benefit_for_business(
        db,
        benefit_id,
        business_id,
    )

    updates = payload.model_dump(exclude_unset=True)

    new_benefit_type = updates.get(
        "benefit_type",
        benefit.benefit_type,
    )

    new_monetary_limit = updates.get(
        "monetary_limit",
        benefit.monetary_limit,
    )

    new_quantity_limit = updates.get(
        "quantity_limit",
        benefit.quantity_limit,
    )

    validate_benefit_limits(
        new_benefit_type,
        new_monetary_limit,
        new_quantity_limit,
    )

    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

    previous = {
        "plan_id": str(benefit.plan_id),
        "name": benefit.name,
        "description": benefit.description,
        "benefit_type": benefit.benefit_type,
        "monetary_limit": (
            str(benefit.monetary_limit)
            if benefit.monetary_limit is not None
            else None
        ),
        "quantity_limit": benefit.quantity_limit,
        "is_included": benefit.is_included,
        "is_active": benefit.is_active,
    }

    for field, value in updates.items():
        setattr(benefit, field, value)

    new_values = {
        "plan_id": str(benefit.plan_id),
        "name": benefit.name,
        "description": benefit.description,
        "benefit_type": benefit.benefit_type,
        "monetary_limit": (
            str(benefit.monetary_limit)
            if benefit.monetary_limit is not None
            else None
        ),
        "quantity_limit": benefit.quantity_limit,
        "is_included": benefit.is_included,
        "is_active": benefit.is_active,
    }

    create_audit_log(
        db=db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="membership_plan_benefit.updated",
        entity_type="membership_plan_benefit",
        entity_id=benefit.id,
        details={
            "previous": previous,
            "new": new_values,
        },
        notes="Membership plan benefit updated by Main Admin.",
    )

    db.commit()
    db.refresh(benefit)

    return benefit


@router.delete(
    "/{benefit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_benefit(
    benefit_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("membership_plans.manage")),
):
    business_id = get_business_id(current_user)

    benefit = get_benefit_for_business(
        db,
        benefit_id,
        business_id,
    )

    previous = {
        "plan_id": str(benefit.plan_id),
        "name": benefit.name,
        "description": benefit.description,
        "benefit_type": benefit.benefit_type,
        "monetary_limit": (
            str(benefit.monetary_limit)
            if benefit.monetary_limit is not None
            else None
        ),
        "quantity_limit": benefit.quantity_limit,
        "is_included": benefit.is_included,
        "is_active": benefit.is_active,
    }

    create_audit_log(
        db=db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="membership_plan_benefit.deleted",
        entity_type="membership_plan_benefit",
        entity_id=benefit.id,
        details=previous,
        notes="Membership plan benefit deleted by Main Admin.",
    )

    db.delete(benefit)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete membership plan benefit",
        )

    return None
