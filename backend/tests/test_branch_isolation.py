"""
A person limited to one branch only ever sees that branch's records.

Managers and the main administrator (branches.all_access) see them all.
Records without a branch belong to the whole business.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models.case_payment import CasePayment
from app.services.branch_scope import ALL_BRANCHES_PERMISSION
from tests.test_branches import (
    make_branch, make_case, make_member, make_resource,
)
from tests.test_workspace_groups import make_staff


@pytest.fixture
def world(db, test_data):
    biz = test_data["business_a"]
    main = make_branch(db, biz, "Main", "MAIN", main=True)
    soweto = make_branch(db, biz, "Soweto", "SWT")
    worker = make_staff(db, test_data["staff"], biz, branch=soweto, name="Sow")
    return {
        "biz": biz, "main": main, "soweto": soweto, "worker": worker,
        "own_case": make_case(db, biz, soweto),
        "other_case": make_case(db, biz, main),
        "shared_case": make_case(db, biz, None),
        "own_member": make_member(db, biz, soweto),
        "other_member": make_member(db, biz, main),
    }


def ids(response):
    assert response.status_code == 200, response.text
    body = response.json()
    rows = body if isinstance(body, list) else body.get("items", body)
    return {str(r["id"]) for r in rows}


def test_limited_user_lists_only_own_branch_cases(client, auth_headers, world):
    got = ids(client.get("/cases", headers=auth_headers(world["worker"])))
    assert str(world["own_case"].id) in got
    assert str(world["shared_case"].id) in got
    assert str(world["other_case"].id) not in got


def test_limited_user_cannot_open_other_branch_case_by_link(
    client, auth_headers, world
):
    h = auth_headers(world["worker"])
    assert client.get(f"/cases/{world['own_case'].id}", headers=h).status_code == 200
    assert client.get(f"/cases/{world['other_case'].id}", headers=h).status_code == 404


def test_limited_user_lists_only_own_branch_members(client, auth_headers, world):
    got = ids(client.get("/members", headers=auth_headers(world["worker"])))
    assert str(world["own_member"].id) in got
    assert str(world["other_member"].id) not in got


def test_records_that_belong_to_a_case_follow_the_case(db, world):
    from app.services.branch_scope import set_scope

    def pay(case):
        row = CasePayment(
            business_id=world["biz"].id,
            case_id=case.id,
            amount=Decimal("100.00"),
            payment_date=date(2026, 10, 2),
            payment_method="cash",
        )
        db.add(row)
        db.commit()
        return row.id

    own, other = pay(world["own_case"]), pay(world["other_case"])
    set_scope(db, world["soweto"].id)
    try:
        seen = {r.id for r in db.query(CasePayment).all()}
    finally:
        set_scope(db, None)
    assert own in seen
    assert other not in seen
    assert other in {r.id for r in db.query(CasePayment).all()}


def test_search_does_not_leak_other_branches(client, auth_headers, db, world):
    world["other_case"].deceased_full_name = "Zzyzx Hidden"
    world["own_case"].deceased_full_name = "Zzyzx Visible"
    db.commit()
    r = client.get("/search?q=Zzyzx", headers=auth_headers(world["worker"]))
    assert r.status_code == 200
    text = r.text
    assert "Zzyzx Visible" in text
    assert "Zzyzx Hidden" not in text


def test_manager_and_main_admin_see_every_branch(
    client, auth_headers, db, test_data, world
):
    for user in (test_data["manager"], test_data["main_admin"]):
        got = ids(client.get("/cases", headers=auth_headers(user)))
        assert {
            str(world["own_case"].id),
            str(world["other_case"].id),
            str(world["shared_case"].id),
        } <= got


def test_user_without_a_branch_is_not_limited(
    client, auth_headers, db, test_data, world
):
    got = ids(client.get("/cases", headers=auth_headers(test_data["staff"])))
    assert str(world["other_case"].id) in got


def test_granting_all_access_lifts_the_limit(
    client, auth_headers, db, world
):
    from tests.test_branches import set_permission

    set_permission(
        db, world["worker"].id, ALL_BRANCHES_PERMISSION, "allow"
    )
    got = ids(client.get("/cases", headers=auth_headers(world["worker"])))
    assert str(world["other_case"].id) in got


def test_limited_user_cannot_place_a_record_in_another_branch(
    client, auth_headers, world
):
    r = client.post(
        "/cases",
        headers=auth_headers(world["worker"]),
        json={
            "deceased_full_name": "Elsewhere",
            "date_of_death": "2026-10-01",
            "branch_id": str(world["main"].id),
        },
    )
    assert r.status_code in (403, 422), r.text


def test_scope_does_not_linger_between_requests(
    client, auth_headers, db, test_data, world
):
    client.get("/cases", headers=auth_headers(world["worker"]))
    assert db.info.get("branch_scope") is None
