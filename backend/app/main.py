from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine

from app.api.businesses import router as businesses_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.cases import router as cases_router
from app.api.tasks import router as tasks_router
from app.api.documents import router as documents_router
from app.api.services import router as services_router
from app.api.contacts import router as contacts_router
from app.api.financials import router as financials_router
from app.api.payments import router as payments_router
from app.api.families import router as families_router
from app.api.dashboard import router as dashboard_router


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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    documents_router
)

app.include_router(
    financials_router
)

app.include_router(
    services_router
)

app.include_router(
    contacts_router
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
def health_check():

    database_status = "unknown"

    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

        database_status = "connected"

    except Exception:
        database_status = "disconnected"

    return {
        "status": "healthy",
        "database": database_status,
    }
