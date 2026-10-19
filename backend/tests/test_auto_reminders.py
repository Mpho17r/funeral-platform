"""Daily automatic queueing of reminders."""

from datetime import timedelta

from app.models.audit_log import AuditLog
from app.models.communication import CommunicationMessage
from app.services.auto_reminders import run_all
from tests.test_communications import call, deny, setup_member, today


def queued(db, business):
    return (
        db.query(CommunicationMessage)
        .filter_by(business_id=business.id, status="queued")
        .count()
    )


def test_off_by_default_so_nothing_is_queued(db, test_data):
    biz = test_data["business_a"]
    setup_member(db, biz, due=today() - timedelta(days=5))

    assert run_all(db) == {}
    assert queued(db, biz) == 0


def test_switched_on_queues_due_reminders_once_a_day(db, test_data):
    biz = test_data["business_a"]
    setup_member(db, biz, due=today() - timedelta(days=5))
    biz.auto_reminders_enabled = True
    db.commit()

    assert run_all(db) == {str(biz.id): 1}
    assert queued(db, biz) == 1
    assert biz.auto_reminders_last_count == 1
    assert biz.auto_reminders_last_run_at is not None

    # A second run the same day adds nothing.
    assert run_all(db) == {str(biz.id): 0}
    assert queued(db, biz) == 1

    log = (
        db.query(AuditLog)
        .filter_by(action="communication.reminders_auto_generated")
        .first()
    )
    assert log.user_id is None and log.details["created"] == 1


def test_only_businesses_that_switched_it_on_are_run(db, test_data):
    a, b = test_data["business_a"], test_data["business_b"]
    setup_member(db, a, due=today() - timedelta(days=5))
    setup_member(db, b, due=today() - timedelta(days=5))
    a.auto_reminders_enabled = True
    db.commit()

    run_all(db)
    assert queued(db, a) == 1 and queued(db, b) == 0


def test_setting_can_be_read_and_changed_and_is_audited(
    client, db, test_data, auth_headers
):
    admin = test_data["main_admin"]
    path = "/communications/reminders/automation"

    r = call(client, auth_headers, admin, "GET", path)
    assert r.status_code == 200 and r.json()["enabled"] is False

    r = call(client, auth_headers, admin, "PUT", path, json={"enabled": True})
    assert r.status_code == 200 and r.json()["enabled"] is True
    assert (
        db.query(AuditLog)
        .filter_by(action="communication.automation_changed")
        .count()
        == 1
    )

    # Saving the same value again is not a change.
    call(client, auth_headers, admin, "PUT", path, json={"enabled": True})
    assert (
        db.query(AuditLog)
        .filter_by(action="communication.automation_changed")
        .count()
        == 1
    )


def test_bad_values_are_rejected(client, test_data, auth_headers):
    r = call(
        client, auth_headers, test_data["main_admin"], "PUT",
        "/communications/reminders/automation", json={"enabled": "yes"},
    )
    assert r.status_code == 422


def test_changing_needs_send_permission(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    deny(db, manager, "communications.send")
    path = "/communications/reminders/automation"

    assert call(client, auth_headers, manager, "GET", path).status_code == 200
    r = call(client, auth_headers, manager, "PUT", path, json={"enabled": True})
    assert r.status_code == 403
