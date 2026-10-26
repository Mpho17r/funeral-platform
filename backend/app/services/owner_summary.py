"""The owner's month-end view.

One summary that answers "how did we do, compared with before, and who
needs a call?": money collected, cases handled, membership growth and
losses for a period beside the period before it, a six-month trend, and
two work lists (members falling behind, families who still owe).

Read-only, scoped to one business and optionally one branch, and built
on the same money rules as the other reports: collected is payments
dated in the period; outstanding is what is owed right now.
"""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.models.membership_plan import MembershipPlan
from app.services.reports import (
    ZERO,
    ReportError,
    created_in_period,
    date_in_period,
    financial_report,
    money,
    validate_branch,
    validate_period,
)

BUSINESS_TZ = ZoneInfo("Africa/Johannesburg")

TREND_MONTHS = 6
LIST_LIMIT = 200


def _first_of_month(day: date) -> date:
    return day.replace(day=1)


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def _last_of_month(day: date) -> date:
    return _add_months(_first_of_month(day), 1) - timedelta(days=1)


def previous_period(date_from: date, date_to: date) -> tuple[date, date]:
    """The stretch of equal length straight before this one. A whole
    calendar month compares with the whole month before it, so March is
    set against February and not against 31 days."""

    if date_from.day == 1 and date_to == _last_of_month(date_from):
        start = _add_months(date_from, -1)
        return start, _last_of_month(start)

    length = (date_to - date_from).days + 1

    return date_from - timedelta(days=length), date_from - timedelta(days=1)


def period_figures(
    db: Session,
    business_id: UUID,
    date_from: date,
    date_to: date,
    branch_id: UUID | None,
) -> dict:
    case_filters = [
        FuneralCase.business_id == business_id,
        FuneralCase.is_archived.is_(False),
        FuneralCase.status != "cancelled",
    ]
    member_filters = [
        Member.business_id == business_id,
        Member.archived_at.is_(None),
    ]

    if branch_id:
        case_filters.append(FuneralCase.branch_id == branch_id)
        member_filters.append(Member.branch_id == branch_id)

    case_money = (
        db.query(func.coalesce(func.sum(CasePayment.amount), ZERO))
        .join(FuneralCase, FuneralCase.id == CasePayment.case_id)
        .filter(
            CasePayment.business_id == business_id,
            *case_filters,
            *date_in_period(CasePayment.payment_date, date_from, date_to),
        )
        .scalar()
    )

    membership_money = (
        db.query(func.coalesce(func.sum(MembershipPayment.amount), ZERO))
        .join(Membership, Membership.id == MembershipPayment.membership_id)
        .join(Member, Member.id == Membership.member_id)
        .filter(
            MembershipPayment.business_id == business_id,
            *member_filters[1:],
            *date_in_period(
                MembershipPayment.payment_date, date_from, date_to
            ),
        )
        .scalar()
    )

    cases_opened = (
        db.query(func.count(FuneralCase.id))
        .filter(
            *case_filters,
            *created_in_period(FuneralCase.created_at, date_from, date_to),
        )
        .scalar()
    )

    funerals_held = (
        db.query(func.count(FuneralCase.id))
        .filter(
            *case_filters,
            *date_in_period(FuneralCase.funeral_date, date_from, date_to),
        )
        .scalar()
    )

    new_members = (
        db.query(func.count(Member.id))
        .filter(
            *member_filters,
            *date_in_period(Member.join_date, date_from, date_to),
        )
        .scalar()
    )

    def memberships_with(column):
        return (
            db.query(func.count(Membership.id))
            .join(Member, Member.id == Membership.member_id)
            .filter(
                Membership.business_id == business_id,
                *member_filters[1:],
                *date_in_period(column, date_from, date_to),
            )
            .scalar()
        )

    case_money = money(case_money)
    membership_money = money(membership_money)

    return {
        "collected": money(case_money + membership_money),
        "collected_cases": case_money,
        "collected_memberships": membership_money,
        "cases_opened": int(cases_opened or 0),
        "funerals_held": int(funerals_held or 0),
        "new_members": int(new_members or 0),
        "memberships_lapsed": int(memberships_with(Membership.lapsed_at) or 0),
        "memberships_cancelled": int(
            memberships_with(Membership.cancelled_at) or 0
        ),
    }


def trend(
    db: Session,
    business_id: UUID,
    anchor: date,
    branch_id: UUID | None,
) -> list[dict]:
    """The six calendar months ending with the month of `anchor`."""

    series = []
    first = _add_months(_first_of_month(anchor), -(TREND_MONTHS - 1))

    for step in range(TREND_MONTHS):
        start = _add_months(first, step)
        figures = period_figures(
            db, business_id, start, _last_of_month(start), branch_id
        )
        series.append(
            {
                "month": start.isoformat(),
                "collected": figures["collected"],
                "cases_opened": figures["cases_opened"],
                "new_members": figures["new_members"],
            }
        )

    return series


