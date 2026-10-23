"""The organization-wide and per-branch groups in the staff workspace."""

import uuid

from app.models.branch import Branch
from app.models.chat import ChatMessage
from app.models.user import User


def make_branch(db, business, name, code):
    branch = Branch(
        business_id=business.id, name=name, code=code,
        is_main=False, is_active=True,
    )
    db.add(branch)
    db.commit()
    return branch


def make_staff(db, like, business, branch=None, role="staff", name="Extra"):
    user = User(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        full_name=name,
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        password_hash=like.password_hash,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def groups(client, auth_headers, user):
    r = client.get("/chat/conversations", headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return {c["title"]: c for c in r.json() if c["automatic"]}


def member_ids(group):
    return set(group["participant_ids"])


def test_everyone_is_in_the_organization_group(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    staff = test_data["staff"]
    extra = make_staff(db, staff, biz)
    gone = make_staff(db, staff, biz)
    gone.is_active = False
    db.commit()

    org = groups(client, auth_headers, staff)["Whole organization"]
    ids = member_ids(org)

    for u in (test_data["main_admin"], test_data["manager"], staff, extra):
        assert str(u.id) in ids
    assert str(gone.id) not in ids
    assert org["scope"] == "organization"
    # Nobody from another business.
    assert str(test_data["other_business_manager"].id) not in ids


def test_each_branch_gets_its_own_team_group(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    staff = test_data["staff"]
    north = make_branch(db, biz, "Northside", "NTH")
    south = make_branch(db, biz, "Southside", "STH")
    n1 = make_staff(db, staff, biz, north, name="North One")
    s1 = make_staff(db, staff, biz, south, name="South One")
    admin = test_data["main_admin"]

    mine = groups(client, auth_headers, n1)
    assert "Northside team" in mine
    # Only the groups this person belongs to are listed.
    assert "Southside team" not in mine

    all_groups = groups(client, auth_headers, admin)
    north_ids = member_ids(all_groups["Northside team"])
    south_ids = member_ids(all_groups["Southside team"])

    assert str(n1.id) in north_ids and str(n1.id) not in south_ids
    assert str(s1.id) in south_ids and str(s1.id) not in north_ids
    # The main administrator oversees every branch.
    assert str(admin.id) in north_ids and str(admin.id) in south_ids
    assert all_groups["Northside team"]["scope"] == "branch"


def test_manager_without_a_branch_oversees_all_but_a_tied_one_does_not(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    staff = test_data["staff"]
    north = make_branch(db, biz, "Northside", "NTH")
    south = make_branch(db, biz, "Southside", "STH")
    roaming = test_data["manager"]
    tied = make_staff(db, staff, biz, south, role="manager", name="Tied")

    seen_by_roaming = groups(client, auth_headers, roaming)
    assert {"Northside team", "Southside team"} <= set(seen_by_roaming)

    seen_by_tied = groups(client, auth_headers, tied)
    assert "Southside team" in seen_by_tied
    assert "Northside team" not in seen_by_tied


def test_moving_or_deactivating_someone_updates_the_groups(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    staff = test_data["staff"]
    north = make_branch(db, biz, "Northside", "NTH")
    south = make_branch(db, biz, "Southside", "STH")
    mover = make_staff(db, staff, biz, north, name="Mover")
    admin = test_data["main_admin"]

    before = groups(client, auth_headers, admin)
    assert str(mover.id) in member_ids(before["Northside team"])

    mover.branch_id = south.id
    db.commit()
    after = groups(client, auth_headers, admin)
    assert str(mover.id) not in member_ids(after["Northside team"])
    assert str(mover.id) in member_ids(after["Southside team"])

    mover.is_active = False
    db.commit()
    final = groups(client, auth_headers, admin)
    assert str(mover.id) not in member_ids(final["Southside team"])
    assert str(mover.id) not in member_ids(final["Whole organization"])


def test_syncing_again_changes_nothing_and_renames_follow(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    admin = test_data["main_admin"]
    north = make_branch(db, biz, "Northside", "NTH")

    first = groups(client, auth_headers, admin)
    second = groups(client, auth_headers, admin)
    assert {c["id"] for c in first.values()} == {
        c["id"] for c in second.values()
    }
    assert len(second["Northside team"]["participant_ids"]) == len(
        set(second["Northside team"]["participant_ids"])
    )

    north.name = "Harbour"
    db.commit()
    renamed = groups(client, auth_headers, admin)
    assert "Harbour team" in renamed and "Northside team" not in renamed
    assert renamed["Harbour team"]["id"] == first["Northside team"]["id"]


def test_automatic_groups_cannot_be_edited_by_hand(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    org = groups(client, auth_headers, staff)["Whole organization"]

    leave = client.delete(
        f"/chat/conversations/{org['id']}/participants/{staff.id}",
        headers=auth_headers(staff),
    )
    assert leave.status_code == 409

    add = client.post(
        f"/chat/conversations/{org['id']}/participants",
        json={"user_ids": [str(test_data["manager"].id)]},
        headers=auth_headers(test_data["main_admin"]),
    )
    assert add.status_code == 409


def test_everyone_can_talk_and_late_joiners_start_caught_up(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    staff = test_data["staff"]
    admin = test_data["main_admin"]

    org = groups(client, auth_headers, admin)["Whole organization"]
    sent = client.post(
        f"/chat/conversations/{org['id']}/messages",
        json={"body": "Welcome everyone"},
        headers=auth_headers(admin),
    )
    assert sent.status_code in (200, 201), sent.text

    newcomer = make_staff(db, staff, biz, name="Newcomer")
    mine = groups(client, auth_headers, newcomer)["Whole organization"]
    assert mine["unread"] == 0

    # And they can answer straight away.
    reply = client.post(
        f"/chat/conversations/{org['id']}/messages",
        json={"body": "Glad to be here"},
        headers=auth_headers(newcomer),
    )
    assert reply.status_code in (200, 201), reply.text
    seen = client.get(
        "/chat/conversations", headers=auth_headers(admin)
    ).json()
    row = next(c for c in seen if c["id"] == org["id"])
    assert row["last_message"]["body"] == "Glad to be here"
    assert db.query(ChatMessage).filter(
        ChatMessage.conversation_id == uuid.UUID(org["id"])
    ).count() >= 3  # system note + two messages


def test_each_business_has_its_own_groups(
    client, db, test_data, auth_headers
):
    a = groups(client, auth_headers, test_data["main_admin"])
    b = groups(client, auth_headers, test_data["other_business_manager"])
    assert a["Whole organization"]["id"] != b["Whole organization"]["id"]
    assert not (
        member_ids(a["Whole organization"])
        & member_ids(b["Whole organization"])
    )


def test_nobody_starts_with_an_unread_message(
    client, db, test_data, auth_headers
):
    for user in (test_data["main_admin"], test_data["staff"]):
        client.get("/chat/conversations", headers=auth_headers(user))
        assert client.get(
            "/chat/unread-count", headers=auth_headers(user)
        ).json() == {"unread": 0, "mentions": 0}


def test_the_automatic_intro_message_is_from_funeralos(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    org = groups(client, auth_headers, staff)["Whole organization"]

    assert org["last_message"]["sender_name"] == "FuneralOS"

    thread = client.get(
        f"/chat/conversations/{org['id']}/messages",
        headers=auth_headers(staff),
    ).json()
    assert thread["messages"][0]["sender_name"] == "FuneralOS"
