from decimal import Decimal

import pytest

from app.services.vat import calculate_vat


def test_standard_vat_exclusive_price():
    result = calculate_vat("1000.00", vat_registered=True)
    assert result.taxable_value == Decimal("1000.00")
    assert result.vat_rate == Decimal("0.15")
    assert result.vat_amount == Decimal("150.00")
    assert result.total_amount == Decimal("1150.00")


def test_standard_vat_inclusive_price_extracts_vat():
    result = calculate_vat(
        "1150.00", vat_registered=True, prices_include_vat=True
    )
    assert result.taxable_value == Decimal("1000.00")
    assert result.vat_amount == Decimal("150.00")
    assert result.total_amount == Decimal("1150.00")


def test_non_registered_business_does_not_charge_vat():
    result = calculate_vat("1000.00", vat_registered=False)
    assert result.vat_amount == Decimal("0.00")
    assert result.total_amount == Decimal("1000.00")


@pytest.mark.parametrize("treatment", ["zero_rated", "exempt", "out_of_scope"])
def test_non_standard_treatments_do_not_add_standard_vat(treatment):
    result = calculate_vat(
        "1000.00", vat_registered=True, treatment=treatment
    )
    assert result.vat_amount == Decimal("0.00")
    assert result.total_amount == Decimal("1000.00")
    assert result.treatment == treatment


def test_rounding_uses_two_decimal_places():
    result = calculate_vat("10.01", vat_registered=True)
    assert result.vat_amount == Decimal("1.50")
    assert result.total_amount == Decimal("11.51")


def test_rejects_unknown_treatment():
    with pytest.raises(ValueError, match="Unsupported tax treatment"):
        calculate_vat("100.00", vat_registered=True, treatment="custom")


def test_rejects_negative_amount():
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_vat("-1.00", vat_registered=True)
