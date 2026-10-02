from datetime import date
from decimal import Decimal
from threading import Barrier, Thread
from uuid import uuid4

from fastapi import HTTPException
from app.api.membership_payments import (
    create_membership_payment,
    update_membership_payment,
)
from app.schemas.membership_payment import (
    MembershipPaymentCreate,
    MembershipPaymentUpdate,
)

from sqlalchemy import func, select

from tests.conftest import TestingSessionLocal

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


def test_concurrent_membership_payment_updates_with_duplicate_reference_return_conflict(
    db,
    test_data,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    first_payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="UPDATE-RACE-001",
        payment_date=date(2026, 9, 15),
    )

    second_payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="UPDATE-RACE-002",
        payment_date=date(2026, 9, 15),
    )

    db.add_all([first_payment, second_payment])
    db.commit()
    db.refresh(first_payment)
    db.refresh(second_payment)

    payment_ids = [
        first_payment.id,
        second_payment.id,
    ]

    barrier = Barrier(2)
    results = []
    errors = []

    def worker(payment_id):
        session = TestingSessionLocal()

        try:
            barrier.wait()

            update_membership_payment(
                db=session,
                payment_id=payment_id,
                payload=MembershipPaymentUpdate(
                    reference="UPDATE-RACE-SHARED",
                ),
                current_user={
                    "user_id": str(test_data["main_admin"].id),
                    "business_id": str(test_data["business_a"].id),
                    "role": "main_admin",
                },
            )

            session.commit()
            results.append(payment_id)

        except Exception as exc:
            session.rollback()
            errors.append(exc)

        finally:
            session.close()

    threads = [
        Thread(
            target=worker,
            args=(payment_id,),
        )
        for payment_id in payment_ids
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(results) == 1
    assert len(errors) == 1

    error = errors[0]

    assert isinstance(error, HTTPException)
    assert error.status_code == 409
    assert error.detail == (
        "A payment with this reference already exists."
    )

    verification_session = TestingSessionLocal()

    try:
        matching_payments = verification_session.scalars(
            select(MembershipPayment).where(
                MembershipPayment.business_id
                == test_data["business_a"].id,
                MembershipPayment.reference
                == "UPDATE-RACE-SHARED",
            )
        ).all()

        assert len(matching_payments) == 1

    finally:
        verification_session.close()


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

def test_payment_completion_automatically_reinstates_lapsed_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    business = test_data["business_a"]
    business.reinstatement_policy = "automatic"
    business.lapse_after_days = 60

    today = date.today()
    membership.status = "lapsed"
    membership.lapsed_at = today
    contribution.due_date = date.fromordinal(today.toordinal() - 10)
    contribution.status = "overdue"

    db.commit()

    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "500.00",
            "payment_method": "eft",
            "reference": f"AUTO-{uuid4().hex[:8]}",
            "payment_date": str(today),
        },
    )

    assert response.status_code == 201, response.text

    db.refresh(membership)
    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("500.00")
    assert contribution.status == "paid"
    assert membership.status == "active"
    assert membership.lapsed_at is None


def test_payment_completion_does_not_automatically_reinstate_manual_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    business = test_data["business_a"]
    business.reinstatement_policy = "manual"
    business.lapse_after_days = 60

    today = date.today()
    membership.status = "lapsed"
    membership.lapsed_at = today
    contribution.due_date = date.fromordinal(today.toordinal() - 10)
    contribution.status = "overdue"

    db.commit()

    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "500.00",
            "payment_method": "eft",
            "reference": f"MANUAL-{uuid4().hex[:8]}",
            "payment_date": str(today),
        },
    )

    assert response.status_code == 201, response.text

    db.refresh(membership)
    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("500.00")
    assert contribution.status == "paid"
    assert membership.status == "lapsed"
    assert membership.lapsed_at == today


def test_payment_completion_does_not_reinstate_not_allowed_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    business = test_data["business_a"]
    business.reinstatement_policy = "not_allowed"
    business.lapse_after_days = 60

    today = date.today()
    membership.status = "lapsed"
    membership.lapsed_at = today
    contribution.due_date = date.fromordinal(today.toordinal() - 10)
    contribution.status = "overdue"

    db.commit()

    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "500.00",
            "payment_method": "eft",
            "reference": f"NOAUTO-{uuid4().hex[:8]}",
            "payment_date": str(today),
        },
    )

    assert response.status_code == 201, response.text

    db.refresh(membership)
    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("500.00")
    assert contribution.status == "paid"
    assert membership.status == "lapsed"
    assert membership.lapsed_at == today


