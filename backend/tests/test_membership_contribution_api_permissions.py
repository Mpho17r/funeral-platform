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


def create_membership(db, business):
    member = Member(
        business_id=business.id,
        member_number=f"MEM-{uuid4().hex[:8]}",
        first_name="Permission",
        last_name="Test Member",
        status="active",
    )
    db.add(member)
    db.flush()

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Permission Plan {uuid4().hex[:6]}",
        description="Membership contribution permission test plan",
        monthly_contribution=Decimal("500.00"),
        is_active=True,
    )
    db.add(plan)
    db.flush()

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"POL-{uuid4().hex[:8]}",
        start_date=date(2026, 9, 1),
        status="active",
        next_due_date=date(2026, 10, 1),
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


def create_contribution(db, business, membership, period="2026-10-01"):
    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=date.fromisoformat(period),
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        due_date=date.fromisoformat(period),
        status="due",
    )
    db.add(contribution)
    db.commit()
    db.refresh(contribution)

    return contribution


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

    (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .delete(synchronize_session=False)
    )
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

    db.commit()


def test_staff_with_contributions_view_can_list_contributions(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    create_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    grant_permission(
        db,
        "staff",
        "contributions.view",
    )

    response = client.get(
        "/membership-contributions",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_staff_without_contributions_view_cannot_list_contributions(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(
        db,
        "staff",
        "contributions.view",
    )

    response = client.get(
        "/membership-contributions",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_staff_with_contributions_view_can_get_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    contribution = create_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    grant_permission(
        db,
        "staff",
        "contributions.view",
    )

    response = client.get(
        f"/membership-contributions/{contribution.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(contribution.id)


def test_staff_with_contributions_create_can_create_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )

    grant_permission(
        db,
        "staff",
        "contributions.create",
    )

    response = client.post(
        "/membership-contributions",
        headers=auth_headers(test_data["staff"]),
        json={
            "membership_id": str(membership.id),
            "contribution_period": "2026-11-01",
            "amount_due": "500.00",
            "due_date": "2026-11-15",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "due"


def test_staff_without_contributions_create_cannot_create_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )

    revoke_permission(
        db,
        "staff",
        "contributions.create",
    )

    response = client.post(
        "/membership-contributions",
        headers=auth_headers(test_data["staff"]),
        json={
            "membership_id": str(membership.id),
            "contribution_period": "2026-11-01",
            "amount_due": "500.00",
            "due_date": "2026-11-15",
        },
    )

    assert response.status_code == 403


def test_staff_with_contributions_edit_can_update_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    contribution = create_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    grant_permission(
        db,
        "staff",
        "contributions.edit",
    )

    response = client.patch(
        f"/membership-contributions/{contribution.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "amount_due": "750.00",
            "due_date": "2026-10-15",
        },
    )

    assert response.status_code == 200
    assert response.json()["amount_due"] == "750.00"
    assert response.json()["due_date"] == "2026-10-15"


def test_staff_without_contributions_edit_cannot_update_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    contribution = create_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    revoke_permission(
        db,
        "staff",
        "contributions.edit",
    )

    response = client.patch(
        f"/membership-contributions/{contribution.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "amount_due": "750.00",
        },
    )

    assert response.status_code == 403


def test_staff_explicit_deny_overrides_contributions_view_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    create_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    grant_permission(
        db,
        "staff",
        "contributions.view",
    )
    deny_permission(
        db,
        test_data["staff"].id,
        "contributions.view",
    )

    response = client.get(
        "/membership-contributions",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_other_business_cannot_access_membership_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )
    contribution = create_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    response = client.get(
        f"/membership-contributions/{contribution.id}",
        headers=auth_headers(
            test_data["other_business_manager"]
        ),
    )

    assert response.status_code == 404


def test_duplicate_membership_contribution_period_returns_conflict(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )

    grant_permission(
        db,
        "staff",
        "contributions.create",
    )

    headers = auth_headers(test_data["staff"])

    first_response = client.post(
        "/membership-contributions",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_period": "2026-12-01",
            "amount_due": "500.00",
            "due_date": "2026-12-15",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/membership-contributions",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_period": "2026-12-01",
            "amount_due": "500.00",
            "due_date": "2026-12-15",
        },
    )

    assert second_response.status_code == 409
