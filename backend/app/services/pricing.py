"""What a business pays.

The model is deliberately simple:

    standard price                      covers a set number of staff and branches
  + R25 for each extra staff account    (per month)
  + R25 for each extra branch           (per month)

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
from app.models.pricing import PlatformPricing, UsageSnapshot
from app.services import plan_limits

STAFF = "staff accounts"
BRANCHES = "branches"

DEFAULTS = dict(
    currency="ZAR",
    base_price_cents=29900,
    included_staff=5,
    included_branches=1,
    extra_staff_cents=2500,
    extra_branch_cents=2500,
)


def today() -> date:
    return datetime.now(ZoneInfo(settings.scheduler_timezone)).date()


def get_pricing(db: Session) -> PlatformPricing:
    row = db.get(PlatformPricing, 1)
    if row is None:
        row = PlatformPricing(id=1, **DEFAULTS)
        db.add(row)
        db.flush()
    return row


def pricing_dict(p: PlatformPricing) -> dict:
    return {
        "currency": p.currency,
        "base_price_cents": p.base_price_cents,
        "included_staff": p.included_staff,
        "included_branches": p.included_branches,
        "extra_staff_cents": p.extra_staff_cents,
        "extra_branch_cents": p.extra_branch_cents,
        "price_note": p.price_note,
    }


def quote(
    p: PlatformPricing,
    *,
    staff: int,
    branches: int,
    base_override_cents: int | None = None,
) -> dict:
    """The monthly price for this many staff and branches."""
    staff = max(0, staff)
    branches = max(0, branches)
    extra_staff = max(0, staff - p.included_staff)
    extra_branches = max(0, branches - p.included_branches)
    base = p.base_price_cents if base_override_cents is None else base_override_cents

    lines = [
        {
            "label": "Agreed plan price" if base_override_cents is not None
            else "Standard plan",
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

    return {
        "staff": staff,
        "branches": branches,
        "extra_staff": extra_staff,
        "extra_branches": extra_branches,
        "lines": lines,
        "total_cents": sum(line["amount_cents"] for line in lines),
    }


def counts_now(db: Session, business_id) -> tuple[int, int]:
    used = plan_limits.usage(db, business_id)
    return used[STAFF], used[BRANCHES]


def next_costs(p: PlatformPricing, staff: int, branches: int) -> dict:
    """What adding one more staff account or branch would add per month."""
    return {
        "next_staff_cents": p.extra_staff_cents if staff >= p.included_staff else 0,
        "next_branch_cents": (
            p.extra_branch_cents if branches >= p.included_branches else 0
        ),
    }


# ------------------------------------------------------------ daily record


def record_snapshots(db: Session, day: date | None = None) -> int:
    """Note today's staff and branch counts for every business in service.

    Run daily. If it runs more than once in a day the larger counts are kept.
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
    p = get_pricing(db)
    staff, branches = peaks(db, business, year, month)
    q = quote(
        p,
        staff=staff,
        branches=branches,
        base_override_cents=business.base_price_override_cents,
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
        "list_total_cents": q["total_cents"],
        "amount_due_cents": q["total_cents"] if billable else 0,
        "note": reason,
    }