def test_deleting_final_membership_payment_recalculates_membership_status(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    business = test_data["business_a"]
    business.lapse_after_days = 60

    today = date.today()
    contribution.due_date = date.fromordinal(today.toordinal() - 1)
    contribution.status = "overdue"

    db.commit()

    headers = auth_headers(test_data["main_admin"])

    create_response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": str(contribution.id),
            "amount": "500.00",
            "payment_method": "eft",
            "reference": f"DELETE-{uuid4().hex[:8]}",
            "payment_date": str(today),
        },
    )

    assert create_response.status_code == 201, create_response.text

    payment_id = create_response.json()["id"]

    db.refresh(membership)
    db.refresh(contribution)

    assert contribution.status == "paid"
    assert membership.status == "active"

    delete_response = client.delete(
        f"/membership-payments/{payment_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204, delete_response.text

    db.refresh(membership)
    db.refresh(contribution)

    assert contribution.amount_paid == Decimal("0.00")
    assert contribution.status == "overdue"
    assert contribution.paid_at is None
    assert membership.status == "arrears"

def test_concurrent_membership_payments_cannot_overpay_contribution(
    db,
    test_data,
):

    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    barrier = Barrier(2)
    results = []
    errors = []

    def worker(worker_number):
        session = TestingSessionLocal()

        try:
            payload = MembershipPaymentCreate(
                membership_id=membership.id,
                contribution_id=contribution.id,
                amount=Decimal("500.00"),
                payment_method="eft",
                reference=f"CONCURRENT-{worker_number}",
                payment_date=date.today(),
                notes="Concurrent payment regression test",
            )

            barrier.wait()

            result = create_membership_payment(
                payload=payload,
                db=session,
                current_user={
                    "user_id": str(test_data["main_admin"].id),
                    "business_id": str(test_data["business_a"].id),
                    "role": "main_admin",
                },
            )

            results.append(result.id)

        except Exception as exc:
            session.rollback()
            errors.append(exc)

        finally:
            session.close()

    thread_a = Thread(target=worker, args=(1,))
    thread_b = Thread(target=worker, args=(2,))

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert len(results) == 1
    assert len(errors) == 1

    total_paid = db.scalar(
        select(
            func.coalesce(
                func.sum(MembershipPayment.amount),
                Decimal("0.00"),
            )
        ).where(
            MembershipPayment.contribution_id == contribution.id,
            MembershipPayment.business_id == test_data["business_a"].id,
        )
    )

    assert Decimal(str(total_paid or "0.00")) == Decimal("500.00")


def test_concurrent_membership_payment_updates_cannot_overpay_contribution(
    db,
    test_data,
):
    from app.api.membership_payments import update_membership_payment
    from app.schemas.membership_payment import MembershipPaymentUpdate

    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    contribution.amount_due = Decimal("1000.00")

    payment_a = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("250.00"),
        payment_method="eft",
        reference="UPDATE-CONCURRENT-A",
        payment_date=date.today(),
    )

    payment_b = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("250.00"),
        payment_method="eft",
        reference="UPDATE-CONCURRENT-B",
        payment_date=date.today(),
    )

    db.add_all([payment_a, payment_b])
    db.commit()

    barrier = Barrier(2)
    results = []
    errors = []

    def worker(payment_id):
        session = TestingSessionLocal()

        try:
            payload = MembershipPaymentUpdate(
                amount=Decimal("750.00"),
            )

            barrier.wait()

            result = update_membership_payment(
                payment_id=payment_id,
                payload=payload,
                db=session,
                current_user={
                    "user_id": str(test_data["main_admin"].id),
                    "business_id": str(test_data["business_a"].id),
                    "role": "main_admin",
                },
            )

            results.append(result.id)

        except Exception as exc:
            session.rollback()
            errors.append(exc)

        finally:
            session.close()

    thread_a = Thread(target=worker, args=(payment_a.id,))
    thread_b = Thread(target=worker, args=(payment_b.id,))

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert len(results) == 1
    assert len(errors) == 1

    total_paid = db.scalar(
        select(
            func.coalesce(
                func.sum(MembershipPayment.amount),
                Decimal("0.00"),
            )
        ).where(
            MembershipPayment.contribution_id == contribution.id,
            MembershipPayment.business_id == test_data["business_a"].id,
        )
    )

    assert Decimal(str(total_paid or "0.00")) == Decimal("1000.00")
