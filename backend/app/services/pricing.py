"""What a business pays.

The model is deliberately simple:

    plan price (before VAT)             covers a set number of staff and branches
  + the plan's price per extra staff    (per month)
  + the plan's price per extra branch   (per month)
  + VAT on the total                    (only when configured)

Each kind of business (funeral, general) has its own plans, set in the
platform admin.

Nothing is blocked when a business grows; the bill grows with it. A month is
charged on its busiest day (taken from a daily snapshot), so people removed
just before month-end still count for that month. There is no part-month
adjustment: a business that starts mid-month pays the full month.

All amounts are whole cents.
"""

import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.business import Business
from app.models.pricing import PlatformPricing, PricingPlan, UsageSnapshot
from app.services import plan_limits

STAFF = "staff accounts"
BRANCHES = "branches"

DEFAULTS = dict(currency="ZAR", vat_percent=0)

# (kind, code, name, tagline, price, staff, branches, extra staff, extra branch)
# Cents, before VAT. Funeral Beginner / Standard and general Startup /
# Standard are the agreed figures; Enterprise and the extra-branch prices are
# starting points for the platform owner to change.
DEFAULT_PLANS = [
    ("funeral", "funeral-beginner", "Beginner", "For a funeral home just starting out", 80000, 5, 1, 6000, 6000),
    ("funeral", "funeral-standard", "Standard", "For an established funeral home", 100000, 7, 2, 6000, 6000),
    ("funeral", "funeral-enterprise", "Enterprise", "For a larger funeral business", 180000, 15, 5, 6000, 6000),
    ("general", "general-startup", "Startup", "For a small business just starting out", 45000, 3, 1, 5000, 5000),
    ("general", "general-standard", "Standard", "For an established business", 95000, 6, 2, 5000, 5000),
    ("general", "general-enterprise", "Enterprise", "For a larger business", 150000, 12, 5, 5000, 5000),
]


def seed_default_plans(db: Session) -> None:
    """Create the starting plans if there are none."""
    if db.query(PricingPlan.id).first() is not None:
        return
    for order, (kind, code, name, tag, base, staff, branches, xs, xb) in enumerate(
        DEFAULT_PLANS
    ):
        db.add(
            PricingPlan(
                business_type=kind, code=code, name=name, tagline=tag,
                base_price_cents=base, included_staff=staff,
                included_branches=branches, extra_staff_cents=xs,
                extra_branch_cents=xb, sort_order=order, is_active=True,
            )
        )
    db.flush()


def today() -> date:
    return datetime.now(ZoneInfo(settings.scheduler_timezone)).date()


def get_pricing(db: Session) -> PlatformPricing:
    """Settings shared by every plan: VAT rate and the note under the prices."""
    row = db.get(PlatformPricing, 1)
    if row is None:
        row = PlatformPricing(id=1, **DEFAULTS)
        db.add(row)
        db.flush()
    return row


def settings_dict(p: PlatformPricing) -> dict:
    return {
        "currency": p.currency,
        "vat_percent": p.vat_percent,
        "price_note": p.price_note,
    }


def plan_dict(plan: PricingPlan) -> dict:
    return {
        "id": str(plan.id),
        "code": plan.code,
        "business_type": plan.business_type,
        "name": plan.name,
        "tagline": plan.tagline,
        "base_price_cents": plan.base_price_cents,
        "included_staff": plan.included_staff,
        "included_branches": plan.included_branches,
        "extra_staff_cents": plan.extra_staff_cents,
        "extra_branch_cents": plan.extra_branch_cents,
        "is_active": plan.is_active,
    }


def plans_for(db: Session, business_type: str, *, only_active: bool = True):
    seed_default_plans(db)
    q = db.query(PricingPlan).filter(PricingPlan.business_type == business_type)
    if only_active:
        q = q.filter(PricingPlan.is_active.is_(True))
    return q.order_by(PricingPlan.sort_order, PricingPlan.name).all()


def plan_for(db: Session, business: Business) -> PricingPlan:
    """The business's chosen plan, or the first plan for its kind of business."""
    if business.plan_id:
        chosen = db.get(PricingPlan, business.plan_id)
        if chosen is not None:
            return chosen
    options = plans_for(db, business.business_type) or plans_for(
        db, business.business_type, only_active=False
    )
    if not options:
        # Nothing set up for this kind of business: use any plan at all.
        options = db.query(PricingPlan).order_by(PricingPlan.sort_order).all()
    return options[0]


def vat_split(ex_vat_cents: int, vat_percent: int) -> tuple[int, int]:
    """(vat, total including vat), rounded to the cent."""
    vat = (ex_vat_cents * vat_percent + 50) // 100
    return vat, ex_vat_cents + vat


