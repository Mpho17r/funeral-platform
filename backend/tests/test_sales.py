"""Customers, quotes, invoices, payments, who-owes-you and bills."""

from datetime import date, timedelta

from app.models.business import Business
from app.models.notification import Notification
from app.services import overdue_alerts
from tests.test_business_mode import go_general


def admin_h(auth_headers, test_data):
    return auth_headers(test_data["main_admin"])


def make_customer(client, h, name="Thandi Stores"):
    r = client.post("/customers", json={"name": name, "phone": "0821234567"}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def make_invoice(client, h, customer, price="1000.00", qty="2", issue=True, due=None):
    r = client.post(
        "/sales/documents",
        json={
            "customer_id": customer,
            "document_type": "invoice",
            "lines": [{"description": "Delivery", "quantity": qty, "unit_price": price}],
            "due_date": due,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    if issue:
        r = client.post(f"/sales/documents/{doc['id']}/issue", json={}, headers=h)
        assert r.status_code == 200, r.text
        doc = r.json()
    return doc


def test_funeral_business_has_none_of_this(client, auth_headers, test_data):
    h = admin_h(auth_headers, test_data)
    assert client.get("/customers", headers=h).status_code == 403
    assert client.get("/sales/documents", headers=h).status_code == 403
    assert client.get("/bills", headers=h).status_code == 403


def test_customer_basics_and_archive(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    cid = make_customer(client, h)
    assert client.get("/customers?search=thandi", headers=h).json()["total"] == 1
    assert client.patch(f"/customers/{cid}", json={"email": "t@x.co"}, headers=h).json()["email"] == "t@x.co"
    assert client.patch(f"/customers/{cid}", json={"name": " "}, headers=h).status_code == 422
    client.post(f"/customers/{cid}/archive", headers=h)
    assert client.get("/customers", headers=h).json()["total"] == 0
    assert client.get("/customers?include_archived=true", headers=h).json()["total"] == 1


def test_invoice_issue_pay_and_profit(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    cid = make_customer(client, h)
    inv = make_invoice(client, h, cid)  # 2 x 1000
    assert inv["number"].startswith("INV-") and inv["total"] == 2000.0
    assert inv["state"] == "unpaid" and inv["balance"] == 2000.0
    assert inv["due_date"] is not None

    # An issued invoice cannot be edited.
    assert client.patch(f"/sales/documents/{inv['id']}", json={"notes": "x"}, headers=h).status_code == 409

    r = client.post(f"/sales/documents/{inv['id']}/payments", json={"amount": "500.00", "method": "cash"}, headers=h)
    assert r.status_code == 201
    assert r.json()["state"] == "partial" and r.json()["balance"] == 1500.0

    # More than is owed is refused.
    assert client.post(f"/sales/documents/{inv['id']}/payments", json={"amount": "1500.01"}, headers=h).status_code == 422

    r = client.post(f"/sales/documents/{inv['id']}/payments", json={"amount": "1500.00", "method": "eft"}, headers=h)
    assert r.json()["state"] == "paid"

    # The money shows up in money received and the profit and loss.
    summary = client.get("/money/summary", headers=h).json()
    assert summary["income"] == 2000.0

    # An invoice with payments cannot be voided until they are cancelled.
    assert client.post(f"/sales/documents/{inv['id']}/void", json={"reason": "mistake"}, headers=h).status_code == 409
    pid = r.json()["payments"][0]["id"]
    r = client.post(f"/sales/payments/{pid}/void", json={"reason": "bounced"}, headers=h)
    assert r.json()["state"] == "partial"
    assert client.get("/money/summary", headers=h).json()["income"] == 1500.0


def test_tax_is_added_automatically(client, auth_headers, db, test_data):
    biz = go_general(db, test_data)
    biz.tax_enabled = True
    biz.tax_rate = 15
    db.commit()
    h = admin_h(auth_headers, test_data)
    inv = make_invoice(client, h, make_customer(client, h), price="100.00", qty="1", issue=False)
    assert inv["tax"] == 15.0 and inv["total"] == 115.0


def test_quote_to_invoice(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    cid = make_customer(client, h)
    q = client.post(
        "/sales/documents",
        json={"customer_id": cid, "document_type": "quote", "lines": [{"description": "Paint job", "quantity": "1", "unit_price": "800"}]},
        headers=h,
    ).json()
    q = client.post(f"/sales/documents/{q['id']}/issue", json={}, headers=h).json()
    assert q["number"].startswith("QUO-")
    assert client.post(f"/sales/documents/{q['id']}/accept", headers=h).json()["status"] == "accepted"
    inv = client.post(f"/sales/documents/{q['id']}/convert", headers=h)
    assert inv.status_code == 201
    assert inv.json()["document_type"] == "invoice" and inv.json()["total"] == 800.0
    assert client.post(f"/sales/documents/{q['id']}/convert", headers=h).status_code == 409


def test_receivables_ageing_and_overdue_alert(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    cid = make_customer(client, h)
    late = make_invoice(client, h, cid, price="300.00", qty="1", due=(date.today() - timedelta(days=45)).isoformat())
    make_invoice(client, h, cid, price="200.00", qty="1", due=(date.today() + timedelta(days=5)).isoformat())

    r = client.get("/sales/receivables", headers=h).json()
    assert r["outstanding"] == 500.0 and r["overdue"] == 300.0
    assert r["buckets"]["31_60"] == 300.0 and r["buckets"]["current"] == 200.0
    assert r["customers"][0]["owes"] == 500.0
    assert r["invoices"][0]["id"] == late["id"]
    assert client.get("/sales/documents?state=overdue", headers=h).json()["total"] == 1

    assert overdue_alerts.run(db) >= 1
    again = overdue_alerts.run(db)
    assert again == 0  # each overdue invoice tells people once
    assert db.query(Notification).filter(Notification.kind == "invoice_overdue").count() >= 1

    detail = client.get(f"/customers/{cid}", headers=h).json()
    assert detail["owes"] == 500.0 and len(detail["documents"]) == 2


def test_bills_become_expenses_when_paid(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    bill = client.post(
        "/bills",
        json={"supplier_name": "City Power", "description": "October", "category": "utilities", "amount": "750.00",
              "bill_date": date.today().isoformat(), "due_date": (date.today() - timedelta(days=2)).isoformat()},
        headers=h,
    )
    assert bill.status_code == 201
    listing = client.get("/bills", headers=h).json()
    assert listing["owed"] == 750.0 and listing["overdue"] == 750.0

    paid = client.post(f"/bills/{bill.json()['id']}/pay", json={"method": "eft"}, headers=h)
    assert paid.json()["status"] == "paid"
    assert client.get("/bills", headers=h).json()["owed"] == 0
    assert client.get("/money/summary", headers=h).json()["expenses"] == 750.0
    assert client.post(f"/bills/{bill.json()['id']}/pay", json={}, headers=h).status_code == 409


def test_staff_can_see_customers_but_not_make_invoices(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    cid = make_customer(client, h)
    staff = auth_headers(test_data["staff"]) if "staff" in test_data else None
    if staff is None:
        return
    assert client.get("/customers", headers=staff).status_code == 200
    assert client.post("/sales/documents", json={"customer_id": cid, "document_type": "quote"}, headers=staff).status_code == 403
