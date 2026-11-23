"""LINDA platform subscription payments via PayFast hosted checkout."""

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user_for_subscription
from app.models.business import Business
from app.models.platform_payment import PlatformPayment
from app.models.user import User
from app.services import pricing as pricing_service
from app.services import payfast
from app.services.permission_service import has_permission

router = APIRouter(tags=["Subscription payments"])


def _can_manage_subscription(db: Session, current_user: dict) -> bool:
    return has_permission(
        db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        permission_key="subscription.view",
    )


@router.post("/subscription/payfast/checkout")
def create_payfast_checkout(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_for_subscription),
):
    """Create a hosted PayFast payment for this month's server-calculated bill."""
    if not _can_manage_subscription(db, current_user):
        raise HTTPException(403, "Only the business owner or authorised administrator can pay.")
    if not (
        settings.payfast_merchant_id
        and settings.payfast_merchant_key
        and settings.payfast_passphrase
        and settings.public_api_url.startswith("https://")
    ):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PayFast is not configured yet. Please contact Saccharum Technologies.",
        )

    business = db.get(Business, current_user["business_id"])
    user = db.get(User, current_user["user_id"])
    if business is None or user is None:
        raise HTTPException(404, "Business or account not found.")

    today = pricing_service.today()
    period_start = date(today.year, today.month, 1)
    staff, branches = pricing_service.peaks(db, business, today.year, today.month)
    plan = pricing_service.plan_for(db, business)
    vat = pricing_service.get_pricing(db).vat_percent
    quote = pricing_service.quote(
        plan,
        staff=staff,
        branches=branches,
        base_override_cents=business.base_price_override_cents,
        vat_percent=vat,
    )
    amount_cents = quote["total_incl_vat_cents"]
    if amount_cents < 500:
        raise HTTPException(422, "The subscription amount is below PayFast's R5 minimum.")

    existing = (
        db.query(PlatformPayment)
        .filter(
            PlatformPayment.business_id == business.id,
            PlatformPayment.period_start == period_start,
            PlatformPayment.status == "paid",
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(409, "This month's LINDA subscription payment is already complete.")

    payment = (
        db.query(PlatformPayment)
        .filter(
            PlatformPayment.business_id == business.id,
            PlatformPayment.period_start == period_start,
            PlatformPayment.status == "pending",
            PlatformPayment.amount_cents == amount_cents,
        )
        .order_by(PlatformPayment.created_at.desc())
        .first()
    )
    if payment is None:
        payment = PlatformPayment(
            business_id=business.id,
            merchant_payment_id=f"LINDA-{uuid4().hex}",
            period_start=period_start,
            amount_cents=amount_cents,
            currency="ZAR",
            status="pending",
            description=f"LINDA {plan.name} subscription - {period_start:%Y-%m}",
        )
        db.add(payment)
        db.flush()

    app_url = settings.public_app_url.rstrip("/")
    api_url = settings.public_api_url.rstrip("/")
    fields = [
        ("merchant_id", settings.payfast_merchant_id),
        ("merchant_key", settings.payfast_merchant_key),
        ("return_url", f"{app_url}/subscription?payment=returned"),
        ("cancel_url", f"{app_url}/subscription?payment=cancelled"),
        ("notify_url", f"{api_url}/subscription/payfast/itn"),
        ("email_address", user.email),
        ("m_payment_id", payment.merchant_payment_id),
        ("amount", f"{amount_cents / 100:.2f}"),
        ("item_name", "LINDA subscription"),
        ("item_description", payment.description[:255]),
        ("custom_str1", str(business.id)),
    ]
    fields.append(("signature", payfast.signature(fields, settings.payfast_passphrase)))
    db.commit()

    return {
        "provider": "payfast",
        "action": payfast.checkout_url(sandbox=settings.payfast_sandbox),
        "fields": dict(fields),
        "amount_cents": amount_cents,
        "currency": "ZAR",
        "period_start": period_start.isoformat(),
        "payment_reference": payment.merchant_payment_id,
    }


@router.post("/subscription/payfast/itn", response_class=PlainTextResponse)
async def payfast_itn(request: Request, db: Session = Depends(get_db)):
    """Public PayFast ITN endpoint. Redirects are never treated as proof of payment."""
    form = await request.form()
    fields = [(key, str(value)) for key, value in form.multi_items() if isinstance(value, str)]
    data = dict(fields)
    supplied_signature = data.get("signature", "")

    if not payfast.valid_signature(fields, supplied_signature, settings.payfast_passphrase):
        raise HTTPException(400, "Invalid PayFast signature.")
    if data.get("merchant_id") != settings.payfast_merchant_id:
        raise HTTPException(400, "PayFast merchant mismatch.")
    if not payfast.validate_itn(fields, sandbox=settings.payfast_sandbox):
        raise HTTPException(400, "PayFast notification could not be verified.")

    merchant_payment_id = data.get("m_payment_id", "")
    payment = (
        db.query(PlatformPayment)
        .filter(PlatformPayment.merchant_payment_id == merchant_payment_id)
        .with_for_update()
        .first()
    )
    if payment is None:
        raise HTTPException(404, "LINDA payment reference not found.")

    if data.get("payment_status") == "CANCELLED":
        if payment.status == "pending":
            payment.status = "cancelled"
            payment.provider_payload = {"payment_status": "CANCELLED"}
            db.commit()
        return "OK"

    if data.get("payment_status") != "COMPLETE":
        return "OK"
    if payment.status == "paid":
        return "OK"

    try:
        gross_cents = int((Decimal(data.get("amount_gross", "0")) * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        raise HTTPException(400, "Invalid PayFast payment amount.")

    if gross_cents != payment.amount_cents:
        raise HTTPException(400, "PayFast amount does not match the LINDA invoice.")

    provider_payment_id = data.get("pf_payment_id", "")
    if not provider_payment_id:
        raise HTTPException(400, "PayFast payment reference is missing.")

    payment.status = "paid"
    payment.provider_payment_id = provider_payment_id
    payment.paid_at = datetime.now(timezone.utc)
    payment.provider_payload = {
        "payment_status": "COMPLETE",
        "merchant_id": data.get("merchant_id"),
        "pf_payment_id": provider_payment_id,
        "amount_gross": data.get("amount_gross"),
        "amount_fee": data.get("amount_fee"),
        "amount_net": data.get("amount_net"),
    }

    business = db.get(Business, payment.business_id)
    if business is None:
        raise HTTPException(404, "LINDA business no longer exists.")
    business.subscription_status = "active"
    db.commit()
    return "OK"
