from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase
from app.models.case_financial import CaseFinancial
from app.models.case_contact import CaseContact

from app.schemas.dashboard import (
    DashboardSummaryResponse,
    DashboardRecentCase,
    DashboardUpcomingFuneral,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


# ============================================================
# DASHBOARD SUMMARY
# GET /dashboard/summary
# ============================================================

@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("dashboard.view")),
):
    business_id = current_user["business_id"]

    # ========================================================
    # TOTAL CASES
    # ========================================================

    total_cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id
        )
        .count()
    )

    # ========================================================
    # ACTIVE CASES
    #
    # Active:
    # - open
    # - confirmed
    # - in_progress
    # ========================================================

    active_cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.status.in_(
                [
                    "open",
                    "confirmed",
                    "in_progress",
                ]
            ),
        )
        .count()
    )

    # ========================================================
    # TOTAL FAMILIES
    #
    # Count unique family / next-of-kin contacts.
    #
    # A contact belongs to the current business and is
    # associated with a funeral case.
    # ========================================================

    total_families = (
        db.query(CaseContact)
        .filter(
            CaseContact.business_id == business_id,
            CaseContact.contact_type.in_(
                [
                    "family",
                    "next_of_kin",
                ]
            ),
        )
        .count()
    )

    # ========================================================
    # FINANCIAL TOTALS
    #
    # These values come from case_financials.
    #
    # amount_paid is maintained from CasePayment records
    # by the financial system.
    # ========================================================

    financial_totals = (
        db.query(
            func.coalesce(
                func.sum(CaseFinancial.total),
                0,
            ).label("total_revenue"),

            func.coalesce(
                func.sum(CaseFinancial.amount_paid),
                0,
            ).label("amount_paid"),

            func.coalesce(
                func.sum(CaseFinancial.balance),
                0,
            ).label("outstanding_balance"),

            func.coalesce(
                func.sum(CaseFinancial.credit),
                0,
            ).label("total_credit"),
        )
        .filter(
            CaseFinancial.business_id == business_id
        )
        .first()
    )

    total_revenue = Decimal(
        str(financial_totals.total_revenue or 0)
    ).quantize(
        Decimal("0.01")
    )

    amount_paid = Decimal(
        str(financial_totals.amount_paid or 0)
    ).quantize(
        Decimal("0.01")
    )

    outstanding_balance = Decimal(
        str(financial_totals.outstanding_balance or 0)
    ).quantize(
        Decimal("0.01")
    )

    total_credit = Decimal(
        str(financial_totals.total_credit or 0)
    ).quantize(
        Decimal("0.01")
    )

    # ========================================================
    # RECENT CASES
    #
    # Latest 5 cases.
    # ========================================================

    recent_cases_db = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id
        )
        .order_by(
            FuneralCase.created_at.desc()
        )
        .limit(5)
        .all()
    )

    recent_cases = [
        DashboardRecentCase(
            id=case.id,
            case_number=case.case_number,
            deceased_full_name=case.deceased_full_name,
            funeral_date=case.funeral_date,
            status=case.status,
            created_at=case.created_at,
        )
        for case in recent_cases_db
    ]

    # ========================================================
    # UPCOMING FUNERALS
    #
    # Today through the next 30 days.
    #
    # Excludes:
    # - cancelled
    # - closed
    # ========================================================

    today = date.today()

    thirty_days_from_now = (
        today + timedelta(days=30)
    )

    upcoming_funerals_db = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id,

            FuneralCase.funeral_date >= today,

            FuneralCase.funeral_date <= thirty_days_from_now,

            FuneralCase.status.notin_(
                [
                    "cancelled",
                    "closed",
                ]
            ),
        )
        .order_by(
            FuneralCase.funeral_date.asc()
        )
        .limit(5)
        .all()
    )

    upcoming_funerals = [
        DashboardUpcomingFuneral(
            id=case.id,
            case_number=case.case_number,
            deceased_full_name=case.deceased_full_name,
            funeral_date=case.funeral_date,
            funeral_venue=case.funeral_venue,
        )
        for case in upcoming_funerals_db
    ]

    # ========================================================
    # RETURN DASHBOARD SUMMARY
    # ========================================================

    return DashboardSummaryResponse(
        total_cases=total_cases,

        active_cases=active_cases,

        upcoming_funeral_count=len(
            upcoming_funerals
        ),

        outstanding_balance=outstanding_balance,

        total_revenue=total_revenue,

        amount_paid=amount_paid,

        total_credit=total_credit,

        total_families=total_families,

        recent_cases=recent_cases,

        upcoming_funerals=upcoming_funerals,
    )
