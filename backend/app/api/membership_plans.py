from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import (
    require_business_user,
    require_main_admin,
)
from app.models.membership_plan import MembershipPlan
from app.schemas.membership_plan import (
    MembershipPlanCreate,
    MembershipPlanResponse,
    MembershipPlanUpdate,
)


router = APIRouter(
    prefix="/membership-plans",
    tags=["Membership Plans"],
)


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


# ============================================================
# CREATE MEMBERSHIP PLAN
# POST /membership-plans
# ============================================================

@router.post(
    "",
    response_model=MembershipPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership_plan(
    plan_data: MembershipPlanCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):
    business_id = get_business_id(current_user)

    plan = MembershipPlan(
        business_id=business_id,
        name=plan_data.name.strip(),
        description=plan_data.description,
        monthly_contribution=plan_data.monthly_contribution,
        is_active=plan_data.is_active,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    return plan


# ============================================================
# LIST MEMBERSHIP PLANS
# GET /membership-plans
# ============================================================

@router.get(
    "",
    response_model=list[MembershipPlanResponse],
)
def list_membership_plans(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_business_user),
):
    business_id = get_business_id(current_user)

    return (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.business_id == business_id,
        )
        .order_by(
            MembershipPlan.created_at.desc()
        )
        .all()
    )


# ============================================================
# GET SINGLE MEMBERSHIP PLAN
# GET /membership-plans/{plan_id}
# ============================================================

@router.get(
    "/{plan_id}",
    response_model=MembershipPlanResponse,
)
def get_membership_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_business_user),
):
    business_id = get_business_id(current_user)

    plan = (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.id == plan_id,
            MembershipPlan.business_id == business_id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    return plan


# ============================================================
# UPDATE MEMBERSHIP PLAN
# PATCH /membership-plans/{plan_id}
# ============================================================

@router.patch(
    "/{plan_id}",
    response_model=MembershipPlanResponse,
)
def update_membership_plan(
    plan_id: UUID,
    plan_data: MembershipPlanUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):
    business_id = get_business_id(current_user)

    plan = (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.id == plan_id,
            MembershipPlan.business_id == business_id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    updates = plan_data.model_dump(
        exclude_unset=True
    )

    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()

    for field, value in updates.items():
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)

    return plan


# ============================================================
# DELETE MEMBERSHIP PLAN
# DELETE /membership-plans/{plan_id}
# ============================================================

@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_membership_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):
    business_id = get_business_id(current_user)

    plan = (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.id == plan_id,
            MembershipPlan.business_id == business_id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    db.delete(plan)
    db.commit()

    return None