def snapshot(
    db: Session,
    business_id: UUID,
    branch_id: UUID | None,
    today: date,
) -> dict:
    """How things stand right now, whatever period is on screen."""

    member_filters = [
        Member.business_id == business_id,
        Member.archived_at.is_(None),
    ]

    if branch_id:
        member_filters.append(Member.branch_id == branch_id)

    rows = (
        db.query(Membership.status, func.count(Membership.id))
        .join(Member, Member.id == Membership.member_id)
        .filter(Membership.business_id == business_id, *member_filters[1:])
        .group_by(Membership.status)
        .all()
    )
    by_status = {status: count for status, count in rows}

    money_report = financial_report(
        db,
        business_id=business_id,
        date_from=None,
        date_to=None,
        branch_id=branch_id,
        today=today,
    )

    return {
        "active_memberships": by_status.get("active", 0),
        "memberships_in_arrears": by_status.get("arrears", 0),
        "memberships_lapsed": by_status.get("lapsed", 0),
        "outstanding": money_report["outstanding"],
        "cases_with_balance": money_report["cases_with_balance"],
    }


def overview(
    db: Session,
    *,
    business_id: UUID,
    date_from: date,
    date_to: date,
    branch_id: UUID | None,
    today: date | None = None,
) -> dict:
    today = today or datetime.now(BUSINESS_TZ).date()

    validate_period(date_from, date_to)
    validate_branch(db, business_id, branch_id)

    if (date_to - date_from).days > 366:
        raise ReportError(422, "Choose a period of a year or less")

    before_from, before_to = previous_period(date_from, date_to)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "previous_from": before_from,
        "previous_to": before_to,
        "branch_id": branch_id,
        "current": period_figures(
            db, business_id, date_from, date_to, branch_id
        ),
        "previous": period_figures(
            db, business_id, before_from, before_to, branch_id
        ),
        "trend": trend(db, business_id, date_to, branch_id),
        "now": snapshot(db, business_id, branch_id, today),
    }


# ============================================================
# WORK LISTS
# ============================================================

def arrears_rows(
    db: Session,
    *,
    business_id: UUID,
    branch_id: UUID | None,
    today: date | None = None,
) -> dict:
    """Memberships behind on contributions, longest first, with how long
    until the lapse rule applies."""

    today = today or datetime.now(BUSINESS_TZ).date()

    business = db.get(Business, business_id)
    lapse_after = business.lapse_after_days if business else 0

    query = (
        db.query(Membership, Member, MembershipPlan)
        .join(Member, Member.id == Membership.member_id)
        .join(MembershipPlan, MembershipPlan.id == Membership.plan_id)
        .filter(
            Membership.business_id == business_id,
            Membership.status == "arrears",
            Member.archived_at.is_(None),
        )
    )

    if branch_id:
        query = query.filter(Member.branch_id == branch_id)

    rows = []

    for membership, member, plan in query.all():
        unpaid = (
            db.query(
                func.coalesce(
                    func.sum(
                        MembershipContribution.amount_due
                        - MembershipContribution.amount_paid
                    ),
                    ZERO,
                )
            )
            .filter(
                MembershipContribution.membership_id == membership.id,
                MembershipContribution.due_date <= today,
                MembershipContribution.amount_paid
                < MembershipContribution.amount_due,
            )
            .scalar()
        )

        since = membership.arrears_since
        days = (today - since).days if since else 0

        rows.append(
            {
                "membership_id": membership.id,
                "membership_number": membership.membership_number,
                "member_name": f"{member.first_name} {member.last_name}",
                "phone": member.phone,
                "plan": plan.name,
                "arrears_since": since,
                "days_in_arrears": days,
                "days_until_lapse": max(lapse_after - days, 0),
                "amount_unpaid": money(unpaid),
            }
        )

    rows.sort(key=lambda r: r["days_in_arrears"], reverse=True)

    return {
        "lapse_after_days": lapse_after,
        "total": len(rows),
        "total_unpaid": money(sum((r["amount_unpaid"] for r in rows), ZERO)),
        "rows": rows[:LIST_LIMIT],
    }


def debtor_rows(
    db: Session,
    *,
    business_id: UUID,
    branch_id: UUID | None,
    today: date | None = None,
) -> dict:
    """Live cases that still owe money, biggest balance first."""

    today = today or datetime.now(BUSINESS_TZ).date()

    query = (
        db.query(FuneralCase, CaseFinancial)
        .join(CaseFinancial, CaseFinancial.case_id == FuneralCase.id)
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.is_archived.is_(False),
            FuneralCase.status != "cancelled",
            CaseFinancial.balance > 0,
        )
    )

    if branch_id:
        query = query.filter(FuneralCase.branch_id == branch_id)

    rows = [
        {
            "case_id": case.id,
            "case_number": case.case_number,
            "deceased_full_name": case.deceased_full_name,
            "next_of_kin_name": case.next_of_kin_name,
            "next_of_kin_phone": case.next_of_kin_phone,
            "funeral_date": case.funeral_date,
            "age_days": max((today - case.created_at.date()).days, 0),
            "total": money(financial.total),
            "balance": money(financial.balance),
        }
        for case, financial in query.all()
    ]

    rows.sort(key=lambda r: r["balance"], reverse=True)

    return {
        "total": len(rows),
        "total_owed": money(sum((r["balance"] for r in rows), ZERO)),
        "rows": rows[:LIST_LIMIT],
    }


# ============================================================
# CSV
# ============================================================

def _safe(value) -> str:
    """Spreadsheets run text that starts with = + - @ as a formula. Names
    and notes come from people, so such text is neutralised."""

    text = "" if value is None else str(value)

    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text

    return text


def to_csv(headers: list[str], keys: list[str], rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)

    for row in rows:
        writer.writerow(
            [
                _safe(row[key]) if not isinstance(row[key], Decimal)
                else str(row[key])
                for key in keys
            ]
        )

    return buffer.getvalue()
