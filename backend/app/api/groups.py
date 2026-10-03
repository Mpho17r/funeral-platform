from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import (
    GroupCreate,
    GroupMemberCreate,
    GroupMemberResponse,
    GroupMemberUpdate,
    GroupResponse,
    GroupUpdate,
)
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/groups",
    tags=["Groups"],
)


def get_business_group(
    group_id: UUID,
    db: Session,
    current_user: dict,
) -> Group:
    """Fetch a group while enforcing tenant isolation."""
    group = (
        db.query(Group)
        .filter(
            Group.id == group_id,
            Group.business_id == current_user["business_id"],
        )
        .first()
    )

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    return group


def get_group_member(
    group_id: UUID,
    user_id: UUID,
    db: Session,
) -> GroupMember | None:
    return (
        db.query(GroupMember)
        .filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
        .first()
    )


def is_group_admin(
    group_id: UUID,
    user_id: UUID,
    db: Session,
) -> bool:
    membership = get_group_member(
        group_id,
        user_id,
        db,
    )

    return membership is not None and membership.is_admin


def require_group_admin(
    group: Group,
    db: Session,
    current_user: dict,
) -> None:
    """Require tenant-level permission and group administrator status."""
    if current_user["role"] == "main_admin":
        return

    if not is_group_admin(
        group.id,
        UUID(str(current_user["user_id"])),
        db,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Group administrator access required",
        )


@router.get(
    "",
    response_model=list[GroupResponse],
)
def list_groups(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.view")),
):
    return (
        db.query(Group)
        .filter(Group.business_id == current_user["business_id"])
        .order_by(Group.created_at)
        .all()
    )


@router.post(
    "",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.create")),
):
    group = Group(
        business_id=current_user["business_id"],
        name=data.name,
        description=data.description,
        created_by=UUID(str(current_user["user_id"])),
    )

    db.add(group)
    db.flush()

    membership = GroupMember(
        group_id=group.id,
        user_id=UUID(str(current_user["user_id"])),
        is_admin=True,
    )

    db.add(membership)

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=UUID(str(current_user["user_id"])),
        action="group.created",
        entity_type="group",
        entity_id=group.id,
        details={
            "name": group.name,
            "description": group.description,
            "created_by": str(group.created_by),
        },
        notes="User group created.",
    )

    db.commit()
    db.refresh(group)

    return group


@router.get(
    "/{group_id}",
    response_model=GroupResponse,
)
def get_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.view")),
):
    return get_business_group(
        group_id,
        db,
        current_user,
    )


@router.patch(
    "/{group_id}",
    response_model=GroupResponse,
)
def update_group(
    group_id: UUID,
    data: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.manage")),
):
    group = get_business_group(
        group_id,
        db,
        current_user,
    )

    require_group_admin(
        group,
        db,
        current_user,
    )

    updates = data.model_dump(exclude_unset=True)

    if not updates:
        return group

    changes = {}

    for field, value in updates.items():
        changes[field] = {
            "before": getattr(group, field),
            "after": value,
        }
        setattr(group, field, value)

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=UUID(str(current_user["user_id"])),
        action="group.updated",
        entity_type="group",
        entity_id=group.id,
        details={"changes": changes},
        notes="User group updated.",
    )

    db.commit()
    db.refresh(group)

    return group


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.delete")),
):
    group = get_business_group(
        group_id,
        db,
        current_user,
    )

    require_group_admin(
        group,
        db,
        current_user,
    )

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=UUID(str(current_user["user_id"])),
        action="group.deleted",
        entity_type="group",
        entity_id=group.id,
        details={
            "name": group.name,
            "description": group.description,
        },
        notes="User group deleted.",
    )

    db.delete(group)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group could not be deleted",
        )

    return None


@router.post(
    "/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_group_member(
    group_id: UUID,
    data: GroupMemberCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.manage")),
):
    group = get_business_group(
        group_id,
        db,
        current_user,
    )

    require_group_admin(
        group,
        db,
        current_user,
    )

    user = (
        db.query(User)
        .filter(
            User.id == data.user_id,
            User.business_id == current_user["business_id"],
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive users cannot be added to groups",
        )

    existing_membership = get_group_member(
        group.id,
        user.id,
        db,
    )

    if existing_membership is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this group",
        )

    membership = GroupMember(
        group_id=group.id,
        user_id=user.id,
        is_admin=data.is_admin,
    )

    db.add(membership)
    db.flush()

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=UUID(str(current_user["user_id"])),
        action="group.member_added",
        entity_type="group_member",
        entity_id=membership.id,
        details={
            "group_id": str(group.id),
            "user_id": str(user.id),
            "is_admin": membership.is_admin,
        },
        notes="User added to group.",
    )

    db.commit()
    db.refresh(membership)

    return membership


@router.patch(
    "/{group_id}/members/{user_id}",
    response_model=GroupMemberResponse,
)
def update_group_member(
    group_id: UUID,
    user_id: UUID,
    data: GroupMemberUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.manage")),
):
    group = get_business_group(
        group_id,
        db,
        current_user,
    )

    require_group_admin(
        group,
        db,
        current_user,
    )

    membership = get_group_member(
        group.id,
        user_id,
        db,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group member not found",
        )

    if membership.is_admin and not data.is_admin:
        admin_count = (
            db.query(GroupMember)
            .filter(
                GroupMember.group_id == group.id,
                GroupMember.is_admin.is_(True),
            )
            .count()
        )

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A group must always have at least one administrator",
            )

    if membership.is_admin == data.is_admin:
        return membership

    previous_is_admin = membership.is_admin
    membership.is_admin = data.is_admin

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=UUID(str(current_user["user_id"])),
        action="group.member_role_updated",
        entity_type="group_member",
        entity_id=membership.id,
        details={
            "group_id": str(group.id),
            "user_id": str(user_id),
            "before": {"is_admin": previous_is_admin},
            "after": {"is_admin": membership.is_admin},
        },
        notes="Group member administrator status updated.",
    )

    db.commit()
    db.refresh(membership)

    return membership


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("groups.manage")),
):
    group = get_business_group(
        group_id,
        db,
        current_user,
    )

    require_group_admin(
        group,
        db,
        current_user,
    )

    membership = get_group_member(
        group.id,
        user_id,
        db,
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group member not found",
        )

    if membership.is_admin:
        admin_count = (
            db.query(GroupMember)
            .filter(
                GroupMember.group_id == group.id,
                GroupMember.is_admin.is_(True),
            )
            .count()
        )

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A group must always have at least one administrator",
            )

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=UUID(str(current_user["user_id"])),
        action="group.member_removed",
        entity_type="group_member",
        entity_id=membership.id,
        details={
            "group_id": str(group.id),
            "user_id": str(user_id),
            "is_admin": membership.is_admin,
        },
        notes="User removed from group.",
    )

    db.delete(membership)
    db.commit()

    return None
