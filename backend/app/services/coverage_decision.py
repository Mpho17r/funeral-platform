from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.covered_dependent import CoveredDependent
from app.models.funeral_case import FuneralCase
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit
from app.services.membership_status import (
    is_membership_covered,
)


@dataclass
class BenefitCoverage:
    benefit_id: UUID
    name: str
    description: str | None
    benefit_type: str
    monetary_limit: Decimal | None
    quantity_limit: int | None
    is_included: bool
    is_active: bool


@dataclass
class CoverageDecision:
    case_id: UUID
    membership_id: UUID | None
    covered_dependent_id: UUID | None
    covered: bool
    reason: str
    plan_id: UUID | None
    plan_name: str | None
    benefits: list[BenefitCoverage]


def get_case_for_business(
    db: Session,
    case_id: UUID,
    business_id: UUID,
) -> FuneralCase | None:
    return db.scalar(
        select(FuneralCase).where(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
    )


def get_membership_for_business(
    db: Session,
    membership_id: UUID,
    business_id: UUID,
) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
    )


def get_dependent_for_business(
    db: Session,
    dependent_id: UUID,
    business_id: UUID,
) -> CoveredDependent | None:
    return db.scalar(
        select(CoveredDependent).where(
            CoveredDependent.id == dependent_id,
            CoveredDependent.business_id == business_id,
        )
    )


def get_plan_for_business(
    db: Session,
    plan_id: UUID,
    business_id: UUID,
) -> MembershipPlan | None:
    return db.scalar(
        select(MembershipPlan).where(
            MembershipPlan.id == plan_id,
            MembershipPlan.business_id == business_id,
        )
    )


def get_active_plan_benefits(
    db: Session,
    plan_id: UUID,
    business_id: UUID,
) -> list[MembershipPlanBenefit]:
    return list(
        db.scalars(
            select(MembershipPlanBenefit)
            .where(
                MembershipPlanBenefit.plan_id == plan_id,
                MembershipPlanBenefit.business_id == business_id,
                MembershipPlanBenefit.is_active.is_(True),
            )
            .order_by(
                MembershipPlanBenefit.created_at.asc(),
            )
        ).all()
    )


def get_coverage_date(
    case: FuneralCase,
) -> date:
    """
    Determine which date is used to evaluate coverage.

    Date of death is the primary coverage date because funeral
    cover is intended to apply to the insured person's death.

    If date of death is unavailable, fall back to funeral date,
    then today's date.
    """

    if case.date_of_death is not None:
        return case.date_of_death

    if case.funeral_date is not None:
        return case.funeral_date

    return date.today()


def validate_dependent_for_case(
    db: Session,
    dependent: CoveredDependent,
    membership: Membership,
    coverage_date: date,
) -> tuple[bool, str]:
    """
    Confirm that the dependent belongs to the membership and
    was actively covered on the relevant case date.
    """

    if dependent.membership_id != membership.id:
        return (
            False,
            "Covered dependent does not belong to the case membership.",
        )

    if dependent.status != "active":
        return (
            False,
            "Covered dependent is not active.",
        )

    if coverage_date < dependent.cover_start_date:
        return (
            False,
            "Covered dependent cover had not started on the case date.",
        )

    if (
        dependent.cover_end_date is not None
        and coverage_date > dependent.cover_end_date
    ):
        return (
            False,
            "Covered dependent cover had ended on the case date.",
        )

    return True, "Covered dependent is active on the case date."


