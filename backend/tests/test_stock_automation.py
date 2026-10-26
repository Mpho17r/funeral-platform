"""Stock that issues itself, warns when low and can reorder."""

from decimal import Decimal

import pytest

from app.config import settings
from app.models.inventory import InventoryItem, PurchaseOrder, Supplier
from app.models.notification import Notification
from app.services import message_delivery as md
from tests.test_branches import make_case


@pytest.fixture
def stock(client, auth_headers, db, test_data):
    h = auth_headers(test_data["main_admin"])
    supplier = Supplier(
        business_id=test_data["business_a"].id, name="Coffins Co",
        email="orders@coffins.test", is_active=True,
    )
    db.add(supplier)
    db.commit()
    r = client.post("/inventory/items", headers=h, json={
        "sku": "COF-1", "name": "Oak coffin", "category": "coffin",
        "supplier_id": str(supplier.id), "reorder_level": "2",
        "reorder_quantity": "5", "opening_quantity": "4",
    })
    assert r.status_code == 201, r.text
    return {"h": h, "item": r.json(), "supplier": supplier,
            "case": make_case(db, test_data["business_a"])}


def add_service(client, stock, **extra):
    body = {"service_type": "coffin", "service_name": "Oak coffin",
            "quantity": 1, "unit_price": "5000",
            "inventory_item_id": stock["item"]["id"], **extra}
    return client.post(f"/cases/{stock['case'].id}/services",
                       json=body, headers=stock["h"])


def on_hand(db, stock):
    db.expire_all()
    return db.get(InventoryItem, stock["item"]["id"]).quantity_on_hand


def test_linked_service_takes_stock_automatically(client, db, stock):
    r = add_service(client, stock)
    assert r.status_code == 201, r.text
    assert r.json()["stock_issued"] == 1
    assert on_hand(db, stock) == Decimal("3.00")
    ledger = client.get(f"/cases/{stock['case'].id}/stock", headers=stock["h"]).json()
    assert [m["movement_type"] for m in ledger] == ["issue"]


def test_changing_quantity_and_cancelling_adjust_stock(client, db, stock):
    sid = add_service(client, stock).json()["id"]
    r = client.patch(f"/cases/services/{sid}", json={"quantity": 3}, headers=stock["h"])
    assert r.status_code == 200, r.text
    assert on_hand(db, stock) == Decimal("1.00")
    client.patch(f"/cases/services/{sid}", json={"status": "cancelled"}, headers=stock["h"])
    assert on_hand(db, stock) == Decimal("4.00")


def test_deleting_the_line_puts_stock_back(client, db, stock):
    sid = add_service(client, stock).json()["id"]
    assert client.delete(f"/cases/services/{sid}", headers=stock["h"]).status_code == 204
    assert on_hand(db, stock) == Decimal("4.00")


def test_not_enough_stock_blocks_the_line(client, db, stock):
    r = add_service(client, stock, quantity=9)
    assert r.status_code == 409
    assert "Not enough" in r.json()["detail"]
    db.rollback()
    assert on_hand(db, stock) == Decimal("4.00")


def test_service_without_an_item_leaves_stock_alone(client, db, stock):
    r = client.post(f"/cases/{stock['case'].id}/services", headers=stock["h"],
                    json={"service_type": "hearse", "service_name": "Hearse"})
    assert r.status_code == 201
    assert on_hand(db, stock) == Decimal("4.00")


def test_running_low_alerts_once_and_creates_a_to_send_order(
    client, db, stock, monkeypatch
):
    monkeypatch.setattr(settings, "smtp_host", "")   # email not set up
    client.patch(f"/inventory/items/{stock['item']['id']}", headers=stock["h"],
                 json={"auto_order": True})
    def alerts():
        db.expire_all()
        return db.query(Notification).filter(Notification.kind == "stock").count()

    add_service(client, stock, quantity=2)            # 4 -> 2: at the level
    first = alerts()
    assert first >= 1
    add_service(client, stock, quantity=1)            # 2 -> 1: still low
    assert alerts() == first                           # told once, not again
    orders = client.get("/inventory/orders", headers=stock["h"]).json()
    assert len(orders) == 1 and orders[0]["status"] == "to_send"
    assert orders[0]["automatic"] is True
    assert "Email sending is not set up" in orders[0]["send_error"]


def test_auto_order_is_emailed_when_email_is_set_up(client, db, stock, monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "me@test")
    monkeypatch.setattr(md, "send_email", lambda to, s, b: sent.append((to, s)))
    client.patch(f"/inventory/items/{stock['item']['id']}", headers=stock["h"],
                 json={"auto_order": True})
    add_service(client, stock, quantity=3)            # 4 -> 1
    orders = client.get("/inventory/orders", headers=stock["h"]).json()
    assert orders[0]["status"] == "sent"
    assert sent and sent[0][0] == "orders@coffins.test"


def test_receiving_the_order_restocks_and_closes_it(client, db, stock, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    client.patch(f"/inventory/items/{stock['item']['id']}", headers=stock["h"],
                 json={"auto_order": True})
    add_service(client, stock, quantity=3)
    order = client.get("/inventory/orders", headers=stock["h"]).json()[0]
    r = client.post(f"/inventory/orders/{order['id']}/receive", headers=stock["h"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"
    assert on_hand(db, stock) == Decimal("6.00")
    # restocked: a later dip alerts and orders again
    add_service(client, stock, quantity=5)
    assert len(client.get("/inventory/orders", headers=stock["h"]).json()) == 2


def test_manual_order_rules(client, db, stock, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    r = client.post(f"/inventory/items/{stock['item']['id']}/order", json={},
                    headers=stock["h"])
    assert r.status_code == 201, r.text
    again = client.post(f"/inventory/items/{stock['item']['id']}/order", json={},
                        headers=stock["h"])
    assert again.status_code == 409                    # one open order per item
    oid = r.json()["id"]
    assert client.post(f"/inventory/orders/{oid}/mark-sent", headers=stock["h"]).json()["status"] == "sent"
    assert client.post(f"/inventory/orders/{oid}/cancel", headers=stock["h"]).json()["status"] == "cancelled"


def test_auto_order_needs_supplier_and_quantity(client, stock):
    r = client.post("/inventory/items", headers=stock["h"], json={
        "sku": "X-1", "name": "Flowers", "category": "flowers",
        "auto_order": True})
    assert r.status_code == 422


def test_a_cancelled_auto_order_is_not_recreated_by_the_scheduler(
    client, db, stock, monkeypatch
):
    from app.services.stock_automation import scan_low_stock

    monkeypatch.setattr(settings, "smtp_host", "")
    client.patch(f"/inventory/items/{stock['item']['id']}", headers=stock["h"],
                 json={"auto_order": True})
    add_service(client, stock, quantity=3)             # low: order created
    (order,) = client.get("/inventory/orders", headers=stock["h"]).json()
    client.post(f"/inventory/orders/{order['id']}/cancel", headers=stock["h"])
    scan_low_stock(db)
    assert len(client.get("/inventory/orders", headers=stock["h"]).json()) == 1