def quote(
    p: PlatformPricing,
    *,
    staff: int,
    branches: int,
    base_override_cents: int | None = None,
    vat_percent: int = 0,
) -> dict:
    """The monthly price on this plan for this many staff and branches.

    `total_cents` is before VAT; `total_incl_vat_cents` adds `vat_percent`.
    """
    staff = max(0, staff)
    branches = max(0, branches)
    extra_staff = max(0, staff - p.included_staff)
    extra_branches = max(0, branches - p.included_branches)
    base = p.base_price_cents if base_override_cents is None else base_override_cents

    lines = [
        {
            "label": "Agreed plan price" if base_override_cents is not None
            else f"{p.name} plan",
            "detail": f"Includes {p.included_staff} staff and "
            f"{p.included_branches} branch{'' if p.included_branches == 1 else 'es'}",
            "quantity": 1,
            "unit_cents": base,
            "amount_cents": base,
        }
    ]
    if extra_staff:
        lines.append(
            {
                "label": "Extra staff",
                "detail": f"{staff} staff, {p.included_staff} included",
                "quantity": extra_staff,
                "unit_cents": p.extra_staff_cents,
                "amount_cents": extra_staff * p.extra_staff_cents,
            }
        )
    if extra_branches:
        lines.append(
            {
                "label": "Extra branches",
                "detail": f"{branches} branches, {p.included_branches} included",
                "quantity": extra_branches,
                "unit_cents": p.extra_branch_cents,
                "amount_cents": extra_branches * p.extra_branch_cents,
            }
        )

    total = sum(line["amount_cents"] for line in lines)
    vat, incl = vat_split(total, vat_percent)
    return {
        "staff": staff,
        "branches": branches,
        "extra_staff": extra_staff,
        "extra_branches": extra_branches,
        "lines": lines,
        "total_cents": total,
        "vat_percent": vat_percent,
        "vat_cents": vat,
        "total_incl_vat_cents": incl,
    }


def counts_now(db: Session, business_id) -> tuple[int, int]:
    used = plan_limits.usage(db, business_id)
    return used[STAFF], used[BRANCHES]


def next_costs(plan, staff: int, branches: int, vat_percent: int = 0) -> dict:
    """What adding one more staff account or branch would add per month."""
    staff_cents = plan.extra_staff_cents if staff >= plan.included_staff else 0
    branch_cents = plan.extra_branch_cents if branches >= plan.included_branches else 0
    return {
        "next_staff_cents": staff_cents,
        "next_staff_incl_vat_cents": vat_split(staff_cents, vat_percent)[1],
        "next_branch_cents": branch_cents,
        "next_branch_incl_vat_cents": vat_split(branch_cents, vat_percent)[1],
    }


# ------------------------------------------------------------ daily record


def record_snapshots(db: Session, day: date | None = None) -> int:
    """Note today's staff and branch counts for every business in service.

    The scheduler runs this hourly. If it runs more than once in a day the
    larger counts are kept so statements use the observed daily peak.
    """
    day = day or today()
    saved = 0
    businesses = (
        db.query(Business)
        .filter(
            Business.is_active.is_(True),
            Business.subscription_status.in_(("trial", "active")),
        )
        .all()
    )
    for business in businesses:
        staff, branches = counts_now(db, business.id)
        row = (
            db.query(UsageSnapshot)
            .filter(
                UsageSnapshot.business_id == business.id,
                UsageSnapshot.day == day,
            )
            .first()
        )
        if row is None:
            db.add(
                UsageSnapshot(
                    business_id=business.id, day=day, staff=staff, branches=branches
                )
            )
        else:
            row.staff = max(row.staff, staff)
            row.branches = max(row.branches, branches)
        saved += 1
    db.commit()
    return saved


# --------------------------------------------------------------- statements


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def peaks(db: Session, business: Business, year: int, month: int) -> tuple[int, int]:
    first, last = month_bounds(year, month)
    staff, branches = (
        db.query(func.max(UsageSnapshot.staff), func.max(UsageSnapshot.branches))
        .filter(
            UsageSnapshot.business_id == business.id,
            UsageSnapshot.day >= first,
            UsageSnapshot.day <= last,
        )
        .one()
    )
    staff, branches = staff or 0, branches or 0

    # The month still running also counts what the business has right now.
    if first <= today() <= last:
        live_staff, live_branches = counts_now(db, business.id)
        staff, branches = max(staff, live_staff), max(branches, live_branches)

    return staff, branches


def statement(db: Session, business: Business, year: int, month: int) -> dict:
    plan = plan_for(db, business)
    vat_percent = get_pricing(db).vat_percent
    staff, branches = peaks(db, business, year, month)
    q = quote(
        plan,
        staff=staff,
        branches=branches,
        base_override_cents=business.base_price_override_cents,
        vat_percent=vat_percent,
    )
    status = business.subscription_status
    billable = status == "active"
    reason = {
        "trial": "On trial: nothing to pay yet.",
        "suspended": "Suspended: not charged.",
        "cancelled": "Cancelled: not charged.",
    }.get(status)

    return {
        "year": year,
        "month": month,
        "status": status,
        "peak_staff": staff,
        "peak_branches": branches,
        **{k: q[k] for k in ("extra_staff", "extra_branches", "lines")},
        "plan": plan.name,
        "vat_percent": vat_percent,
        "list_total_cents": q["total_cents"],
        "list_total_incl_vat_cents": q["total_incl_vat_cents"],
        "amount_due_cents": q["total_cents"] if billable else 0,
        "vat_cents": q["vat_cents"] if billable else 0,
        "amount_due_incl_vat_cents": q["total_incl_vat_cents"] if billable else 0,
        "note": reason,
    }
