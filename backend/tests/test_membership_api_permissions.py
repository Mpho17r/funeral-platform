from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.audit_log import AuditLog
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.models.membership_payment import MembershipPayment
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



def test_membership_create_rejects_arrears_status(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]

    member = Member(
        business_id=business.id,
        member_number=f"CREATE-ARREARS-M-{uuid4().hex[:8]}",
        first_name="Create",
        last_name="Arrears",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Create Arrears Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )

    db.add_all([member, plan])
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": f"MEM-ARREARS-{uuid4().hex[:8]}",
            "start_date": "2026-09-01",
            "status": "arrears",
            "next_due_date": "2026-10-01",
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "status"
        for error in response.json()["detail"]
    )


def test_membership_create_rejects_lapsed_status(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]

    member = Member(
        business_id=business.id,
        member_number=f"CREATE-LAPSED-M-{uuid4().hex[:8]}",
        first_name="Create",
        last_name="Lapsed",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Create Lapsed Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )

    db.add_all([member, plan])
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": f"MEM-LAPSED-{uuid4().hex[:8]}",
            "start_date": "2026-09-01",
            "status": "lapsed",
            "next_due_date": "2026-10-01",
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "status"
        for error in response.json()["detail"]
    )


def test_membership_create_rejects_cancelled_status(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]

    member = Member(
        business_id=business.id,
        member_number=f"CREATE-CANCELLED-M-{uuid4().hex[:8]}",
        first_name="Create",
        last_name="Cancelled",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Create Cancelled Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )

    db.add_all([member, plan])
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": f"MEM-CANCELLED-{uuid4().hex[:8]}",
            "start_date": "2026-09-01",
            "status": "cancelled",
            "next_due_date": "2026-10-01",
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "status"
        for error in response.json()["detail"]
    )

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


def test_membership_patch_cannot_change_lifecycle_status(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
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
            "status": "cancelled",
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "status"
        for error in response.json()["detail"]
    )


def test_membership_patch_cannot_change_lifecycle_timestamps(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
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
            "lapsed_at": "2026-09-01",
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "lapsed_at"
        for error in response.json()["detail"]
    )


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


def test_main_admin_can_cancel_active_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None
    assert data["arrears_since"] is None
    assert data["lapsed_at"] is None


def test_manager_can_cancel_active_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"


def test_staff_without_memberships_manage_cannot_cancel_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )
    db.commit()

    revoke_permission(
        db,
        "staff",
        "memberships.manage",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_wrong_business_cannot_cancel_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404


def test_already_cancelled_membership_cannot_be_cancelled_again(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="cancelled",
    )
    membership.cancelled_at = date(2026, 9, 1)
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Membership is already cancelled"


def test_cancellation_creates_membership_audit_log(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == test_data["business_a"].id,
            AuditLog.user_id == test_data["main_admin"].id,
            AuditLog.action == "membership.cancelled",
            AuditLog.entity_type == "membership",
            AuditLog.entity_id == membership.id,
        )
        .one()
    )

    assert audit_log.details == {
        "previous_status": "active",
        "new_status": "cancelled",
    }
    assert audit_log.notes == "Membership cancelled."


def test_lapsed_membership_can_be_cancelled(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="lapsed",
    )
    membership.lapsed_at = date(2026, 9, 1)
    membership.arrears_since = date(2026, 8, 1)
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None
    assert data["lapsed_at"] is None
    assert data["arrears_since"] is None


def test_cancelling_membership_does_not_modify_contributions_or_payments(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )

    contribution = MembershipContribution(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_period=date(2026, 10, 1),
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("300.00"),
        due_date=date(2026, 10, 1),
        status="partially_paid",
        paid_at=None,
    )
    db.add(contribution)
    db.flush()

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("300.00"),
        payment_method="eft",
        reference="CANCEL-FINANCIAL-001",
        payment_date=date(2026, 9, 15),
        notes="Payment before cancellation",
    )
    db.add(payment)
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    db.refresh(membership)
    db.refresh(contribution)
    db.refresh(payment)

    assert membership.status == "cancelled"
    assert membership.cancelled_at is not None

    assert contribution.amount_due == Decimal("500.00")
    assert contribution.amount_paid == Decimal("300.00")
    assert contribution.status == "partially_paid"
    assert contribution.paid_at is None

    assert payment.amount == Decimal("300.00")
    assert payment.payment_method == "eft"
    assert payment.reference == "CANCEL-FINANCIAL-001"
    assert payment.contribution_id == contribution.id


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


def test_membership_create_rejects_duplicate_membership_number(
    client,
    db,
    test_data,
    auth_headers,
):
    existing = create_membership(
        db,
        test_data["business_a"],
    )

    member = Member(
        business_id=test_data["business_a"].id,
        member_number=f"TEST-M-{uuid4().hex[:8]}",
        first_name="Duplicate",
        last_name="Number",
        join_date=date(2026, 1, 1),
        status="active",
    )
    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Duplicate Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add_all([member, plan])
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": existing.membership_number,
            "start_date": "2026-10-01",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Membership number already exists"


