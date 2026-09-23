from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.member import Member
from app.models.audit_log import AuditLog
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.services.membership_status import (
    is_membership_covered,
    recalculate_membership_status,
)


def create_membership_with_contribution(
    db,
    business,
    *,
    membership_status="lapsed",
    lapsed_at=date(2027, 1, 20),
    contribution_status="paid",
    amount_paid=Decimal("200.00"),
    amount_due=Decimal("200.00"),
    due_date=date(2026, 10, 11),
):
    member = Member(
        business_id=business.id,
        member_number=f"TEST-M-{uuid4().hex[:8]}",
        first_name="Test",
        last_name="Member",
        join_date=date(2026, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Test Plan {uuid4().hex[:8]}",
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
        status=membership_status,
        next_due_date=date(2026, 11, 11),
        lapsed_at=lapsed_at,
    )

    db.add(membership)
    db.flush()

    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=date(2026, 10, 1),
        amount_due=amount_due,
        amount_paid=amount_paid,
        due_date=due_date,
        status=contribution_status,
        paid_at=date(2027, 1, 20)
        if contribution_status == "paid"
        else None,
    )

    db.add(contribution)
    db.flush()

    return membership, contribution


def test_automatic_reinstatement(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "automatic"

    membership, _ = create_membership_with_contribution(
        db,
        business,
    )

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert result.status == "active"
    assert result.lapsed_at is None
    assert result.arrears_since is None


def test_manual_reinstatement_keeps_membership_lapsed(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, _ = create_membership_with_contribution(
        db,
        business,
    )

    original_lapsed_at = membership.lapsed_at

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert result.status == "lapsed"
    assert result.lapsed_at == original_lapsed_at
    assert result.arrears_since is None


def test_not_allowed_reinstatement_keeps_membership_lapsed(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "not_allowed"

    membership, _ = create_membership_with_contribution(
        db,
        business,
    )

    original_lapsed_at = membership.lapsed_at

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert result.status == "lapsed"
    assert result.lapsed_at == original_lapsed_at
    assert result.arrears_since is None


def test_cancelled_membership_stays_cancelled(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "automatic"

    membership, _ = create_membership_with_contribution(
        db,
        business,
        membership_status="cancelled",
        lapsed_at=None,
    )

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert result.status == "cancelled"


def test_automatic_reinstatement_restores_cover(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "automatic"

    membership, _ = create_membership_with_contribution(
        db,
        business,
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert membership.status == "active"
    assert membership.lapsed_at is None
    assert covered is True


def test_manual_reinstatement_does_not_restore_cover(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, _ = create_membership_with_contribution(
        db,
        business,
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert membership.status == "lapsed"
    assert covered is False


def test_not_allowed_reinstatement_does_not_restore_cover(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "not_allowed"

    membership, _ = create_membership_with_contribution(
        db,
        business,
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2027, 1, 21),
    )

    assert membership.status == "lapsed"
    assert covered is False


def test_no_cover_during_arrears_but_grace_period_still_covers(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = False
    business.grace_period_days = 30
    business.lapse_after_days = 90

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
        due_date=date(2026, 10, 1),
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 10, 15),
    )

    assert membership.status == "arrears"
    assert membership.arrears_since == date(2026, 10, 1)
    assert covered is True


def test_no_cover_after_grace_period_expires(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = False
    business.grace_period_days = 30
    business.lapse_after_days = 90

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
        due_date=date(2026, 10, 1),
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 10, 31),
    )

    assert membership.status == "arrears"
    assert membership.arrears_since == date(2026, 10, 1)
    assert covered is False


def test_grace_period_boundary_day_29_is_covered(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = False
    business.grace_period_days = 30
    business.lapse_after_days = 90

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
        due_date=date(2026, 10, 1),
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 10, 30),
    )

    assert membership.status == "arrears"
    assert covered is True


def test_grace_period_boundary_day_30_is_not_covered(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = False
    business.grace_period_days = 30
    business.lapse_after_days = 90

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
        due_date=date(2026, 10, 1),
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 10, 31),
    )

    assert membership.status == "arrears"
    assert covered is False


def test_cover_during_arrears_ignores_grace_period(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = True
    business.grace_period_days = 30
    business.lapse_after_days = 90

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
        due_date=date(2026, 10, 1),
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 11, 30),
    )

    assert membership.status == "arrears"
    assert covered is True


def test_membership_lapses_at_lapse_threshold(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = False
    business.grace_period_days = 30
    business.lapse_after_days = 90

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
        due_date=date(2026, 10, 1),
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 12, 30),
    )

    assert membership.status == "lapsed"
    assert membership.lapsed_at == date(2026, 12, 30)
    assert covered is False


def create_lapsed_membership_for_api(
    db,
    business,
    *,
    contribution_status="paid",
    amount_paid=Decimal("200.00"),
    amount_due=Decimal("200.00"),
):
    return create_membership_with_contribution(
        db,
        business,
        membership_status="lapsed",
        lapsed_at=date(2026, 12, 1),
        contribution_status=contribution_status,
        amount_paid=amount_paid,
        amount_due=amount_due,
        due_date=date(2026, 9, 1),
    )


def test_main_admin_can_manually_reinstate_paid_lapsed_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business,
    )
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
    assert audit_log.notes == "Membership manually reinstated by Main Admin."


def test_manager_cannot_manually_reinstate_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business,
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 403
    assert "Main Admin" in response.json()["detail"]


def test_staff_cannot_manually_reinstate_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business,
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "Main Admin" in response.json()["detail"]


def test_wrong_business_cannot_reinstate_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]

    business_a.reinstatement_policy = "manual"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business_a,
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 403


def test_active_membership_cannot_be_reinstated(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, contribution = create_membership_with_contribution(
        db,
        business,
        membership_status="active",
        lapsed_at=None,
        contribution_status="paid",
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only lapsed memberships can be reinstated"


def test_manual_reinstatement_requires_all_contributions_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "manual"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business,
        contribution_status="overdue",
        amount_paid=Decimal("0.00"),
        amount_due=Decimal("200.00"),
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Membership must have no unpaid contributions before reinstatement"
    )


def test_automatic_policy_rejects_manual_reinstatement_endpoint(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "automatic"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business,
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Manual reinstatement is not enabled for this business"
    )


def test_not_allowed_policy_rejects_manual_reinstatement_endpoint(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    business.reinstatement_policy = "not_allowed"

    membership, _ = create_lapsed_membership_for_api(
        db,
        business,
    )
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Manual reinstatement is not enabled for this business"
    )


def test_missing_membership_cannot_be_reinstated(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        f"/memberships/{uuid4()}/reinstate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership not found"
