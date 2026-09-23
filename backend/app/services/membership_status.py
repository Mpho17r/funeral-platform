from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution


UNPAID_CONTRIBUTION_STATUSES = {
    "due",
    "partially_paid",
    "overdue",
}


def get_membership_contributions(
    db: Session,
    membership: Membership,
) -> list[MembershipContribution]:
    return list(
        db.scalars(
            select(MembershipContribution)
            .where(
                MembershipContribution.membership_id == membership.id,
                MembershipContribution.business_id == membership.business_id,
            )
            .order_by(
                MembershipContribution.due_date.asc(),
                MembershipContribution.contribution_period.asc(),
            )
        ).all()
    )


def get_oldest_unpaid_contribution(
    db: Session,
    membership: Membership,
    today: date,
) -> MembershipContribution | None:
    contributions = get_membership_contributions(
        db,
        membership,
    )

    for contribution in contributions:
        # A future contribution cannot put a membership into arrears.
        if contribution.due_date > today:
            continue

        if (
            contribution.status in UNPAID_CONTRIBUTION_STATUSES
            and contribution.amount_paid < contribution.amount_due
        ):
            return contribution

    return None


def recalculate_membership_status(
    db: Session,
    membership: Membership,
    today: date | None = None,
) -> Membership:
    """
    Recalculate membership status from contribution records
    and the business cover policy.
    """

    today = today or date.today()

    business = db.scalar(
        select(Business).where(
            Business.id == membership.business_id,
        )
    )

    if not business:
        return membership

    # Cancelled memberships remain cancelled.
    if membership.status == "cancelled":
        return membership

    oldest_unpaid = get_oldest_unpaid_contribution(
        db,
        membership,
        today,
    )

    # No contribution is currently overdue/unpaid.
    if oldest_unpaid is None:
        membership.arrears_since = None

        # Previously lapsed memberships require the configured
        # reinstatement policy to determine what happens next.
        if membership.lapsed_at is not None:
            if business.reinstatement_policy == "automatic":
                membership.status = "active"
                membership.lapsed_at = None

            elif business.reinstatement_policy == "manual":
                membership.status = "lapsed"

            else:
                # not_allowed
                membership.status = "lapsed"

            return membership

        membership.status = "active"

        return membership

    # The membership entered arrears on the due date of the
    # oldest unpaid contribution.
    membership.arrears_since = oldest_unpaid.due_date

    days_in_arrears = (
        today - oldest_unpaid.due_date
    ).days

    if days_in_arrears >= business.lapse_after_days:
        membership.status = "lapsed"

        if membership.lapsed_at is None:
            membership.lapsed_at = today

        return membership

    membership.status = "arrears"

    return membership


def is_membership_covered(
    db: Session,
    membership: Membership,
    today: date | None = None,
) -> bool:
    """
    Determine whether the membership currently has funeral cover.

    Coverage rules:
    - active memberships are covered.
    - cancelled and lapsed memberships are not covered.
    - during arrears, cover depends on the business policy.
    - when cover_during_arrears is False, cover continues only
      through the configured grace period.
    """

    today = today or date.today()

    membership = recalculate_membership_status(
        db,
        membership,
        today=today,
    )

    if membership.status in {"cancelled", "lapsed"}:
        return False

    if membership.status == "active":
        return True

    if membership.status == "arrears":
        business = db.scalar(
            select(Business).where(
                Business.id == membership.business_id,
            )
        )

        if not business:
            return False

        # Business explicitly keeps members covered throughout arrears.
        if business.cover_during_arrears:
            return True

        # Otherwise, cover continues only during the grace period.
        if membership.arrears_since is None:
            return False

        days_in_arrears = (
            today - membership.arrears_since
        ).days

        return days_in_arrears < business.grace_period_days

    return False
