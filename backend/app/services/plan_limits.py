"""
Subscription plans and usage limits.

Limits live on the business (None = unlimited) and are enforced centrally
when records are saved, so every route and import obeys them. A suspended
or cancelled business cannot use the system at all.
"""

from fastapi import HTTPException
from sqlalchemy import event, func
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.business import Business
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.user import User

TIERS = ("starter", "growth", "professional", "enterprise")
STATUSES = ("trial", "active", "suspended", "cancelled")

# Starting points only; exact amounts and limits are set per customer.
TIER_DEFAULTS = {
    "starter": dict(max_branches=1, max_users=5, max_members=500,
                    max_active_cases=100),
    "growth": dict(max_branches=3, max_users=15, max_members=2000,
                   max_active_cases=500),
    "professional": dict(max_branches=10, max_users=50, max_members=10000,
                         max_active_cases=2500),
    "enterprise": dict(max_branches=None, max_users=None, max_members=None,
                       max_active_cases=None),
}

# model -> (business column holding the limit, label, what is counted)
LIMITED = {
    Branch: ("max_branches", "branches", lambda: Branch.is_active.is_(True)),
    User: ("max_users", "staff accounts", lambda: User.is_active.is_(True)),
    Member: ("max_members", "members", lambda: Member.archived_at.is_(None)),
    FuneralCase: ("max_active_cases", "active cases",
                  lambda: FuneralCase.is_archived.is_(False)),
}


def usage(db: Session, business_id) -> dict:
    out = {}
    for model, (_, label, where) in LIMITED.items():
        out[label] = (
            db.query(func.count(model.id))
            .filter(model.business_id == business_id, where())
            .execution_options(all_branches=True)
            .scalar()
        )
    return out


def limits(business: Business) -> dict:
    return {
        label: getattr(business, column)
        for _, (column, label, _) in LIMITED.items()
    }


def ensure_active(business: Business | None) -> None:
    if business is not None and business.subscription_status in (
        "suspended", "cancelled",
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "This subscription is not active. Please contact "
                "Saccharum Technologies."
            ),
        )


@event.listens_for(Session, "before_flush")
def _enforce_limits(session, flush_context, instances):
    fresh: dict = {}
    for obj in session.new:
        entry = LIMITED.get(type(obj))
        if entry is None or getattr(obj, "business_id", None) is None:
            continue
        counts = fresh.setdefault((type(obj), obj.business_id), 0)
        active = entry[2]
        # Only things that would count toward the limit.
        if type(obj) is Branch and obj.is_active is False:
            continue
        if type(obj) is User and obj.is_active is False:
            continue
        fresh[(type(obj), obj.business_id)] = counts + 1

    if not fresh:
        return

    with session.no_autoflush:
        for (model, business_id), adding in fresh.items():
            business = session.get(Business, business_id)
            if business is None:
                continue
            column, label, where = LIMITED[model]
            cap = getattr(business, column)
            if cap is None:
                continue
            current = (
                session.query(func.count(model.id))
                .filter(model.business_id == business_id, where())
                .execution_options(all_branches=True)
                .scalar()
            )
            if current + adding > cap:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Your plan allows up to {cap} {label}. "
                        "Contact Saccharum Technologies to upgrade."
                    ),
                )
