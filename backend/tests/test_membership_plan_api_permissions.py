from decimal import Decimal

from app.models.membership_plan import MembershipPlan
from app.models.user_permission import UserPermission
from app.models.permission import Permission
from app.models.role_permission import RolePermission


def create_plan(db, business, *, name="Standard Cover"):
    plan = MembershipPlan(
        business_id=business.id,
        name=name,
        description="Standard funeral cover",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


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


def test_staff_with_view_permission_can_list_membership_plans(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.view")
    create_plan(db, test_data["business_a"])

    response = client.get(
        "/membership-plans",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Standard Cover"


def test_staff_without_view_permission_cannot_list_membership_plans(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.view")
    create_plan(db, test_data["business_a"])

    response = client.get(
        "/membership-plans",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.view"
    )


def test_staff_with_view_permission_can_get_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.view")
    plan = create_plan(db, test_data["business_a"])

    response = client.get(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(plan.id)


def test_staff_with_manage_permission_can_create_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.manage")

    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["staff"]),
        json={
            "name": "Premium Cover",
            "description": "Premium funeral cover",
            "monthly_contribution": "450.00",
            "is_active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Premium Cover"

    plan = (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.business_id == test_data["business_a"].id,
            MembershipPlan.name == "Premium Cover",
        )
        .first()
    )
    assert plan is not None


def test_staff_without_manage_permission_cannot_create_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.manage")

    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["staff"]),
        json={
            "name": "Premium Cover",
            "description": "Premium funeral cover",
            "monthly_contribution": "450.00",
            "is_active": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.manage"
    )


def test_staff_with_manage_permission_can_update_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.manage")
    plan = create_plan(db, test_data["business_a"])

    response = client.patch(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "name": "Updated Cover",
            "monthly_contribution": "300.00",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Cover"
    assert response.json()["monthly_contribution"] == "300.00"


def test_staff_without_manage_permission_cannot_update_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.manage")
    plan = create_plan(db, test_data["business_a"])

    response = client.patch(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "name": "Updated Cover",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.manage"
    )


def test_staff_with_manage_permission_can_delete_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.manage")
    plan = create_plan(db, test_data["business_a"])

    response = client.delete(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204

    deleted_plan = (
        db.query(MembershipPlan)
        .filter(MembershipPlan.id == plan.id)
        .first()
    )
    assert deleted_plan is None


def test_staff_without_manage_permission_cannot_delete_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.manage")
    plan = create_plan(db, test_data["business_a"])

    response = client.delete(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.manage"
    )


def test_explicit_user_deny_overrides_role_permission_for_view(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.view")
    deny_permission(
        db,
        test_data["staff"].id,
        "membership_plans.view",
    )
    create_plan(db, test_data["business_a"])

    response = client.get(
        "/membership-plans",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.view"
    )


def test_other_business_cannot_access_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "manager", "membership_plans.view")
    plan = create_plan(db, test_data["business_a"])

    response = client.get(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership plan not found"
