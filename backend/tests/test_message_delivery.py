"""Queued email goes out by itself; everything else stays manual."""

import pytest

from app.config import settings
from app.models.communication import (
    CommunicationMessage, MemberCommunicationPreference,
)
from app.services import message_delivery as md
from tests.test_branches import make_member


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "noreply@test")
    sent = []
    monkeypatch.setattr(
        md, "send_email", lambda to, subject, body: sent.append((to, subject))
    )
    return sent


def queue(db, test_data, channel="email", member=None):
    biz = test_data["business_a"]
    member = member or make_member(db, biz)
    m = CommunicationMessage(
        business_id=biz.id,
        member_id=member.id,
        kind="custom",
        channel=channel,
        recipient="a@b.co" if channel == "email" else "0821234567",
        subject="Hello",
        body="Body",
    )
    db.add(m)
    db.commit()
    return m


def test_queued_email_is_sent_and_recorded(db, test_data, smtp):
    m = queue(db, test_data)
    result = md.deliver_queued(db)
    db.refresh(m)
    assert result["sent"] == 1
    assert smtp == [("a@b.co", "Hello")]
    assert m.status == "sent" and m.delivered_by == "smtp"
    assert m.sent_at is not None


def test_whatsapp_and_sms_are_left_for_a_person(db, test_data, smtp):
    m = queue(db, test_data, channel="whatsapp")
    assert md.deliver_queued(db)["sent"] == 0
    db.refresh(m)
    assert m.status == "queued"


def test_nothing_happens_when_email_is_not_configured(db, test_data, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    m = queue(db, test_data)
    assert md.deliver_queued(db) == {"sent": 0, "failed": 0, "skipped": 0}
    db.refresh(m)
    assert m.status == "queued"


def test_opted_out_member_is_never_contacted(db, test_data, smtp):
    biz = test_data["business_a"]
    member = make_member(db, biz)
    from datetime import datetime, timezone
    db.add(MemberCommunicationPreference(
        member_id=member.id, business_id=biz.id, preferred_channel="email",
        opted_out=True, opted_out_at=datetime.now(timezone.utc),
    ))
    db.commit()
    m = queue(db, test_data, member=member)
    result = md.deliver_queued(db)
    db.refresh(m)
    assert smtp == []
    assert result["skipped"] == 1
    assert m.status == "cancelled"


def test_failure_keeps_the_message_queued_and_stops_after_max_attempts(
    db, test_data, monkeypatch
):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "noreply@test")

    def boom(*a):
        raise md.DeliveryError("server down")

    monkeypatch.setattr(md, "send_email", boom)
    m = queue(db, test_data)
    for _ in range(5):
        md.deliver_queued(db)
    db.refresh(m)
    assert m.status == "queued"
    assert m.delivery_attempts == settings.delivery_max_attempts
    assert m.delivery_error == "server down"


def test_deliver_endpoint_and_status(client, auth_headers, db, test_data, smtp):
    h = auth_headers(test_data["main_admin"])
    r = client.get("/communications/delivery", headers=h)
    assert r.json()["automatic"] == ["email"]
    m = queue(db, test_data)
    r = client.post(f"/communications/messages/{m.id}/deliver", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent" and r.json()["delivered_by"] == "smtp"
    again = client.post(f"/communications/messages/{m.id}/deliver", headers=h)
    assert again.status_code == 409


def test_deliver_endpoint_explains_manual_channels(
    client, auth_headers, db, test_data, smtp
):
    m = queue(db, test_data, channel="sms")
    r = client.post(
        f"/communications/messages/{m.id}/deliver",
        headers=auth_headers(test_data["main_admin"]),
    )
    assert r.status_code == 409
    assert "Only email" in r.json()["detail"]
