"""Profit and loss, sales by customer and the spreadsheet download."""

from datetime import date

from tests.test_business_mode import go_general
from tests.test_sales import admin_h, make_customer, make_invoice


def test_report_adds_up_and_exports(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)

    customer = make_customer(client, h, "Report Customer")
    inv = make_invoice(client, h, customer, price="500.00", qty="2")
    assert client.post(
        f"/sales/documents/{inv['id']}/payments",
        json={"amount": 400, "method": "eft"},
        headers=h,
    ).status_code == 201

    bill = client.post(
        "/bills",
        json={
            "supplier_name": "Landlord",
            "description": "Rent",
            "category": "rent",
            "amount": 150,
            "bill_date": date.today().isoformat(),
        },
        headers=h,
    ).json()
    assert client.post(
        f"/bills/{bill['id']}/pay", json={"method": "eft"}, headers=h
    ).status_code == 200

    body = client.get("/business-reports/overview", headers=h).json()
    assert body["income"] == 400.0
    assert body["expenses"] == 150.0
    assert body["profit"] == 250.0 and body["result"] == "profit"
    assert body["sales"]["invoiced"] == 1000.0
    assert body["sales"]["collected"] == 400.0
    top = body["top_customers"][0]
    assert top["customer_name"] == "Report Customer"
    assert top["invoiced"] == 1000.0 and top["paid"] == 400.0

    csv = client.get("/business-reports/export", headers=h)
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert "Report Customer" in csv.text and "250.00" in csv.text


def test_bad_range_and_funeral_business(client, auth_headers, db, test_data):
    h = admin_h(auth_headers, test_data)
    # A funeral business has no business reports.
    assert client.get("/business-reports/overview", headers=h).status_code == 403

    go_general(db, test_data)
    r = client.get(
        "/business-reports/overview",
        params={"date_from": "2026-05-01", "date_to": "2026-04-01"},
        headers=h,
    )
    assert r.status_code == 422
