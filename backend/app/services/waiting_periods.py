"""Waiting-period rules for funeral cover.

Kept apart from the membership status engine ("is this membership in
good standing?") and the coverage decision ("what does the case
receive?"). This module only answers: has enough time passed since cover
started for this kind of death, and is the member still waiting out an
upgrade?

Rules
-----
* Waiting periods are set per plan, in months, for a natural death, an
  accidental death and a suicide. Zero means no waiting period.
* They are counted from the date cover started: the membership start
  date for the main member, the dependent's own cover start date for a
  covered dependent.
* The cause comes from the case's death record. A homicide is treated as
  accidental. Until the cause is known the answer may be undecided: if
  every possible cause is still inside its waiting period the claim is
  definitely waiting; if none is, the claim is served; otherwise the
  result is ``cause_pending`` so staff know the answer depends on the
  cause of death.
* After an upgrade, cover stays at the previous plan's level until the
  new plan's upgrade waiting period has passed. A known accidental death
  is not held back by an upgrade waiting period.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from app.models.death_record import DeathRecord
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan


NATURAL = "natural"
ACCIDENTAL = "accidental"
SUICIDE = "suicide"

CATEGORIES = (NATURAL, ACCIDENTAL, SUICIDE)

CATEGORY_LABELS = {
    NATURAL: "natural death",
    ACCIDENTAL: "accidental death",
    SUICIDE: "suicide",
}

# Waiting-period statuses.
NOT_APPLICABLE = "not_applicable"
SERVED = "served"
IN_WAITING = "in_waiting"
CAUSE_PENDING = "cause_pending"


@dataclass
class WaitingPeriodResult:
    status: str
    # natural / accidental / suicide, or None while the cause is unknown.
    cause_category: str | None
    cover_start_date: date
    months: int
    # When the waiting period ends (first day cover applies). For
    # cause_pending this is the earliest end that could apply.
    ends_on: date | None
    message: str


@dataclass
class UpgradeWaitingResult:
    active: bool
    previous_plan_id: object | None
    ends_on: date | None
    message: str | None


def add_months(start: date, months: int) -> date:
    """Calendar months after ``start``; the day is clamped to the end of
    shorter months (31 Aug + 6 months is 28/29 Feb)."""

    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])

    return date(year, month, day)


def cause_category(record: DeathRecord | None) -> str | None:
    """The waiting-period category for a death record, or None when the
    cause cannot be told yet."""

    if record is None:
        return None

    if record.manner_of_death == "natural":
        return NATURAL

    if record.manner_of_death == "unnatural":
        if record.unnatural_cause in ("accident", "homicide"):
            return ACCIDENTAL

        if record.unnatural_cause == "suicide":
            return SUICIDE

    # pending, or unnatural with no (or an undetermined) cause.
    return None


def plan_months(plan: MembershipPlan) -> dict[str, int]:
    return {
        NATURAL: plan.waiting_natural_months,
        ACCIDENTAL: plan.waiting_accidental_months,
        SUICIDE: plan.waiting_suicide_months,
    }


def format_date(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def evaluate_waiting_period(
    plan: MembershipPlan,
    *,
    cover_start: date,
    coverage_date: date,
    record: DeathRecord | None,
) -> WaitingPeriodResult:
    months = plan_months(plan)
    ends = {
        category: add_months(cover_start, months[category])
        for category in CATEGORIES
    }
    waiting = {
        category: coverage_date < ends[category]
        for category in CATEGORIES
    }

    category = cause_category(record)

    # Known cause.
    if category is not None:
        label = CATEGORY_LABELS[category]

        if months[category] == 0:
            return WaitingPeriodResult(
                status=NOT_APPLICABLE,
                cause_category=category,
                cover_start_date=cover_start,
                months=0,
                ends_on=None,
                message=f"No waiting period applies to a {label}.",
            )

        if waiting[category]:
            return WaitingPeriodResult(
                status=IN_WAITING,
                cause_category=category,
                cover_start_date=cover_start,
                months=months[category],
                ends_on=ends[category],
                message=(
                    f"Within the {months[category]}-month waiting period "
                    f"for a {label}, which ends on "
                    f"{format_date(ends[category])}."
                ),
            )

        return WaitingPeriodResult(
            status=SERVED,
            cause_category=category,
            cover_start_date=cover_start,
            months=months[category],
            ends_on=ends[category],
            message=(
                f"The {months[category]}-month waiting period for a "
                f"{label} ended on {format_date(ends[category])}."
            ),
        )

    # Unknown cause.
    if all(value == 0 for value in months.values()):
        return WaitingPeriodResult(
            status=NOT_APPLICABLE,
            cause_category=None,
            cover_start_date=cover_start,
            months=0,
            ends_on=None,
            message="This plan has no waiting periods.",
        )

    longest = max(months.values())
    earliest_end = min(ends.values())

    if all(waiting.values()):
        return WaitingPeriodResult(
            status=IN_WAITING,
            cause_category=None,
            cover_start_date=cover_start,
            months=min(months.values()),
            ends_on=earliest_end,
            message=(
                "Within the waiting period whatever the cause of death; "
                f"the shortest one ends on {format_date(earliest_end)}."
            ),
        )

    if not any(waiting.values()):
        return WaitingPeriodResult(
            status=SERVED,
            cause_category=None,
            cover_start_date=cover_start,
            months=longest,
            ends_on=max(ends.values()),
            message="All waiting periods have been served.",
        )

    still_waiting = [
        CATEGORY_LABELS[category]
        for category in CATEGORIES
        if waiting[category]
    ]

    return WaitingPeriodResult(
        status=CAUSE_PENDING,
        cause_category=None,
        cover_start_date=cover_start,
        months=longest,
        ends_on=earliest_end,
        message=(
            "Whether cover applies depends on the cause of death, which "
            "is not confirmed yet. Still waiting for: "
            + ", ".join(still_waiting)
            + "."
        ),
    )


def evaluate_upgrade_waiting(
    membership: Membership,
    plan: MembershipPlan,
    *,
    coverage_date: date,
    category: str | None,
) -> UpgradeWaitingResult:
    """Whether the member is still on the previous plan's cover level."""

    none = UpgradeWaitingResult(False, None, None, None)

    if (
        membership.previous_plan_id is None
        or membership.plan_changed_at is None
        or plan.waiting_upgrade_months == 0
    ):
        return none

    # A confirmed accident is not held back by an upgrade.
    if category == ACCIDENTAL:
        return none

    ends_on = add_months(
        membership.plan_changed_at,
        plan.waiting_upgrade_months,
    )

    if coverage_date >= ends_on:
        return none

    return UpgradeWaitingResult(
        active=True,
        previous_plan_id=membership.previous_plan_id,
        ends_on=ends_on,
        message=(
            "The plan was upgraded on "
            f"{format_date(membership.plan_changed_at)}. Cover stays at "
            "the previous plan's level until "
            f"{format_date(ends_on)}."
        ),
    )


def upgrade_waiting_still_running(
    membership: Membership,
    plan: MembershipPlan,
    *,
    today: date,
) -> bool:
    """True while an earlier upgrade's waiting period is still running,
    so a second upgrade keeps the plan the member had fully earned."""

    if (
        membership.previous_plan_id is None
        or membership.plan_changed_at is None
        or plan.waiting_upgrade_months == 0
    ):
        return False

    return today < add_months(
        membership.plan_changed_at,
        plan.waiting_upgrade_months,
    )
