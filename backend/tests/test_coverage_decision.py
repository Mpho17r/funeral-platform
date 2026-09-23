from datetime import date
from decimal import Decimal

from app.models.covered_dependent import CoveredDependent
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit
from app.services.coverage_decision import calculate_case_coverage


def create_membership_fixture(
    db,
    test_data,
    *,
    membership_number="COVER-001",
    member_number="MEM-COVER-001",
):
    member = Member(
        business_id=test_data["business_a"].id,
        member_number=member_number,
        first_name="Coverage",
        last_name="Member",
        join_date=date(2026, 1, 1),
        status="active",
    )

    db.add(member)
    db.flush()

    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name="Coverage Plan",
        description="Coverage test plan",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )

    db.add(plan)
    db.flush()

    membership = Membership(
        business_id=test_data["business_a"].id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=membership_number,
        start_date=date(2026, 1, 1),
        status="active",
        next_due_date=date(2026, 10, 1),
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return member, plan, membership


def create_case(
    db,
    business,
    *,
    membership_id=None,
    covered_dependent_id=None,
    date_of_death=date(2026, 10, 15),
):
    case = FuneralCase(
        business_id=business.id,
        case_number="CASE-COVER-001",
        membership_id=membership_id,
        covered_dependent_id=covered_dependent_id,
        deceased_full_name="Coverage Test Person",
        date_of_death=date_of_death,
        status="open",
    )

    db.add(case)
    db.commit()
    db.refresh(case)

    return case


def create_benefit(
    db,
    business,
    plan,
    *,
    name="Funeral Cover",
    benefit_type="monetary",
    monetary_limit=Decimal("15000.00"),
    quantity_limit=None,
):
    benefit = MembershipPlanBenefit(
        business_id=business.id,
        plan_id=plan.id,
        name=name,
        description="Coverage test benefit",
        benefit_type=benefit_type,
        monetary_limit=monetary_limit,
        quantity_limit=quantity_limit,
        is_included=True,
        is_active=True,
    )

    db.add(benefit)
    db.commit()
    db.refresh(benefit)

    return benefit


def create_paid_contribution(
    db,
    business,
    membership,
):
    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=date(2026, 10, 1),
        amount_due=Decimal("200.00"),
        amount_paid=Decimal("200.00"),
        due_date=date(2026, 10, 1),
        status="paid",
        paid_at=date(2026, 10, 1),
    )

    db.add(contribution)
    db.commit()
    db.refresh(contribution)

    return contribution


def test_covered_member_gets_plan_benefits(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
    )

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is True
    assert decision.membership_id == membership.id
    assert decision.plan_id == plan.id
    assert decision.plan_name == "Coverage Plan"
    assert len(decision.benefits) == 1
    assert decision.benefits[0].name == "Funeral Cover"
    assert decision.benefits[0].benefit_type == "monetary"
    assert decision.benefits[0].monetary_limit == Decimal("15000.00")


def test_private_case_is_not_membership_covered(
    db,
    test_data,
):
    case = create_case(
        db,
        test_data["business_a"],
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is False
    assert decision.membership_id is None
    assert decision.benefits == []


def test_uncovered_membership_is_not_covered(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-002",
        member_number="MEM-COVER-002",
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
    )

    # Create an unpaid contribution far enough in the past
    # for the existing membership-status engine to determine
    # that the membership has lapsed.
    contribution = MembershipContribution(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_period=date(2026, 7, 1),
        amount_due=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        due_date=date(2026, 7, 1),
        status="overdue",
        paid_at=None,
    )

    db.add(contribution)
    db.commit()

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
        date_of_death=date(2026, 10, 15),
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is False
    assert decision.benefits == []
    assert "not covered" in decision.reason


def test_quantity_benefit_is_returned(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-003",
        member_number="MEM-COVER-003",
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
        name="Hearse Trips",
        benefit_type="quantity",
        monetary_limit=None,
        quantity_limit=2,
    )

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is True
    assert len(decision.benefits) == 1
    assert decision.benefits[0].benefit_type == "quantity"
    assert decision.benefits[0].quantity_limit == 2


def test_multiple_active_benefits_are_returned(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-004",
        member_number="MEM-COVER-004",
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
        name="Funeral Cover",
        benefit_type="monetary",
        monetary_limit=Decimal("15000.00"),
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
        name="Standard Coffin",
        benefit_type="included_service",
        monetary_limit=None,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
        name="Hearse Trips",
        benefit_type="quantity",
        monetary_limit=None,
        quantity_limit=2,
    )

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is True
    assert len(decision.benefits) == 3

    names = [benefit.name for benefit in decision.benefits]

    assert names == [
        "Funeral Cover",
        "Standard Coffin",
        "Hearse Trips",
    ]


def test_inactive_benefits_are_not_returned(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-005",
        member_number="MEM-COVER-005",
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    active_benefit = create_benefit(
        db,
        test_data["business_a"],
        plan,
        name="Active Benefit",
    )

    inactive_benefit = create_benefit(
        db,
        test_data["business_a"],
        plan,
        name="Inactive Benefit",
    )

    inactive_benefit.is_active = False
    db.commit()

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is True
    assert len(decision.benefits) == 1
    assert decision.benefits[0].benefit_id == active_benefit.id


def test_dependent_must_belong_to_membership(
    db,
    test_data,
):
    _, plan, membership_a = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-006",
        member_number="MEM-COVER-006",
    )

    _, _, membership_b = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-007",
        member_number="MEM-COVER-007",
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership_a,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
    )

    dependent = CoveredDependent(
        business_id=test_data["business_a"].id,
        membership_id=membership_b.id,
        first_name="Wrong",
        last_name="Membership",
        relationship="child",
        status="active",
        cover_start_date=date(2026, 1, 1),
    )

    db.add(dependent)
    db.commit()
    db.refresh(dependent)

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership_a.id,
        covered_dependent_id=dependent.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is False
    assert "does not belong" in decision.reason


def test_active_dependent_can_be_covered(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-008",
        member_number="MEM-COVER-008",
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
    )

    dependent = CoveredDependent(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        first_name="Covered",
        last_name="Dependent",
        relationship="child",
        status="active",
        cover_start_date=date(2026, 1, 1),
    )

    db.add(dependent)
    db.commit()
    db.refresh(dependent)

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
        covered_dependent_id=dependent.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is True
    assert decision.covered_dependent_id == dependent.id
    assert len(decision.benefits) == 1


def test_expired_dependent_is_not_covered(
    db,
    test_data,
):
    _, plan, membership = create_membership_fixture(
        db,
        test_data,
        membership_number="COVER-009",
        member_number="MEM-COVER-009",
    )

    create_paid_contribution(
        db,
        test_data["business_a"],
        membership,
    )

    create_benefit(
        db,
        test_data["business_a"],
        plan,
    )

    dependent = CoveredDependent(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        first_name="Expired",
        last_name="Dependent",
        relationship="child",
        status="active",
        cover_start_date=date(2026, 1, 1),
        cover_end_date=date(2026, 9, 30),
    )

    db.add(dependent)
    db.commit()
    db.refresh(dependent)

    case = create_case(
        db,
        test_data["business_a"],
        membership_id=membership.id,
        covered_dependent_id=dependent.id,
    )

    decision = calculate_case_coverage(
        db,
        case,
        test_data["business_a"].id,
    )

    assert decision.covered is False
    assert "ended" in decision.reason