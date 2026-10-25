"""Private family and member portal links, and what they may show."""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.case_financial import CaseFinancial
from app.models.case_service import CaseService
from app.models.financial_document import FinancialDocument
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.models.membership_plan import MembershipPlan
from app.models.portal import PortalLink

DEFAULT_DAYS = 30
MAX_DAYS = 180


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_link(
    db: Session, *, business_id, kind, case_id=None, member_id=None,
    created_by=None, days=DEFAULT_DAYS,
) -> tuple[PortalLink, str]:
    token = secrets.token_urlsafe(32)
    link = PortalLink(
        business_id=business_id,
        kind=kind,
        case_id=case_id,
        member_id=member_id,
        token_hash=hash_token(token),
        created_by=created_by,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
    )
    db.add(link)
    db.flush()
    return link, token


def find_link(db: Session, token: str) -> PortalLink | None:
    link = (
        db.query(PortalLink)
        .filter(PortalLink.token_hash == hash_token(token))
        .first()
    )
    now = datetime.now(timezone.utc)
    if link is None or link.revoked_at is not None or link.expires_at <= now:
        return None
    link.last_used_at = now
    return link


# ---- a small brake on guessing links -----------------------------------

_failures: dict[str, deque] = defaultdict(deque)
WINDOW_SECONDS = 600
MAX_FAILURES = 20


def too_many_failures(ip: str) -> bool:
    now = time.monotonic()
    q = _failures[ip]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    return len(q) >= MAX_FAILURES


def record_failure(ip: str) -> None:
    _failures[ip].append(time.monotonic())


# ---- what each portal shows ---------------------------------------------


def _f(value) -> float:
    return float(value or 0)


def family_view(db: Session, link: PortalLink) -> dict:
    case = db.get(FuneralCase, link.case_id)
    business = db.get(Business, link.business_id)
    fin = (
        db.query(CaseFinancial)
        .filter(CaseFinancial.case_id == case.id)
        .first()
    )
    services = (
        db.query(CaseService)
        .filter(CaseService.case_id == case.id, CaseService.status != "cancelled")
        .order_by(CaseService.scheduled_date.asc().nullslast())
        .all()
    )
    documents = (
        db.query(FinancialDocument)
        .filter(
            FinancialDocument.case_id == case.id,
            FinancialDocument.issued_at.isnot(None),
            FinancialDocument.voided_at.is_(None),
        )
        .order_by(FinancialDocument.issued_at)
        .all()
    )
    return {
        "kind": "family",
        "business_name": business.name if business else "",
        "case_number": case.case_number,
        "deceased_full_name": case.deceased_full_name,
        "funeral_date": case.funeral_date,
        "funeral_venue": case.funeral_venue,
        "status": case.status,
        "schedule": [
            {
                "name": s.service_name,
                "type": s.service_type,
                "scheduled_for": s.scheduled_date,
                "status": s.status,
            }
            for s in services
        ],
        "balance": (
            {
                "total": _f(fin.total),
                "paid": _f(fin.amount_paid),
                "outstanding": _f(fin.balance),
            }
            if fin
            else None
        ),
        "documents": [
            {
                "type": d.document_type,
                "number": d.number,
                "total": _f(d.total),
                "status": d.status,
                "issued_at": d.issued_at,
                "due_date": d.due_date,
            }
            for d in documents
        ],
    }


def member_view(db: Session, link: PortalLink) -> dict:
    member = db.get(Member, link.member_id)
    business = db.get(Business, link.business_id)
    memberships = (
        db.query(Membership)
        .filter(Membership.member_id == member.id)
        .order_by(Membership.start_date)
        .all()
    )
    ids = [m.id for m in memberships]
    plans = {
        p.id: p
        for p in db.query(MembershipPlan)
        .filter(MembershipPlan.id.in_({m.plan_id for m in memberships}))
        .all()
    } if memberships else {}
    contributions = (
        db.query(MembershipContribution)
        .filter(MembershipContribution.membership_id.in_(ids))
        .order_by(MembershipContribution.contribution_period.desc())
        .limit(12)
        .all()
    ) if ids else []
    payments = (
        db.query(MembershipPayment)
        .filter(MembershipPayment.membership_id.in_(ids))
        .order_by(MembershipPayment.payment_date.desc())
        .limit(10)
        .all()
    ) if ids else []
    owing = sum(
        max(_f(c.amount_due) - _f(c.amount_paid), 0)
        for c in contributions
        if c.status not in ("paid", "waived", "cancelled")
    )
    return {
        "kind": "member",
        "business_name": business.name if business else "",
        "member_name": f"{member.first_name} {member.last_name}".strip(),
        "memberships": [
            {
                "number": m.membership_number,
                "plan": plans[m.plan_id].name if m.plan_id in plans else None,
                "monthly_contribution": (
                    _f(plans[m.plan_id].monthly_contribution)
                    if m.plan_id in plans else None
                ),
                "status": m.status,
                "next_due_date": m.next_due_date,
                "arrears_since": m.arrears_since,
            }
            for m in memberships
        ],
        "outstanding": owing,
        "contributions": [
            {
                "period": c.contribution_period,
                "due": _f(c.amount_due),
                "paid": _f(c.amount_paid),
                "status": c.status,
                "due_date": c.due_date,
            }
            for c in contributions
        ],
        "payments": [
            {
                "date": p.payment_date,
                "amount": _f(p.amount),
                "method": p.payment_method,
            }
            for p in payments
        ],
    }
