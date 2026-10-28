"""Automatic tax (VAT) for quotes, invoices and case accounts.

The main admin switches tax on and sets the rate for their country
(South Africa: VAT 15%). Prices are entered without tax and the tax is
added on top: tax = (subtotal - discount) x rate, rounded to cents.
When tax is off, the tax amount stays whatever was entered (usually 0).
"""

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business

CENT = Decimal("0.01")


def tax_settings(db: Session, business_id: UUID) -> dict:
    business = db.get(Business, business_id)
    if business is None or not business.tax_enabled:
        return {"enabled": False, "name": "VAT", "rate": Decimal("0")}
    return {
        "enabled": True,
        "name": business.tax_name,
        "rate": Decimal(business.tax_rate),
    }


def automatic_tax(
    db: Session, business_id: UUID, subtotal: Decimal, discount: Decimal
) -> Decimal | None:
    """The tax to charge, or None when tax is not automatic."""

    settings = tax_settings(db, business_id)
    if not settings["enabled"]:
        return None
    taxable = max(Decimal(subtotal or 0) - Decimal(discount or 0), Decimal("0"))
    return (taxable * settings["rate"] / Decimal("100")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
