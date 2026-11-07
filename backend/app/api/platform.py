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
from app.models.pricing import PricingPlan
from app.security import verify_password
from app.services.permission_service import has_permission
from app.services import plan_limits
from app.services import pricing as pricing_service

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


def _business_row(
    db: Session,
    b: Business,
    *,
    usage: dict | None = None,
    plan: PricingPlan | None = None,
) -> dict:
    # Callers rendering many businesses pass preloaded usage and plans to
    # avoid an N+1 query pattern. Single-business updates can use the defaults.
    usage = usage if usage is not None else plan_limits.usage(db, b.id)
    plan = plan or pricing_service.plan_for(db, b)
    monthly = pricing_service.quote(
        plan,
        staff=usage[pricing_service.STAFF],
        branches=usage[pricing_service.BRANCHES],
        base_override_cents=b.base_price_override_cents,
    )["total_cents"]

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
        "usage": usage,
        "base_price_override_cents": b.base_price_override_cents,
        "plan": plan.name,
        "monthly_cents": monthly,
    }


@router.get("/platform/businesses")
def platform_businesses(
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    businesses = db.query(Business).order_by(Business.created_at.desc()).all()
    business_ids = [business.id for business in businesses]
    usage_by_business = plan_limits.usage_many(db, business_ids)

    # Load plans once, then select each business's chosen plan or the same
    # active-first fallback used by pricing_service.plan_for().
    plans = db.query(PricingPlan).order_by(PricingPlan.sort_order).all()
    plans_by_id = {plan.id: plan for plan in plans}
    active_by_type: dict[str, list[PricingPlan]] = {}
    all_by_type: dict[str, list[PricingPlan]] = {}
    for plan in plans:
        all_by_type.setdefault(plan.business_type, []).append(plan)
        if plan.is_active:
            active_by_type.setdefault(plan.business_type, []).append(plan)

    fallback_plans = plans

    def selected_plan(business: Business) -> PricingPlan:
        if business.plan_id and business.plan_id in plans_by_id:
            return plans_by_id[business.plan_id]
        options = active_by_type.get(business.business_type) or all_by_type.get(
            business.business_type
        ) or fallback_plans
        return options[0]

    return [
        _business_row(
            db,
            business,
            usage=usage_by_business[business.id],
            plan=selected_plan(business),
        )
        for business in businesses
    ]


@router.get("/platform/summary")
def platform_summary(
    db: Session = Depends(get_db),
    admin: PlatformAdmin = Depends(get_platform_admin),
):
    # The summary needs only aggregate counts. Do not build a full pricing
    # row for every customer or issue one count query per business.
    businesses = db.query(Business.id, Business.subscription_status).all()
    business_ids = [business_id for business_id, _ in businesses]

    by_status: dict[str, int] = {}
    for _, status in businesses:
        by_status[status] = by_status.get(status, 0) + 1

    usage = plan_limits.usage_many(db, business_ids)
    totals: dict[str, int] = {}
    for counts in usage.values():
        for key, value in counts.items():
            totals[key] = totals.get(key, 0) + value

    return {"businesses": len(businesses), "by_status": by_status, "totals": totals}


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
    # A special base price for this customer (cents). Send null to go back
    # to the standard price.
    base_price_override_cents: int | None = Field(
        default=None, ge=0, le=10_000_000
    )


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
                   "max_active_cases", "base_price_override_cents"):
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
    used = plan_limits.usage(db, b.id)
    staff, branches = used[pricing_service.STAFF], used[pricing_service.BRANCHES]
    settings_row = pricing_service.get_pricing(db)
    vat = settings_row.vat_percent
    plan = pricing_service.plan_for(db, b)

    out = {
        "tier": b.subscription_tier,
        "status": b.subscription_status,
        "trial_ends_at": b.trial_ends_at,
        "limits": plan_limits.limits(b),
        "usage": used,
        **pricing_service.settings_dict(settings_row),
        "plan": pricing_service.plan_dict(plan),
        "plan_chosen": b.plan_id is not None,
        "plans": [
            pricing_service.plan_dict(x)
            for x in pricing_service.plans_for(db, b.business_type)
        ],
        # Lets the "add staff" and "add branch" screens say what it will cost.
        **pricing_service.next_costs(plan, staff, branches, vat),
    }

    # The bill itself is for the people who run the business.
    if has_permission(
        db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        permission_key="subscription.view",
    ):
        now = pricing_service.today()
        out["bill"] = pricing_service.statement(db, b, now.year, now.month)
        out["bill"]["now"] = pricing_service.quote(
            plan,
            staff=staff,
            branches=branches,
            base_override_cents=b.base_price_override_cents,
            vat_percent=vat,
        )

    return out


class PlanChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str = Field(min_length=1, max_length=40)


@router.put("/subscription/plan")
def choose_plan(
    data: PlanChoice,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """The people who run the business pick (or change) its plan."""
    if not has_permission(
        db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        permission_key="subscription.view",
    ):
        raise HTTPException(403, "Only the people who run the business can change the plan")

    b = db.get(Business, current_user["business_id"])
    pricing_service.seed_default_plans(db)
    plan = (
        db.query(PricingPlan)
        .filter(
            PricingPlan.code == data.plan_code,
            PricingPlan.business_type == b.business_type,
            PricingPlan.is_active.is_(True),
        )
        .first()
    )
    if plan is None:
        raise HTTPException(404, "That plan is not available for your kind of business")

    b.plan_id = plan.id
    db.commit()
    return {"plan": pricing_service.plan_dict(plan)}
