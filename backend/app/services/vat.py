"""Deterministic VAT calculations for South African business transactions.

The caller must determine whether the business is VAT registered and the
correct tax treatment for the supply. This module does not provide tax advice
or decide whether a supply legally qualifies as zero-rated/exempt.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
STANDARD_VAT_RATE = Decimal("0.15")
TAX_TREATMENTS = frozenset({"standard", "zero_rated", "exempt", "out_of_scope"})


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class VATCalculation:
    entered_amount: Decimal
    taxable_value: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    treatment: str
    prices_include_vat: bool


def calculate_vat(
    amount: Decimal | str | int,
    *,
    vat_registered: bool,
    prices_include_vat: bool = False,
    treatment: str = "standard",
    rate: Decimal = STANDARD_VAT_RATE,
) -> VATCalculation:
    """Calculate VAT for one positive line amount.

    For VAT-inclusive pricing, amount is the gross price and VAT is extracted.
    For VAT-exclusive pricing, VAT is added to the entered amount.
    Non-registered businesses do not charge VAT. The rate is supplied by
    centrally managed code/configuration, never by an individual business.
    """
    entered = money(amount)
    if entered < 0:
        raise ValueError("Amount cannot be negative")
    if treatment not in TAX_TREATMENTS:
        raise ValueError("Unsupported tax treatment")
    if rate < 0 or rate > 1:
        raise ValueError("VAT rate must be between 0 and 1")

    chargeable = vat_registered and treatment == "standard"
    effective_rate = rate if chargeable else Decimal("0")

    if not chargeable:
        return VATCalculation(
            entered_amount=entered,
            taxable_value=entered,
            vat_rate=effective_rate,
            vat_amount=Decimal("0.00"),
            total_amount=entered,
            treatment=treatment,
            prices_include_vat=prices_include_vat,
        )

    if prices_include_vat:
        taxable_value = money(entered / (Decimal("1") + effective_rate))
        vat_amount = money(entered - taxable_value)
        total_amount = entered
    else:
        taxable_value = entered
        vat_amount = money(taxable_value * effective_rate)
        total_amount = money(taxable_value + vat_amount)

    return VATCalculation(
        entered_amount=entered,
        taxable_value=taxable_value,
        vat_rate=effective_rate,
        vat_amount=vat_amount,
        total_amount=total_amount,
        treatment=treatment,
        prices_include_vat=prices_include_vat,
    )
