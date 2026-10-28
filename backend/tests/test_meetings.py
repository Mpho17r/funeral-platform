"""Meetings, invitations, call links and their chat cards."""

from datetime import datetime, timedelta, timezone

from tests.test_chat import call as chat_call, open_dm
from tests.test_reports import deny


def now():
    return datetime.now(timezone.utc)


def meet(client, auth_headers, user, method, path="", **kw):
    return getattr(client, method)(
        f"/meetings{path}", headers=auth_headers(user), **kw
    )


def body(hours_from_now=2, length=1, **extra):
    start = now() + timedelta(hours=hours_from_now)
    return {
        "title": "Morning briefing",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=length)).isoformat(),
        **extra,
    }


def create(client, auth_headers, user, **extra):
    r = meet(client, auth_headers, user, "post", json=body(**extra))
    assert r.status_code == 201, r.text
    return r.json()


def test_create_invite_and_both_see_it(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    m = create(client, auth_headers, a, user_ids=[str(b.id)],
               description="Agenda")
    assert m["is_organizer"] and m["my_response"] == "accepted"
    assert {i["id"]: i["response"] for i in m["invitees"]} == {
        str(a.id): "accepted", str(b.id): "pending"}

    mine = meet(client, auth_headers, b, "get").json()
    assert [x["id"] for x in mine] == [m["id"]]
    assert mine[0]["my_response"] == "pending"
    assert meet(client, auth_headers, test_data["main_admin"], "get").json() == []


def test_outsiders_cannot_open_a_meeting(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    m = create(client, auth_headers, a, user_ids=[str(b.id)])
    for outsider in (test_data["main_admin"],
                     test_data["other_business_manager"]):
        assert meet(client, auth_headers, outsider, "get",
                    f"/{m['id']}").status_code == 404
        assert meet(client, auth_headers, outsider, "post",
                    f"/{m['id']}/respond",
                    json={"response": "accepted"}).status_code == 404


def test_time_rules(client, test_data, auth_headers):
    a = test_data["manager"]
    t = now() + timedelta(hours=1)
    bad = [
        {"starts_at": t.isoformat(), "ends_at": t.isoformat()},
        {"starts_at": t.isoformat(),
         "ends_at": (t + timedelta(hours=25)).isoformat()},
        {"starts_at": (now() - timedelta(hours=2)).isoformat(),
         "ends_at": (now() - timedelta(hours=1)).isoformat()},
    ]
    for times in bad:
        r = meet(client, auth_headers, a, "post",
                 json={"title": "x", **times})
        assert r.status_code == 422, times


def test_join_link_must_be_https_and_can_be_generated(
    client, test_data, auth_headers
):
    a = test_data["manager"]
    r = meet(client, auth_headers, a, "post",
             json=body(join_url="javascript:alert(1)"))
    assert r.status_code == 422
    r = meet(client, auth_headers, a, "post",
             json=body(join_url="http://insecure.example"))
    assert r.status_code == 422

    ok = create(client, auth_headers, a, join_url="https://zoom.us/j/123")
    assert ok["join_url"] == "https://zoom.us/j/123"

    made = create(client, auth_headers, a, make_call_link=True)
    assert made["join_url"].startswith("https://")
    other = create(client, auth_headers, a, make_call_link=True)
    assert made["join_url"] != other["join_url"]


def test_cannot_invite_people_from_another_business(
    client, test_data, auth_headers
):
    r = meet(client, auth_headers, test_data["manager"], "post",
             json=body(user_ids=[str(test_data["other_business_manager"].id)]))
    assert r.status_code == 404


def test_respond_and_only_invitees_can(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    m = create(client, auth_headers, a, user_ids=[str(b.id)])
    r = meet(client, auth_headers, b, "post", f"/{m['id']}/respond",
             json={"response": "declined"})
    assert r.status_code == 200 and r.json()["my_response"] == "declined"
    assert meet(client, auth_headers, b, "post", f"/{m['id']}/respond",
                json={"response": "maybe"}).status_code == 422


def test_clashes_are_reported_for_invitees(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    create(client, auth_headers, a, user_ids=[str(b.id)], hours_from_now=3)
    r = meet(client, auth_headers, test_data["main_admin"], "post",
             json=body(hours_from_now=3, user_ids=[str(b.id)]))
    assert r.status_code == 201
    assert [c["title"] for c in r.json()["conflicts"]] == ["Morning briefing"]


def test_only_organizer_edits_and_new_time_resets_replies(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    m = create(client, auth_headers, a, user_ids=[str(b.id)])
    meet(client, auth_headers, b, "post", f"/{m['id']}/respond",
         json={"response": "accepted"})

    assert meet(client, auth_headers, b, "patch", f"/{m['id']}",
                json={"title": "hijack"}).status_code == 403

    later = now() + timedelta(hours=6)
    r = meet(client, auth_headers, a, "patch", f"/{m['id']}",
             json={"starts_at": later.isoformat(),
                   "ends_at": (later + timedelta(hours=1)).isoformat(),
                   "title": "Renamed"})
    assert r.status_code == 200 and r.json()["title"] == "Renamed"
    resp = {i["id"]: i["response"] for i in r.json()["invitees"]}
    assert resp[str(b.id)] == "pending" and resp[str(a.id)] == "accepted"


def test_cancel(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    m = create(client, auth_headers, a, user_ids=[str(b.id)])
    assert meet(client, auth_headers, b, "post",
                f"/{m['id']}/cancel").status_code == 403
    r = meet(client, auth_headers, a, "post", f"/{m['id']}/cancel")
    assert r.json()["cancelled"] is True
    assert meet(client, auth_headers, b, "post", f"/{m['id']}/respond",
                json={"response": "accepted"}).status_code == 409
    assert meet(client, auth_headers, a, "patch", f"/{m['id']}",
                json={"title": "x"}).status_code == 409


def test_upcoming_and_past_scopes(client, db, test_data, auth_headers):
    from app.models.meeting import Meeting

    a = test_data["manager"]
    soon = create(client, auth_headers, a)
    old = create(client, auth_headers, a, hours_from_now=1)
    row = db.get(Meeting, old["id"])
    row.starts_at = now() - timedelta(days=2)
    row.ends_at = now() - timedelta(days=2) + timedelta(hours=1)
    db.commit()

    up = meet(client, auth_headers, a, "get", params={"scope": "upcoming"})
    past = meet(client, auth_headers, a, "get", params={"scope": "past"})
    assert [m["id"] for m in up.json()] == [soon["id"]]
    assert [m["id"] for m in past.json()] == [old["id"]]


def test_meeting_in_a_chat_invites_everyone_and_posts_a_card(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    m = create(client, auth_headers, a, conversation_id=conv["id"])
    assert str(b.id) in {i["id"] for i in m["invitees"]}

    msgs = chat_call(client, auth_headers, b, "get",
                     f"/conversations/{conv['id']}/messages"
                     ).json()["messages"]
    card = [x for x in msgs if x["kind"] == "meeting"][0]
    assert card["meta"]["meeting_id"] == m["id"]

    meet(client, auth_headers, a, "post", f"/{m['id']}/cancel")
    msgs = chat_call(client, auth_headers, b, "get",
                     f"/conversations/{conv['id']}/messages"
                     ).json()["messages"]
    assert [x["body"] for x in msgs if x["kind"] == "meeting"] == [
        "scheduled a meeting", "cancelled a meeting"]


def test_meeting_in_someone_elses_chat_is_refused(
    client, test_data, auth_headers
):
    a, b, c = test_data["manager"], test_data["staff"], test_data["main_admin"]
    conv = open_dm(client, auth_headers, a, b)
    r = meet(client, auth_headers, c, "post",
             json=body(conversation_id=conv["id"]))
    assert r.status_code == 404


def test_huddle_posts_a_call_card(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    r = meet(client, auth_headers, a, "post", "/huddle",
             json={"conversation_id": conv["id"]})
    assert r.status_code == 201 and r.json()["join_url"].startswith("https://")

    theirs = next(
        c for c in chat_call(client, auth_headers, b, "get",
                             "/conversations").json()
        if c["id"] == conv["id"]
    )
    assert theirs["unread"] == 1
    msgs = chat_call(client, auth_headers, b, "get",
                     f"/conversations/{conv['id']}/messages"
                     ).json()["messages"]
    assert msgs[-1]["kind"] == "call"
    assert msgs[-1]["meta"]["join_url"] == r.json()["join_url"]

    outsider = test_data["main_admin"]
    assert meet(client, auth_headers, outsider, "post", "/huddle",
                json={"conversation_id": conv["id"]}).status_code == 404


def test_meetings_need_permission(client, db, test_data, auth_headers):
    a = test_data["manager"]
    deny(db, a, "meetings.use")
    assert meet(client, auth_headers, a, "get").status_code == 403
    assert meet(client, auth_headers, a, "post",
                json=body()).status_code == 403


def test_voice_call_starts_with_camera_off_and_rings_the_other(
    client, test_data, auth_headers, db
):
    from app.models.notification import Notification

    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    r = meet(client, auth_headers, a, "post", "/huddle",
             json={"conversation_id": conv["id"], "voice_only": True})
    assert r.status_code == 201
    assert "startWithVideoMuted=true" in r.json()["join_url"]

    msgs = chat_call(client, auth_headers, b, "get",
                     f"/conversations/{conv['id']}/messages"
                     ).json()["messages"]
    assert msgs[-1]["body"] == "started a voice call"
    ring = db.query(Notification).filter(
        Notification.user_id == b.id, Notification.kind == "call"
    ).one()
    assert "calling you" in ring.title
    # The caller is not rung.
    assert db.query(Notification).filter(
        Notification.user_id == a.id, Notification.kind == "call"
    ).count() == 0
