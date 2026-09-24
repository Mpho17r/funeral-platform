from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission

from tests.test_covered_dependents import (
    create_member,
    create_plan_and_membership,
    create_dependent,
)


def grant_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            RolePermission(
                role=role,
                permission_id=permission.id,
            )
        )
        db.commit()


def revoke_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is not None:
        db.delete(existing)
        db.commit()


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

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


def dependent_payload(membership):
    return {
        "membership_id": str(membership.id),
        "first_name": "Lerato",
        "last_name": "Mokoena",
        "relationship": "child",
        "date_of_birth": "2015-05-10",
        "phone": "0712345678",
        "status": "active",
        "cover_start_date": "2026-01-01",
    }


def test_staff_with_view_permission_can_list_dependents(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "memberships.view")

    business = test_data["business_a"]
    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    client.post(
        "/covered-dependents",
        json=dependent_payload(membership),
        headers=auth_headers(test_data["main_admin"]),
    )

    response = client.get(
        "/covered-dependents",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["first_name"] == "Lerato"


def test_staff_without_view_permission_cannot_list_dependents(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "memberships.view")

    business = test_data["business_a"]
    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    client.post(
        "/covered-dependents",
        json=dependent_payload(membership),
        headers=auth_headers(test_data["main_admin"]),
    )

    response = client.get(
        "/covered-dependents",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: memberships.view"
    )


def test_staff_with_view_permission_can_get_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "memberships.view")

    business = test_data["business_a"]
    data, _ = create_dependent(
        client,
        db,
        business,
        test_data["main_admin"],
        auth_headers,
    )

    response = client.get(
        f"/covered-dependents/{data['id']}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == data["id"]


def test_staff_with_manage_permission_can_create_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "memberships.manage")

    business = test_data["business_a"]
    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    response = client.post(
        "/covered-dependents",
        json=dependent_payload(membership),
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 201
    assert response.json()["first_name"] == "Lerato"
    assert response.json()["membership_id"] == str(membership.id)


def test_staff_without_manage_permission_cannot_create_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "memberships.manage")

    business = test_data["business_a"]
    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    response = client.post(
        "/covered-dependents",
        json=dependent_payload(membership),
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: memberships.manage"
    )


def test_staff_with_manage_permission_can_update_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "memberships.manage")

    business = test_data["business_a"]
    data, _ = create_dependent(
        client,
        db,
        business,
        test_data["main_admin"],
        auth_headers,
    )

    response = client.patch(
        f"/covered-dependents/{data['id']}",
        json={
            "relationship": "sibling",
            "status": "removed",
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["relationship"] == "sibling"
    assert response.json()["status"] == "removed"


def test_staff_without_manage_permission_cannot_update_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "memberships.manage")

    business = test_data["business_a"]
    data, _ = create_dependent(
        client,
        db,
        business,
        test_data["main_admin"],
        auth_headers,
    )

    response = client.patch(
        f"/covered-dependents/{data['id']}",
        json={"status": "removed"},
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: memberships.manage"
    )


def test_staff_with_manage_permission_can_delete_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "memberships.manage")

    business = test_data["business_a"]
    data, _ = create_dependent(
        client,
        db,
        business,
        test_data["main_admin"],
        auth_headers,
    )

    response = client.delete(
        f"/covered-dependents/{data['id']}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204


def test_staff_without_manage_permission_cannot_delete_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "memberships.manage")

    business = test_data["business_a"]
    data, _ = create_dependent(
        client,
        db,
        business,
        test_data["main_admin"],
        auth_headers,
    )

    response = client.delete(
        f"/covered-dependents/{data['id']}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: memberships.manage"
    )


def test_explicit_user_deny_overrides_role_permission_for_view(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "memberships.view")
    deny_permission(
        db,
        test_data["staff"].id,
        "memberships.view",
    )

    business = test_data["business_a"]
    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    client.post(
        "/covered-dependents",
        json=dependent_payload(membership),
        headers=auth_headers(test_data["main_admin"]),
    )

    response = client.get(
        "/covered-dependents",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: memberships.view"
    )


def test_other_business_cannot_access_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "manager", "memberships.view")

    business = test_data["business_a"]
    data, _ = create_dependent(
        client,
        db,
        business,
        test_data["main_admin"],
        auth_headers,
    )

    response = client.get(
        f"/covered-dependents/{data['id']}",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Covered dependent not found."
