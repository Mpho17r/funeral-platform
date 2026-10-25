"""A mortuary hosted by one branch can be shared with others."""

import uuid
from datetime import datetime, timezone

import pytest

from tests.test_branches import make_branch, make_case
from tests.test_mortuary import make_location, take_in
from tests.test_workspace_groups import make_staff


@pytest.fixture
def world(db, test_data):
    biz = test_data["business_a"]
    main = make_branch(db, biz, "Main", "MAIN", main=True)
    soweto = make_branch(db, biz, "Soweto", "SWT")
    location = make_location(db, biz, "Main Fridge", capacity=4)
    location.branch_id = main.id
    db.commit()
    return {
        "biz": biz, "main": main, "soweto": soweto, "location": location,
        "worker": make_staff(
            db, test_data["staff"], biz, branch=soweto, role="mortuary"
        ),
        "main_worker": make_staff(
            db, test_data["staff"], biz, branch=main, role="mortuary"
        ),
        "soweto_case": make_case(db, biz, soweto),
    }


def names(response):
    assert response.status_code == 200, response.text
    return {row["name"] for row in response.json()}


def share(client, auth_headers, user, w):
    return client.post(
        f"/mortuary/locations/{w['location'].id}/branches/{w['soweto'].id}",
        headers=auth_headers(user),
    )


def test_other_branch_cannot_see_a_location_until_shared(
    client, auth_headers, test_data, world
):
    h = auth_headers(world["worker"])
    assert "Main Fridge" not in names(client.get("/mortuary/locations", headers=h))
    r = share(client, auth_headers, test_data["main_admin"], world)
    assert r.status_code == 200, r.text
    assert r.json()["shared_with"] == [str(world["soweto"].id)]
    assert "Main Fridge" in names(client.get("/mortuary/locations", headers=h))
    assert "Main Fridge" in names(
        client.get("/mortuary/locations", headers=auth_headers(world["main_worker"]))
    )


def test_sharing_needs_branch_management(client, auth_headers, world):
    r = share(client, auth_headers, world["worker"], world)
    assert r.status_code == 403


def test_cannot_share_with_the_host_branch_or_a_stranger(
    client, auth_headers, test_data, world
):
    h = auth_headers(test_data["main_admin"])
    r = client.post(
        f"/mortuary/locations/{world['location'].id}/branches/{world['main'].id}",
        headers=h,
    )
    assert r.status_code == 409
    r = client.post(
        f"/mortuary/locations/{world['location'].id}/branches/{uuid.uuid4()}",
        headers=h,
    )
    assert r.status_code == 404


def test_remains_in_a_shared_location_are_visible_to_the_host(
    client, db, auth_headers, test_data, world
):
    admin = auth_headers(test_data["main_admin"])
    share(client, auth_headers, test_data["main_admin"], world)
    r = take_in(
        client, auth_headers, test_data["main_admin"], world["soweto_case"],
        location_id=str(world["location"].id),
    )
    assert r.status_code == 201, r.text
    # The hosting branch's staff see remains kept in their facility.
    board = client.get(
        "/mortuary/board", headers=auth_headers(world["main_worker"])
    )
    assert board.status_code == 200, board.text
    assert board.json()["in_custody"] == 1
    # Staff of an unrelated branch do not.
    third = make_branch(db, world["biz"], "Third", "THR")
    outsider = make_staff(
        db, test_data["staff"], world["biz"], branch=third, role="mortuary"
    )
    board = client.get("/mortuary/board", headers=auth_headers(outsider))
    assert board.json()["in_custody"] == 0
    r = client.get("/mortuary/locations", headers=auth_headers(world["main_worker"]))
    assert [x for x in r.json() if x["name"] == "Main Fridge"][0]["occupied"] == 1


def test_cannot_unshare_while_that_branch_still_has_remains_there(
    client, auth_headers, test_data, world
):
    share(client, auth_headers, test_data["main_admin"], world)
    take_in(
        client, auth_headers, test_data["main_admin"], world["soweto_case"],
        location_id=str(world["location"].id),
    )
    url = f"/mortuary/locations/{world['location'].id}/branches/{world['soweto'].id}"
    r = client.delete(url, headers=auth_headers(test_data["main_admin"]))
    assert r.status_code == 409
