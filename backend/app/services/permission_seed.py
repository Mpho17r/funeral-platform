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
        "cases.archive",
        "cases.restore",
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
        "resources.view",
        "resources.manage",
        "resource_bookings.view",
        "resource_bookings.manage",
        "financial_documents.view",
        "financial_documents.manage",
        "financial_documents.issue",
        "financial_documents.void",
        "receipts.view",
        "receipts.issue",
        "beneficiaries.view",
        "beneficiaries.manage",
        "claims.view",
        "claims.create",
        "claims.review",
        "claims.pay",
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
        "members.create",
        "members.edit",
        "membership_plans.view",
        "memberships.view",
        "memberships.create",
        "memberships.edit",
        "contributions.view",
        "payments.view",
        "payments.create",
        "payments.edit",
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
        "resources.view",
        "resource_bookings.view",
        "resource_bookings.manage",
        "financial_documents.view",
        "receipts.view",
        "beneficiaries.view",
        "claims.view",
        "claims.create",
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

    Role permissions are synchronized exactly to the default role
    catalogue. Missing assignments are created and stale assignments
    are removed.

    User-specific permission overrides are not affected.
    """

    permissions = {
        permission.key: permission
        for permission in db.query(Permission).filter(
            Permission.is_active.is_(True)
        ).all()
    }

    created = 0

    for role, default_permission_keys in DEFAULT_ROLE_PERMISSIONS.items():
        default_permission_keys = set(default_permission_keys)

        for permission_key in default_permission_keys:
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

        existing_role_permissions = (
            db.query(RolePermission)
            .join(
                Permission,
                RolePermission.permission_id == Permission.id,
            )
            .filter(RolePermission.role == role)
            .all()
        )

        for role_permission in existing_role_permissions:
            permission = db.get(
                Permission,
                role_permission.permission_id,
            )

            if permission is None:
                continue

            if permission.key not in default_permission_keys:
                db.delete(role_permission)

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
