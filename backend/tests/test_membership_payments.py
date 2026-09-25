from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.audit_log import AuditLog
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.models.membership_payment import MembershipPayment


def create_membership_with_contribution(db, test_data):
    business = test_data["business_a"]

    member = Member(
        business_id=business.id,
        member_number=f"MEM-{uuid4().hex[:8]}",
        first_name="Test",
        last_name="Member",
        status="active",
    )
    db.add(member)
    db.flush()

    plan = MembershipPlan(
        business_id=business.id,
        name="Standard Plan",
        description="Test membership plan",
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

    return membership, contribution


def test_main_admin_can_create_membership_payment_and_audit_is_created(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "500.00",
            "payment_method": "eft",
            "reference": "PAY-TEST-001",
            "payment_date": "2026-09-15",
            "notes": "September contribution",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["contribution_id"] == str(contribution.id)
    assert Decimal(data["amount"]) == Decimal("500.00")
    assert data["payment_method"] == "eft"
    assert data["reference"] == "PAY-TEST-001"
    assert data["payment_date"] == "2026-09-15"

    payment = (
        db.query(MembershipPayment)
        .filter(MembershipPayment.id == data["id"])
        .one()
    )

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == test_data["business_a"].id,
            AuditLog.user_id == test_data["main_admin"].id,
            AuditLog.action == "membership.payment_created",
            AuditLog.entity_type == "membership_payment",
            AuditLog.entity_id == payment.id,
        )
        .one()
    )

    assert audit_log.details == {
        "amount": "500.00",
        "payment_method": "eft",
        "reference": "PAY-TEST-001",
        "payment_date": "2026-09-15",
        "membership_id": str(membership.id),
        "contribution_id": str(contribution.id),
    }

    assert audit_log.notes == (
        "Membership payment created."
    )


def test_main_admin_can_update_membership_payment_and_audit_records_changes(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("300.00"),
        payment_method="cash",
        reference="PAY-TEST-002",
        payment_date=date(2026, 9, 10),
        notes="Initial payment",
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/membership-payments/{payment.id}",
        headers=headers,
        json={
            "amount": "400.00",
            "payment_method": "eft",
            "reference": "PAY-TEST-002-UPDATED",
            "payment_date": "2026-09-15",
            "notes": "Updated payment",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert Decimal(data["amount"]) == Decimal("400.00")
    assert data["payment_method"] == "eft"
    assert data["reference"] == "PAY-TEST-002-UPDATED"
    assert data["payment_date"] == "2026-09-15"
    assert data["notes"] == "Updated payment"

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == test_data["business_a"].id,
            AuditLog.user_id == test_data["main_admin"].id,
            AuditLog.action == "membership.payment_updated",
            AuditLog.entity_type == "membership_payment",
            AuditLog.entity_id == payment.id,
        )
        .one()
    )

    assert audit_log.details == {
        "changes": {
            "amount": {
                "before": "300.00",
                "after": "400.00",
            },
            "payment_method": {
                "before": "cash",
                "after": "eft",
            },
            "reference": {
                "before": "PAY-TEST-002",
                "after": "PAY-TEST-002-UPDATED",
            },
            "payment_date": {
                "before": "2026-09-10",
                "after": "2026-09-15",
            },
            "notes": {
                "before": "Initial payment",
                "after": "Updated payment",
            },
        }
    }

    assert audit_log.notes == (
        "Membership payment updated."
    )


def test_updating_payment_cannot_overpay_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("300.00"),
        payment_method="cash",
        reference="PAY-UPDATE-OVERPAY-001",
        payment_date=date(2026, 9, 15),
        notes="Initial payment",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/membership-payments/{payment.id}",
        headers=headers,
        json={
            "amount": "600.00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Updated payment would exceed the contribution amount due."
    )

    db.refresh(payment)
    db.refresh(contribution)

    assert payment.amount == Decimal("300.00")
    assert contribution.amount_paid == Decimal("0.00")


def test_updating_payment_cannot_use_duplicate_reference(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    first_payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("200.00"),
        payment_method="cash",
        reference="PAY-REFERENCE-001",
        payment_date=date(2026, 9, 15),
    )

    second_payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="PAY-REFERENCE-002",
        payment_date=date(2026, 9, 15),
    )

    db.add_all([first_payment, second_payment])
    db.commit()
    db.refresh(second_payment)

    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/membership-payments/{second_payment.id}",
        headers=headers,
        json={
            "reference": "PAY-REFERENCE-001",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A payment with this reference already exists."
    )

    db.refresh(second_payment)
    assert second_payment.reference == "PAY-REFERENCE-002"


def test_manager_can_create_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "500.00",
            "payment_method": "cash",
            "reference": "PAY-TEST-003",
            "payment_date": "2026-09-15",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["contribution_id"] == str(contribution.id)
    assert Decimal(data["amount"]) == Decimal("500.00")



def test_manager_can_update_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("300.00"),
        payment_method="cash",
        reference="PAY-TEST-004",
        payment_date=date(2026, 9, 10),
        notes="Initial payment",
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/membership-payments/{payment.id}",
        headers=headers,
        json={
            "amount": "400.00",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert Decimal(data["amount"]) == Decimal("400.00")



def test_payment_updates_contribution_amount_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "300.00",
            "payment_method": "cash",
            "reference": "PAY-TEST-005",
        },
    )

    assert response.status_code == 201, response.text

    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("300.00")
    assert contribution.status == "partially_paid"

    response = client.patch(
        f"/membership-payments/{response.json()['id']}",
        headers=headers,
        json={
            "amount": "500.00",
        },
    )

    assert response.status_code == 200, response.text

    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("500.00")
    assert contribution.status == "paid"

def test_main_admin_can_delete_membership_payment_and_recalculate_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("500.00"),
        payment_method="cash",
        reference="PAY-DELETE-001",
        payment_date=date(2026, 9, 15),
        notes="Payment to delete",
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    headers = auth_headers(test_data["main_admin"])

    response = client.delete(
        f"/membership-payments/{payment.id}",
        headers=headers,
    )

    assert response.status_code == 204, response.text

    deleted_payment = (
        db.query(MembershipPayment)
        .filter(MembershipPayment.id == payment.id)
        .first()
    )

    assert deleted_payment is None

    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("0.00")
    assert contribution.status == "due"
    assert contribution.paid_at is None

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == test_data["business_a"].id,
            AuditLog.user_id == test_data["main_admin"].id,
            AuditLog.action == "membership.payment_deleted",
            AuditLog.entity_type == "membership_payment",
            AuditLog.entity_id == payment.id,
        )
        .one()
    )

    assert audit_log.details == {
        "amount": "500.00",
        "payment_method": "cash",
        "reference": "PAY-DELETE-001",
        "payment_date": "2026-09-15",
        "membership_id": str(membership.id),
        "contribution_id": str(contribution.id),
    }

    assert audit_log.notes == (
        "Membership payment deleted."
    )


def test_manager_can_delete_membership_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("300.00"),
        payment_method="cash",
        reference="PAY-DELETE-002",
        payment_date=date(2026, 9, 15),
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    payment_id = payment.id

    headers = auth_headers(test_data["manager"])

    response = client.delete(
        f"/membership-payments/{payment_id}",
        headers=headers,
    )

    assert response.status_code == 204, response.text

    existing_payment = (
        db.query(MembershipPayment)
        .filter(MembershipPayment.id == payment_id)
        .first()
    )

    assert existing_payment is None

def test_delete_nonexistent_membership_payment_returns_404(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])

    response = client.delete(
        f"/membership-payments/{uuid4()}",
        headers=headers,
    )

    assert response.status_code == 404, response.text
