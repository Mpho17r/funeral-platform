from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.services.membership_status import (
    get_oldest_unpaid_contribution,
    is_membership_covered,
    recalculate_membership_status,
)


def make_membership(
    db,
    business,
    *,
    status="active",
    lapsed_at=None,
):
    member = Member(
        business_id=business.id,
        member_number=f"EDGE-M-{uuid4().hex[:8]}",
        first_name="Edge",
        last_name="Case",
        join_date=date(2026, 1, 1),
        status="active",
    )
    plan = MembershipPlan(
        business_id=business.id,
        name=f"Edge Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add_all([member, plan])
    db.flush()

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"EDGE-MS-{uuid4().hex[:8]}",
        start_date=date(2026, 1, 1),
        status=status,
        next_due_date=date(2026, 12, 1),
        lapsed_at=lapsed_at,
    )
    db.add(membership)
    db.flush()
    return membership


def add_contribution(
    db,
    business,
    membership,
    *,
    due_date,
    amount_due=Decimal("200.00"),
    amount_paid=Decimal("0.00"),
    status="due",
):
    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=due_date.replace(day=1),
        amount_due=amount_due,
        amount_paid=amount_paid,
        due_date=due_date,
        status=status,
    )
    db.add(contribution)
    db.flush()
    return contribution


def test_future_unpaid_contribution_does_not_put_membership_into_arrears(
    db,
    test_data,
):
    business = test_data["business_a"]
    membership = make_membership(db, business)

    contribution = add_contribution(
        db,
        business,
        membership,
        due_date=date(2026, 12, 15),
        status="due",
    )

    oldest = get_oldest_unpaid_contribution(
        db,
        membership,
        today=date(2026, 12, 1),
    )

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2026, 12, 1),
    )

    assert oldest is None
    assert result.status == "active"
    assert result.arrears_since is None
    assert contribution.amount_paid == Decimal("0.00")


def test_partial_payment_keeps_membership_in_arrears_until_fully_paid(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.lapse_after_days = 90

    membership = make_membership(db, business)
    contribution = add_contribution(
        db,
        business,
        membership,
        due_date=date(2026, 10, 1),
        amount_paid=Decimal("100.00"),
        status="partially_paid",
    )

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2026, 10, 15),
    )

    assert result.status == "arrears"
    assert result.arrears_since == date(2026, 10, 1)
    assert contribution.amount_paid < contribution.amount_due


def test_membership_lapses_one_day_after_threshold_not_before(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.lapse_after_days = 90

    membership = make_membership(db, business)
    add_contribution(
        db,
        business,
        membership,
        due_date=date(2026, 10, 1),
        status="overdue",
    )

    before = recalculate_membership_status(
        db,
        membership,
        today=date(2026, 12, 29),
    )

    assert before.status == "arrears"
    assert before.lapsed_at is None

    after = recalculate_membership_status(
        db,
        membership,
        today=date(2026, 12, 30),
    )

    assert after.status == "lapsed"
    assert after.lapsed_at == date(2026, 12, 30)


def test_grace_period_zero_removes_arrears_cover_immediately(
    db,
    test_data,
):
    business = test_data["business_a"]
    business.cover_during_arrears = False
    business.grace_period_days = 0
    business.lapse_after_days = 90

    membership = make_membership(db, business)
    add_contribution(
        db,
        business,
        membership,
        due_date=date(2026, 10, 1),
        status="overdue",
    )

    covered = is_membership_covered(
        db,
        membership,
        today=date(2026, 10, 1),
    )

    assert membership.status == "arrears"
    assert covered is False


def test_paid_lapsed_membership_requires_automatic_policy_to_restore(
    db,
    test_data,
):
    business = test_data["business_a"]
    membership = make_membership(
        db,
        business,
        status="lapsed",
        lapsed_at=date(2026, 9, 1),
    )
    add_contribution(
        db,
        business,
        membership,
        due_date=date(2026, 8, 1),
        amount_paid=Decimal("200.00"),
        status="paid",
    )

    business.reinstatement_policy = "manual"

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2026, 10, 1),
    )

    assert result.status == "lapsed"
    assert result.lapsed_at == date(2026, 9, 1)
    assert result.arrears_since is None


def test_paid_lapsed_membership_restores_when_automatic(
    db,
    test_data,
):
    business = test_data["business_a"]
    membership = make_membership(
        db,
        business,
        status="lapsed",
        lapsed_at=date(2026, 9, 1),
    )
    add_contribution(
        db,
        business,
        membership,
        due_date=date(2026, 8, 1),
        amount_paid=Decimal("200.00"),
        status="paid",
    )

    business.reinstatement_policy = "automatic"

    result = recalculate_membership_status(
        db,
        membership,
        today=date(2026, 10, 1),
    )

    assert result.status == "active"
    assert result.lapsed_at is None
    assert result.arrears_since is None
