from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.permissions import PERMISSIONS


DEFAULT_ROLE_PERMISSIONS = {
    "manager": {
        "branches.all_access",
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
        "imports.run",
        "members.view",
        "members.create",
        "members.edit",
        "members.delete",
        "members.restore",
        "members.export",
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
        "finance.overview",
        "financials.manage",
        "users.view",
        "users.create",
        "users.edit",
        "users.delete",
        "employees.view",
        "employees.manage",
        "chat.use",
        "meetings.use",
        "chat.manage",
        "presence.view",
        "presence.manage",
        "expenses.view",
        "expenses.manage",
        "reconciliation.view",
        "reconciliation.manage",
        "reports.view",
        "audit.view",
        "settings.view",
        "branding.view",
        "resources.view",
        "resources.manage",
        "resource_bookings.view",
        "resource_bookings.manage",
        "branches.view",
        "death_records.view",
        "death_records.manage",
        "paperwork.view",
        "paperwork.manage",
        "mortuary.view",
        "mortuary.manage",
        "remains.view",
        "remains.manage",
        "remains.release",
        "remains.release_override",
        "arrangements.view",
        "arrangements.manage",
        "collections.view",
        "collections.manage",
        "run_sheet.view",
        "communications.view",
        "communications.send",
        "communications.templates",
        "branches.transfer",
        "inventory.view",
        "inventory.manage",
        "inventory.stock",
        "suppliers.view",
        "suppliers.manage",
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
        "chat.use",
        "meetings.use",
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
        "branches.view",
        "death_records.view",
        "death_records.manage",
        "paperwork.view",
        "paperwork.manage",
        "mortuary.view",
        "remains.view",
        "remains.manage",
        "arrangements.view",
        "arrangements.manage",
        "collections.view",
        "collections.manage",
        "run_sheet.view",
        "communications.view",
        "communications.send",
        "inventory.view",
        "inventory.stock",
        "suppliers.view",
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


# Job-focused roles. Least privilege: each gets what the job needs.
_EVERYONE = {
    "dashboard.view",
    "chat.use",
    "meetings.use",
    "presence.view",
    "presence.manage",
    "tasks.view",
    "tasks.manage",
    "documents.view",
    "branches.view",
    "groups.view",
}

DEFAULT_ROLE_PERMISSIONS["mortuary"] = _EVERYONE | {
    "cases.view",
    "families.view",
    "mortuary.view",
    "mortuary.manage",
    "remains.view",
    "remains.manage",
    "remains.release",
    "death_records.view",
    "death_records.manage",
    "paperwork.view",
    "paperwork.manage",
    "documents.manage",
    "run_sheet.view",
    "arrangements.view",
    "services.view",
    "resources.view",
    "resource_bookings.view",
    "inventory.view",
    "inventory.stock",
}

DEFAULT_ROLE_PERMISSIONS["finance"] = _EVERYONE | {
    "cases.view",
    "families.view",
    "families.manage",
    "contacts.view",
    "members.view",
    "members.create",
    "members.edit",
    "membership_plans.view",
    "memberships.view",
    "memberships.create",
    "memberships.edit",
    "contributions.view",
    "contributions.create",
    "contributions.edit",
    "payments.view",
    "payments.create",
    "payments.edit",
    "financials.view",
    "finance.overview",
    "financial_documents.view",
    "receipts.view",
    "receipts.issue",
    "beneficiaries.view",
    "claims.view",
    "claims.create",
    "communications.view",
    "communications.send",
    "reports.view",
    "expenses.view",
    "expenses.manage",
    "reconciliation.view",
    "reconciliation.manage",
}

DEFAULT_ROLE_PERMISSIONS["operations"] = _EVERYONE | {
    "cases.view",
    "cases.create",
    "cases.edit",
    "families.view",
    "families.manage",
    "contacts.view",
    "contacts.manage",
    "members.view",
    "memberships.view",
    "services.view",
    "services.manage",
    "arrangements.view",
    "arrangements.manage",
    "collections.view",
    "run_sheet.view",
    "resources.view",
    "resource_bookings.view",
    "resource_bookings.manage",
    "mortuary.view",
    "remains.view",
    "death_records.view",
    "death_records.manage",
    "paperwork.view",
    "paperwork.manage",
    "documents.manage",
    "inventory.view",
    "suppliers.view",
    "communications.view",
    "communications.send",
}


# Family viewings and the licences/certificates register.
DEFAULT_ROLE_PERMISSIONS["manager"] |= {
    "viewings.view", "viewings.manage",
    "compliance.view", "compliance.manage",
}
DEFAULT_ROLE_PERMISSIONS["staff"] |= {"viewings.view"}
DEFAULT_ROLE_PERMISSIONS["mortuary"] |= {
    "viewings.view", "viewings.manage", "compliance.view",
}
DEFAULT_ROLE_PERMISSIONS["operations"] |= {
    "viewings.view", "viewings.manage",
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
