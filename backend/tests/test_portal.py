"""Private family and member links: who can mint them, what they show."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.portal import PortalLink
from app.services import portal as svc
from tests.test_branches import make_case, make_member
from tests.test_workspace_groups import make_staff


def mint(client, auth_headers, user, **body):
    return client.post("/portal-links", json=body, headers=auth_headers(user))


def test_family_link_shows_only_that_funeral(
    client, auth_headers, db, test_data
):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    other = make_case(db, biz)
    r = mint(client, auth_headers, test_data["manager"],
             kind="family", case_id=str(case.id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert "token_hash" not in body
    view = client.get(f"/portal/{body['token']}")   # no sign-in
    assert view.status_code == 200, view.text
    data = view.json()
    assert data["case_number"] == case.case_number
    assert other.case_number not in view.text
    assert view.headers["cache-control"] == "no-store"


def test_member_link_shows_only_that_member(
    client, auth_headers, db, test_data
):
    biz = test_data["business_a"]
    member = make_member(db, biz)
    rival = make_member(db, biz)
    rival.first_name = "Rival"
    db.commit()
    r = mint(client, auth_headers, test_data["manager"],
             kind="member", member_id=str(member.id))
    data = client.get(f"/portal/{r.json()['token']}").json()
    assert data["kind"] == "member"
    assert data["member_name"].startswith("Branch")
    assert "Rival" not in str(data)


def test_the_secret_is_stored_hashed(client, auth_headers, db, test_data):
    case = make_case(db, test_data["business_a"])
    token = mint(client, auth_headers, test_data["manager"],
                 kind="family", case_id=str(case.id)).json()["token"]
    row = db.query(PortalLink).one()
    assert token not in row.token_hash
    assert row.token_hash == svc.hash_token(token)


def test_revoked_expired_and_unknown_links_look_identical(
    client, auth_headers, db, test_data
):
    case = make_case(db, test_data["business_a"])
    m = test_data["manager"]
    made = mint(client, auth_headers, m, kind="family", case_id=str(case.id)).json()
    assert client.delete(
        f"/portal-links/{made['id']}", headers=auth_headers(m)
    ).status_code == 200
    revoked = client.get(f"/portal/{made['token']}")

    second = mint(client, auth_headers, m, kind="family", case_id=str(case.id)).json()
    link = db.get(PortalLink, second["id"])
    link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    expired = client.get(f"/portal/{second['token']}")
    unknown = client.get("/portal/not-a-real-token")
    assert revoked.status_code == expired.status_code == unknown.status_code == 404
    assert revoked.json() == expired.json() == unknown.json()


def test_only_permitted_staff_can_make_links(
    client, auth_headers, db, test_data
):
    case = make_case(db, test_data["business_a"])
    r = mint(client, auth_headers, test_data["staff"],
             kind="family", case_id=str(case.id))
    assert r.status_code == 403


def test_cannot_link_another_business_or_mismatched_target(
    client, auth_headers, db, test_data
):
    foreign = make_case(db, test_data["business_b"])
    m = test_data["manager"]
    assert mint(client, auth_headers, m, kind="family",
                case_id=str(foreign.id)).status_code == 404
    assert mint(client, auth_headers, m, kind="family").status_code == 422
    own = make_case(db, test_data["business_a"])
    assert mint(client, auth_headers, m, kind="member",
                case_id=str(own.id)).status_code == 422


def test_guessing_links_is_throttled(client, monkeypatch):
    svc._failures.clear()
    monkeypatch.setattr(svc, "MAX_FAILURES", 3)
    codes = [client.get(f"/portal/guess{i}").status_code for i in range(5)]
    assert codes[:3] == [404, 404, 404]
    assert codes[3] == 429
    svc._failures.clear()


def test_family_sees_how_to_pay_only_while_something_is_owed(
    client, auth_headers, db, test_data
):
    from decimal import Decimal

    from app.models.business import Business
    from app.models.case_financial import CaseFinancial

    biz = test_data["business_a"]
    case = make_case(db, biz)
    db.get(Business, biz.id).payment_instructions = "FNB 123456 - use the case number"
    fin = CaseFinancial(
        business_id=biz.id, case_id=case.id, subtotal=Decimal("100"), discount=Decimal("0"),
        tax=Decimal("0"), total=Decimal("100"), amount_paid=Decimal("0"), balance=Decimal("100"),
    )
    db.add(fin)
    db.commit()
    token = mint(client, auth_headers, test_data["manager"],
                 kind="family", case_id=str(case.id)).json()["token"]
    data = client.get(f"/portal/{token}").json()
    assert data["payment_instructions"] == "FNB 123456 - use the case number"
    assert data["payment_reference"] == case.case_number

    fin.balance = Decimal("0")
    db.commit()
    assert client.get(f"/portal/{token}").json()["payment_instructions"] is None
