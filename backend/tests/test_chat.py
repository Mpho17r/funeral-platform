"""Staff chat: direct messages, channels, unread counts, isolation."""

from datetime import datetime, timedelta, timezone

from app.models.chat import ChatMessage, ChatParticipant
from tests.test_reports import deny


def call(client, auth_headers, user, method, path, **kw):
    return getattr(client, method)(
        f"/chat{path}", headers=auth_headers(user), **kw
    )


def open_dm(client, auth_headers, me, other):
    r = call(client, auth_headers, me, "post", "/conversations",
             json={"kind": "direct", "user_id": str(other.id)})
    assert r.status_code == 201, r.text
    return r.json()


def say(client, auth_headers, user, conv_id, body, **extra):
    return call(client, auth_headers, user, "post",
                f"/conversations/{conv_id}/messages",
                json={"body": body, **extra})


def test_direct_message_is_one_conversation_per_pair(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    first = open_dm(client, auth_headers, a, b)
    again = open_dm(client, auth_headers, b, a)
    assert first["id"] == again["id"]
    assert first["kind"] == "direct"
    assert first["title"] == b.full_name
    assert again["title"] == a.full_name


def test_cannot_message_yourself_or_another_business(
    client, test_data, auth_headers
):
    me = test_data["manager"]
    r = call(client, auth_headers, me, "post", "/conversations",
             json={"kind": "direct", "user_id": str(me.id)})
    assert r.status_code == 422
    r = call(client, auth_headers, me, "post", "/conversations",
             json={"kind": "direct",
                   "user_id": str(test_data["other_business_manager"].id)})
    assert r.status_code == 404


def test_send_read_and_unread_counts(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    assert say(client, auth_headers, a, conv["id"], "  Hello  ").status_code == 201
    assert say(client, auth_headers, a, conv["id"], "Are you in?").status_code == 201

    # Sender sees nothing unread; the other person sees two.
    mine = call(client, auth_headers, a, "get", "/conversations").json()
    assert mine[0]["unread"] == 0
    theirs = call(client, auth_headers, b, "get", "/conversations").json()
    assert theirs[0]["unread"] == 2
    assert theirs[0]["last_message"]["body"] == "Are you in?"
    assert call(client, auth_headers, b, "get",
                "/unread-count").json() == {"unread": 2, "mentions": 0}

    msgs = call(client, auth_headers, b, "get",
                f"/conversations/{conv['id']}/messages").json()["messages"]
    assert [m["body"] for m in msgs] == ["Hello", "Are you in?"]

    assert call(client, auth_headers, b, "post",
                f"/conversations/{conv['id']}/read").status_code == 204
    assert call(client, auth_headers, b, "get",
                "/unread-count").json() == {"unread": 0, "mentions": 0}


def test_empty_and_overlong_messages_are_refused(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    assert say(client, auth_headers, a, conv["id"], "   ").status_code == 422
    assert say(client, auth_headers, a, conv["id"], "x" * 4001).status_code == 422
    assert say(client, auth_headers, a, conv["id"], "x" * 4000).status_code == 201


def test_polling_with_after_returns_only_newer(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    first = say(client, auth_headers, a, conv["id"], "one").json()
    say(client, auth_headers, a, conv["id"], "two")

    r = call(client, auth_headers, b, "get",
             f"/conversations/{conv['id']}/messages",
             params={"after": first["created_at"]}).json()
    assert [m["body"] for m in r["messages"]] == ["two"]


def test_paging_backwards(client, db, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    for i in range(5):
        say(client, auth_headers, a, conv["id"], f"m{i}")

    page = call(client, auth_headers, a, "get",
                f"/conversations/{conv['id']}/messages",
                params={"limit": 2}).json()
    assert [m["body"] for m in page["messages"]] == ["m3", "m4"]
    assert page["has_more"] is True

    older = call(client, auth_headers, a, "get",
                 f"/conversations/{conv['id']}/messages",
                 params={"limit": 10,
                         "before": page["messages"][0]["created_at"]}).json()
    assert [m["body"] for m in older["messages"]] == ["m0", "m1", "m2"]


def test_outsiders_cannot_read_or_write(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    say(client, auth_headers, a, conv["id"], "private")

    for outsider in (test_data["main_admin"],
                     test_data["other_business_manager"]):
        r = call(client, auth_headers, outsider, "get",
                 f"/conversations/{conv['id']}/messages")
        assert r.status_code == 404
        assert say(client, auth_headers, outsider, conv["id"], "hi").status_code == 404
        assert call(client, auth_headers, outsider, "get",
                    "/conversations").json() == []


def test_reply_must_point_inside_the_conversation(
    client, test_data, auth_headers
):
    a, b, c = test_data["manager"], test_data["staff"], test_data["main_admin"]
    one = open_dm(client, auth_headers, a, b)
    two = open_dm(client, auth_headers, a, c)
    parent = say(client, auth_headers, a, one["id"], "question").json()

    ok = say(client, auth_headers, b, one["id"], "answer",
             reply_to_id=parent["id"])
    assert ok.status_code == 201 and ok.json()["reply_to_id"] == parent["id"]
    bad = say(client, auth_headers, a, two["id"], "x",
              reply_to_id=parent["id"])
    assert bad.status_code == 404


def test_edit_and_delete_own_messages_only(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    msg = say(client, auth_headers, a, conv["id"], "typo").json()

    r = call(client, auth_headers, a, "patch", f"/messages/{msg['id']}",
             json={"body": "fixed"})
    assert r.status_code == 200
    assert r.json()["body"] == "fixed" and r.json()["edited_at"]

    assert call(client, auth_headers, b, "patch", f"/messages/{msg['id']}",
                json={"body": "hijack"}).status_code == 403
    assert call(client, auth_headers, b, "delete",
                f"/messages/{msg['id']}").status_code == 403

    assert call(client, auth_headers, a, "delete",
                f"/messages/{msg['id']}").status_code == 204
    shown = call(client, auth_headers, b, "get",
                 f"/conversations/{conv['id']}/messages").json()["messages"]
    assert shown[0]["deleted"] is True and shown[0]["body"] == ""
    assert call(client, auth_headers, a, "patch", f"/messages/{msg['id']}",
                json={"body": "again"}).status_code == 409


def test_deleted_messages_do_not_count_as_unread(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    msg = say(client, auth_headers, a, conv["id"], "oops").json()
    call(client, auth_headers, a, "delete", f"/messages/{msg['id']}")
    assert call(client, auth_headers, b, "get",
                "/unread-count").json() == {"unread": 0, "mentions": 0}


def test_channel_lifecycle(client, test_data, auth_headers):
    a, b, c = test_data["manager"], test_data["staff"], test_data["main_admin"]
    r = call(client, auth_headers, a, "post", "/conversations",
             json={"kind": "channel", "name": "  Mortuary  ",
                   "user_ids": [str(b.id)]})
    assert r.status_code == 201, r.text
    chan = r.json()
    assert chan["title"] == "  Mortuary  ".strip() or chan["title"] == "  Mortuary  "
    assert {p["id"] for p in chan["participants"]} == {str(a.id), str(b.id)}

    # c is not in it yet.
    assert call(client, auth_headers, c, "get",
                f"/conversations/{chan['id']}/messages").status_code == 404

    r = call(client, auth_headers, b, "post",
             f"/conversations/{chan['id']}/participants",
             json={"user_ids": [str(c.id)]})
    assert r.status_code == 200 and len(r.json()["participants"]) == 3
    assert call(client, auth_headers, c, "get",
                f"/conversations/{chan['id']}/messages").status_code == 200

    # A newcomer does not see the channel's history as unread.
    assert call(client, auth_headers, c, "get",
                "/unread-count").json() == {"unread": 0, "mentions": 0}

    # Leave yourself; removing others needs chat.manage (manager has it).
    assert call(client, auth_headers, b, "delete",
                f"/conversations/{chan['id']}/participants/{b.id}"
                ).status_code == 204
    assert call(client, auth_headers, a, "delete",
                f"/conversations/{chan['id']}/participants/{c.id}"
                ).status_code == 204


def test_staff_cannot_remove_others_and_dms_cannot_be_left(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    chan = call(client, auth_headers, a, "post", "/conversations",
                json={"kind": "channel", "name": "Ops",
                      "user_ids": [str(b.id)]}).json()
    assert call(client, auth_headers, b, "delete",
                f"/conversations/{chan['id']}/participants/{a.id}"
                ).status_code == 403

    dm = open_dm(client, auth_headers, a, b)
    assert call(client, auth_headers, a, "delete",
                f"/conversations/{dm['id']}/participants/{a.id}"
                ).status_code == 409
    assert call(client, auth_headers, a, "post",
                f"/conversations/{dm['id']}/participants",
                json={"user_ids": [str(test_data['main_admin'].id)]}
                ).status_code == 409


def test_manager_can_delete_someone_elses_message(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    chan = call(client, auth_headers, a, "post", "/conversations",
                json={"kind": "channel", "name": "Ops",
                      "user_ids": [str(b.id)]}).json()
    msg = say(client, auth_headers, b, chan["id"], "rude").json()
    assert call(client, auth_headers, a, "delete",
                f"/messages/{msg['id']}").status_code == 204


def test_channel_needs_a_name_and_real_people(
    client, test_data, auth_headers
):
    a = test_data["manager"]
    assert call(client, auth_headers, a, "post", "/conversations",
                json={"kind": "channel", "name": " "}).status_code == 422
    r = call(client, auth_headers, a, "post", "/conversations",
             json={"kind": "channel", "name": "X",
                   "user_ids": [str(test_data["other_business_manager"].id)]})
    assert r.status_code == 404


def test_channel_from_a_group_brings_its_members(
    client, db, test_data, auth_headers
):
    from app.models.group import Group, GroupMember

    a, b = test_data["manager"], test_data["staff"]
    group = Group(business_id=a.business_id, name="Drivers")
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=b.id))
    db.commit()

    r = call(client, auth_headers, a, "post", "/conversations",
             json={"kind": "channel", "group_id": str(group.id)})
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "Drivers"
    assert {p["id"] for p in r.json()["participants"]} == {str(a.id), str(b.id)}


def test_people_list_excludes_me_other_businesses_and_inactive(
    client, db, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    b.is_active = False
    db.commit()
    ids = {p["id"] for p in call(client, auth_headers, a, "get", "/people").json()}
    assert str(a.id) not in ids
    assert str(b.id) not in ids
    assert str(test_data["other_business_manager"].id) not in ids
    assert str(test_data["main_admin"].id) in ids


def test_chat_needs_permission(client, db, test_data, auth_headers):
    a = test_data["manager"]
    deny(db, a, "chat.use")
    for method, path in (("get", "/people"), ("get", "/conversations"),
                         ("get", "/unread-count")):
        assert call(client, auth_headers, a, method, path).status_code == 403
