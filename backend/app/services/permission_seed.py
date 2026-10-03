from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.permissions import PERMISSIONS


DEFAULT_ROLE_PERMISSIONS = {
    "manager": {
        "dashboard.view",
        "cases.view",
        "cases.create",
        "cases.edit",
        "cases.delete",
        "families.view",
        "families.manage",
        "contacts.view",
        "contacts.manage",
        "members.view",
        "members.create",
        "members.edit",
        "members.delete",
        "membership_plans.view",
        "membership_plans.manage",
        "memberships.view",
        "memberships.create",
        "memberships.edit",
        "memberships.manage",
        "contributions.view",
        "contributions.create",
        "contributions.edit",
        "payments.view",
        "payments.create",
        "payments.edit",
        "payments.delete",
        "services.view",
        "services.manage",
        "documents.view",
        "documents.manage",
        "tasks.view",
        "tasks.manage",
        "financials.view",
        "financials.manage",
        "users.view",
        "users.create",
        "users.edit",
        "users.delete",
        "employees.view",
        "employees.manage",
        "presence.view",
        "presence.manage",
        "reports.view",
        "settings.view",
        "branding.view",
        "groups.view",
        "groups.create",
        "groups.manage",
        "groups.delete",
    },
    "staff": {
        "dashboard.view",
        "cases.view",
        "cases.create",
        "cases.edit",
        "families.view",
        "families.manage",
        "members.view",
        "membership_plans.view",
        "memberships.view",
        "contributions.view",
        "payments.view",
        "services.view",
        "services.manage",
        "presence.view",
        "presence.manage",
        "documents.view",
        "documents.manage",
        "tasks.view",
        "tasks.manage",
        "financials.view",
        "reports.view",
        "settings.view",
        "branding.view",
        "groups.view",
        "groups.create",
        "groups.manage",
        "groups.delete",
    },
}


def sync_permissions(db: Session) -> int:
    """
    Synchronize the database permission catalogue with app/permissions.py.

    Existing permissions are updated rather than duplicated.
    Missing permissions are created.
    Permissions removed from the application catalogue are marked inactive.
    """

    existing_permissions = {
        permission.key: permission
        for permission in db.query(Permission).all()
    }

    created = 0

    for key, description in PERMISSIONS.items():
        permission = existing_permissions.get(key)

        if permission is None:
            permission = Permission(
                key=key,
                description=description,
                is_active=True,
            )
            db.add(permission)
            created += 1
        else:
            permission.description = description
            permission.is_active = True

    for key, permission in existing_permissions.items():
        if key not in PERMISSIONS:
            permission.is_active = False

    db.commit()

    return created


def sync_role_permissions(db: Session) -> int:
    """
    Synchronize default role permissions for manager and staff.

    Main Admin is intentionally excluded because Main Admin currently
    has tenant-level authority through has_permission().

    Existing role permissions are preserved unless they are no longer
    part of the default role catalogue.
    """

    permissions = {
        permission.key: permission
        for permission in db.query(Permission).filter(
            Permission.is_active.is_(True)
        ).all()
    }

    created = 0

    for role, permission_keys in DEFAULT_ROLE_PERMISSIONS.items():
        for permission_key in permission_keys:
            permission = permissions.get(permission_key)

            if permission is None:
                raise ValueError(
                    f"Default permission '{permission_key}' for role "
                    f"'{role}' does not exist in the permission catalogue."
                )

            existing = db.query(RolePermission).filter(
                RolePermission.role == role,
                RolePermission.permission_id == permission.id,
            ).first()

            if existing is None:
                db.add(
                    RolePermission(
                        role=role,
                        permission_id=permission.id,
                    )
                )
                created += 1

    db.commit()

    return created


def sync_permission_system(db: Session) -> dict[str, int]:
    """
    Synchronize the complete permission system.

    Returns the number of newly-created permissions and role assignments.
    """

    permissions_created = sync_permissions(db)
    role_permissions_created = sync_role_permissions(db)

    return {
        "permissions_created": permissions_created,
        "role_permissions_created": role_permissions_created,
    }
