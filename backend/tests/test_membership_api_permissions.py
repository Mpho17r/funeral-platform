from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def create_membership(db, business, *, status="active"):
    member = Member(
        business_id=business.id,
        member_number=f"TEST-M-{uuid4().hex[:8]}",
        first_name="Permission",
        last_name="Test",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Permission Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )

    db.add_all([member, plan])
    db.flush()

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"TEST-MS-{uuid4().hex[:8]}",
        start_date=date(2026, 1, 1),
        status=status,
        next_due_date=date(2026, 10, 1),
    )

    db.add(membership)
    db.flush()

    return membership


def create_lapsed_membership(db, business):
    membership = create_membership(
        db,
        business,
        status="lapsed",
    )

    membership.lapsed_at = date(2026, 9, 1)

    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=date(2026, 9, 1),
        amount_due=Decimal("200.00"),
        amount_paid=Decimal("200.00"),
        due_date=date(2026, 9, 1),
        status="paid",
        paid_at=date(2026, 9, 1),
    )

    db.add(contribution)
    db.flush()

    return membership


def grant_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .one()
    )

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if not existing:
        db.add(
            RolePermission(
                role=role,
                permission_id=permission.id,
            )
        )
        db.flush()


def revoke_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .one()
    )

    db.query(RolePermission).filter(
        RolePermission.role == role,
        RolePermission.permission_id == permission.id,
    ).delete(synchronize_session=False)

    db.flush()


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .one()
    )

    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

    if existing:
        existing.effect = "deny"
    else:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )

    db.flush()


def test_staff_with_memberships_view_can_list_memberships(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    grant_permission(
        db,
        "staff",
        "memberships.view",
    )
    db.commit()

    response = client.get(
        "/memberships",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200, response.text
    assert any(
        item["id"] == str(membership.id)
        for item in response.json()
    )


def test_staff_without_memberships_view_cannot_list_memberships(
    client,
    db,
    test_data,
    auth_headers,
):
    create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    revoke_permission(
        db,
        "staff",
        "memberships.view",
    )
    db.commit()

    response = client.get(
        "/memberships",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_staff_with_memberships_view_can_get_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    grant_permission(
        db,
        "staff",
        "memberships.view",
    )
    db.commit()

    response = client.get(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(membership.id)


def test_staff_with_memberships_create_can_create_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]

    member = Member(
        business_id=business.id,
        member_number=f"CREATE-M-{uuid4().hex[:8]}",
        first_name="Create",
        last_name="Test",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Create Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )

    db.add_all([member, plan])
    db.flush()

    grant_permission(
        db,
        "staff",
        "memberships.create",
    )
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["staff"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": f"MEM-{uuid4().hex[:8]}",
            "start_date": "2026-09-01",
            "status": "active",
            "next_due_date": "2026-10-01",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["member_id"] == str(member.id)
    assert response.json()["plan_id"] == str(plan.id)


def test_staff_without_memberships_create_cannot_create_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]

    member = Member(
        business_id=business.id,
        member_number=f"NO-CREATE-M-{uuid4().hex[:8]}",
        first_name="No",
        last_name="Create",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"No Create Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )

    db.add_all([member, plan])
    db.flush()

    revoke_permission(
        db,
        "staff",
        "memberships.create",
    )
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["staff"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": f"MEM-{uuid4().hex[:8]}",
            "start_date": "2026-09-01",
            "status": "active",
            "next_due_date": "2026-10-01",
        },
    )

    assert response.status_code == 403


def test_staff_with_memberships_edit_can_update_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    grant_permission(
        db,
        "staff",
        "memberships.edit",
    )
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "next_due_date": "2026-11-01",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["next_due_date"] == "2026-11-01"


def test_staff_without_memberships_edit_cannot_update_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    revoke_permission(
        db,
        "staff",
        "memberships.edit",
    )
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "next_due_date": "2026-11-01",
        },
    )

    assert response.status_code == 403


def test_staff_with_memberships_manage_can_reinstate_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership = create_lapsed_membership(
        db,
        business,
    )
    db.commit()

    grant_permission(
        db,
        "staff",
        "memberships.manage",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"


def test_staff_without_memberships_manage_cannot_reinstate_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership = create_lapsed_membership(
        db,
        business,
    )
    db.commit()

    revoke_permission(
        db,
        "staff",
        "memberships.manage",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_staff_explicit_deny_overrides_memberships_view_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    grant_permission(
        db,
        "staff",
        "memberships.view",
    )
    deny_permission(
        db,
        test_data["staff"].id,
        "memberships.view",
    )
    db.commit()

    response = client.get(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_other_business_cannot_access_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    response = client.get(
        f"/memberships/{membership.id}",
        headers=auth_headers(
            test_data["other_business_manager"]
        ),
    )

    assert response.status_code == 404
