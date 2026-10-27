"""Price list, packages, and quotes/invoices built from a case's services."""

import pytest

from tests.test_branches import make_case


@pytest.fixture
def ctx(client, auth_headers, db, test_data):
    h = auth_headers(test_data["main_admin"])
    case = make_case(db, test_data["business_a"])
    return {"h": h, "case": case, "data": test_data}


def item(client, h, name, price, **extra):
    r = client.post(
        "/service-catalog", headers=h,
        json={"name": name, "service_type": "transport",
              "unit_price": price, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_catalogue_crud_and_duplicate_name(client, ctx):
    h = ctx["h"]
    a = item(client, h, "Hearse", "1500")
    dup = client.post("/service-catalog", headers=h,
                      json={"name": "Hearse", "service_type": "transport"})
    assert dup.status_code == 409
    r = client.patch(f"/service-catalog/{a['id']}", headers=h,
                     json={"unit_price": "1800"})
    assert r.json()["unit_price"] == "1800.00"
    client.patch(f"/service-catalog/{a['id']}", headers=h,
                 json={"is_active": False})
    assert client.get("/service-catalog", headers=h).json() == []
    assert len(client.get("/service-catalog?include_inactive=true", headers=h).json()) == 1


def test_add_from_catalog_copies_price_and_allows_override(client, ctx):
    h, case = ctx["h"], ctx["case"]
    a = item(client, h, "Hearse", "1500", price_varies=True)
    r = client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                    json={"catalog_item_id": a["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["unit_price"] == "1500.00"
    assert r.json()["catalog_item_id"] == a["id"]
    r = client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                    json={"catalog_item_id": a["id"], "unit_price": "1200",
                          "quantity": 2})
    assert r.json()["total_price"] == "2400.00"


def test_package_adds_each_service_once(client, ctx):
    h, case = ctx["h"], ctx["case"]
    a = item(client, h, "Hearse", "1500")
    b = item(client, h, "Tent", "800")
    p = client.post("/service-packages", headers=h, json={
        "name": "Standard", "items": [
            {"catalog_item_id": a["id"]},
            {"catalog_item_id": b["id"], "quantity": 2}]})
    assert p.status_code == 201, p.text
    assert p.json()["total"] == "3100.00"
    r = client.post(f"/cases/{case.id}/services/from-package", headers=h,
                    json={"package_id": p.json()["id"]})
    assert len(r.json()) == 2
    again = client.post(f"/cases/{case.id}/services/from-package", headers=h,
                        json={"package_id": p.json()["id"]})
    assert again.json() == []


def test_standard_services_apply(client, ctx):
    h, case = ctx["h"], ctx["case"]
    item(client, h, "Admin fee", "300", is_standard=True)
    item(client, h, "Hearse", "1500")
    r = client.post(f"/cases/{case.id}/services/apply-standard", headers=h)
    assert [s["service_name"] for s in r.json()] == ["Admin fee"]


def test_quote_and_invoice_build_from_services(client, ctx):
    h, case = ctx["h"], ctx["case"]
    a = item(client, h, "Hearse", "1500")
    b = item(client, h, "Tent", "800")
    for i in (a, b):
        client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                    json={"catalog_item_id": i["id"]})
    r = client.post(f"/cases/{case.id}/financial-documents/from-services",
                    headers=h, json={"document_type": "quote"})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["total"] == "2300.00"
    assert len(doc["lines"]) == 2
    # Nothing left to bill on another quote.
    again = client.post(f"/cases/{case.id}/financial-documents/from-services",
                        headers=h, json={"document_type": "quote"})
    assert again.status_code == 409
    # An invoice is independent of the quote.
    inv = client.post(f"/cases/{case.id}/financial-documents/from-services",
                      headers=h, json={"document_type": "invoice"})
    assert inv.status_code == 201


def test_sync_adds_updates_and_removes(client, ctx):
    h, case = ctx["h"], ctx["case"]
    a = item(client, h, "Hearse", "1500")
    s1 = client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                     json={"catalog_item_id": a["id"]}).json()
    doc = client.post(f"/cases/{case.id}/financial-documents/from-services",
                      headers=h, json={"document_type": "invoice"}).json()
    b = item(client, h, "Tent", "800")
    s2 = client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                     json={"catalog_item_id": b["id"]}).json()
    client.patch(f"/cases/services/{s1['id']}", headers=h,
                 json={"unit_price": "2000"})
    r = client.post(f"/financial-documents/{doc['id']}/sync-services", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == "2800.00"
    client.patch(f"/cases/services/{s2['id']}", headers=h,
                 json={"status": "cancelled"})
    r = client.post(f"/financial-documents/{doc['id']}/sync-services", headers=h)
    assert r.json()["total"] == "2000.00"


def test_cancelled_services_are_not_billed(client, ctx):
    h, case = ctx["h"], ctx["case"]
    a = item(client, h, "Hearse", "1500")
    s = client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                    json={"catalog_item_id": a["id"]}).json()
    client.patch(f"/cases/services/{s['id']}", headers=h,
                 json={"status": "cancelled"})
    r = client.post(f"/cases/{case.id}/financial-documents/from-services",
                    headers=h, json={"document_type": "quote"})
    assert r.status_code == 409


def test_issued_document_cannot_be_synced(client, ctx):
    h, case = ctx["h"], ctx["case"]
    a = item(client, h, "Hearse", "1500")
    client.post(f"/cases/{case.id}/services/from-catalog", headers=h,
                json={"catalog_item_id": a["id"]})
    doc = client.post(f"/cases/{case.id}/financial-documents/from-services",
                      headers=h, json={"document_type": "invoice"}).json()
    r = client.post(f"/financial-documents/{doc['id']}/issue", headers=h)
    assert r.status_code == 200, r.text
    r = client.post(f"/financial-documents/{doc['id']}/sync-services", headers=h)
    assert r.status_code == 409


def test_other_business_cannot_use_my_catalogue(client, auth_headers, ctx):
    h2 = auth_headers(ctx["data"]["other_business_manager"])
    a = item(client, ctx["h"], "Hearse", "1500")
    assert client.get("/service-catalog", headers=h2).json() == []
    r = client.patch(f"/service-catalog/{a['id']}", headers=h2,
                     json={"unit_price": "1"})
    assert r.status_code == 404
