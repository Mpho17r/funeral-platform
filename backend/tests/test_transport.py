"""Partner drivers: cars matched by colour and type, alerts, replies, pay."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.expense import Expense
from tests.test_branches import make_case


@pytest.fixture
def t(client, auth_headers, db, test_data):
    h = auth_headers(test_data["main_admin"])
    case = make_case(db, test_data["business_a"])
    return {"h": h, "case": case, "db": db, "user": test_data["main_admin"]}


def driver(client, t, name, colour, vtype="sedan", model="Corolla", **extra):
    r = client.post("/transport/drivers", headers=t["h"],
                    json={"full_name": name, "phone": "0821234567", **extra})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    v = client.post(f"/transport/drivers/{did}/vehicles", headers=t["h"],
                    json={"make": "Toyota", "model": model,
                          "vehicle_type": vtype, "colour": colour})
    assert v.status_code == 201, v.text
    return did, v.json()["id"]


def when(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def make_job(client, t, hours=48, **extra):
    body = {"report_time": when(hours), "venue": "St Mary's Church",
            "destination": "Westpark Cemetery", "dress_code": "Black suit",
            **extra}
    r = client.post(f"/cases/{t['case'].id}/transport-jobs",
                    headers=t["h"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_candidates_match_colour_and_type(client, t):
    black, _ = driver(client, t, "Sipho Black", "Black", "sedan")
    driver(client, t, "Anna White", "White", "sedan")
    driver(client, t, "Bheki Minibus", "Black", "minibus", model="Quantum")
    job = make_job(client, t, required_colour="Black", required_type="sedan")[0]
    r = client.get(f"/transport/jobs/{job['id']}/candidates", headers=t["h"])
    assert [c["driver_id"] for c in r.json()] == [black]


def test_assign_alerts_driver_and_blocks_a_mismatch(client, t):
    did, vid = driver(client, t, "Anna White", "White")
    job = make_job(client, t, required_colour="black")[0]
    r = client.post(f"/transport/jobs/{job['id']}/assign", headers=t["h"],
                    json={"driver_id": did, "vehicle_id": vid})
    assert r.status_code == 409
    r = client.post(f"/transport/jobs/{job['id']}/assign", headers=t["h"],
                    json={"driver_id": did, "vehicle_id": vid, "force": True})
    assert r.status_code == 200, r.text
    text = r.json()["alert"]["text"]
    for needle in ("St Mary's Church", "Black suit", "Westpark Cemetery", "Report at"):
        assert needle in text
    assert r.json()["alert"]["whatsapp"].startswith("https://wa.me/27821234567")
    assert r.json()["status"] == "assigned"


def test_driver_cannot_take_two_jobs_close_together(client, t):
    did, vid = driver(client, t, "Sipho Black", "black")
    a = make_job(client, t, 48)[0]
    b = make_job(client, t, 49)[0]
    c = make_job(client, t, 60)[0]
    body = {"driver_id": did, "vehicle_id": vid}
    assert client.post(f"/transport/jobs/{a['id']}/assign", headers=t["h"], json=body).status_code == 200
    assert client.post(f"/transport/jobs/{b['id']}/assign", headers=t["h"], json=body).status_code == 409
    assert client.post(f"/transport/jobs/{c['id']}/assign", headers=t["h"], json=body).status_code == 200


def test_auto_assign_spreads_cars_by_colour(client, t):
    driver(client, t, "Sipho Black", "black")
    driver(client, t, "Thabo Black", "black")
    driver(client, t, "Anna White", "white")
    make_job(client, t, required_colour="black", count=2)
    make_job(client, t, required_colour="white")
    make_job(client, t, required_colour="red")
    r = client.post("/transport/auto-assign", headers=t["h"], json={"case_id": str(t["case"].id)})
    assert r.status_code == 200, r.text
    assert r.json()["assigned"] == 3 and r.json()["still_open"] == 1
    names = sorted(j["driver_name"] for j in r.json()["jobs"] if j["driver_name"])
    assert names == ["Anna White", "Sipho Black", "Thabo Black"]


def test_driver_link_shows_jobs_and_reply_works(client, t):
    did, vid = driver(client, t, "Sipho Black", "black")
    other, ovid = driver(client, t, "Thabo Black", "black")
    job = make_job(client, t, required_colour="black")[0]
    client.post(f"/transport/jobs/{job['id']}/assign", headers=t["h"],
                json={"driver_id": did, "vehicle_id": vid})
    token = client.post(f"/transport/drivers/{did}/link", headers=t["h"]).json()["token"]
    page = client.get(f"/driver-portal/{token}").json()
    assert page["driver"] == "Sipho Black" and len(page["jobs"]) == 1
    assert page["jobs"][0]["dress_code"] == "Black suit"
    r = client.post(f"/driver-portal/{token}/jobs/{job['id']}/respond", json={"accept": True})
    assert r.json()["status"] == "accepted"
    # Declining sends it back to the pool and never offers it to him again.
    r = client.post(f"/driver-portal/{token}/jobs/{job['id']}/respond", json={"accept": False})
    assert r.json()["status"] == "open"
    cands = client.get(f"/transport/jobs/{job['id']}/candidates", headers=t["h"]).json()
    assert [c["driver_id"] for c in cands] == [other]
    # A new link cancels the old one.
    client.post(f"/transport/drivers/{did}/link", headers=t["h"])
    assert client.get(f"/driver-portal/{token}").status_code == 404


def test_pay_records_an_expense_once(client, t, db):
    did, vid = driver(client, t, "Sipho Black", "black")
    job = make_job(client, t, pay_amount="350")[0]
    client.post(f"/transport/jobs/{job['id']}/assign", headers=t["h"],
                json={"driver_id": did, "vehicle_id": vid})
    assert client.post(f"/transport/jobs/{job['id']}/pay", headers=t["h"]).status_code == 409
    assert client.post(f"/transport/jobs/{job['id']}/complete", headers=t["h"]).status_code == 200
    r = client.post(f"/transport/jobs/{job['id']}/pay", headers=t["h"])
    assert r.status_code == 200 and r.json()["paid"] is True
    assert client.post(f"/transport/jobs/{job['id']}/pay", headers=t["h"]).status_code == 409
    exp = db.query(Expense).filter(Expense.case_id == t["case"].id).all()
    assert len(exp) == 1 and exp[0].amount == Decimal("350.00")
    assert exp[0].category == "transport_and_fuel"


def test_other_business_cannot_see_drivers(client, auth_headers, test_data, t):
    did, _ = driver(client, t, "Sipho Black", "black")
    other = auth_headers(test_data["other_business_manager"])
    assert client.get("/transport/drivers", headers=other).json() == []
    assert client.patch(f"/transport/drivers/{did}", headers=other,
                        json={"notes": "x"}).status_code == 404