def calculate_case_coverage(
    db: Session,
    case: FuneralCase,
    business_id: UUID,
    today: date | None = None,
) -> CoverageDecision:
    """
    Calculate the current coverage position for a funeral case.

    This service is intentionally read/calculation focused.

    It does not:
    - modify CaseFinancial
    - create CasePayments
    - create coverage records
    - alter membership contributions

    The membership status service remains the source of truth
    for whether the membership itself is covered.
    """

    coverage_date = get_coverage_date(case)

    # ---------------------------------------------------------
    # Private / non-membership case
    # ---------------------------------------------------------

    if case.membership_id is None:
        return CoverageDecision(
            case_id=case.id,
            membership_id=None,
            covered_dependent_id=case.covered_dependent_id,
            covered=False,
            reason="This is a private/non-membership funeral case.",
            plan_id=None,
            plan_name=None,
            benefits=[],
        )

    # ---------------------------------------------------------
    # Membership ownership
    # ---------------------------------------------------------

    membership = get_membership_for_business(
        db,
        case.membership_id,
        business_id,
    )

    if membership is None:
        return CoverageDecision(
            case_id=case.id,
            membership_id=case.membership_id,
            covered_dependent_id=case.covered_dependent_id,
            covered=False,
            reason="Membership was not found for this business.",
            plan_id=None,
            plan_name=None,
            benefits=[],
        )

    # ---------------------------------------------------------
    # Membership coverage
    # ---------------------------------------------------------

    covered = is_membership_covered(
        db,
        membership,
        today=coverage_date if today is None else today,
    )

    if not covered:
        return CoverageDecision(
            case_id=case.id,
            membership_id=membership.id,
            covered_dependent_id=case.covered_dependent_id,
            covered=False,
            reason="Membership is not covered on the relevant case date.",
            plan_id=membership.plan_id,
            plan_name=None,
            benefits=[],
        )

    # ---------------------------------------------------------
    # Dependent validation
    # ---------------------------------------------------------

    if case.covered_dependent_id is not None:
        dependent = get_dependent_for_business(
            db,
            case.covered_dependent_id,
            business_id,
        )

        if dependent is None:
            return CoverageDecision(
                case_id=case.id,
                membership_id=membership.id,
                covered_dependent_id=case.covered_dependent_id,
                covered=False,
                reason="Covered dependent was not found for this business.",
                plan_id=membership.plan_id,
                plan_name=None,
                benefits=[],
            )

        dependent_valid, dependent_reason = validate_dependent_for_case(
            db,
            dependent,
            membership,
            coverage_date,
        )

        if not dependent_valid:
            return CoverageDecision(
                case_id=case.id,
                membership_id=membership.id,
                covered_dependent_id=dependent.id,
                covered=False,
                reason=dependent_reason,
                plan_id=membership.plan_id,
                plan_name=None,
                benefits=[],
            )

    # ---------------------------------------------------------
    # Membership plan
    # ---------------------------------------------------------

    plan = get_plan_for_business(
        db,
        membership.plan_id,
        business_id,
    )

    if plan is None:
        return CoverageDecision(
            case_id=case.id,
            membership_id=membership.id,
            covered_dependent_id=case.covered_dependent_id,
            covered=False,
            reason="Membership plan was not found for this business.",
            plan_id=membership.plan_id,
            plan_name=None,
            benefits=[],
        )

    if not plan.is_active:
        return CoverageDecision(
            case_id=case.id,
            membership_id=membership.id,
            covered_dependent_id=case.covered_dependent_id,
            covered=False,
            reason="Membership plan is inactive.",
            plan_id=plan.id,
            plan_name=plan.name,
            benefits=[],
        )

    # ---------------------------------------------------------
    # Benefits
    # ---------------------------------------------------------

    benefits = get_active_plan_benefits(
        db,
        plan.id,
        business_id,
    )

    benefit_results = [
        BenefitCoverage(
            benefit_id=benefit.id,
            name=benefit.name,
            description=benefit.description,
            benefit_type=benefit.benefit_type,
            monetary_limit=benefit.monetary_limit,
            quantity_limit=benefit.quantity_limit,
            is_included=benefit.is_included,
            is_active=benefit.is_active,
        )
        for benefit in benefits
    ]

    return CoverageDecision(
        case_id=case.id,
        membership_id=membership.id,
        covered_dependent_id=case.covered_dependent_id,
        covered=True,
        reason="Membership and applicable dependent coverage are valid.",
        plan_id=plan.id,
        plan_name=plan.name,
        benefits=benefit_results,
    )
