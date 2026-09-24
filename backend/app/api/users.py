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
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.security import hash_password


router = APIRouter(
    prefix="/users",
    tags=["Users"],
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("users.view")),
):
    users = (
        db.query(User)
        .filter(User.business_id == current_user["business_id"])
        .order_by(User.created_at)
        .all()
    )

    return users


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

    user = User(
        business_id=current_user["business_id"],
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=True,
    )

    db.add(user)
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

        if data.full_name is not None:
            user.full_name = data.full_name

        db.commit()
        db.refresh(user)

        return user

    if not can_manage_user(current_user["role"], user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user",
        )

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

    user.is_active = False

    db.commit()

    return None
