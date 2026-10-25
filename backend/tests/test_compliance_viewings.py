"""Licence/certificate renewals and family viewings."""

from datetime import date, datetime, timedelta, timezone

from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.services import compliance as svc
from app.services import mortuary_alerts
from tests.test_mortuary import identify, make_case, make_location, take_in
from tests.test_workspace_groups import make_staff

TODAY = date.today()


def team(db, test_data):
    biz, base = test_data["business_a"], test_data["staff"]
    return {
        "ops": make_staff(db, base, biz, role="operations", name="Ops"),
        "mortuary": make_staff(db, base, biz, role="mortuary", name="Morgue"),
        "finance": make_staff(db, base, biz, role="finance", name="Money"),
    }


def add_item(client, auth_headers, user, days=400, **over):
    body = {
        "kind": "certificate_of_competence",
        "title": "Certificate of competence - Main premises",
        "reference": "COC-1234",
        "issued_on": (TODAY - timedelta(days=330)).isoformat(),
        "expires_on": (TODAY + timedelta(days=days)).isoformat(),
    }
    body.update(over)
    return client.post("/compliance", json=body, headers=auth_headers(user))


# ------------------------------------------------------------- compliance


def test_states_follow_the_days_left():
    assert svc.state(TODAY - timedelta(days=1), TODAY) == "expired"
    assert svc.state(TODAY, TODAY) == "urgent"
    assert svc.state(TODAY + timedelta(days=30), TODAY) == "urgent"
    assert svc.state(TODAY + timedelta(days=31), TODAY) == "soon"
    assert svc.state(TODAY + timedelta(days=91), TODAY) == "ok"


def test_record_list_update_archive_and_audit(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    r = add_item(client, auth_headers, manager, days=45)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["state"] == "soon" and item["days_left"] == 45

    listing = client.get("/compliance", headers=auth_headers(manager)).json()
    assert listing["soon"] == 1 and listing["expired"] == 0

    new_date = (TODAY + timedelta(days=760)).isoformat()
    upd = client.patch(
        f"/compliance/{item['id']}",
        json={"expires_on": new_date},
        headers=auth_headers(manager),
    )
    assert upd.json()["state"] == "ok"

    client.post(f"/compliance/{item['id']}/archive", headers=auth_headers(manager))
    assert client.get(
        "/compliance", headers=auth_headers(manager)
    ).json()["items"] == []
    assert len(client.get(
        "/compliance", params={"include_archived": "true"},
        headers=auth_headers(manager),
    ).json()["items"]) == 1

    actions = {
        a.action for a in db.query(AuditLog).filter(
            AuditLog.business_id == test_data["business_a"].id,
            AuditLog.entity_type == "compliance_item",
        )
    }
    assert {"compliance.created", "compliance.updated",
            "compliance.archived"} <= actions


def test_validation(client, test_data, auth_headers):
    manager = test_data["manager"]
    assert add_item(client, auth_headers, manager, kind="nope").status_code == 422
    assert add_item(
        client, auth_headers, manager,
        issued_on=(TODAY + timedelta(days=10)).isoformat(),
        expires_on=TODAY.isoformat(),
    ).status_code == 422


def test_permissions_and_isolation(client, db, test_data, auth_headers):
    people = team(db, test_data)
    manager = test_data["manager"]
    item = add_item(client, auth_headers, manager).json()

    # Mortuary can see but not change; operations/finance/staff cannot see.
    assert client.get("/compliance", headers=auth_headers(people["mortuary"])).status_code == 200
    assert add_item(client, auth_headers, people["mortuary"]).status_code == 403
    for who in (people["ops"], people["finance"], test_data["staff"]):
        assert client.get("/compliance", headers=auth_headers(who)).status_code == 403

    other = test_data["other_business_manager"]
    assert client.patch(
        f"/compliance/{item['id']}", json={"title": "Hijack"},
        headers=auth_headers(other),
    ).status_code == 404
    assert client.get("/compliance", headers=auth_headers(other)).json()["items"] == []


def notices(db, user):
    return [
        n for n in db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.kind == "compliance_alert",
        )
    ]


