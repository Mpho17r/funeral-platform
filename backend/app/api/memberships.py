from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan
from app.services.audit_service import create_audit_log
from app.schemas.membership import (
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
)


router = APIRouter(
    prefix="/memberships",
    tags=["Memberships"],
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
# CREATE MEMBERSHIP
# POST /memberships
# ============================================================

@router.post(
    "",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_membership(
    membership_data: MembershipCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("memberships.create")),
):
    business_id = get_business_id(current_user)

    # --------------------------------------------------------
    # Verify member belongs to this business
    # --------------------------------------------------------

    member = (
        db.query(Member)
        .filter(
            Member.id == membership_data.member_id,
            Member.business_id == business_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # --------------------------------------------------------
    # Verify plan belongs to this business
    # --------------------------------------------------------

    plan = (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.id == membership_data.plan_id,
            MembershipPlan.business_id == business_id,
        )
        .first()
    )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found",
        )

    # --------------------------------------------------------
    # New memberships cannot use an inactive plan
    # --------------------------------------------------------

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a membership using an inactive plan",
        )

    # --------------------------------------------------------
    # Check membership number is unique within the business
    # --------------------------------------------------------

    existing_number = (
        db.query(Membership)
        .filter(
            Membership.business_id == business_id,
            Membership.membership_number
            == membership_data.membership_number.strip(),
        )
        .first()
    )

    if existing_number:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership number already exists",
        )

    # --------------------------------------------------------
    # Prevent multiple active/arrears memberships for member
    # --------------------------------------------------------

    existing_membership = (
        db.query(Membership)
        .filter(
            Membership.business_id == business_id,
            Membership.member_id == membership_data.member_id,
            Membership.status.in_(["active", "arrears"]),
        )
        .first()
    )

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already has an active membership",
        )

    # --------------------------------------------------------
    # Determine next due date
    # --------------------------------------------------------

    next_due_date = membership_data.next_due_date

    if next_due_date is None:
        from calendar import monthrange
        from datetime import date

        start_date = membership_data.start_date

        if start_date.month == 12:
            next_year = start_date.year + 1
            next_month = 1
        else:
            next_year = start_date.year
            next_month = start_date.month + 1

        next_day = min(
            start_date.day,
            monthrange(next_year, next_month)[1],
        )

        next_due_date = date(
            next_year,
            next_month,
            next_day,
        )

    # --------------------------------------------------------
    # Create membership
    # --------------------------------------------------------

    membership = Membership(
        business_id=business_id,
        member_id=membership_data.member_id,
        plan_id=membership_data.plan_id,
        membership_number=membership_data.membership_number.strip(),
        start_date=membership_data.start_date,
        status=membership_data.status,
        next_due_date=next_due_date,
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


# ============================================================
# LIST MEMBERSHIPS
# GET /memberships
# ============================================================

@router.get(
    "",
    response_model=list[MembershipResponse],
)
def list_memberships(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("memberships.view")),
):
    business_id = get_business_id(current_user)

    return (
        db.query(Membership)
        .filter(
            Membership.business_id == business_id,
        )
        .order_by(
            Membership.created_at.desc()
        )
        .all()
    )


# ============================================================
# GET SINGLE MEMBERSHIP
# GET /memberships/{membership_id}
# ============================================================

@router.get(
    "/{membership_id}",
    response_model=MembershipResponse,
)
def get_membership(
    membership_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("memberships.view")),
):
    business_id = get_business_id(current_user)

    membership = (
        db.query(Membership)
        .filter(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    return membership


# ============================================================
# UPDATE MEMBERSHIP
# PATCH /memberships/{membership_id}
# ============================================================

@router.patch(
    "/{membership_id}",
    response_model=MembershipResponse,
)
def update_membership(
    membership_id: UUID,
    membership_data: MembershipUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("memberships.edit")),
):
    business_id = get_business_id(current_user)

    membership = (
        db.query(Membership)
        .filter(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    updates = membership_data.model_dump(
        exclude_unset=True
    )

    # --------------------------------------------------------
    # Membership number
    # --------------------------------------------------------

    if "membership_number" in updates:
        membership_number = updates["membership_number"]

        if membership_number is not None:
            membership_number = membership_number.strip()

            duplicate = (
                db.query(Membership)
                .filter(
                    Membership.business_id == business_id,
                    Membership.membership_number == membership_number,
                    Membership.id != membership.id,
                )
                .first()
            )

            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Membership number already exists",
                )

            updates["membership_number"] = membership_number

    # --------------------------------------------------------
    # Plan change
    # --------------------------------------------------------

    if "plan_id" in updates and updates["plan_id"] is not None:
        plan = (
            db.query(MembershipPlan)
            .filter(
                MembershipPlan.id == updates["plan_id"],
                MembershipPlan.business_id == business_id,
            )
            .first()
        )

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership plan not found",
            )

        if not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign an inactive membership plan",
            )

    # --------------------------------------------------------
    # Apply updates
    # --------------------------------------------------------

    for field, value in updates.items():
        setattr(membership, field, value)

    db.commit()
    db.refresh(membership)

    return membership


# ============================================================
# CANCEL MEMBERSHIP
# POST /memberships/{membership_id}/cancel
# ============================================================

@router.post(
    "/{membership_id}/cancel",
    response_model=MembershipResponse,
)
def cancel_membership(
    membership_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("memberships.manage")),
):
    business_id = get_business_id(current_user)

    membership = (
        db.query(Membership)
        .filter(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    if membership.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Membership is already cancelled",
        )

    previous_status = membership.status

    membership.status = "cancelled"
    membership.cancelled_at = date.today()
    membership.arrears_since = None
    membership.lapsed_at = None

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.cancelled",
        entity_type="membership",
        entity_id=membership.id,
        details={
            "previous_status": previous_status,
            "new_status": membership.status,
        },
        notes="Membership cancelled.",
    )

    db.commit()
    db.refresh(membership)

    return membership


# ============================================================
# APPROVE MANUAL REINSTATEMENT
# POST /memberships/{membership_id}/reinstate
# ============================================================

@router.post(
    "/{membership_id}/reinstate",
    response_model=MembershipResponse,
)
def reinstate_membership(
    membership_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("memberships.manage")),
):
    business_id = get_business_id(current_user)

    membership = (
        db.query(Membership)
        .filter(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    # Only lapsed memberships can be manually reinstated.
    if membership.status != "lapsed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only lapsed memberships can be reinstated",
        )

    # The business must allow manual reinstatement.
    from app.models.business import Business

    business = (
        db.query(Business)
        .filter(
            Business.id == business_id,
        )
        .first()
    )

    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    if business.reinstatement_policy != "manual":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual reinstatement is not enabled for this business",
        )

    # A manually reinstated membership must be paid up.
    from app.services.membership_status import get_oldest_unpaid_contribution
    from datetime import date

    oldest_unpaid = get_oldest_unpaid_contribution(
        db,
        membership,
        date.today(),
    )

    if oldest_unpaid is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Membership must have no unpaid contributions before reinstatement",
        )

    previous_status = membership.status

    membership.status = "active"
    membership.lapsed_at = None
    membership.arrears_since = None

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="membership.reinstated",
        entity_type="membership",
        entity_id=membership.id,
        details={
            "previous_status": previous_status,
            "new_status": membership.status,
        },
        notes="Membership manually reinstated.",
    )

    db.commit()
    db.refresh(membership)

    return membership
