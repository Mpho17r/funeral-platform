
from fastapi import FastAPI
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.services import scheduler_state
from app.database import engine

from app.api.businesses import router as businesses_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.cases import router as cases_router
from app.api.tasks import router as tasks_router
from app.api.task_workspace import router as task_workspace_router
from app.api.documents import router as documents_router
from app.api.services import router as services_router
from app.api.contacts import router as contacts_router
from app.api.contact_workspace import router as contact_workspace_router
from app.api.calendar import router as calendar_router
from app.api.financials import router as financials_router
from app.api.payments import router as payments_router
from app.api.families import router as families_router
from app.api.dashboard import router as dashboard_router
from app.api.presence import router as presence_router
from app.api.attendance import router as attendance_router
from app.api.groups import router as groups_router
from app.api.resources import router as resources_router
from app.api.claims import router as claims_router
from app.api.branches import router as branches_router
from app.api.inventory import router as inventory_router
from app.api.suppliers import router as suppliers_router
from app.api.communications import router as communications_router
from app.api.reports import router as reports_router
from app.api.audit_logs import router as audit_logs_router
from app.api.death_records import router as death_records_router
from app.api.arrangements import router as arrangements_router
from app.api.case_coverage import router as case_coverage_router
from app.api.mortuary import router as mortuary_router
from app.api.remains import router as remains_router
from app.api.branch_transfers import (
    router as branch_transfers_router,
)
from app.api.financial_documents import (
    router as financial_documents_router,
)

from app.api.membership_plans import router as membership_plans_router
from app.api.membership_plan_benefits import (
    router as membership_plan_benefits_router
)
from app.api.membership_contributions import (
    router as membership_contributions_router
)
from app.api.memberships import router as memberships_router
from app.api.imports import router as imports_router
from app.api.chat import router as chat_router
from app.api.finance_overview import router as finance_overview_router
from app.api.search import router as search_router
from app.api.compliance import router as compliance_router
from app.api.viewings import router as viewings_router
from app.api.data_export import router as data_export_router
from app.api.notifications import router as notifications_router
from app.api.expenses import router as expenses_router
from app.api.reconciliation import router as reconciliation_router
from app.api.operations_overview import router as operations_overview_router
from app.api.mortuary_overview import router as mortuary_overview_router
from app.api.meetings import router as meetings_router
from app.api.service_overview import router as service_overview_router
from app.api.onboarding import router as onboarding_router
from app.api.service_overview import router as service_overview_router
from app.api.members import router as members_router
from app.api.covered_dependents import (
    router as covered_dependents_router
)
from app.api.membership_payments import (
    router as membership_payments_router
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SECURITY HEADERS
# ============================================================

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/portal"):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.is_production:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


# ============================================================
# API ROUTERS
# ============================================================

app.include_router(
    businesses_router
)

app.include_router(
    auth_router
)

app.include_router(
    users_router
)

app.include_router(
    cases_router
)

app.include_router(
    tasks_router
)
app.include_router(
    task_workspace_router
)

app.include_router(
    documents_router
)

app.include_router(
    services_router
)

app.include_router(
    contacts_router
)
app.include_router(
    contact_workspace_router
)

app.include_router(
    calendar_router
)

app.include_router(
    financials_router
)

app.include_router(
    payments_router
)

app.include_router(
    families_router
)

app.include_router(
    dashboard_router
)

app.include_router(
    presence_router
)

app.include_router(
    attendance_router
)

# Groups
app.include_router(
    groups_router
)

# Resources (vehicles, venues, equipment) and bookings
app.include_router(
    resources_router
)

# Branches
app.include_router(
    branches_router
)

app.include_router(
    branch_transfers_router
)

# Communications
app.include_router(
    communications_router
)

# Inventory and suppliers
app.include_router(
    suppliers_router
)

app.include_router(
    inventory_router
)

# Death records and paperwork
app.include_router(
    death_records_router
)

# Mortuary and custody of remains
app.include_router(
    mortuary_router
)

app.include_router(
    remains_router
)

# Funeral arrangements, collections and run sheet
app.include_router(
    arrangements_router
)

# Case coverage and waiting periods
app.include_router(
    case_coverage_router
)

# Reports
app.include_router(
    reports_router
)

# Audit trail
app.include_router(
    audit_logs_router
)

# Beneficiaries and claims
app.include_router(
    claims_router
)

# Quotes, invoices and receipts
app.include_router(
    financial_documents_router
)

# Membership plans
app.include_router(
    membership_plans_router
)

# Membership plan benefits
app.include_router(
    membership_plan_benefits_router
)

# Memberships
app.include_router(
    memberships_router
)

# Members
app.include_router(
    imports_router
)

app.include_router(
    chat_router
)

app.include_router(
    search_router
)

app.include_router(
    compliance_router
)

app.include_router(
    viewings_router
)

app.include_router(
    data_export_router
)

app.include_router(
    notifications_router
)

app.include_router(
    finance_overview_router
)

app.include_router(
    expenses_router
)

app.include_router(
    reconciliation_router
)

app.include_router(
    operations_overview_router
)

app.include_router(
    mortuary_overview_router
)

app.include_router(
    meetings_router
)

app.include_router(
    service_overview_router
)

app.include_router(
    onboarding_router
)

app.include_router(
    service_overview_router
)

app.include_router(
    members_router
)

# Covered dependents
app.include_router(
    covered_dependents_router
)

# Membership contributions
app.include_router(
    membership_contributions_router
)

# Membership payments
app.include_router(
    membership_payments_router
)

# Family and member portals
from app.api.portal import router as portal_router  # noqa: E402

app.include_router(portal_router)

from app.api.platform import router as platform_router  # noqa: E402

app.include_router(platform_router)

from app.api.assistant import router as assistant_router  # noqa: E402

app.include_router(assistant_router)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "online",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check(response: Response):
    """For hosting health checks and uptime monitors.

    Answers 503 when the database cannot be reached, so a monitor or load
    balancer sees the problem instead of a false "healthy".
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "disconnected"
        response.status_code = 503

    return {
        "status": "healthy" if database_status == "connected" else "unhealthy",
        "database": database_status,
        "scheduler": scheduler_state.read()["state"],
    }
