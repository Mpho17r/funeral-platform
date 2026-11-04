"""Appointments, customer messages and the document library."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.appointments import Appointment, ContactMessage
from app.models.business import Business
from app.models.notification import Notification
from app.services import appointments as appt_service
from app.services import contact_messages as messages
from app.services import library as library_service
from app.services import message_delivery
from tests.test_business_api_permissions import deny_permission
from tests.test_business_mode import go_general
from tests.test_sales import make_customer, make_invoice

ZONE = ZoneInfo("Africa/Johannesburg")
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def next_monday() -> date:
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()))


def at(day: date, hour: int, minute: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE).isoformat()


def book(client, headers, title="Site visit", hour=10, day=None, **extra):
    day = day or next_monday()
    body = {"title": title, "start_at": at(day, hour), "duration_minutes": 60, **extra}
    return client.post("/appointments", json=body, headers=headers)


# ---------------------------------------------------------------- appointments


def test_book_list_and_clash(client, auth_headers, db, test_data):
    mh = auth_headers(test_data["manager"])
    staff = str(test_data["staff"].id)

    first = book(client, mh, assigned_user_id=staff, contact_name="Mrs Dube")
    assert first.status_code == 201, first.text
    appt = first.json()["appointment"]
    assert appt["status"] == "scheduled" and appt["who"] == "Mrs Dube"

    # The same person cannot be in two places at once...
    clash = book(client, mh, title="Quote", hour=10, assigned_user_id=staff)
    assert clash.status_code == 409 and "Site visit" in clash.json()["detail"]
    # ...unless the booking is confirmed anyway; back-to-back is fine.
    assert book(client, mh, title="Quote", hour=10, assigned_user_id=staff, allow_clash=True).status_code == 201
    assert book(client, mh, title="Later", hour=11, assigned_user_id=staff).status_code == 201

    listing = client.get("/appointments", headers=mh).json()
    assert len(listing["items"]) == 3
    assert listing["reminders_on"] is False
    assert [i["title"] for i in listing["items"]][0] in {"Site visit", "Quote"}


def test_a_person_on_leave_cannot_be_booked(client, auth_headers, test_data):
    mh, sh = auth_headers(test_data["manager"]), auth_headers(test_data["staff"])
    monday = next_monday()
    leave = client.post(
        "/leave",
        json={
            "leave_type": "annual",
            "start_date": monday.isoformat(),
            "end_date": (monday + timedelta(days=1)).isoformat(),
        },
        headers=sh,
    ).json()
    assert client.post(f"/leave/{leave['id']}/approve", json={}, headers=mh).status_code == 200

    staff = str(test_data["staff"].id)
    refused = book(client, mh, assigned_user_id=staff)
    assert refused.status_code == 409 and "leave" in refused.json()["detail"]
    assert book(client, mh, assigned_user_id=staff, allow_clash=True).status_code == 201


def test_reschedule_keeps_the_length_and_rechecks_clashes(client, auth_headers, test_data):
    mh = auth_headers(test_data["manager"])
    staff = str(test_data["staff"].id)
    a = book(client, mh, hour=9, assigned_user_id=staff).json()["appointment"]
    book(client, mh, title="Other", hour=14, assigned_user_id=staff)

    moved = client.patch(
        f"/appointments/{a['id']}",
        json={"start_at": at(next_monday(), 15)},
        headers=mh,
    )
    # 15:00 to 16:00 would overlap nothing... 14:00-15:00 ends at 15:00.
    assert moved.status_code == 200, moved.text
    start = datetime.fromisoformat(moved.json()["start_at"])
    end = datetime.fromisoformat(moved.json()["end_at"])
    assert end - start == timedelta(hours=1)

    into_clash = client.patch(
        f"/appointments/{a['id']}", json={"start_at": at(next_monday(), 14, 30)}, headers=mh
    )
    assert into_clash.status_code == 409


def test_status_changes_and_their_rules(client, auth_headers, test_data):
    mh = auth_headers(test_data["manager"])
    a = book(client, mh).json()["appointment"]

    assert client.post(f"/appointments/{a['id']}/confirm", headers=mh).json()["status"] == "confirmed"
    # It has not started yet.
    assert client.post(f"/appointments/{a['id']}/no-show", headers=mh).status_code == 409
    # A reason is required to cancel.
    assert client.post(f"/appointments/{a['id']}/cancel", json={"reason": ""}, headers=mh).status_code == 422
    done = client.post(f"/appointments/{a['id']}/complete", headers=mh)
    assert done.json()["status"] == "completed"
    # Finished appointments are closed.
    assert client.post(f"/appointments/{a['id']}/cancel", json={"reason": "x"}, headers=mh).status_code == 409
    assert client.patch(f"/appointments/{a['id']}", json={"title": "New"}, headers=mh).status_code == 409

    b = book(client, mh, title="Cancel me", hour=13).json()["appointment"]
    cancelled = client.post(f"/appointments/{b['id']}/cancel", json={"reason": "Customer asked"}, headers=mh)
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_reason"] == "Customer asked"


def test_validation_and_access(client, auth_headers, db, test_data):
    mh, sh = auth_headers(test_data["manager"]), auth_headers(test_data["staff"])
    monday = next_monday()

    backwards = client.post(
        "/appointments",
        json={"title": "x", "start_at": at(monday, 11), "end_at": at(monday, 10)},
        headers=mh,
    )
    assert backwards.status_code == 422
    assert book(client, mh, contact_phone="abc").status_code == 422
    assert book(client, mh, contact_email="nope").status_code == 422
    assert book(client, mh, customer_id="00000000-0000-0000-0000-000000000000").status_code == 404

    # Another business cannot see or change it.
    a = book(client, mh).json()["appointment"]
    other = auth_headers(test_data["other_business_manager"])
    assert client.get(f"/appointments/{a['id']}", headers=other).status_code == 404
    assert client.post(f"/appointments/{a['id']}/confirm", headers=other).status_code == 404
    assert client.get("/appointments", headers=other).json()["items"] == []

    # Taking the permission away is enforced.
    deny_permission(db, test_data["staff"].id, "appointments.manage")
    assert book(client, sh).status_code == 403
    assert client.get("/appointments", headers=sh).status_code == 200
    assert client.get("/appointments").status_code in (401, 403)


def test_assignee_is_told_and_the_calendar_shows_it(client, auth_headers, db, test_data):
    mh, sh = auth_headers(test_data["manager"]), auth_headers(test_data["staff"])
    staff = str(test_data["staff"].id)
    book(client, mh, title="Meet the supplier", assigned_user_id=staff)
    book(client, mh, title="Someone else's", hour=12)

    assert db.query(Notification).filter(Notification.kind == "appointment").count() == 1

    monday = next_monday()
    params = {"start": monday.isoformat(), "end": monday.isoformat()}
    manager_events = client.get("/calendar", params=params, headers=mh).json()
    titles = {e["title"] for e in manager_events if e["event_type"] == "appointment"}
    assert titles == {"Meet the supplier", "Someone else's"}

    # Shared like the Appointments page; "only my schedule" narrows it.
    staff_events = client.get("/calendar", params=params, headers=sh).json()
    assert {e["title"] for e in staff_events if e["event_type"] == "appointment"} == titles
    mine = client.get("/calendar", params={**params, "mine": "true"}, headers=sh).json()
    assert {e["title"] for e in mine if e["event_type"] == "appointment"} == {"Meet the supplier"}


# -------------------------------------------------------------------- messages


def test_templates_use_the_customers_name(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = auth_headers(test_data["main_admin"])
    customer = make_customer(client, h, "Thandi Stores")
    found = client.get("/outbox/templates", params={"customer_id": customer}, headers=h).json()
    thanks = next(t for t in found if t["key"] == "thank_you")
    assert "Hello Thandi Stores" in thanks["body"] and "{" not in thanks["body"]


def test_compose_whatsapp_sms_and_email(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = auth_headers(test_data["main_admin"])
    customer = make_customer(client, h)

    wa = client.post(
        "/outbox",
        json={"channel": "whatsapp", "customer_id": customer, "body": "Hi, your order is ready"},
        headers=h,
    )
    assert wa.status_code == 201, wa.text
    body = wa.json()
    # A South African number becomes international and the text is in the link.
    assert body["recipient"] == "27821234567"
    assert body["link"].startswith("https://wa.me/27821234567?text=Hi%2C%20your%20order")
    assert body["status"] == "queued"

    sms = client.post(
        "/outbox", json={"channel": "sms", "recipient": "0831112222", "body": "Ready"}, headers=h
    ).json()
    assert sms["link"].startswith("sms:+27831112222?body=")

    # The customer has no email saved, and typed ones are checked.
    no_email = client.post(
        "/outbox", json={"channel": "email", "customer_id": customer, "body": "Hi"}, headers=h
    )
    assert no_email.status_code == 422 and "email" in no_email.json()["detail"]
    assert client.post(
        "/outbox", json={"channel": "email", "recipient": "bad", "body": "Hi"}, headers=h
    ).status_code == 422
    assert client.post(
        "/outbox", json={"channel": "sms", "recipient": "12", "body": "Hi"}, headers=h
    ).status_code == 422
    assert client.post("/outbox", json={"channel": "sms", "body": "Hi"}, headers=h).status_code == 422

    # Marking sent, cancelling, and the rules around both.
    sent = client.post(f"/outbox/{body['id']}/mark-sent", headers=h).json()
    assert sent["status"] == "sent" and sent["delivered_by"] == "manual" and sent["link"] is None
    assert client.post(f"/outbox/{body['id']}/mark-sent", headers=h).status_code == 409
    assert client.post(f"/outbox/{sms['id']}/cancel", json={"reason": ""}, headers=h).status_code == 422
    assert client.post(f"/outbox/{sms['id']}/cancel", json={"reason": "Wrong number"}, headers=h).json()["status"] == "cancelled"
    assert client.post(f"/outbox/{body['id']}/cancel", json={"reason": "x"}, headers=h).status_code == 409

    listing = client.get("/outbox", params={"customer_id": customer}, headers=h).json()
    assert len(listing["items"]) == 1 and listing["items"][0]["customer_name"] == "Thandi Stores"
    assert client.get("/outbox", params={"status": "cancelled"}, headers=h).json()["items"][0]["id"] == sms["id"]


def test_email_goes_out_when_email_is_set_up(client, auth_headers, db, test_data, monkeypatch):
    go_general(db, test_data)
    h = auth_headers(test_data["main_admin"])
    sent = []
    monkeypatch.setattr(message_delivery, "email_configured", lambda: True)
    monkeypatch.setattr(message_delivery, "send_email", lambda to, subject, body: sent.append((to, subject)))

    r = client.post(
        "/outbox",
        json={"channel": "email", "recipient": "buyer@example.com", "subject": "Hello", "body": "Hi there"},
        headers=h,
    )
    assert r.json()["status"] == "sent" and r.json()["delivered_by"] == "smtp"
    assert sent == [("buyer@example.com", "Hello")]

    # A failed send stays queued with the reason, and the scheduler retries it.
    def broken(to, subject, body):
        raise message_delivery.DeliveryError("mail server down")

    monkeypatch.setattr(message_delivery, "send_email", broken)
    failed = client.post(
        "/outbox",
        json={"channel": "email", "recipient": "buyer@example.com", "body": "Again"},
        headers=h,
    ).json()
    assert failed["status"] == "queued" and "mail server down" in failed["delivery_error"]

    monkeypatch.setattr(message_delivery, "send_email", lambda to, subject, body: sent.append((to, subject)))
    assert messages.deliver_queued(db) == {"sent": 1, "failed": 0}
    assert db.get(ContactMessage, failed["id"]).status == "sent"


def test_appointment_messages(client, auth_headers, db, test_data):
    mh = auth_headers(test_data["manager"])
    customer_h = auth_headers(test_data["main_admin"])
    go_general(db, test_data)
    customer = make_customer(client, customer_h, "Mr Khumalo")
    db.get(Business, test_data["business_a"].id).phone = "011 555 0000"
    db.commit()

    made = book(client, mh, customer_id=customer, location="Our shop", send_confirmation=True)
    assert made.status_code == 201, made.text
    note = made.json()["message"]
    assert note["kind"] == "appointment_confirmation" and note["channel"] == "whatsapp"
    assert "Hello Mr Khumalo" in note["body"] and "Our shop" in note["body"] and "011 555 0000" in note["body"]
    assert "Test Funeral Business A" in note["body"]

    # No way to reach them: the booking still works, and says why.
    nobody = book(client, mh, title="Walk-in", hour=15, send_confirmation=True).json()
    assert nobody["message"] is None and "phone number or email" in nobody["message_note"]

    appt = made.json()["appointment"]
    reminder = client.post(f"/appointments/{appt['id']}/message", json={"kind": "appointment_reminder"}, headers=mh)
    assert reminder.status_code == 201 and "reminder" in reminder.json()["subject"].lower()
    detail = client.get(f"/appointments/{appt['id']}", headers=mh).json()
    assert len(detail["messages"]) == 2
    assert client.post(f"/appointments/{appt['id']}/message", json={"kind": "custom"}, headers=mh).status_code == 422


def test_reminders_are_opt_in_and_sent_once(client, auth_headers, db, test_data):
    mh = auth_headers(test_data["manager"])
    ah = auth_headers(test_data["main_admin"])
    business_id = test_data["business_a"].id
    soon = datetime.now(timezone.utc) + timedelta(hours=5)
    db.add(
        Appointment(
            business_id=business_id,
            title="Fitting",
            start_at=soon,
            end_at=soon + timedelta(hours=1),
            status="scheduled",
            contact_name="Lerato",
            contact_phone="0821230000",
        )
    )
    db.commit()

    assert appt_service.plan_reminders(db) == 0  # switched off by default

    assert client.put("/appointments/settings/reminders", json={"appointment_reminders": True}, headers=mh).status_code == 200
    assert client.get("/appointments", headers=mh).json()["reminders_on"] is True
    assert appt_service.plan_reminders(db) == 1
    assert appt_service.plan_reminders(db) == 0  # once per appointment time
    queued = db.query(ContactMessage).filter(ContactMessage.kind == "appointment_reminder").all()
    assert len(queued) == 1 and queued[0].recipient == "27821230000"

    # Cancelled or far-off appointments are left alone.
    later = datetime.now(timezone.utc) + timedelta(days=3)
    db.add(Appointment(business_id=business_id, title="Far", start_at=later, end_at=later + timedelta(hours=1),
                       status="scheduled", contact_phone="0821230000"))
    db.commit()
    assert appt_service.plan_reminders(db) == 0
    assert ah  # (main admin header kept for symmetry)


def test_invoice_reminder(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = auth_headers(test_data["main_admin"])
    customer = make_customer(client, h, "Thandi Stores")
    invoice = make_invoice(client, h, customer, price="500.00", qty="2")
    r = client.post(f"/outbox/invoice/{invoice['id']}/reminder", headers=h)
    assert r.status_code == 201, r.text
    assert "R1,000.00 outstanding" in r.json()["body"] and invoice["number"] in r.json()["body"]

    client.post(
        f"/sales/documents/{invoice['id']}/payments",
        json={"amount": "1000.00", "method": "cash"},
        headers=h,
    )
    assert client.post(f"/outbox/invoice/{invoice['id']}/reminder", headers=h).status_code == 409


def test_messages_need_their_permission(client, auth_headers, test_data):
    sh = auth_headers(test_data["staff"])
    assert client.get("/outbox", headers=sh).status_code == 403
    assert client.post("/outbox", json={"channel": "sms", "recipient": "0821234567", "body": "x"}, headers=sh).status_code == 403


# ------------------------------------------------------------------- documents


def upload(client, headers, name="contract.pdf", content=PDF, **form):
    return client.post("/library", files={"file": (name, content, "application/pdf")}, data=form, headers=headers)


def test_upload_download_and_details(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = auth_headers(test_data["main_admin"])
    customer = make_customer(client, h, "Thandi Stores")

    r = upload(client, h, title="Supply contract", category="contract", customer_id=customer,
               expires_on=(date.today() + timedelta(days=10)).isoformat())
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["title"] == "Supply contract" and doc["customer_name"] == "Thandi Stores"
    assert doc["expiry"] == "soon" and doc["content_type"] == "application/pdf"

    file = client.get(f"/library/{doc['id']}/file", headers=h)
    assert file.status_code == 200 and file.content == PDF
    assert file.headers["x-content-type-options"] == "nosniff"

    # The title falls back to the file name.
    plain = upload(client, h, name="licence.pdf").json()
    assert plain["title"] == "licence" and plain["category"] == "other"

    edited = client.patch(f"/library/{doc['id']}", json={"title": "New title", "expires_on": None, "category": "licence"}, headers=h).json()
    assert edited["title"] == "New title" and edited["expiry"] is None and edited["category"] == "licence"

    found = client.get("/library", params={"q": "thandi"}, headers=h).json()
    assert [d["id"] for d in found["items"]] == [doc["id"]]
    assert client.get("/library", params={"category": "licence"}, headers=h).json()["counts"]["total"] == 2


def test_only_everyday_files_are_kept(client, auth_headers, test_data):
    h = auth_headers(test_data["main_admin"])
    assert upload(client, h, name="virus.exe", content=b"MZ\x90\x00 not a document").status_code == 422
    assert upload(client, h, name="empty.pdf", content=b"").status_code == 422
    # A file named .pdf that is really something else is judged by its contents.
    assert upload(client, h, name="fake.pdf", content=b"\x00\x01\x02binary").status_code == 422
    assert upload(client, h, category="nonsense").status_code == 422
    assert upload(client, h, customer_id="00000000-0000-0000-0000-000000000000").status_code == 404


def test_expiry_archive_and_alerts(client, auth_headers, db, test_data):
    h = auth_headers(test_data["main_admin"])
    today = date.today()
    expired = upload(client, h, title="Old licence", expires_on=(today - timedelta(days=1)).isoformat()).json()
    soon = upload(client, h, title="Insurance", expires_on=(today + timedelta(days=5)).isoformat()).json()
    upload(client, h, title="Fine", expires_on=(today + timedelta(days=200)).isoformat())

    assert (expired["expiry"], soon["expiry"]) == ("expired", "soon")
    listing = client.get("/library", params={"expiring": "true"}, headers=h).json()
    assert {d["title"] for d in listing["items"]} == {"Old licence", "Insurance"}
    assert listing["counts"] == {"total": 3, "expired": 1, "soon": 1}

    assert library_service.alert_expiring(db) >= 2
    alerts = db.query(Notification).filter(Notification.kind == "document_expiry").all()
    assert {a.title for a in alerts} >= {"Old licence has expired", "Insurance expires in 5 days"}
    # Not repeated the next time it runs.
    before = db.query(Notification).filter(Notification.kind == "document_expiry").count()
    assert library_service.alert_expiring(db) == 0
    assert db.query(Notification).filter(Notification.kind == "document_expiry").count() == before

    # Archiving hides it, and an archived document no longer alerts.
    assert client.post(f"/library/{expired['id']}/archive", headers=h).json()["archived"] is True
    assert expired["id"] not in [d["id"] for d in client.get("/library", headers=h).json()["items"]]
    assert [d["id"] for d in client.get("/library", params={"archived": "true"}, headers=h).json()["items"]] == [expired["id"]]
    assert client.post(f"/library/{expired['id']}/restore", headers=h).json()["archived"] is False


def test_documents_are_private_to_the_business_and_permission(client, auth_headers, test_data):
    h = auth_headers(test_data["main_admin"])
    doc = upload(client, h).json()

    other = auth_headers(test_data["other_business_manager"])
    assert client.get(f"/library/{doc['id']}/file", headers=other).status_code == 404
    assert client.patch(f"/library/{doc['id']}", json={"title": "x"}, headers=other).status_code == 404
    assert client.post(f"/library/{doc['id']}/archive", headers=other).status_code == 404

    sh = auth_headers(test_data["staff"])
    assert client.get("/library", headers=sh).status_code == 403
    assert client.get(f"/library/{doc['id']}/file", headers=sh).status_code == 403
    assert upload(client, sh).status_code == 403
