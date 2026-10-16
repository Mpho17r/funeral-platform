from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.constants import (
    MANAGEABLE_ROLES,
    ROLE_MAIN_ADMIN,
    ROLE_MANAGER,
    ROLE_STAFF,
)
from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.branch_service import (
    BranchError,
    resolve_branch_id,
)
from app.models.user import User
from app.schemas.user import (
    PasswordReset,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.security import hash_password
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

AUDITED_USER_FIELDS = ("full_name", "role", "is_active")


def audit_user_change(
    db: Session,
    *,
    user: User,
    current_user: dict,
    old_values: dict,
) -> None:
    """Record what changed on a user account, if anything."""

    changes = build_audit_changes(
        old_values,
        snapshot_fields(user, AUDITED_USER_FIELDS),
    )

    if not changes:
        return

    if "role" in changes:
        action = "user.role_changed"
    elif "is_active" in changes:
        action = (
            "user.reactivated" if user.is_active else "user.deactivated"
        )
    else:
        action = "user.updated"

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=current_user["user_id"],
        action=action,
        entity_type="user",
        entity_id=user.id,
        details={"changes": changes},
    )


def can_manage_role(current_role: str, target_role: str) -> bool:
    """Return whether the current role can manage the target role."""
    if current_role == ROLE_MAIN_ADMIN:
        return target_role in MANAGEABLE_ROLES

    if current_role == ROLE_MANAGER:
        return target_role == ROLE_STAFF

    return False


def can_manage_user(current_role: str, target_role: str) -> bool:
    """Return whether the current user can manage the target user."""
    if target_role == ROLE_MAIN_ADMIN:
        return False

    return can_manage_role(current_role, target_role)


def get_business_user(
    user_id: UUID,
    db: Session,
    current_user: dict,
) -> User:
    """Fetch a user while enforcing tenant isolation."""
    user = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.business_id == current_user["business_id"],
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.get(
    "",
    response_model=list[UserResponse],
)
def list_users(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.view")),
):
    query = db.query(User).filter(
        User.business_id == current_user["business_id"]
    )

    if branch_id is not None:
        query = query.filter(User.branch_id == branch_id)

    return query.order_by(User.created_at).all()


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.create")),
):
    if data.role not in MANAGEABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only manager and staff accounts can be created here",
        )

    if not can_manage_role(current_user["role"], data.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create this role",
        )

    existing_user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        branch_id = resolve_branch_id(
            db,
            business_id=current_user["business_id"],
            requested=data.branch_id,
            acting_user_id=current_user["user_id"],
        )
    except BranchError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    user = User(
        business_id=current_user["business_id"],
        branch_id=branch_id,
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=True,
    )

    db.add(user)
    db.flush()

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=current_user["user_id"],
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        details={
            "role": user.role,
            "branch_id": (
                str(user.branch_id) if user.branch_id else None
            ),
        },
    )

    db.commit()
    db.refresh(user)

    return user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.view")),
):
    return get_business_user(user_id, db, current_user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
)
def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.edit")),
):
    user = get_business_user(user_id, db, current_user)

    if user.id == current_user["user_id"]:
        if data.role is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own role",
            )

        if data.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate yourself",
            )

        old_values = snapshot_fields(user, AUDITED_USER_FIELDS)

        if data.full_name is not None:
            user.full_name = data.full_name

        audit_user_change(
            db,
            user=user,
            current_user=current_user,
            old_values=old_values,
        )

        db.commit()
        db.refresh(user)

        return user

    if not can_manage_user(current_user["role"], user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user",
        )

    old_values = snapshot_fields(user, AUDITED_USER_FIELDS)

    if data.role is not None:
        if data.role not in MANAGEABLE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only manager and staff roles can be assigned here",
            )

        if not can_manage_role(current_user["role"], data.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to assign this role",
            )

        user.role = data.role

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.is_active is not None:
        user.is_active = data.is_active

    audit_user_change(
        db,
        user=user,
        current_user=current_user,
        old_values=old_values,
    )

    db.commit()
    db.refresh(user)

    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.delete")),
):
    user = get_business_user(user_id, db, current_user)

    if user.id == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate yourself",
        )

    if not can_manage_user(current_user["role"], user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to deactivate this user",
        )

    was_active = user.is_active

    user.is_active = False

    if was_active:
        create_audit_log(
            db,
            business_id=current_user["business_id"],
            user_id=current_user["user_id"],
            action="user.deactivated",
            entity_type="user",
            entity_id=user.id,
            details={
                "changes": {
                    "is_active": {"old": True, "new": False},
                },
            },
        )

    db.commit()

    return None


@router.post(
    "/{user_id}/unlock",
    response_model=UserResponse,
)
def unlock_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.edit")),
):
    """Let someone back in after too many wrong passwords."""

    user = get_business_user(user_id, db, current_user)

    if not can_manage_user(current_user["role"], user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user",
        )

    user.locked_until = None
    user.failed_login_count = 0

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=current_user["user_id"],
        action="user.unlocked",
        entity_type="user",
        entity_id=user.id,
    )

    db.commit()
    db.refresh(user)

    return user


@router.post(
    "/{user_id}/reset-password",
    response_model=UserResponse,
)
def reset_user_password(
    user_id: UUID,
    data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.edit")),
):
    """Set a new password for someone who has forgotten theirs. Their
    earlier sessions end and any lock is lifted."""

    user = get_business_user(user_id, db, current_user)

    if user.id == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use change password for your own account",
        )

    if not can_manage_user(current_user["role"], user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user",
        )

    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.locked_until = None
    user.failed_login_count = 0

    create_audit_log(
        db,
        business_id=current_user["business_id"],
        user_id=current_user["user_id"],
        action="user.password_reset",
        entity_type="user",
        entity_id=user.id,
    )

    db.commit()
    db.refresh(user)

    return user
