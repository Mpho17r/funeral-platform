import uuid

from app.models.business import Business
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_permission import UserPermission
from app.services.permission_service import (
    has_permission,
    validate_permission_effect,
)


# ---------------------------------------------------------------------------
# TEST HELPERS
# ---------------------------------------------------------------------------

def create_business(db):
    """
    Create a real business so User foreign-key relationships
    are valid.
    """

    business = Business(
        id=uuid.uuid4(),
        name=f"Permission Test Business {uuid.uuid4().hex[:8]}",
        slug=f"permission-test-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )

    db.add(business)
    db.flush()

    return business


def create_user(db, role="staff"):
    """
    Create a real database user.

    UserPermission.user_id has a foreign-key relationship to
    users.id, so permission tests must use an actual persisted user.
    """

    business = create_business(db)

    user = User(
        id=uuid.uuid4(),
        business_id=business.id,
        full_name="Permission Test User",
        email=f"permission-user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-password-hash",
        role=role,
        is_active=True,
    )

    db.add(user)
    db.flush()

    return user


def create_permission(db, key="cases.view", is_active=True):
    """
    Create a permission for testing.
    """

    permission = Permission(
        key=key,
        description=f"Test permission: {key}",
        is_active=is_active,
    )

    db.add(permission)
    db.flush()

    return permission


# ---------------------------------------------------------------------------
# MAIN ADMIN
# ---------------------------------------------------------------------------

def test_main_admin_has_all_permissions(db):
    user = create_user(db, role="main_admin")

    assert has_permission(
        db,
        user_id=user.id,
        role="main_admin",
        permission_key="anything.at.all",
    ) is True


# ---------------------------------------------------------------------------
# ROLE PERMISSIONS
# ---------------------------------------------------------------------------

def test_role_permission_grants_access(db):
    permission = create_permission(db)
    user = create_user(db, role="staff")

    db.add(
        RolePermission(
            role="staff",
            permission_id=permission.id,
        )
    )

    db.commit()

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="cases.view",
    ) is True


def test_missing_role_permission_denies_access(db):
    create_permission(db)
    user = create_user(db, role="staff")

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="cases.view",
    ) is False


# ---------------------------------------------------------------------------
# USER PERMISSIONS
# ---------------------------------------------------------------------------

def test_user_allow_grants_access(db):
    permission = create_permission(db)
    user = create_user(db, role="staff")

    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="allow",
        )
    )

    db.commit()

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="cases.view",
    ) is True


def test_user_deny_blocks_access(db):
    permission = create_permission(db)
    user = create_user(db, role="staff")

    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )

    db.commit()

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="cases.view",
    ) is False


def test_user_deny_overrides_role_allow(db):
    permission = create_permission(db)
    user = create_user(db, role="staff")

    db.add(
        RolePermission(
            role="staff",
            permission_id=permission.id,
        )
    )

    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )

    db.commit()

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="cases.view",
    ) is False


# ---------------------------------------------------------------------------
# INACTIVE / UNKNOWN PERMISSIONS
# ---------------------------------------------------------------------------

def test_inactive_permission_denies_access(db):
    permission = create_permission(
        db,
        key="cases.view",
        is_active=False,
    )

    user = create_user(db, role="staff")

    db.add(
        RolePermission(
            role="staff",
            permission_id=permission.id,
        )
    )

    db.commit()

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="cases.view",
    ) is False


def test_unknown_permission_denies_access(db):
    user = create_user(db, role="staff")

    assert has_permission(
        db,
        user_id=user.id,
        role="staff",
        permission_key="does.not.exist",
    ) is False


# ---------------------------------------------------------------------------
# PERMISSION EFFECT VALIDATION
# ---------------------------------------------------------------------------

def test_validate_permission_effect_accepts_allow():
    assert validate_permission_effect("allow") == "allow"


def test_validate_permission_effect_accepts_deny():
    assert validate_permission_effect("deny") == "deny"


def test_validate_permission_effect_normalizes_case():
    assert validate_permission_effect("  ALLOW ") == "allow"


def test_validate_permission_effect_rejects_invalid_value():
    try:
        validate_permission_effect("something_else")
        assert False, "Expected ValueError"
    except ValueError:
        pass