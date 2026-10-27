"""Saved services flow onto cases and then onto quotes and invoices."""

from decimal import Decimal

import pytest

from app.models.inventory import InventoryItem
from tests.test_branches import make_case


@pytest.fixture
def ctx(client, auth_headers, db, test_data):
    h = auth_headers(test_data["main_admin"])
    return {"h": h, "case": make_case(db, test_data["business_a"]), "db": db}


def item(client, ctx, name="Hearse hire", price="1500", **extra):
    r = client.post("/service-catalogue", headers=ctx["h"], json={
        "name": name, "service_type": "transport",
        "default_price": price, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def add(client, ctx, cid, **extra):
    return client.post(
        f"/cases/{ctx['case'].id}/services/from-catalogue",
        headers=ctx["h"], json={"catalogue_item_id": cid, **extra})


def test_add_saved_service_uses_default_and_allows_price_change(client, ctx):
    c = item(client, ctx)
    r = add(client, ctx, c["id"])
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["unit_price"]) == Decimal("1500")
    r = add(client, ctx, c["id"], unit_price="1800", quantity=2)
    assert Decimal(r.json()["total_price"]) == Decimal("3600")


def test_duplicate_name_is_refused(client, ctx):
    item(client, ctx)
    r = client.post("/service-catalogue", headers=ctx["h"],
                    json={"name": "Hearse hire", "default_price": "1"})
    assert r.status_code == 409


def test_package_adds_every_item(client, ctx):
    a = item(client, ctx, "Hearse hire", "1500")
    b = item(client, ctx, "Tent", "800")
    p = client.post("/service-packages", headers=ctx["h"], json={
        "name": "Standard", "items": [
            {"catalogue_item_id": a["id"], "quantity": 1},
            {"catalogue_item_id": b["id"], "quantity": 2}]})
    assert p.status_code == 201, p.text
    assert Decimal(p.json()["total"]) == Decimal("3100")
    r = client.post(f"/cases/{ctx['case'].id}/services/from-package",
                    headers=ctx["h"], json={"package_id": p.json()["id"],
                                            "prices": {b["id"]: "700"}})
    assert r.status_code == 201, r.text
    assert len(r.json()["services"]) == 2
    totals = sorted(Decimal(s["total_price"]) for s in r.json()["services"])
    assert totals == [Decimal("1400"), Decimal("1500")]


def test_stock_linked_catalogue_item_issues_stock(client, ctx, db):
    st = client.post("/inventory/items", headers=ctx["h"], json={
        "sku": "TNT-1", "name": "Tent", "category": "other",
        "opening_quantity": "5"}).json()
    c = item(client, ctx, "Tent", "800", inventory_item_id=st["id"])
    assert add(client, ctx, c["id"]).status_code == 201
    db.expire_all()
    assert db.get(InventoryItem, st["id"]).quantity_on_hand == Decimal("4.00")


def test_document_is_built_from_services_without_retyping(client, ctx):
    a = item(client, ctx, "Hearse hire", "1500")
    add(client, ctx, a["id"])
    add(client, ctx, a["id"], quantity=2)
    cid = ctx["case"].id
    r = client.post(f"/cases/{cid}/financial-documents/from-services",
                    headers=ctx["h"], json={"document_type": "invoice"})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert len(doc["lines"]) == 2
    assert Decimal(doc["total"]) == Decimal("4500")
    # Nothing left to bill, so a second invoice is refused.
    r = client.post(f"/cases/{cid}/financial-documents/from-services",
                    headers=ctx["h"], json={"document_type": "invoice"})
    assert r.status_code == 409
    # A quote is a separate document type and can still be built.
    r = client.post(f"/cases/{cid}/financial-documents/from-services",
                    headers=ctx["h"], json={"document_type": "quote"})
    assert r.status_code == 201, r.text


def test_draft_follows_service_changes(client, ctx):
    a = item(client, ctx, "Hearse hire", "1500")
    cid = ctx["case"].id
    first = add(client, ctx, a["id"]).json()
    doc = client.post(f"/cases/{cid}/financial-documents/from-services",
                      headers=ctx["h"], json={"document_type": "invoice"}).json()
    # A service added later lands on the draft by itself.
    second = add(client, ctx, a["id"], unit_price="500").json()
    d = client.get(f"/financial-documents/{doc['id']}", headers=ctx["h"]).json()
    assert Decimal(d["total"]) == Decimal("2000")
    # A price change follows.
    client.patch(f"/cases/services/{second['id']}", headers=ctx["h"],
                 json={"unit_price": "700"})
    d = client.get(f"/financial-documents/{doc['id']}", headers=ctx["h"]).json()
    assert Decimal(d["total"]) == Decimal("2200")
    # Cancelling and deleting remove the lines.
    client.patch(f"/cases/services/{first['id']}", headers=ctx["h"],
                 json={"status": "cancelled"})
    client.delete(f"/cases/services/{second['id']}", headers=ctx["h"])
    d = client.get(f"/financial-documents/{doc['id']}", headers=ctx["h"]).json()
    assert d["lines"] == [] and Decimal(d["total"]) == 0


def test_issued_invoice_is_not_touched(client, ctx):
    a = item(client, ctx, "Hearse hire", "1500")
    cid = ctx["case"].id
    sid = add(client, ctx, a["id"]).json()["id"]
    doc = client.post(f"/cases/{cid}/financial-documents/from-services",
                      headers=ctx["h"], json={"document_type": "invoice"}).json()
    r = client.post(f"/financial-documents/{doc['id']}/issue", headers=ctx["h"], json={})
    assert r.status_code == 200, r.text
    client.patch(f"/cases/services/{sid}", headers=ctx["h"], json={"unit_price": "9999"})
    d = client.get(f"/financial-documents/{doc['id']}", headers=ctx["h"]).json()
    assert Decimal(d["total"]) == Decimal("1500")
