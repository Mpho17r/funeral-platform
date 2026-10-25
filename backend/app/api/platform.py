"""
Saccharum platform administration.

A separate layer from any business: its own sign-in and token type, and it
sees only counts and subscription details, never cases, members or
documents. Platform admins are created from the command line
(python -m app.create_platform_admin).
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.audit_log import AuditLog
from app.models.business import Business
from app.models.platform_admin import PlatformAdmin
from app.security import verify_password
from app.services import plan_limits

router = APIRouter(tags=["Platform"])
bearer = HTTPBearer()

AUTH_TYPE = "platform_admin"

_failures: dict[str, deque] = defaultdict(deque)


def _throttled(ip: str) -> bool:
    now = time.monotonic()
    q = _failures[ip]
    while q and now - q[0] > 600:
        q.popleft()
    return len(q) >= 10


def make_token(admin: PlatformAdmin) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(admin.id),
            "auth_type": AUTH_TYPE,
            "iat": int(now.timestamp()),
            "exp": now + timedelta(minutes=120),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def get_platform_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> PlatformAdmin:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid authentication token")
    if payload.get("auth_type") != AUTH_TYPE:
        raise HTTPException(401, "Invalid authentication layer")
    admin = db.get(PlatformAdmin, UUID(payload["sub"]))
    if admin is None or not admin.is_active:
        raise HTTPException(401, "Invalid authentication token")
    return admin


class PlatformLogin(BaseModel):
    email: str
    password: str


@router.post("/platform/login")
def platform_login(
    data: PlatformLogin, request: Request, db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    if _throttled(ip):
        raise HTTPException(429, "Too many attempts. Try again later.")
    admin = (
        db.query(PlatformAdmin)
        .filter(func.lower(PlatformAdmin.email) == data.email.strip().lower())
        .first()
    )
    if (
        admin is None
        or not admin.is_active
        or not verify_password(data.password, admin.password_hash)
    ):
        _failures[ip].append(time.monotonic())
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": make_token(admin), "token_type": "bearer"}


def _business_row(db: Session, b: Business) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "slug": b.slug,
        "is_active": b.is_active,
        "created_at": b.created_at,
        "tier": b.subscription_tier,
        "status": b.subscription_status,
        "trial_ends_at": b.trial_ends_at,
        "limits": plan_limits.limits(b),
        "usage": plan_limits.usage(db, b.id),
    }


@router.get("/platform/businesses")
def platform_businesses(
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    rows = db.query(Business).order_by(Business.created_at.desc()).all()
    return [_business_row(db, b) for b in rows]


@router.get("/platform/summary")
def platform_summary(
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    rows = [_business_row(db, b) for b in db.query(Business).all()]
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    totals: dict[str, int] = {}
    for r in rows:
        for key, value in r["usage"].items():
            totals[key] = totals.get(key, 0) + value
    return {"businesses": len(rows), "by_status": by_status, "totals": totals}


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str | None = None
    status: str | None = None
    apply_tier_defaults: bool = False
    trial_ends_at: datetime | None = None
    max_branches: int | None = Field(default=None, ge=1)
    max_users: int | None = Field(default=None, ge=1)
    max_members: int | None = Field(default=None, ge=1)
    max_active_cases: int | None = Field(default=None, ge=1)


@router.patch("/platform/businesses/{business_id}/subscription")
def update_subscription(
    business_id: UUID,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    b = db.get(Business, business_id)
    if b is None:
        raise HTTPException(404, "Business not found")

    sent = data.model_fields_set
    if data.tier is not None:
        if data.tier not in plan_limits.TIERS:
            raise HTTPException(422, "Unknown plan tier")
        b.subscription_tier = data.tier
        if data.apply_tier_defaults:
            for column, value in plan_limits.TIER_DEFAULTS[data.tier].items():
                setattr(b, column, value)
    if data.status is not None:
        if data.status not in plan_limits.STATUSES:
            raise HTTPException(422, "Unknown subscription status")
        b.subscription_status = data.status
    if "trial_ends_at" in sent:
        b.trial_ends_at = data.trial_ends_at
    for column in ("max_branches", "max_users", "max_members",
                   "max_active_cases"):
        if column in sent:
            setattr(b, column, getattr(data, column))

    db.add(
        AuditLog(
            business_id=b.id,
            user_id=None,
            action="platform.subscription_changed",
            entity_type="business",
            entity_id=b.id,
            details={
                "by_platform_admin": str(admin.id),
                "changed": sorted(sent),
            },
            notes="Subscription changed by the platform owner.",
        )
    )
    db.commit()
    return _business_row(db, b)


# ------------------------------------------------- the business's own view


@router.get("/subscription")
def my_subscription(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    b = db.get(Business, current_user["business_id"])
    return {
        "tier": b.subscription_tier,
        "status": b.subscription_status,
        "trial_ends_at": b.trial_ends_at,
        "limits": plan_limits.limits(b),
        "usage": plan_limits.usage(db, b.id),
    }
