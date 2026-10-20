from uuid import UUID

from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role_permission import RolePermission
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
    4. Role permission grants access.
    5. Otherwise access is denied.
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

    role_permission = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    return role_permission is not None


def effective_permissions(
    db: Session,
    *,
    user_id: UUID,
    role: str,
) -> list[str]:
    """Every permission key the person holds right now.

    Main Admin holds all of them. Everyone else: what their role grants,
    plus explicit allows, minus explicit denies (deny always wins).
    """

    active = {
        p.id: p.key
        for p in db.query(Permission).filter(Permission.is_active.is_(True))
    }

    if role == "main_admin":
        return sorted(active.values())

    held = {
        active[rp.permission_id]
        for rp in db.query(RolePermission).filter(RolePermission.role == role)
        if rp.permission_id in active
    }

    for override in db.query(UserPermission).filter(
        UserPermission.user_id == user_id
    ):
        key = active.get(override.permission_id)

        if key is None:
            continue

        if override.effect == "allow":
            held.add(key)
        elif override.effect == "deny":
            held.discard(key)

    return sorted(held)


def validate_permission_effect(effect: str) -> str:
    """Validate and normalize a user permission effect."""
    normalized = effect.strip().lower()

    if normalized not in VALID_EFFECTS:
        raise ValueError(
            f"Invalid permission effect '{effect}'. "
            f"Expected one of: {', '.join(sorted(VALID_EFFECTS))}"
        )

    return normalized
