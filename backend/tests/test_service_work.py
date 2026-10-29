"""Services work like tasks: given to people, who keep the status up to date."""

from datetime import datetime, timedelta, timezone

from app.models.business import Business
from app.models.case_service import CaseService
from app.models.notification import Notification
from app.services import archive as archive_service
from tests.test_branches import make_case
from tests.test_financial_documents import make_service
from tests.test_task_workspace import deny
from tests.test_workspace_groups import make_staff


def assign(client, auth_headers, admin, service, people, **extra):
    return client.post(
        f"/service-work/{service.id}/assign",
        json={"assignee_ids": [str(p.id) for p in people], **extra},
        headers=auth_headers(admin),
    )


def test_a_service_can_be_given_to_several_people_who_are_told(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    service = make_service(db, biz, case, name="Hearse")
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    b = make_staff(db, test_data["staff"], biz, name="Ben")
    due = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    r = assign(client, auth_headers, test_data["main_admin"], service, [a, b], due_at=due.isoformat())
    assert r.status_code == 200, r.text
    for who in (a, b):
        mine = client.get("/service-work/board", headers=auth_headers(who)).json()["services"]
        assert [s["id"] for s in mine] == [str(service.id)]
        assert mine[0]["can_update"] is True and mine[0]["due_at"]
        assert db.query(Notification).filter(
            Notification.user_id == who.id, Notification.kind == "service_assigned"
        ).count() == 1
    c = make_staff(db, test_data["staff"], biz, name="Cee")
    assert client.get("/service-work/board", headers=auth_headers(c)).json()["services"] == []


def test_assignee_updates_status_without_manage_permission(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    service = make_service(db, biz, case, name="Flowers")
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    b = make_staff(db, test_data["staff"], biz, name="Ben")
    outsider = make_staff(db, test_data["staff"], biz, name="Out")
    assign(client, auth_headers, test_data["main_admin"], service, [a, b])
    for who in (a, outsider):
        deny(db, who, "services.manage")

    r = client.post(f"/service-work/{service.id}/status", json={"status": "in_progress"},
                    headers=auth_headers(a))
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    assert db.query(Notification).filter(
        Notification.user_id == b.id, Notification.kind == "service_update"
    ).count() == 1
    assert client.post(f"/service-work/{service.id}/status", json={"status": "completed"},
                       headers=auth_headers(outsider)).status_code == 403
    # An assignee cannot cancel; that is for managers.
    assert client.post(f"/service-work/{service.id}/status", json={"status": "cancelled"},
                       headers=auth_headers(a)).status_code == 403
    done = client.post(f"/service-work/{service.id}/status", json={"status": "completed"},
                       headers=auth_headers(a))
    assert done.status_code == 200
    db.expire_all()
    assert db.get(CaseService, service.id).completed_at is not None
    assert client.post(f"/service-work/{service.id}/status", json={"status": "nonsense"},
                       headers=auth_headers(a)).status_code == 422


def test_only_managers_assign_and_only_to_their_own_team(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    service = make_service(db, biz, case)
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    deny(db, a, "services.manage")
    assert assign(client, auth_headers, a, service, [a]).status_code == 403
    stranger = test_data["main_admin_b"] if "main_admin_b" in test_data else None
    if stranger is not None:
        assert assign(client, auth_headers, test_data["main_admin"], service, [stranger]).status_code == 422


def test_finished_services_are_archived_and_leave_my_list(client, auth_headers, db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    case = make_case(db, biz)
    service = make_service(db, biz, case, name="Tent")
    a = make_staff(db, test_data["staff"], biz, name="Ann")
    assign(client, auth_headers, test_data["main_admin"], service, [a])
    client.post(f"/service-work/{service.id}/status", json={"status": "completed"},
                headers=auth_headers(a))

    assert len(client.get("/service-work/board?state=open", headers=auth_headers(a)).json()["services"]) == 0
    assert len(client.get("/service-work/board?state=done", headers=auth_headers(a)).json()["services"]) == 1

    # Fresh: the sweep leaves it. Old: it is archived.
    assert archive_service.sweep(db, biz)["services_archived"] == 0
    row = db.get(CaseService, service.id)
    row.updated_at = datetime.now(timezone.utc) - timedelta(days=60)
    db.commit()
    assert archive_service.sweep(db, biz)["services_archived"] == 1

    assert client.get("/service-work/board?state=done", headers=auth_headers(a)).json()["services"] == []
    listed = client.get("/archive?kind=services", headers=auth_headers(a)).json()
    assert [s["id"] for s in listed] == [str(service.id)]
    assert client.post(f"/archive/services/{service.id}/restore",
                       headers=auth_headers(a)).status_code == 200
    # It is never deleted from the archive.
    assert client.delete(f"/archive/services/{service.id}",
                         headers=auth_headers(test_data["main_admin"])).status_code == 404


def test_an_open_service_cannot_be_archived(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    service = make_service(db, biz, case)
    r = client.post(f"/archive/services/{service.id}/archive", headers=auth_headers(test_data["main_admin"]))
    assert r.status_code == 409