def test_membership_create_rejects_foreign_business_member(
    client,
    db,
    test_data,
    auth_headers,
):
    foreign_membership = create_membership(
        db,
        test_data["business_b"],
    )

    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Local Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(foreign_membership.member_id),
            "plan_id": str(plan.id),
            "membership_number": f"FOREIGN-MEMBER-{uuid4().hex[:8]}",
            "start_date": "2026-10-01",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"


def test_membership_create_rejects_foreign_business_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    local_membership = create_membership(
        db,
        test_data["business_a"],
    )
    foreign_plan = (
        db.query(MembershipPlan)
        .filter(
            MembershipPlan.business_id == test_data["business_b"].id,
        )
        .first()
    )

    if foreign_plan is None:
        foreign_plan = MembershipPlan(
            business_id=test_data["business_b"].id,
            name=f"Foreign Plan {uuid4().hex[:8]}",
            monthly_contribution=Decimal("200.00"),
            is_active=True,
        )
        db.add(foreign_plan)
        db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(local_membership.member_id),
            "plan_id": str(foreign_plan.id),
            "membership_number": f"FOREIGN-PLAN-{uuid4().hex[:8]}",
            "start_date": "2026-10-01",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership plan not found"


def test_membership_create_rejects_inactive_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    local_membership = create_membership(
        db,
        test_data["business_a"],
    )

    inactive_plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Inactive Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=False,
    )
    db.add(inactive_plan)
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(local_membership.member_id),
            "plan_id": str(inactive_plan.id),
            "membership_number": f"INACTIVE-PLAN-{uuid4().hex[:8]}",
            "start_date": "2026-10-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Cannot create a membership using an inactive plan"
    )


def test_membership_create_rejects_existing_active_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    existing = create_membership(
        db,
        test_data["business_a"],
        status="active",
    )

    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Second Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(existing.member_id),
            "plan_id": str(plan.id),
            "membership_number": f"SECOND-MS-{uuid4().hex[:8]}",
            "start_date": "2026-10-01",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Member already has an active membership"
    )


def test_membership_create_calculates_next_due_date_when_omitted(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )

    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Date Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(membership.member_id),
            "plan_id": str(plan.id),
            "membership_number": f"DATE-MS-{uuid4().hex[:8]}",
            "start_date": "2026-01-31",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Member already has an active membership"
    )


def test_membership_create_calculates_next_due_date_for_new_member(
    client,
    db,
    test_data,
    auth_headers,
):
    member = Member(
        business_id=test_data["business_a"].id,
        member_number=f"TEST-M-{uuid4().hex[:8]}",
        first_name="Due",
        last_name="Date",
        join_date=date(2026, 1, 1),
        status="active",
    )
    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Date Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add_all([member, plan])
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": f"DATE-MS-{uuid4().hex[:8]}",
            "start_date": "2026-01-31",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["next_due_date"] == "2026-02-28"


def test_membership_patch_rejects_duplicate_membership_number(
    client,
    db,
    test_data,
    auth_headers,
):
    first = create_membership(
        db,
        test_data["business_a"],
    )
    second = create_membership(
        db,
        test_data["business_a"],
    )
    db.commit()

    response = client.patch(
        f"/memberships/{second.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "membership_number": first.membership_number,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Membership number already exists"
    )


def test_membership_patch_rejects_foreign_business_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )

    foreign_plan = MembershipPlan(
        business_id=test_data["business_b"].id,
        name=f"Foreign Patch Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add(foreign_plan)
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "plan_id": str(foreign_plan.id),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership plan not found"


def test_membership_patch_rejects_inactive_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(
        db,
        test_data["business_a"],
    )

    inactive_plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name=f"Inactive Patch Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=False,
    )
    db.add(inactive_plan)
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "plan_id": str(inactive_plan.id),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Cannot assign an inactive membership plan"
    )


def test_reinstate_rejects_non_manual_reinstatement_policy(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "automatic"

    membership = create_lapsed_membership(
        db,
        business,
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Manual reinstatement is not enabled for this business"
    )


def test_reinstate_rejects_unpaid_contributions(
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

    unpaid = (
        db.query(MembershipContribution)
        .filter(
            MembershipContribution.membership_id == membership.id,
            MembershipContribution.contribution_period == date(2026, 9, 1),
        )
        .one()
    )
    unpaid.amount_paid = Decimal("0.00")
    unpaid.status = "due"
    unpaid.paid_at = None
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Membership must have no unpaid contributions before reinstatement"
    )


def test_reinstate_clears_lifecycle_dates(
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
    membership.arrears_since = date(2026, 8, 1)
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "active"
    assert data["lapsed_at"] is None
    assert data["arrears_since"] is None


def test_reinstatement_creates_membership_audit_log(
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

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == business.id,
            AuditLog.user_id == test_data["main_admin"].id,
            AuditLog.action == "membership.reinstated",
            AuditLog.entity_type == "membership",
            AuditLog.entity_id == membership.id,
        )
        .one()
    )

    assert audit_log.details == {
        "previous_status": "lapsed",
        "new_status": "active",
    }
    assert audit_log.notes == "Membership manually reinstated."
