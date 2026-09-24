import uuid

import pytest

from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.permissions import PERMISSIONS
from app.services.permission_seed import (
    DEFAULT_ROLE_PERMISSIONS,
    sync_permission_system,
    sync_permissions,
    sync_role_permissions,
)


def test_sync_permissions_creates_missing_permissions(db):
    # Start with an empty permission catalogue.
    db.query(RolePermission).delete()
    db.query(Permission).delete()
    db.commit()

    created = sync_permissions(db)

    assert created == len(PERMISSIONS)

    permissions = db.query(Permission).all()

    assert len(permissions) == len(PERMISSIONS)

    keys = {permission.key for permission in permissions}

    assert keys == set(PERMISSIONS.keys())

    assert all(permission.is_active for permission in permissions)


def test_sync_permissions_updates_existing_permission(db):
    key = "cases.view"

    permission = Permission(
        key=key,
        description="Old description",
        is_active=True,
    )

    db.add(permission)
    db.commit()

    created = sync_permissions(db)

    db.refresh(permission)

    assert created == len(PERMISSIONS) - 1
    assert permission.description == PERMISSIONS[key]
    assert permission.is_active is True


def test_sync_permissions_reactivates_existing_permission(db):
    key = "cases.view"

    permission = Permission(
        key=key,
        description="Old description",
        is_active=False,
    )

    db.add(permission)
    db.commit()

    sync_permissions(db)

    db.refresh(permission)

    assert permission.is_active is True
    assert permission.description == PERMISSIONS[key]


def test_sync_permissions_deactivates_removed_permission(db):
    obsolete_key = f"obsolete.test.{uuid.uuid4()}"

    permission = Permission(
        key=obsolete_key,
        description="Obsolete permission",
        is_active=True,
    )

    db.add(permission)
    db.commit()

    sync_permissions(db)

    db.refresh(permission)

    assert permission.is_active is False


def test_sync_role_permissions_creates_default_assignments(db):
    db.query(RolePermission).delete()
    db.query(Permission).delete()
    db.commit()

    sync_permissions(db)

    created = sync_role_permissions(db)

    expected_count = sum(
        len(permission_keys)
        for permission_keys in DEFAULT_ROLE_PERMISSIONS.values()
    )

    assert created == expected_count

    assignments = db.query(RolePermission).all()

    assert len(assignments) == expected_count

    actual = set()

    permissions = {
        permission.id: permission.key
        for permission in db.query(Permission).all()
    }

    for assignment in assignments:
        actual.add(
            (
                assignment.role,
                permissions[assignment.permission_id],
            )
        )

    expected = {
        (role, permission_key)
        for role, permission_keys in DEFAULT_ROLE_PERMISSIONS.items()
        for permission_key in permission_keys
    }

    assert actual == expected


def test_sync_role_permissions_is_idempotent(db):
    db.query(RolePermission).delete()
    db.query(Permission).delete()
    db.commit()

    sync_permissions(db)

    first_created = sync_role_permissions(db)
    second_created = sync_role_permissions(db)

    assert first_created > 0
    assert second_created == 0

    expected_count = sum(
        len(permission_keys)
        for permission_keys in DEFAULT_ROLE_PERMISSIONS.values()
    )

    assert db.query(RolePermission).count() == expected_count


def test_sync_permission_system_is_idempotent(db):
    db.query(RolePermission).delete()
    db.query(Permission).delete()
    db.commit()

    first = sync_permission_system(db)
    second = sync_permission_system(db)

    assert first["permissions_created"] == len(PERMISSIONS)
    assert first["role_permissions_created"] == sum(
        len(permission_keys)
        for permission_keys in DEFAULT_ROLE_PERMISSIONS.values()
    )

    assert second["permissions_created"] == 0
    assert second["role_permissions_created"] == 0


def test_sync_role_permissions_rejects_unknown_default_permission(db):
    db.query(RolePermission).delete()
    db.query(Permission).delete()
    db.commit()

    sync_permissions(db)

    DEFAULT_ROLE_PERMISSIONS["manager"].add(
        "permission.that.does.not.exist"
    )

    try:
        with pytest.raises(ValueError, match="does not exist"):
            sync_role_permissions(db)
    finally:
        DEFAULT_ROLE_PERMISSIONS["manager"].remove(
            "permission.that.does.not.exist"
        )
