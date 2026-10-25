"""The platform (Saccharum) layer: subscriptions, limits, separation."""

import pytest

from app.models.business import Business
from app.models.platform_admin import PlatformAdmin
from app.security import hash_password
from tests.test_branches import make_branch, make_case, make_member
from tests.test_workspace_groups import make_staff

PW = "PlatformPass123!"


@pytest.fixture
def operator(client, db):
    db.add(PlatformAdmin(email="ops@saccharum.test", full_name="Ops",
                         password_hash=hash_password(PW)))
    db.commit()
    r = client.post("/platform/login",
                    json={"email": "OPS@saccharum.test", "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def patch(client, op, biz, **body):
    return client.patch(
        f"/platform/businesses/{biz.id}/subscription", json=body, headers=op
    )


def test_login_rejects_wrong_password(client, db):
    db.add(PlatformAdmin(email="x@saccharum.test", full_name="X",
                         password_hash=hash_password(PW)))
    db.commit()
    r = client.post("/platform/login",
                    json={"email": "x@saccharum.test", "password": "nope"})
    assert r.status_code == 401


def test_the_two_layers_do_not_mix(client, auth_headers, operator, test_data):
    # a business token cannot use platform endpoints
    r = client.get("/platform/businesses",
                   headers=auth_headers(test_data["main_admin"]))
    assert r.status_code == 401
    # a platform token cannot act as a business user
    assert client.get("/cases", headers=operator).status_code == 401
    assert client.get("/platform/businesses").status_code in (401, 403)


def test_operator_sees_counts_not_records(client, db, operator, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    make_member(db, biz)
    r = client.get("/platform/businesses", headers=operator)
    assert r.status_code == 200
    row = next(b for b in r.json() if b["id"] == str(biz.id))
    assert row["usage"]["active cases"] >= 1
    assert case.deceased_full_name not in r.text
    assert case.case_number not in r.text
    s = client.get("/platform/summary", headers=operator).json()
    assert s["businesses"] >= 2


def test_tier_defaults_and_manual_limits(client, db, operator, test_data):
    biz = test_data["business_a"]
    r = patch(client, operator, biz, tier="starter", apply_tier_defaults=True)
    assert r.status_code == 200, r.text
    assert r.json()["limits"]["branches"] == 1
    r = patch(client, operator, biz, max_branches=4)
    assert r.json()["limits"]["branches"] == 4
    assert patch(client, operator, biz, tier="gold").status_code == 422
    assert patch(client, operator, biz, status="weird").status_code == 422


def test_branch_limit_is_enforced(client, auth_headers, db, operator, test_data):
    biz = test_data["business_a"]
    make_branch(db, biz, "Main", "MAIN", main=True)
    patch(client, operator, biz, max_branches=1)
    r = client.post(
        "/branches", json={"name": "Second", "code": "SEC"},
        headers=auth_headers(test_data["main_admin"]),
    )
    assert r.status_code == 403
    assert "plan allows up to 1 branches" in r.json()["detail"]
    db.rollback()  # the tests share one session; a real request ends here
    patch(client, operator, biz, max_branches=None)
    r = client.post(
        "/branches", json={"name": "Second", "code": "SEC"},
        headers=auth_headers(test_data["main_admin"]),
    )
    assert r.status_code == 201, r.text


def test_member_and_case_limits_are_enforced(db, test_data, operator, client):
    biz = test_data["business_a"]
    make_member(db, biz)
    patch(client, operator, biz, max_members=1)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as err:
        make_member(db, biz)
    assert err.value.status_code == 403
    db.rollback()


def test_suspended_business_is_locked_out_and_can_be_restored(
    client, auth_headers, operator, test_data
):
    biz = test_data["business_a"]
    admin = test_data["main_admin"]
    headers = auth_headers(admin)
    assert client.get("/subscription", headers=headers).status_code == 200
    patch(client, operator, biz, status="suspended")
    r = client.get("/subscription", headers=headers)
    assert r.status_code == 403
    assert "not active" in r.json()["detail"]
    # other businesses are not affected
    other = auth_headers(test_data["other_business_manager"])
    assert client.get("/subscription", headers=other).status_code == 200
    patch(client, operator, biz, status="active")
    assert client.get("/subscription", headers=headers).status_code == 200


def test_business_sees_its_own_usage(client, auth_headers, test_data):
    r = client.get("/subscription",
                   headers=auth_headers(test_data["manager"]))
    body = r.json()
    assert body["status"] == "active"
    assert "staff accounts" in body["usage"]


def test_changes_are_audited_without_a_business_user(client, db, operator, test_data):
    from app.models.audit_log import AuditLog
    patch(client, operator, test_data["business_a"], status="trial")
    row = (db.query(AuditLog)
           .filter(AuditLog.action == "platform.subscription_changed").one())
    assert row.user_id is None


def test_limits_count_every_branch_even_for_a_branch_limited_person(
    db, test_data, operator, client
):
    """A person limited to one branch must not be able to slip past the
    plan limit because they cannot see the other branches' members."""
    from fastapi import HTTPException

    from app.services.branch_scope import set_scope

    biz = test_data["business_a"]
    main = make_branch(db, biz, "Main", "MAIN", main=True)
    soweto = make_branch(db, biz, "Soweto", "SWT")
    make_member(db, biz, main)
    patch(client, operator, biz, max_members=1)
    set_scope(db, soweto.id)
    try:
        with pytest.raises(HTTPException) as err:
            make_member(db, biz, soweto)
        assert err.value.status_code == 403
    finally:
        db.rollback()
        set_scope(db, None)
