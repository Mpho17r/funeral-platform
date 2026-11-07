"""Prices, and the monthly statement the platform owner bills from."""

import csv
import io
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.platform import get_platform_admin
from app.database import get_db
from app.models.business import Business
from app.models.platform_admin import PlatformAdmin
from app.models.pricing import PricingPlan
from app.services import pricing as pricing_service

router = APIRouter(tags=["Pricing"])

MAX_CENTS = 10_000_000  # R100 000: a typing slip is caught, real prices are not.


@router.get("/pricing")
def public_pricing(db: Session = Depends(get_db)):
    """Every plan, for the public pricing page. No sign-in needed."""
    row = pricing_service.get_pricing(db)
    out = {
        **pricing_service.settings_dict(row),
        "plans": {
            kind: [
                pricing_service.plan_dict(p)
                for p in pricing_service.plans_for(db, kind)
            ]
            for kind in ("funeral", "general")
        },
    }
    db.commit()
    return out


@router.get("/pricing/quote")
def public_quote(
    plan: str = Query(min_length=1, max_length=40, description="Plan code"),
    staff: int = Query(ge=0, le=10_000),
    branches: int = Query(default=1, ge=0, le=1_000),
    db: Session = Depends(get_db),
):
    """The monthly price on a plan for this many staff and branches."""
    pricing_service.seed_default_plans(db)
    chosen = (
        db.query(PricingPlan)
        .filter(PricingPlan.code == plan, PricingPlan.is_active.is_(True))
        .first()
    )
    if chosen is None:
        raise HTTPException(404, "That plan does not exist")
    row = pricing_service.get_pricing(db)
    db.commit()
    return pricing_service.quote(
        chosen, staff=staff, branches=branches, vat_percent=row.vat_percent
    )


class PricingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vat_percent: int | None = Field(default=None, ge=0, le=100)
    price_note: str | None = Field(default=None, max_length=200)


@router.put("/platform/pricing")
def update_pricing(
    data: PricingUpdate,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    """VAT rate and the note shown under the prices."""
    row = pricing_service.get_pricing(db)

    for field in data.model_fields_set:
        value = getattr(data, field)
        if field == "price_note":
            value = (value or "").strip() or None
        elif value is None:
            continue
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    return pricing_service.settings_dict(row)


@router.get("/platform/plans")
def list_plans(
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    return [
        pricing_service.plan_dict(p)
        for p in db.query(PricingPlan).order_by(
            PricingPlan.business_type, PricingPlan.sort_order
        )
    ]


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=60)
    tagline: str | None = Field(default=None, max_length=160)
    base_price_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    included_staff: int | None = Field(default=None, ge=0, le=10_000)
    included_branches: int | None = Field(default=None, ge=0, le=1_000)
    extra_staff_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    extra_branch_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    is_active: bool | None = None


@router.put("/platform/plans/{plan_id}")
def update_plan(
    plan_id: uuid.UUID,
    data: PlanUpdate,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    plan = db.get(PricingPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")

    for field in data.model_fields_set:
        value = getattr(data, field)
        if field == "tagline":
            value = (value or "").strip() or None
        elif value is None:
            continue
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)
    return pricing_service.plan_dict(plan)


def _month(value: str | None) -> tuple[int, int]:
    if not value:
        now = pricing_service.today()
        return now.year, now.month
    match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", value)
    if not match or not 2024 <= int(match.group(1)) <= 2100:
        raise HTTPException(422, "Month must look like 2026-11")
    return int(match.group(1)), int(match.group(2))


def _rands(cents: int) -> str:
    return f"{cents / 100:.2f}"


@router.get("/platform/statements")
def statements(
    month: str | None = Query(default=None, description="YYYY-MM"),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    """What each business owes for a month, from its busiest day."""
    year, mon = _month(month)
    rows = []
    for business in db.query(Business).order_by(Business.name).all():
        s = pricing_service.statement(db, business, year, mon)
        rows.append(
            {
                "business_id": str(business.id),
                "business": business.name,
                "plan": s["plan"],
                "status": s["status"],
                "peak_staff": s["peak_staff"],
                "peak_branches": s["peak_branches"],
                "extra_staff": s["extra_staff"],
                "extra_branches": s["extra_branches"],
                "special_price": business.base_price_override_cents is not None,
                "list_total_cents": s["list_total_cents"],
                "amount_due_cents": s["amount_due_cents"],
                "vat_cents": s["vat_cents"],
                "amount_due_incl_vat_cents": s["amount_due_incl_vat_cents"],
                "note": s["note"],
            }
        )

    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "Business", "Plan", "Status", "Peak staff", "Peak branches",
                "Extra staff", "Extra branches", "Special price",
                "Plan total excl VAT (R)", "Amount due excl VAT (R)",
                "VAT (R)", "Amount due incl VAT (R)", "Note",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    # A leading = + - @ would run as a formula in Excel.
                    ("'" + r["business"]) if r["business"][:1] in "=+-@" else r["business"],
                    r["plan"], r["status"], r["peak_staff"], r["peak_branches"],
                    r["extra_staff"], r["extra_branches"],
                    "yes" if r["special_price"] else "",
                    _rands(r["list_total_cents"]), _rands(r["amount_due_cents"]),
                    _rands(r["vat_cents"]), _rands(r["amount_due_incl_vat_cents"]),
                    r["note"] or "",
                ]
            )
        return Response(
            out.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="linda-statements-{year}-{mon:02d}.csv"'
            },
        )

    return {
        "year": year,
        "month": mon,
        "rows": rows,
        "total_due_cents": sum(r["amount_due_cents"] for r in rows),
        "total_due_incl_vat_cents": sum(
            r["amount_due_incl_vat_cents"] for r in rows
        ),
    }
