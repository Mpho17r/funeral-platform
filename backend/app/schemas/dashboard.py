from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ============================================================
# RECENT CASE
# ============================================================

class DashboardRecentCase(BaseModel):
    id: UUID
    case_number: str
    deceased_full_name: str
    funeral_date: date | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# UPCOMING FUNERAL
# ============================================================

class DashboardUpcomingFuneral(BaseModel):
    id: UUID
    case_number: str
    deceased_full_name: str
    funeral_date: date
    funeral_venue: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# DASHBOARD SUMMARY
# ============================================================

class DashboardSummaryResponse(BaseModel):
    total_cases: int
    active_cases: int
    upcoming_funeral_count: int

    # Left out (null) for people without financial access.
    outstanding_balance: Decimal | None = None
    total_revenue: Decimal | None = None
    amount_paid: Decimal | None = None
    total_credit: Decimal | None = None

    # Families module does not have its own table yet.
    # We will connect this properly when the Families module
    # is implemented.
    total_families: int | None = None

    recent_cases: list[DashboardRecentCase]
    upcoming_funerals: list[DashboardUpcomingFuneral]
