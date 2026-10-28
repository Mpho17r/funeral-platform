from decimal import Decimal

from app.models.business import Business
from app.services.tax import automatic_tax, tax_settings


def test_off_by_default_leaves_tax_alone(db, test_data):
    biz = test_data["business_a"]
    assert automatic_tax(db, biz.id, Decimal("1000"), Decimal("0")) is None
    assert tax_settings(db, biz.id)["enabled"] is False


def test_fifteen_percent_after_discount(db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    biz.tax_enabled, biz.tax_rate = True, Decimal("15.00")
    db.commit()
    assert automatic_tax(db, biz.id, Decimal("1000"), Decimal("100")) == Decimal("135.00")
    assert automatic_tax(db, biz.id, Decimal("0.10"), Decimal("0")) == Decimal("0.02")


def test_only_main_admin_can_change_tax(client, auth_headers, test_data):
    biz = test_data["business_a"]
    body = {"tax_enabled": True, "tax_name": "VAT", "tax_rate": 15}
    ok = client.patch(f"/businesses/{biz.id}/tax", json=body,
                      headers=auth_headers(test_data["main_admin"]))
    assert ok.status_code == 200 and ok.json()["tax_rate"] == 15.0
    no = client.patch(f"/businesses/{biz.id}/tax", json=body,
                      headers=auth_headers(test_data["staff"]))
    assert no.status_code == 403
    bad = client.patch(f"/businesses/{biz.id}/tax", json={**body, "tax_rate": 150},
                       headers=auth_headers(test_data["main_admin"]))
    assert bad.status_code == 422


def test_quote_gets_vat_automatically(client, auth_headers, db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    biz.tax_enabled, biz.tax_rate = True, Decimal("15.00")
    db.commit()
    from tests.test_branches import make_case
    case = make_case(db, biz)
    r = client.post(
        f"/cases/{case.id}/financial-documents",
        json={"document_type": "quote", "valid_until": "2030-01-01",
              "tax": 0, "discount": 0,
              "lines": [{"description": "Hearse", "quantity": 1, "unit_price": 1000}]},
        headers=auth_headers(test_data["manager"]),
    )
    assert r.status_code in (200, 201), r.text
    doc = r.json()
    assert Decimal(str(doc["tax"])) == Decimal("150.00")
    assert Decimal(str(doc["total"])) == Decimal("1150.00")
