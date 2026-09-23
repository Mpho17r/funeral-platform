from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user


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


# Temporary compatibility alias.
# Existing endpoints still using require_admin will continue to work
# while the role hierarchy is migrated endpoint-by-endpoint.
require_admin = require_main_admin
