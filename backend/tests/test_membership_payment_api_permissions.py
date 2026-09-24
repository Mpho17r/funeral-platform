from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.models.membership_payment import MembershipPayment
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def create_membership_with_contribution(db, business):
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
        name="Permission Test Plan",
        description="Membership payment permission test plan",
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
    db.flush()

    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=date(2026, 10, 1),
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        due_date=date(2026, 10, 1),
        status="due",
    )
    db.add(contribution)
    db.commit()

    db.refresh(membership)
    db.refresh(contribution)

    return membership, contribution


def create_payment(
    db,
    business,
    membership,
    contribution=None,
    amount="100.00",
    reference=None,
):
    payment = MembershipPayment(
        business_id=business.id,
        membership_id=membership.id,
        contribution_id=(
            contribution.id if contribution else None
        ),
        amount=Decimal(amount),
        payment_method="cash",
        reference=reference,
        payment_date=date.today(),
        notes=None,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


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

    if existing is None:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )
        db.commit()


def test_staff_with_payments_view_can_list_membership_payments(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.view")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        reference="MEM-LIST-001",
    )

    response = client.get(
        "/membership-payments",
        params={"membership_id": str(membership.id)},
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["reference"] == "MEM-LIST-001"


def test_staff_without_payments_view_cannot_list_membership_payments(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.view")

    membership, _ = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    response = client.get(
        "/membership-payments",
        params={"membership_id": str(membership.id)},
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "payments.view" in response.json()["detail"]


def test_staff_with_payments_view_can_get_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.view")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    payment = create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        reference="MEM-GET-001",
    )

    response = client.get(
        f"/membership-payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["reference"] == "MEM-GET-001"


def test_staff_with_payments_create_can_create_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.create")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    response = client.post(
        "/membership-payments",
        headers=auth_headers(test_data["staff"]),
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "250.00",
            "payment_method": "cash",
            "reference": "MEM-CREATE-001",
            "payment_date": str(date.today()),
        },
    )

    assert response.status_code == 201
    assert response.json()["reference"] == "MEM-CREATE-001"
    assert response.json()["amount"] == "250.00"

    db.refresh(contribution)
    assert contribution.amount_paid == Decimal("250.00")
    assert contribution.status == "partially_paid"


def test_staff_without_payments_create_cannot_create_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.create")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    response = client.post(
        "/membership-payments",
        headers=auth_headers(test_data["staff"]),
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "250.00",
            "payment_method": "cash",
            "reference": "MEM-DENY-CREATE-001",
            "payment_date": str(date.today()),
        },
    )

    assert response.status_code == 403
    assert "payments.create" in response.json()["detail"]


def test_staff_with_payments_edit_can_update_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.edit")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    payment = create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        amount="100.00",
        reference="MEM-EDIT-001",
    )

    response = client.patch(
        f"/membership-payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "amount": "300.00",
            "reference": "MEM-EDIT-002",
        },
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "300.00"
    assert response.json()["reference"] == "MEM-EDIT-002"

    db.refresh(contribution)
    assert contribution.amount_paid == Decimal("300.00")


def test_staff_without_payments_edit_cannot_update_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.edit")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    payment = create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        reference="MEM-DENY-EDIT-001",
    )

    response = client.patch(
        f"/membership-payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
        json={"amount": "300.00"},
    )

    assert response.status_code == 403
    assert "payments.edit" in response.json()["detail"]


def test_staff_with_payments_delete_can_delete_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.delete")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    payment = create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        amount="250.00",
        reference="MEM-DELETE-001",
    )

    response = client.delete(
        f"/membership-payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204

    deleted = (
        db.query(MembershipPayment)
        .filter(MembershipPayment.id == payment.id)
        .first()
    )

    assert deleted is None

    db.refresh(contribution)
    assert contribution.amount_paid == Decimal("0.00")
    assert contribution.status == "due"


def test_staff_without_payments_delete_cannot_delete_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.delete")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    payment = create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        reference="MEM-DENY-DELETE-001",
    )

    response = client.delete(
        f"/membership-payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "payments.delete" in response.json()["detail"]

    existing = (
        db.query(MembershipPayment)
        .filter(MembershipPayment.id == payment.id)
        .first()
    )

    assert existing is not None


def test_staff_explicit_deny_overrides_payments_view_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.view")
    deny_permission(
        db,
        test_data["staff"].id,
        "payments.view",
    )

    membership, _ = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    response = client.get(
        "/membership-payments",
        params={"membership_id": str(membership.id)},
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_other_business_cannot_access_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "manager", "payments.view")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    payment = create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        reference="MEM-TENANT-001",
    )

    response = client.get(
        f"/membership-payments/{payment.id}",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404


def test_duplicate_membership_payment_reference_returns_conflict(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.create")

    membership, contribution = create_membership_with_contribution(
        db,
        test_data["business_a"],
    )

    create_payment(
        db,
        test_data["business_a"],
        membership,
        contribution,
        amount="100.00",
        reference="MEM-DUPLICATE-001",
    )

    response = client.post(
        "/membership-payments",
        headers=auth_headers(test_data["staff"]),
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "100.00",
            "payment_method": "cash",
            "reference": "MEM-DUPLICATE-001",
            "payment_date": str(date.today()),
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
