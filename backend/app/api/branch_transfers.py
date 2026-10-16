from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.users import can_manage_user
from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase
from app.models.inventory import InventoryItem
from app.models.member import Member
from app.models.resource import Resource
from app.models.user import User
from app.schemas.branch import BranchTransfer
from app.schemas.funeral_case import FuneralCaseResponse
from app.schemas.inventory import InventoryItemResponse
from app.schemas.member import MemberResponse
from app.schemas.resource import ResourceResponse
from app.schemas.user import UserResponse
from app.services.audit_service import create_audit_log
from app.services.branch_service import BranchError, move_to_branch


router = APIRouter(
    tags=["Branch Transfers"],
)


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def load_or_404(
    db: Session,
    model,
    record_id: UUID,
    business_id: UUID,
    label: str,
):
    """Load one record of this business, locked for the move."""

    record = (
        db.query(model)
        .filter(
            model.id == record_id,
            model.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found",
        )

    return record


def transfer(
    db: Session,
    *,
    record,
    entity_type: str,
    data: BranchTransfer,
    current_user: dict,
    business_id: UUID,
    details: dict | None = None,
):
    """Move the record, audit the move and commit.

    The audit entry records which branches were involved and the
    identifying number of the record, never personal details.
    """

    try:
        previous = move_to_branch(
            db,
            business_id=business_id,
            record=record,
            target_branch_id=data.branch_id,
        )
    except BranchError as error:
        db.rollback()

        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action=f"{entity_type}.branch_changed",
        entity_type=entity_type,
        entity_id=record.id,
        details={
            "from_branch_id": str(previous) if previous else None,
            "to_branch_id": str(record.branch_id),
            **(details or {}),
        },
        notes=(
            f"{entity_type.replace('_', ' ').capitalize()} "
            "was moved to another branch."
        ),
    )

    db.commit()
    db.refresh(record)

    return record


# ============================================================
# CASES
# ============================================================

@router.post(
    "/cases/{case_id}/transfer",
    response_model=FuneralCaseResponse,
)
def transfer_case(
    case_id: UUID,
    data: BranchTransfer,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.transfer")),
):
    business_id = get_business_id(current_user)

    case = load_or_404(db, FuneralCase, case_id, business_id, "Case")

    if case.is_archived:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived cases cannot be moved. Restore it first.",
        )

    return transfer(
        db,
        record=case,
        entity_type="case",
        data=data,
        current_user=current_user,
        business_id=business_id,
        details={"case_number": case.case_number},
    )


# ============================================================
# MEMBERS
# ============================================================

@router.post(
    "/members/{member_id}/transfer",
    response_model=MemberResponse,
)
def transfer_member(
    member_id: UUID,
    data: BranchTransfer,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.transfer")),
):
    business_id = get_business_id(current_user)

    member = load_or_404(
        db, Member, member_id, business_id, "Member"
    )

    return transfer(
        db,
        record=member,
        entity_type="member",
        data=data,
        current_user=current_user,
        business_id=business_id,
        details={"member_number": member.member_number},
    )


# ============================================================
# RESOURCES
# ============================================================

@router.post(
    "/resources/{resource_id}/transfer",
    response_model=ResourceResponse,
)
def transfer_resource(
    resource_id: UUID,
    data: BranchTransfer,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.transfer")),
):
    business_id = get_business_id(current_user)

    resource = load_or_404(
        db, Resource, resource_id, business_id, "Resource"
    )

    return transfer(
        db,
        record=resource,
        entity_type="resource",
        data=data,
        current_user=current_user,
        business_id=business_id,
        details={"resource_type": resource.resource_type},
    )


# ============================================================
# STOCK
# ============================================================

@router.post(
    "/inventory/items/{item_id}/transfer",
    response_model=InventoryItemResponse,
)
def transfer_inventory_item(
    item_id: UUID,
    data: BranchTransfer,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.transfer")),
):
    """Move a stock item, with all of its stock, to another branch."""

    business_id = get_business_id(current_user)

    item = load_or_404(
        db, InventoryItem, item_id, business_id, "Inventory item"
    )

    return transfer(
        db,
        record=item,
        entity_type="inventory_item",
        data=data,
        current_user=current_user,
        business_id=business_id,
        details={"sku": item.sku},
    )


# ============================================================
# STAFF
# ============================================================

@router.post(
    "/users/{user_id}/transfer",
    response_model=UserResponse,
)
def transfer_user(
    user_id: UUID,
    data: BranchTransfer,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.transfer")),
):
    business_id = get_business_id(current_user)

    user = load_or_404(db, User, user_id, business_id, "User")

    # Moving someone is managing them, so the same role rules apply as
    # for editing them: a manager moves staff, never other managers or
    # the main admin.
    if not can_manage_user(current_user["role"], user.role):
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to move this user",
        )

    return transfer(
        db,
        record=user,
        entity_type="user",
        data=data,
        current_user=current_user,
        business_id=business_id,
    )
