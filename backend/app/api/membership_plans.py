from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    serialize_snapshot,
    snapshot_fields,
)
from app.schemas.membership_plan import (
    MembershipPlanCreate,
    MembershipPlanResponse,
    MembershipPlanUpdate,
)


AUDITED_PLAN_FIELDS = (
    "name",
    "description",
    "monthly_contribution",
    "is_active",
    "waiting_natural_months",
    "waiting_accidental_months",
    "waiting_suicide_months",
    "waiting_upgrade_months",
)

# Waiting periods can never be null.
NOT_NULL_PLAN_FIELDS = (
    "waiting_natural_months",
    "waiting_accidental_months",
    "waiting_suicide_months",
    "waiting_upgrade_months",
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
    current_user: dict = Depends(require_permission("membership_plans.manage")),
):
    business_id = get_business_id(current_user)

    plan = MembershipPlan(
        business_id=business_id,
        name=plan_data.name.strip(),
        description=plan_data.description,
        monthly_contribution=plan_data.monthly_contribution,
        is_active=plan_data.is_active,
        waiting_natural_months=plan_data.waiting_natural_months,
        waiting_accidental_months=plan_data.waiting_accidental_months,
        waiting_suicide_months=plan_data.waiting_suicide_months,
        waiting_upgrade_months=plan_data.waiting_upgrade_months,
    )

    db.add(plan)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="membership_plan.created",
        entity_type="membership_plan",
        entity_id=plan.id,
        details=serialize_snapshot(
            snapshot_fields(plan, AUDITED_PLAN_FIELDS)
        ),
        notes="Membership plan was created.",
    )

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
    current_user: dict = Depends(require_permission("membership_plans.view")),
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
    current_user: dict = Depends(require_permission("membership_plans.view")),
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
    current_user: dict = Depends(require_permission("membership_plans.manage")),
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

    for field in NOT_NULL_PLAN_FIELDS:
        if field in updates and updates[field] is None:
            del updates[field]

    old_values = snapshot_fields(plan, AUDITED_PLAN_FIELDS)

    for field, value in updates.items():
        setattr(plan, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(plan, AUDITED_PLAN_FIELDS),
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="membership_plan.updated",
            entity_type="membership_plan",
            entity_id=plan.id,
            details={"changes": changes},
            notes="Membership plan was updated.",
        )

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
    current_user: dict = Depends(require_permission("membership_plans.manage")),
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

    in_use = (
        db.query(Membership)
        .filter(
            Membership.business_id == business_id,
            (Membership.plan_id == plan.id)
            | (Membership.previous_plan_id == plan.id),
        )
        .count()
    )

    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Members are on this plan, so it cannot be deleted. "
                "Deactivate it instead."
            ),
        )

    snapshot = serialize_snapshot(
        snapshot_fields(plan, AUDITED_PLAN_FIELDS)
    )

    db.delete(plan)

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="membership_plan.deleted",
        entity_type="membership_plan",
        entity_id=plan_id,
        details=snapshot,
        notes="Membership plan was deleted.",
    )

    db.commit()

    return None
