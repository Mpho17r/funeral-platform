"""The finance dashboard: money in, money due, who is behind, and what
needs chasing today. Read-only."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case_payment import CasePayment
from app.models.communication import CommunicationMessage
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_claim import MembershipClaim
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.services import owner_summary
from app.services.communications import UNPAID_STATUSES
from app.services.mortuary_overview import SAST

ZERO = Decimal("0.00")
DUE_SOON_DAYS = 7
OPEN_CLAIM_STATUSES = ("submitted", "under_review", "approved")


def _money(value) -> float:
    return float(Decimal(value or 0).quantize(Decimal("0.01")))


def overview(
    db: Session,
    *,
    business_id: UUID,
    branch_id: UUID | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(SAST).date()
    month_start = today.replace(day=1)
    prev_from, prev_to = owner_summary.previous_period(month_start, today)

    this_month = owner_summary.period_figures(
        db, business_id, month_start, today, branch_id
    )
    last_month = owner_summary.period_figures(
        db, business_id, prev_from, prev_to, branch_id
    )
    today_figures = owner_summary.period_figures(
        db, business_id, today, today, branch_id
    )
    snap = owner_summary.snapshot(db, business_id, branch_id, today)

    # --- contributions: due soon, overdue, and the collection rate
    contrib = db.query(MembershipContribution).filter(
        MembershipContribution.business_id == business_id
    )
    if branch_id is not None:
        contrib = (
            contrib.join(
                Membership,
                Membership.id == MembershipContribution.membership_id,
            )
            .join(Member, Member.id == Membership.member_id)
            .filter(Member.branch_id == branch_id)
        )

    owing = func.coalesce(
        func.sum(
            MembershipContribution.amount_due
            - MembershipContribution.amount_paid
        ),
        ZERO,
    )
    unpaid = contrib.filter(
        MembershipContribution.status.in_(UNPAID_STATUSES),
        MembershipContribution.amount_paid
        < MembershipContribution.amount_due,
    )

    soon_n, soon_amount = unpaid.filter(
        MembershipContribution.due_date >= today,
        MembershipContribution.due_date
        <= today + timedelta(days=DUE_SOON_DAYS),
    ).with_entities(func.count(MembershipContribution.id), owing).one()

    late_n, late_amount = unpaid.filter(
        MembershipContribution.due_date < today
    ).with_entities(func.count(MembershipContribution.id), owing).one()

    due_this_month, paid_this_month = contrib.filter(
        MembershipContribution.due_date >= month_start,
        MembershipContribution.due_date <= today,
    ).with_entities(
        func.coalesce(func.sum(MembershipContribution.amount_due), ZERO),
        func.coalesce(func.sum(MembershipContribution.amount_paid), ZERO),
    ).one()
    rate = (
        round(float(paid_this_month) / float(due_this_month) * 100, 1)
        if due_this_month
        else None
    )

    # --- recent payments, newest first, both kinds together
    recent = []
    q = (
        db.query(MembershipPayment, Member, Membership)
        .join(Membership, Membership.id == MembershipPayment.membership_id)
        .join(Member, Member.id == Membership.member_id)
        .filter(MembershipPayment.business_id == business_id)
    )
    if branch_id is not None:
        q = q.filter(Member.branch_id == branch_id)
    for pay, member, ms in (
        q.order_by(MembershipPayment.payment_date.desc(),
                   MembershipPayment.created_at.desc())
        .limit(8)
        .all()
    ):
        recent.append(
            {
                "kind": "membership",
                "date": pay.payment_date.isoformat(),
                "created_at": pay.created_at.isoformat(),
                "who": f"{member.first_name} {member.last_name}",
                "reference": ms.membership_number,
                "method": pay.payment_method,
                "amount": _money(pay.amount),
                "link": "/memberships",
            }
        )

    cq = (
        db.query(CasePayment, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CasePayment.case_id)
        .filter(
            CasePayment.business_id == business_id,
            FuneralCase.is_archived.is_(False),
        )
    )
    if branch_id is not None:
        cq = cq.filter(FuneralCase.branch_id == branch_id)
    for pay, case in (
        cq.order_by(CasePayment.payment_date.desc(),
                    CasePayment.created_at.desc())
        .limit(8)
        .all()
    ):
        recent.append(
            {
                "kind": "case",
                "date": pay.payment_date.isoformat(),
                "created_at": pay.created_at.isoformat(),
                "who": case.deceased_full_name,
                "reference": case.case_number,
                "method": pay.payment_method,
                "amount": _money(pay.amount),
                "link": f"/cases/{case.id}/financial",
            }
        )
    recent.sort(key=lambda r: (r["date"], r["created_at"]), reverse=True)
    for r in recent:
        r.pop("created_at")

    claims = db.query(MembershipClaim).filter(
        MembershipClaim.business_id == business_id,
        MembershipClaim.status.in_(OPEN_CLAIM_STATUSES),
    )
    claims_open = claims.count()

    queued = (
        db.query(func.count(CommunicationMessage.id))
        .filter(
            CommunicationMessage.business_id == business_id,
            CommunicationMessage.status == "queued",
        )
        .scalar()
        or 0
    )

    arrears = owner_summary.arrears_rows(
        db, business_id=business_id, branch_id=branch_id, today=today
    )
    debtors = owner_summary.debtor_rows(
        db, business_id=business_id, branch_id=branch_id, today=today
    )

    return {
        "today": today.isoformat(),
        "collected": {
            "today": _money(today_figures["collected"]),
            "month": _money(this_month["collected"]),
            "month_cases": _money(this_month["collected_cases"]),
            "month_memberships": _money(this_month["collected_memberships"]),
            "last_month": _money(last_month["collected"]),
        },
        "contributions": {
            "due_soon_count": soon_n,
            "due_soon_amount": _money(soon_amount),
            "overdue_count": late_n,
            "overdue_amount": _money(late_amount),
            "collection_rate_percent": rate,
            "due_days": DUE_SOON_DAYS,
        },
        "memberships": {
            "active": snap["active_memberships"],
            "in_arrears": snap["memberships_in_arrears"],
            "lapsed": snap["memberships_lapsed"],
            "new_this_month": this_month["new_members"],
            "lapsed_this_month": this_month["memberships_lapsed"],
        },
        "outstanding_on_cases": _money(snap["outstanding"]),
        "claims_open": claims_open,
        "reminders_queued": queued,
        "trend": owner_summary.trend(db, business_id, today, branch_id),
        "arrears": {
            "total": arrears["total"],
            "total_unpaid": _money(arrears["total_unpaid"]),
            "rows": arrears["rows"][:8],
        },
        "debtors": {
            "total": debtors["total"],
            "total_owed": _money(debtors["total_owed"]),
            "rows": debtors["rows"][:8],
        },
        "recent_payments": recent[:10],
    }
