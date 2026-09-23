from app.api.users import can_manage_role, can_manage_user
from app.constants import (
    ROLE_MAIN_ADMIN,
    ROLE_MANAGER,
    ROLE_STAFF,
)


def test_main_admin_can_manage_manager():
    assert can_manage_role(
        ROLE_MAIN_ADMIN,
        ROLE_MANAGER,
    ) is True


def test_main_admin_can_manage_staff():
    assert can_manage_role(
        ROLE_MAIN_ADMIN,
        ROLE_STAFF,
    ) is True


def test_manager_can_manage_staff():
    assert can_manage_role(
        ROLE_MANAGER,
        ROLE_STAFF,
    ) is True


def test_staff_cannot_manage_staff():
    assert can_manage_role(
        ROLE_STAFF,
        ROLE_STAFF,
    ) is False


def test_manager_cannot_manage_manager():
    assert can_manage_role(
        ROLE_MANAGER,
        ROLE_MANAGER,
    ) is False


def test_manager_cannot_manage_main_admin():
    assert can_manage_role(
        ROLE_MANAGER,
        ROLE_MAIN_ADMIN,
    ) is False


def test_main_admin_cannot_manage_main_admin():
    assert can_manage_user(
        ROLE_MAIN_ADMIN,
        ROLE_MAIN_ADMIN,
    ) is False


def test_manager_cannot_manage_main_admin_user():
    assert can_manage_user(
        ROLE_MANAGER,
        ROLE_MAIN_ADMIN,
    ) is False


def test_staff_cannot_manage_main_admin():
    assert can_manage_user(
        ROLE_STAFF,
        ROLE_MAIN_ADMIN,
    ) is False
