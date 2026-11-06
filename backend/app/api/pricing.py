"""Prices, and the monthly statement the platform owner bills from."""

import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.platform import get_platform_admin
from app.database import get_db
from app.models.business import Business
from app.models.platform_admin import PlatformAdmin
from app.services import pricing as pricing_service

router = APIRouter(tags=["Pricing"])

MAX_CENTS = 10_000_000  # R100 000: a typing slip is caught, real prices are not.


@router.get("/pricing")
def public_pricing(db: Session = Depends(get_db)):
    """The prices, for the public pricing page. No sign-in needed."""
    row = pricing_service.get_pricing(db)
    db.commit()
    return pricing_service.pricing_dict(row)


@router.get("/pricing/quote")
def public_quote(
    staff: int = Query(ge=0, le=10_000),
    branches: int = Query(default=1, ge=0, le=1_000),
    db: Session = Depends(get_db),
):
    """The monthly price for this many staff and branches (pricing page)."""
    row = pricing_service.get_pricing(db)
    db.commit()
    return pricing_service.quote(row, staff=staff, branches=branches)


class PricingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_price_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    included_staff: int | None = Field(default=None, ge=0, le=10_000)
    included_branches: int | None = Field(default=None, ge=0, le=1_000)
    extra_staff_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    extra_branch_cents: int | None = Field(default=None, ge=0, le=MAX_CENTS)
    price_note: str | None = Field(default=None, max_length=200)


@router.put("/platform/pricing")
def update_pricing(
    data: PricingUpdate,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
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
    return pricing_service.pricing_dict(row)


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
                "status": s["status"],
                "peak_staff": s["peak_staff"],
                "peak_branches": s["peak_branches"],
                "extra_staff": s["extra_staff"],
                "extra_branches": s["extra_branches"],
                "special_price": business.base_price_override_cents is not None,
                "list_total_cents": s["list_total_cents"],
                "amount_due_cents": s["amount_due_cents"],
                "note": s["note"],
            }
        )

    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "Business", "Status", "Peak staff", "Peak branches",
                "Extra staff", "Extra branches", "Special price",
                "Plan total (R)", "Amount due (R)", "Note",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    # A leading = + - @ would run as a formula in Excel.
                    ("'" + r["business"]) if r["business"][:1] in "=+-@" else r["business"],
                    r["status"], r["peak_staff"], r["peak_branches"],
                    r["extra_staff"], r["extra_branches"],
                    "yes" if r["special_price"] else "",
                    _rands(r["list_total_cents"]), _rands(r["amount_due_cents"]),
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
    }
