"""Claim workflow rules.

Kept separate from the membership status engine and the coverage
decision engine on purpose: those answer "is this membership covered?"
and "what benefits does this case receive?". This module only decides
what may happen to a claim next, using their answers.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.membership_beneficiary import MembershipBeneficiary
from app.models.membership_claim import MembershipClaim
from app.services.coverage_decision import CoverageDecision


CENT = Decimal("0.01")

HUNDRED = Decimal("100")


CLAIM_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"under_review", "cancelled"},
    "under_review": {"approved", "rejected", "cancelled"},
    "approved": {"paid", "cancelled"},
    "rejected": set(),
    "paid": set(),
    "cancelled": set(),
}


class ClaimError(Exception):
    """A claim rule was violated. Carries an HTTP-friendly status."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def ensure_transition(current: str, target: str) -> None:
    if target not in CLAIM_TRANSITIONS.get(current, set()):
        raise ClaimError(
            409,
            f"A claim that is '{current}' cannot become '{target}'",
        )


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def coverage_snapshot(decision: CoverageDecision) -> dict:
    """JSON-safe record of what the coverage engine said at a moment
    in time."""

    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "covered": decision.covered,
        "reason": decision.reason,
        "plan_id": str(decision.plan_id) if decision.plan_id else None,
        "plan_name": decision.plan_name,
        "benefits": [
            {
                "benefit_id": str(benefit.benefit_id),
                "name": benefit.name,
                "benefit_type": benefit.benefit_type,
                "monetary_limit": (
                    str(benefit.monetary_limit)
                    if benefit.monetary_limit is not None
                    else None
                ),
                "quantity_limit": benefit.quantity_limit,
                "is_included": benefit.is_included,
            }
            for benefit in decision.benefits
        ],
    }


def max_payable(decision: CoverageDecision) -> Decimal | None:
    """Total of the monetary limits of included benefits.

    Returns None when the plan defines no monetary limits, meaning
    there is no cap to enforce.
    """

    limits = [
        Decimal(str(benefit.monetary_limit))
        for benefit in decision.benefits
        if benefit.is_included and benefit.monetary_limit is not None
    ]

    if not limits:
        return None

    return money(sum(limits, Decimal("0")))


def active_beneficiaries(
    db: Session,
    *,
    business_id: UUID,
    membership_id: UUID,
) -> list[MembershipBeneficiary]:
    return (
        db.query(MembershipBeneficiary)
        .filter(
            MembershipBeneficiary.business_id == business_id,
            MembershipBeneficiary.membership_id == membership_id,
            MembershipBeneficiary.is_active.is_(True),
        )
        .order_by(
            MembershipBeneficiary.created_at,
            MembershipBeneficiary.id,
        )
        .all()
    )


def allocated_percent(beneficiaries) -> Decimal:
    return sum(
        (Decimal(str(b.share_percent)) for b in beneficiaries),
        Decimal("0"),
    )


def compute_allocations(
    beneficiaries: list[MembershipBeneficiary],
    amount: Decimal,
) -> list[dict]:
    """Split a payout between beneficiaries by share.

    Rounding never loses or invents money: every beneficiary except
    the last gets their rounded share and the last gets the remainder,
    so the allocations always sum to exactly the payout.

    Returns [] when there are no beneficiaries. Raises ClaimError when
    shares do not total exactly 100%.
    """

    if not beneficiaries:
        return []

    total = allocated_percent(beneficiaries)

    if total != HUNDRED:
        raise ClaimError(
            409,
            "Beneficiary shares must total 100% before a claim can "
            f"be paid (currently {total}%)",
        )

    amount = money(amount)
    allocations = []
    paid_so_far = Decimal("0.00")

    for index, beneficiary in enumerate(beneficiaries):
        is_last = index == len(beneficiaries) - 1

        if is_last:
            share_amount = amount - paid_so_far
        else:
            share_amount = money(
                amount * Decimal(str(beneficiary.share_percent)) / HUNDRED
            )
            paid_so_far += share_amount

        allocations.append(
            {
                "beneficiary_id": str(beneficiary.id),
                "name": f"{beneficiary.first_name} {beneficiary.last_name}",
                "relationship": beneficiary.relationship,
                "share_percent": str(beneficiary.share_percent),
                "amount": str(share_amount),
            }
        )

    return allocations


def next_claim_number(db: Session, business_id: UUID) -> str:
    """Next human-readable claim number for the business, e.g.
    CLM-2026-00007.

    The unique (business_id, claim_number) constraint is the real
    guard; callers retry on a collision.
    """

    year = datetime.now(timezone.utc).year

    existing = (
        db.query(func.count(MembershipClaim.id))
        .filter(MembershipClaim.business_id == business_id)
        .scalar()
    )

    return f"CLM-{year}-{existing + 1:05d}"
