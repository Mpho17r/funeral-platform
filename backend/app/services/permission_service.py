from uuid import UUID

from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user import User
from app.services.work_areas import area_permissions
from app.models.user_permission import UserPermission


VALID_EFFECTS = {"allow", "deny"}


def has_permission(
    db: Session,
    *,
    user_id: UUID,
    role: str,
    permission_key: str,
) -> bool:
    """
    Determine whether a user has a specific permission.

    Authorization precedence:

    1. main_admin always has tenant-level authority.
    2. Explicit user deny overrides everything for non-admin users.
    3. Explicit user allow grants access.
    4. A staff member's work area, when they have one, decides
       instead of the general staff permissions.
    5. Role permission grants access.
    6. Otherwise access is denied.
    """

    if role == "main_admin":
        return True

    permission = (
        db.query(Permission)
        .filter(
            Permission.key == permission_key,
            Permission.is_active.is_(True),
        )
        .first()
    )

    if permission is None:
        return False

    user_override = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

    if user_override is not None:
        if user_override.effect == "deny":
            return False

        if user_override.effect == "allow":
            return True

    if role == "staff":
        area = db.query(User.work_area).filter(User.id == user_id).scalar()
        allowed = area_permissions(area)

        if allowed is not None:
            return permission_key in allowed

    role_permission = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    return role_permission is not None


def validate_permission_effect(effect: str) -> str:
    """Validate and normalize a user permission effect."""
    normalized = effect.strip().lower()

    if normalized not in VALID_EFFECTS:
        raise ValueError(
            f"Invalid permission effect '{effect}'. "
            f"Expected one of: {', '.join(sorted(VALID_EFFECTS))}"
        )

    return normalized


def effective_permissions(db: Session, *, user: User) -> set[str]:
    """Every permission key the user holds right now."""

    keys = [
        row[0]
        for row in db.query(Permission.key).filter(
            Permission.is_active.is_(True)
        )
    ]

    if user.role == "main_admin":
        return set(keys)

    overrides = {
        key: effect
        for key, effect in db.query(Permission.key, UserPermission.effect)
        .join(UserPermission, UserPermission.permission_id == Permission.id)
        .filter(UserPermission.user_id == user.id)
    }

    area = (
        area_permissions(user.work_area) if user.role == "staff" else None
    )

    if area is None:
        base = {
            row[0]
            for row in db.query(Permission.key)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role == user.role)
        }
    else:
        base = area

    granted = set()

    for key in keys:
        effect = overrides.get(key)

        if effect == "deny":
            continue

        if effect == "allow" or key in base:
            granted.add(key)

    return granted
