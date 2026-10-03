from app.models.group import Group, GroupMember
from app.models.permission import Permission
from app.models.user_permission import UserPermission


def deny_permission(db, user_id, permission_key):
    permission = db.query(Permission).filter(
        Permission.key == permission_key
    ).first()

    assert permission is not None

    existing = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.permission_id == permission.id,
    ).first()

    if existing is None:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )
    else:
        existing.effect = "deny"

    db.commit()


def create_group(db, business, admin):
    group = Group(
        business_id=business.id,
        name="Permission Test Group",
        description="Permission testing",
        created_by=admin.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=admin.id,
            is_admin=True,
        )
    )

    db.commit()
    return group


# ============================================================
# GROUPS VIEW
# ============================================================

def test_groups_view_permission_is_required(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    deny_permission(
        db,
        staff.id,
        "groups.view",
    )

    response = client.get(
        "/groups",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: groups.view"
    )


def test_groups_view_allows_access_without_explicit_deny(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.get(
        "/groups",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text


# ============================================================
# GROUPS CREATE
# ============================================================

def test_groups_create_permission_is_required(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    deny_permission(
        db,
        staff.id,
        "groups.create",
    )

    response = client.post(
        "/groups",
        json={
            "name": "Blocked Group",
            "description": "Should not be created",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: groups.create"
    )


def test_groups_create_allows_access_without_explicit_deny(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/groups",
        json={
            "name": "Allowed Group",
            "description": "Should be created",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text


# ============================================================
# GROUPS MANAGE
# ============================================================

def test_groups_manage_permission_is_required(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = create_group(
        db,
        business,
        staff,
    )

    deny_permission(
        db,
        staff.id,
        "groups.manage",
    )

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Blocked Update",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: groups.manage"
    )


def test_groups_manage_allows_group_admin_without_explicit_deny(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = create_group(
        db,
        business,
        staff,
    )

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Allowed Update",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text


# ============================================================
# GROUPS DELETE
# ============================================================

def test_groups_delete_permission_is_required(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = create_group(
        db,
        business,
        staff,
    )

    deny_permission(
        db,
        staff.id,
        "groups.delete",
    )

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: groups.delete"
    )


def test_groups_delete_allows_group_admin_without_explicit_deny(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = create_group(
        db,
        business,
        staff,
    )

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 204


# ============================================================
# MAIN ADMIN OVERRIDE
# ============================================================

def test_main_admin_can_view_groups(
    client,
    db,
    test_data,
    auth_headers,
):
    main_admin = test_data["main_admin"]

    deny_permission(
        db,
        main_admin.id,
        "groups.view",
    )

    response = client.get(
        "/groups",
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 200, response.text


def test_main_admin_can_create_groups(
    client,
    db,
    test_data,
    auth_headers,
):
    main_admin = test_data["main_admin"]

    deny_permission(
        db,
        main_admin.id,
        "groups.create",
    )

    response = client.post(
        "/groups",
        json={
            "name": "Main Admin Group",
            "description": "Created by Main Admin",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 201, response.text


def test_main_admin_can_manage_groups(
    client,
    db,
    test_data,
    auth_headers,
):
    main_admin = test_data["main_admin"]
    business = test_data["business_a"]

    group = create_group(
        db,
        business,
        main_admin,
    )

    deny_permission(
        db,
        main_admin.id,
        "groups.manage",
    )

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Main Admin Updated",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 200, response.text


def test_main_admin_can_delete_groups(
    client,
    db,
    test_data,
    auth_headers,
):
    main_admin = test_data["main_admin"]
    business = test_data["business_a"]

    group = create_group(
        db,
        business,
        main_admin,
    )

    deny_permission(
        db,
        main_admin.id,
        "groups.delete",
    )

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 204
