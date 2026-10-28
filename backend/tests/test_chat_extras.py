"""Chat reactions, @mentions and shared files."""

import io

from app.services import chat_files
from tests.test_chat import call, open_dm, say

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def upload(client, auth_headers, user, conv_id, name, data):
    return client.post(
        f"/chat/conversations/{conv_id}/attachments",
        headers=auth_headers(user),
        files={"file": (name, io.BytesIO(data), "application/octet-stream")},
    )


def test_reaction_toggles_and_counts(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    msg = say(client, auth_headers, a, conv["id"], "Done").json()

    r = call(client, auth_headers, b, "post",
             f"/messages/{msg['id']}/reactions", json={"emoji": "👍"})
    assert r.json() == [{"emoji": "👍", "count": 1, "mine": True}]
    r = call(client, auth_headers, a, "post",
             f"/messages/{msg['id']}/reactions", json={"emoji": "👍"})
    assert r.json()[0]["count"] == 2

    seen = call(client, auth_headers, a, "get",
                f"/conversations/{conv['id']}/messages").json()["messages"]
    assert seen[0]["reactions"] == [{"emoji": "👍", "count": 2, "mine": True}]

    r = call(client, auth_headers, b, "post",
             f"/messages/{msg['id']}/reactions", json={"emoji": "👍"})
    assert r.json() == [{"emoji": "👍", "count": 1, "mine": False}]


def test_reaction_rules(client, test_data, auth_headers):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    msg = say(client, auth_headers, a, conv["id"], "hi").json()

    assert call(client, auth_headers, b, "post",
                f"/messages/{msg['id']}/reactions",
                json={"emoji": "💩"}).status_code == 422
    assert call(client, auth_headers, test_data["main_admin"], "post",
                f"/messages/{msg['id']}/reactions",
                json={"emoji": "👍"}).status_code == 404
    call(client, auth_headers, a, "delete", f"/messages/{msg['id']}")
    assert call(client, auth_headers, b, "post",
                f"/messages/{msg['id']}/reactions",
                json={"emoji": "👍"}).status_code == 409


def test_mentions_flag_the_conversation_until_read(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    say(client, auth_headers, a, conv["id"], "plain")
    assert call(client, auth_headers, b, "get",
                "/conversations").json()[0]["mentioned"] is False

    r = say(client, auth_headers, a, conv["id"], "@Staff look",
            mention_ids=[str(b.id)])
    assert r.status_code == 201
    assert call(client, auth_headers, b, "get",
                "/conversations").json()[0]["mentioned"] is True

    call(client, auth_headers, b, "post", f"/conversations/{conv['id']}/read")
    assert call(client, auth_headers, b, "get",
                "/conversations").json()[0]["mentioned"] is False


def test_cannot_mention_someone_outside_the_conversation(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    r = say(client, auth_headers, a, conv["id"], "hey",
            mention_ids=[str(test_data["main_admin"].id)])
    assert r.status_code == 422


def test_share_a_picture_and_download_it(
    client, test_data, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(chat_files, "STORAGE_ROOT", tmp_path)
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    up = upload(client, auth_headers, a, conv["id"], "photo.png", PNG)
    assert up.status_code == 201, up.text
    assert up.json()["is_image"] is True

    # Not yet sent: the other person cannot fetch it.
    assert client.get(f"/chat/attachments/{up.json()['id']}",
                      headers=auth_headers(b)).status_code == 404

    sent = say(client, auth_headers, a, conv["id"], "",
               attachment_ids=[up.json()["id"]])
    assert sent.status_code == 201
    assert sent.json()["attachments"][0]["filename"] == "photo.png"

    got = client.get(f"/chat/attachments/{up.json()['id']}",
                     headers=auth_headers(b))
    assert got.status_code == 200 and got.content == PNG
    assert got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"

    outsider = test_data["main_admin"]
    assert client.get(f"/chat/attachments/{up.json()['id']}",
                      headers=auth_headers(outsider)).status_code == 404

    call(client, auth_headers, a, "delete", f"/messages/{sent.json()['id']}")
    assert client.get(f"/chat/attachments/{up.json()['id']}",
                      headers=auth_headers(b)).status_code == 404


def test_non_images_download_as_attachments(
    client, test_data, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(chat_files, "STORAGE_ROOT", tmp_path)
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    up = upload(client, auth_headers, a, conv["id"], "list.csv", b"a,b\n1,2\n")
    say(client, auth_headers, a, conv["id"], "csv", attachment_ids=[up.json()["id"]])
    got = client.get(f"/chat/attachments/{up.json()['id']}",
                     headers=auth_headers(b))
    assert "attachment" in got.headers["content-disposition"]


def test_unsafe_or_oversized_files_are_refused(
    client, test_data, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(chat_files, "STORAGE_ROOT", tmp_path)
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    # An HTML page pretending to be a picture.
    r = upload(client, auth_headers, a, conv["id"], "x.png",
               b"<script>alert(1)</script>")
    assert r.status_code == 400
    assert upload(client, auth_headers, a, conv["id"], "run.exe",
                  b"MZ" + b"0" * 50).status_code == 400
    assert upload(client, auth_headers, a, conv["id"], "e.png",
                  b"").status_code == 400
    big = PNG + b"0" * chat_files.MAX_BYTES
    assert upload(client, auth_headers, a, conv["id"], "big.png",
                  big).status_code == 400


def test_cannot_send_someone_elses_or_foreign_attachment(
    client, test_data, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(chat_files, "STORAGE_ROOT", tmp_path)
    a, b, c = test_data["manager"], test_data["staff"], test_data["main_admin"]
    one = open_dm(client, auth_headers, a, b)
    two = open_dm(client, auth_headers, a, c)
    up = upload(client, auth_headers, a, one["id"], "p.png", PNG).json()

    # Another person in the chat cannot send my upload.
    assert say(client, auth_headers, b, one["id"], "mine now",
               attachment_ids=[up["id"]]).status_code == 404
    # And it cannot be reused in a different conversation.
    assert say(client, auth_headers, a, two["id"], "wrong place",
               attachment_ids=[up["id"]]).status_code == 404
    # An upload can only be sent once.
    assert say(client, auth_headers, a, one["id"], "",
               attachment_ids=[up["id"]]).status_code == 201
    assert say(client, auth_headers, a, one["id"], "",
               attachment_ids=[up["id"]]).status_code == 404


def test_file_only_message_needs_no_text_but_empty_is_refused(
    client, test_data, auth_headers
):
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)
    assert say(client, auth_headers, a, conv["id"], "").status_code == 422


def test_voice_note_is_sent_and_played_by_the_other_person(
    client, test_data, auth_headers, tmp_path, monkeypatch
):
    monkeypatch.setattr(chat_files, "STORAGE_ROOT", tmp_path)
    a, b = test_data["manager"], test_data["staff"]
    conv = open_dm(client, auth_headers, a, b)

    note = b"\x1a\x45\xdf\xa3" + b"0" * 200  # what a browser records (webm)
    up = upload(client, auth_headers, a, conv["id"], "voice-note.webm", note)
    assert up.status_code == 201, up.text
    assert up.json()["is_audio"] is True and up.json()["is_image"] is False

    sent = say(client, auth_headers, a, conv["id"], "",
               attachment_ids=[up.json()["id"]])
    assert sent.status_code == 201
    assert sent.json()["attachments"][0]["is_audio"] is True

    got = client.get(f"/chat/attachments/{up.json()['id']}",
                     headers=auth_headers(b))
    assert got.status_code == 200 and got.content == note
    assert got.headers["content-type"].startswith("audio/webm")
