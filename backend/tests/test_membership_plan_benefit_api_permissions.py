from decimal import Decimal

from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def create_plan(db, business, name="Standard Cover"):
    plan = MembershipPlan(
        business_id=business.id,
        name=name,
        description="Standard funeral cover",
        monthly_contribution=Decimal("500.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def create_benefit(db, business, plan, name="Funeral Cover"):
    benefit = MembershipPlanBenefit(
        business_id=business.id,
        plan_id=plan.id,
        name=name,
        description="Standard funeral benefit",
        benefit_type="monetary",
        monetary_limit=Decimal("15000.00"),
        quantity_limit=None,
        is_included=True,
        is_active=True,
    )
    db.add(benefit)
    db.commit()
    db.refresh(benefit)
    return benefit


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


def create_benefit_payload(plan):
    return {
        "plan_id": str(plan.id),
        "name": "Funeral Cover",
        "description": "Standard funeral benefit",
        "benefit_type": "monetary",
        "monetary_limit": "15000.00",
        "quantity_limit": None,
        "is_included": True,
        "is_active": True,
    }


def test_staff_with_view_permission_can_list_benefits(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.view")

    plan = create_plan(db, test_data["business_a"])
    create_benefit(db, test_data["business_a"], plan)

    response = client.get(
        "/membership-plan-benefits",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Funeral Cover"


def test_staff_without_view_permission_cannot_list_benefits(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.view")

    plan = create_plan(db, test_data["business_a"])
    create_benefit(db, test_data["business_a"], plan)

    response = client.get(
        "/membership-plan-benefits",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.view"
    )


def test_staff_with_view_permission_can_get_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.view")

    plan = create_plan(db, test_data["business_a"])
    benefit = create_benefit(db, test_data["business_a"], plan)

    response = client.get(
        f"/membership-plan-benefits/{benefit.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(benefit.id)


def test_staff_with_manage_permission_can_create_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.manage")

    plan = create_plan(db, test_data["business_a"])

    response = client.post(
        "/membership-plan-benefits",
        headers=auth_headers(test_data["staff"]),
        json=create_benefit_payload(plan),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Funeral Cover"

    benefit = (
        db.query(MembershipPlanBenefit)
        .filter(
            MembershipPlanBenefit.business_id
            == test_data["business_a"].id,
            MembershipPlanBenefit.name == "Funeral Cover",
        )
        .first()
    )
    assert benefit is not None


def test_staff_without_manage_permission_cannot_create_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.manage")

    plan = create_plan(db, test_data["business_a"])

    response = client.post(
        "/membership-plan-benefits",
        headers=auth_headers(test_data["staff"]),
        json=create_benefit_payload(plan),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.manage"
    )


def test_staff_with_manage_permission_can_update_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.manage")

    plan = create_plan(db, test_data["business_a"])
    benefit = create_benefit(db, test_data["business_a"], plan)

    response = client.patch(
        f"/membership-plan-benefits/{benefit.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "name": "Enhanced Funeral Cover",
            "monetary_limit": "20000.00",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Enhanced Funeral Cover"
    assert response.json()["monetary_limit"] == "20000.00"


def test_staff_without_manage_permission_cannot_update_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.manage")

    plan = create_plan(db, test_data["business_a"])
    benefit = create_benefit(db, test_data["business_a"], plan)

    response = client.patch(
        f"/membership-plan-benefits/{benefit.id}",
        headers=auth_headers(test_data["staff"]),
        json={"name": "Not Allowed"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.manage"
    )


def test_staff_with_manage_permission_can_delete_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "membership_plans.manage")

    plan = create_plan(db, test_data["business_a"])
    benefit = create_benefit(db, test_data["business_a"], plan)

    response = client.delete(
        f"/membership-plan-benefits/{benefit.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204

    deleted = (
        db.query(MembershipPlanBenefit)
        .filter(MembershipPlanBenefit.id == benefit.id)
        .first()
    )
    assert deleted is None


def test_staff_without_manage_permission_cannot_delete_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "membership_plans.manage")

    plan = create_plan(db, test_data["business_a"])
    benefit = create_benefit(db, test_data["business_a"], plan)

    response = client.delete(
        f"/membership-plan-benefits/{benefit.id}",
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

    plan = create_plan(db, test_data["business_a"])
    create_benefit(db, test_data["business_a"], plan)

    response = client.get(
        "/membership-plan-benefits",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: membership_plans.view"
    )


def test_other_business_cannot_access_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "manager", "membership_plans.view")

    plan = create_plan(db, test_data["business_a"])
    benefit = create_benefit(db, test_data["business_a"], plan)

    response = client.get(
        f"/membership-plan-benefits/{benefit.id}",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership plan benefit not found"
