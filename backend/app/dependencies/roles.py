from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.services.permission_service import has_permission


BUSINESS_ROLES = {
    "main_admin",
    "manager",
    "staff",
}


def require_business_user(
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in BUSINESS_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business user access required",
        )
    return current_user


def require_main_admin(
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] != "main_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Main Admin access required",
        )
    return current_user


def require_manager_or_admin(
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in {"main_admin", "manager"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Main Admin access required",
        )
    return current_user


def require_staff_or_above(
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in {"main_admin", "manager", "staff"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business user access required",
        )
    return current_user


def require_permission(permission_key: str):
    """
    Create a FastAPI dependency that requires a specific
    FuneralOS permission.

    Authentication and tenant identity are established by
    get_current_user(). Permission evaluation is then handled
    centrally by has_permission().
    """

    def permission_dependency(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        allowed = has_permission(
            db,
            user_id=UUID(str(current_user["user_id"])),
            role=current_user["role"],
            permission_key=permission_key,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission_key}",
            )

        return current_user

    return permission_dependency


# Temporary compatibility alias.
# Existing endpoints still using require_admin will continue to work
# while the role hierarchy is migrated endpoint-by-endpoint.
require_admin = require_main_admin