def test_each_renewal_reminder_is_sent_once(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    biz = test_data["business_a"]
    add_item(client, auth_headers, manager, days=80)

    svc.run_for_business(db, biz.id, TODAY)
    first = len(notices(db, manager))
    assert first == 1
    assert "Renew soon" in notices(db, manager)[0].title

    # Same day again: nothing new.
    svc.run_for_business(db, biz.id, TODAY)
    assert len(notices(db, manager)) == 1

    # 30 days later it crosses the next threshold and tells them again.
    svc.run_for_business(db, biz.id, TODAY + timedelta(days=51))
    assert len(notices(db, manager)) == 2


def test_far_away_certificates_are_quiet_and_expired_ones_shout(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    biz = test_data["business_a"]
    add_item(client, auth_headers, manager, days=400, title="Far away")
    svc.run_for_business(db, biz.id, TODAY)
    assert notices(db, manager) == []

    add_item(client, auth_headers, manager, days=-3, title="Lapsed one")
    svc.run_for_business(db, biz.id, TODAY)
    expired = notices(db, manager)
    assert len(expired) == 1 and expired[0].title.startswith("EXPIRED")

    # Weekly while it stays expired, not daily.
    svc.run_for_business(db, biz.id, TODAY)
    assert len(notices(db, manager)) == 1
    svc.run_for_business(db, biz.id, TODAY + timedelta(days=7))
    assert len(notices(db, manager)) == 2


def test_the_scheduled_mortuary_job_includes_renewals(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    add_item(client, auth_headers, manager, days=10)
    mortuary_alerts.run_for_business(db, test_data["business_a"].id)
    assert len(notices(db, manager)) == 1


# --------------------------------------------------------------- viewings


def in_care(client, db, test_data, auth_headers, *, identified=True):
    biz = test_data["business_a"]
    who = test_data["manager"]
    case = make_case(db, biz)
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    r = take_in(client, auth_headers, who, case, location_id=str(fridge.id))
    assert r.status_code == 201, r.text
    if identified:
        identify(client, auth_headers, who, case)
    return case


def book(client, auth_headers, user, case, hours=3, **over):
    body = {
        "case_id": str(case.id),
        "starts_at": (
            datetime.now(timezone.utc) + timedelta(hours=hours)
        ).isoformat(),
        "duration_minutes": 30,
        "room": "Chapel of rest",
        "visitor_name": "Thandi Nkosi",
    }
    body.update(over)
    return client.post("/mortuary/viewings", json=body, headers=auth_headers(user))


def test_schedule_list_complete_and_cancel(client, db, test_data, auth_headers):
    people = team(db, test_data)
    case = in_care(client, db, test_data, auth_headers)

    r = book(client, auth_headers, people["ops"], case)
    assert r.status_code == 201, r.text
    viewing = r.json()
    assert viewing["tag_number"] and viewing["deceased_name"]

    # The mortuary team is told; the person who booked is not.
    told = db.query(Notification).filter(
        Notification.user_id == people["mortuary"].id,
        Notification.kind == "viewing",
    ).all()
    assert len(told) == 1 and "Viewing booked" in told[0].title
    assert not db.query(Notification).filter(
        Notification.user_id == people["ops"].id,
        Notification.kind == "viewing",
    ).count()

    listing = client.get(
        "/mortuary/viewings", headers=auth_headers(people["mortuary"])
    ).json()["items"]
    assert [v["id"] for v in listing] == [viewing["id"]]

    done = client.post(
        f"/mortuary/viewings/{viewing['id']}/complete",
        headers=auth_headers(people["mortuary"]),
    )
    assert done.json()["status"] == "completed"

    second = book(client, auth_headers, people["ops"], case, hours=6).json()
    cancelled = client.post(
        f"/mortuary/viewings/{second['id']}/cancel",
        json={"reason": "Family postponed"},
        headers=auth_headers(people["ops"]),
    )
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(
        f"/mortuary/viewings/{second['id']}/cancel",
        json={"reason": "again"},
        headers=auth_headers(people["ops"]),
    ).status_code == 409


def test_only_identified_remains_in_care_can_be_viewed(
    client, db, test_data, auth_headers
):
    ops = team(db, test_data)["ops"]
    not_in_care = make_case(db, test_data["business_a"])
    assert book(client, auth_headers, ops, not_in_care).status_code == 409

    unidentified = in_care(
        client, db, test_data, auth_headers, identified=False
    )
    r = book(client, auth_headers, ops, unidentified)
    assert r.status_code == 409 and "identified" in r.json()["detail"]


def test_past_times_and_double_booked_rooms_are_refused(
    client, db, test_data, auth_headers
):
    ops = team(db, test_data)["ops"]
    case = in_care(client, db, test_data, auth_headers)

    assert book(client, auth_headers, ops, case, hours=-3).status_code == 422
    assert book(client, auth_headers, ops, case, hours=3).status_code == 201

    clash = book(client, auth_headers, ops, case, hours=3)
    assert clash.status_code == 409 and "already booked" in clash.json()["detail"]
    # A different room, or right after, is fine.
    assert book(client, auth_headers, ops, case, hours=3, room="Room 2").status_code == 201
    assert book(client, auth_headers, ops, case, hours=4).status_code == 201


def test_viewing_permissions_and_isolation(client, db, test_data, auth_headers):
    people = team(db, test_data)
    case = in_care(client, db, test_data, auth_headers)

    assert book(client, auth_headers, people["finance"], case).status_code == 403
    assert client.get(
        "/mortuary/viewings", headers=auth_headers(people["finance"])
    ).status_code == 403

    viewing = book(client, auth_headers, people["ops"], case).json()
    other = test_data["other_business_manager"]
    assert client.post(
        f"/mortuary/viewings/{viewing['id']}/cancel",
        json={"reason": "not yours"},
        headers=auth_headers(other),
    ).status_code == 404
    assert client.get(
        "/mortuary/viewings", headers=auth_headers(other)
    ).json()["items"] == []