def test_concurrent_membership_payments_with_duplicate_reference_return_conflict(
    db,
    test_data,
):
    membership, _ = create_membership_with_contribution(
        db,
        test_data,
    )

    barrier = Barrier(2)
    results = []
    errors = []

    reference = "CONCURRENT-REFERENCE-REPRO"

    def worker(worker_number):
        session = TestingSessionLocal()

        try:
            payload = MembershipPaymentCreate(
                membership_id=membership.id,
                contribution_id=None,
                amount=Decimal("100.00"),
                payment_method="eft",
                reference=reference,
                payment_date=date.today(),
                notes=f"Reference race worker {worker_number}",
            )

            barrier.wait()

            result = create_membership_payment(
                payload=payload,
                db=session,
                current_user={
                    "user_id": str(test_data["main_admin"].id),
                    "business_id": str(test_data["business_a"].id),
                    "role": "main_admin",
                },
            )

            results.append(result.id)

        except Exception as exc:
            session.rollback()
            errors.append(exc)

        finally:
            session.close()

    thread_a = Thread(target=worker, args=(1,))
    thread_b = Thread(target=worker, args=(2,))

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], HTTPException)
    assert errors[0].status_code == 409
    assert errors[0].detail == "A payment with this reference already exists."


def test_membership_payment_list_is_ordered_by_payment_date_desc_then_created_at_desc(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    older = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="ORDER-OLDER",
        payment_date=date(2026, 9, 10),
    )
    newer = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="ORDER-NEWER",
        payment_date=date(2026, 9, 15),
    )
    same_date_later_created = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="ORDER-SAME-DATE",
        payment_date=date(2026, 9, 15),
    )

    db.add(older)
    db.flush()
    db.add(newer)
    db.flush()
    db.add(same_date_later_created)
    db.commit()

    response = client.get(
        "/membership-payments",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text

    references = [
        item["reference"]
        for item in response.json()
        if item["reference"] in {
            "ORDER-OLDER",
            "ORDER-NEWER",
            "ORDER-SAME-DATE",
        }
    ]

    assert references == [
        "ORDER-SAME-DATE",
        "ORDER-NEWER",
        "ORDER-OLDER",
    ]


def test_membership_payment_list_can_filter_by_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, contribution = create_membership_with_contribution(
        db,
        test_data,
    )

    second_contribution = MembershipContribution(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_period=date(2026, 11, 1),
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        due_date=date(2026, 11, 1),
        status="due",
    )
    db.add(second_contribution)
    db.commit()
    db.refresh(second_contribution)

    first_payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="FILTER-CONTRIBUTION-1",
        payment_date=date(2026, 9, 10),
    )
    second_payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=second_contribution.id,
        amount=Decimal("100.00"),
        payment_method="cash",
        reference="FILTER-CONTRIBUTION-2",
        payment_date=date(2026, 9, 11),
    )

    db.add_all([first_payment, second_payment])
    db.commit()

    response = client.get(
        "/membership-payments",
        params={"contribution_id": str(contribution.id)},
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 1
    assert data[0]["reference"] == "FILTER-CONTRIBUTION-1"
    assert data[0]["contribution_id"] == str(contribution.id)


def test_get_nonexistent_membership_payment_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.get(
        f"/membership-payments/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership payment not found."


def test_membership_payment_can_be_created_without_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, _ = create_membership_with_contribution(
        db,
        test_data,
    )

    response = client.post(
        "/membership-payments",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "membership_id": str(membership.id),
            "amount": "150.00",
            "payment_method": "cash",
            "reference": "NO-CONTRIBUTION-001",
            "payment_date": "2026-09-20",
            "notes": "Unallocated membership payment",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["contribution_id"] is None
    assert Decimal(data["amount"]) == Decimal("150.00")
    assert data["reference"] == "NO-CONTRIBUTION-001"


def test_membership_payment_rejects_invalid_payment_method(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, _ = create_membership_with_contribution(
        db,
        test_data,
    )

    response = client.post(
        "/membership-payments",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "membership_id": str(membership.id),
            "amount": "100.00",
            "payment_method": "bitcoin",
        },
    )

    assert response.status_code == 422


def test_membership_payment_rejects_non_positive_amount(
    client,
    db,
    test_data,
    auth_headers,
):
    membership, _ = create_membership_with_contribution(
        db,
        test_data,
    )

    response = client.post(
        "/membership-payments",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "membership_id": str(membership.id),
            "amount": "0.00",
            "payment_method": "cash",
        },
    )

    assert response.status_code == 422
