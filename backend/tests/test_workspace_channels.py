"""Automatic organisation and branch channels."""

import uuid

from app.models.branch import Branch
from app.models.chat import ChatParticipant
from app.models.user import User
from app.services import workspace_channels
from tests.test_chat import call
from tests.test_reports import deny


def channels(client, auth_headers, user):
    r = call(client, auth_headers, user, "get", "/conversations")
    assert r.status_code == 200
    return {c["title"]: c for c in r.json() if c["system"]}


def new_branch(db, business, name):
    branch = Branch(
        business_id=business.id,
        name=name,
        code=f"B{uuid.uuid4().hex[:5].upper()}",
        is_active=True,
        is_main=False,
    )
    db.add(branch)
    db.commit()
    return branch


def member_ids(conv):
    return set(conv["participant_ids"])


def test_everyone_is_in_the_organisation_channel(
    client, db, test_data, auth_headers
):
    mine = channels(client, auth_headers, test_data["staff"])
    org = mine["Whole organisation"]
    assert org["scope"] == "organisation"

    active = {
        str(u.id)
        for u in db.query(User).filter(
            User.business_id == test_data["business_a"].id,
            User.is_active.is_(True),
        )
    }
    assert member_ids(org) == active

    # Another business never shares it.
    theirs = channels(client, auth_headers, test_data["other_business_manager"])
    assert theirs["Whole organisation"]["id"] != org["id"]


def test_everyone_can_talk_in_it(client, test_data, auth_headers):
    org = channels(client, auth_headers, test_data["staff"])[
        "Whole organisation"
    ]
    sent = call(
        client, auth_headers, test_data["staff"], "post",
        f"/conversations/{org['id']}/messages", json={"body": "Hello all"},
    )
    assert sent.status_code == 201
    seen = call(
        client, auth_headers, test_data["manager"], "get",
        f"/conversations/{org['id']}/messages",
    ).json()["messages"]
    assert [m["body"] for m in seen if m["kind"] == "text"] == ["Hello all"]


def test_branch_channels_group_each_branch(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    north = new_branch(db, biz, "North Branch")
    south = new_branch(db, biz, "South Branch")

    staff = test_data["staff"]
    staff.branch_id = north.id
    db.commit()

    mine = channels(client, auth_headers, staff)
    assert "North Branch" in mine and "South Branch" not in mine
    assert mine["North Branch"]["scope"] == "branch"
    assert str(staff.id) in member_ids(mine["North Branch"])

    # The manager and main admin oversee every branch.
    for boss in (test_data["manager"], test_data["main_admin"]):
        seen = channels(client, auth_headers, boss)
        assert {"North Branch", "South Branch"} <= set(seen)


def test_moving_branch_moves_access_at_once(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    north = new_branch(db, biz, "North")
    south = new_branch(db, biz, "South")
    staff = test_data["staff"]
    staff.branch_id = north.id
    db.commit()
    north_chat = channels(client, auth_headers, staff)["North"]

    staff.branch_id = south.id
    db.commit()

    after = channels(client, auth_headers, staff)
    assert "North" not in after and "South" in after
    # Old channel is closed to them straight away.
    r = call(
        client, auth_headers, staff, "get",
        f"/conversations/{north_chat['id']}/messages",
    )
    assert r.status_code == 404


def test_deactivated_person_leaves_everything(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    org = channels(client, auth_headers, test_data["manager"])[
        "Whole organisation"
    ]
    assert str(staff.id) in member_ids(org)

    staff.is_active = False
    db.commit()

    after = channels(client, auth_headers, test_data["manager"])[
        "Whole organisation"
    ]
    assert str(staff.id) not in member_ids(after)


def test_single_branch_has_no_duplicate_branch_channel(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    db.query(Branch).filter(
        Branch.business_id == biz.id, Branch.is_active.is_(True)
    )
    only = new_branch(db, biz, "Only One")
    # Ensure this is the only active branch for the business.
    for b in db.query(Branch).filter(
        Branch.business_id == biz.id, Branch.id != only.id
    ):
        b.is_active = False
    db.commit()

    assert set(channels(client, auth_headers, test_data["manager"])) == {
        "Whole organisation"
    }


def test_membership_cannot_be_edited_by_hand(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    org = channels(client, auth_headers, manager)["Whole organisation"]

    add = call(
        client, auth_headers, manager, "post",
        f"/conversations/{org['id']}/participants",
        json={"user_ids": [str(test_data["staff"].id)]},
    )
    assert add.status_code == 409

    leave = call(
        client, auth_headers, manager, "delete",
        f"/conversations/{org['id']}/participants/{manager.id}",
    )
    assert leave.status_code == 409


def test_sync_is_idempotent_and_renames_follow_the_branch(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    a = new_branch(db, biz, "Alpha")
    new_branch(db, biz, "Beta")
    channels(client, auth_headers, test_data["manager"])

    assert workspace_channels.sync(db, biz.id) is False

    a.name = "Alpha Renamed"
    db.commit()
    seen = channels(client, auth_headers, test_data["manager"])
    assert "Alpha Renamed" in seen and "Alpha" not in seen
    assert (
        db.query(ChatParticipant).count() > 0
    )  # nothing duplicated or lost


def test_people_without_chat_permission_get_no_channels(
    client, db, test_data, auth_headers
):
    deny(db, test_data["staff"], "chat.use")
    r = call(client, auth_headers, test_data["staff"], "get", "/conversations")
    assert r.status_code == 403
