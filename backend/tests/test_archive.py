"""The archive: finished work leaves the working lists."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.business import Business
from app.models.case_task import CaseTask
from app.models.financial_document import FinancialDocument
from app.models.funeral_case import FuneralCase
from app.services import archive as service
from tests.test_branches import make_case
from tests.test_task_workspace import give

LONG_AGO = datetime.now(timezone.utc) - timedelta(days=60)


def finish(client, auth_headers, user, task):
    r = client.post(f"/tasks/{task['id']}/status", json={"status": "completed"},
                    headers=auth_headers(user))
    assert r.status_code == 200, r.text


def board(client, auth_headers, user, state="all"):
    return client.get(f"/tasks/board?scope=mine&state={state}",
                      headers=auth_headers(user)).json()["tasks"]


def test_archived_task_leaves_the_lists_and_can_come_back(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    admin = test_data["main_admin"]
    task = give(client, auth_headers, admin, case, [admin])

    # Open work cannot be archived.
    assert client.post(f"/archive/tasks/{task['id']}/archive",
                       headers=auth_headers(admin)).status_code == 409

    finish(client, auth_headers, admin, task)
    assert len(board(client, auth_headers, admin)) == 1
    assert client.post(f"/archive/tasks/{task['id']}/archive",
                       headers=auth_headers(admin)).status_code == 200

    assert board(client, auth_headers, admin) == []
    assert len(board(client, auth_headers, admin, "archived")) == 1
    on_case = client.get(f"/cases/{case.id}/tasks", headers=auth_headers(admin)).json()
    assert on_case == []
    listed = client.get("/archive?kind=tasks", headers=auth_headers(admin)).json()
    assert [t["id"] for t in listed] == [task["id"]]

    assert client.post(f"/archive/tasks/{task['id']}/restore",
                       headers=auth_headers(admin)).status_code == 200
    assert len(board(client, auth_headers, admin)) == 1


def test_sweep_archives_old_finished_work_only(db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    old = make_case(db, biz, status="closed")
    fresh = make_case(db, biz, status="closed")
    live = make_case(db, biz, status="open")
    for c, when in ((old, LONG_AGO), (fresh, datetime.now(timezone.utc)), (live, LONG_AGO)):
        c.updated_at = when
    t_old = CaseTask(business_id=biz.id, case_id=live.id, title="Old", status="completed",
                     completed_at=LONG_AGO)
    t_new = CaseTask(business_id=biz.id, case_id=live.id, title="New", status="completed",
                     completed_at=datetime.now(timezone.utc))
    t_open = CaseTask(business_id=biz.id, case_id=live.id, title="Open", status="pending")
    db.add_all([t_old, t_new, t_open])
    db.commit()

    result = service.sweep(db, biz)
    assert result["cases_archived"] == 1 and result["tasks_archived"] == 1
    db.refresh(old); db.refresh(fresh); db.refresh(live)
    db.refresh(t_old); db.refresh(t_new); db.refresh(t_open)
    assert old.is_archived and not fresh.is_archived and not live.is_archived
    assert t_old.archived_at and not t_new.archived_at and not t_open.archived_at


def test_automatic_archiving_can_be_switched_off(db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    biz.archive_after_days = 0
    case = make_case(db, biz, status="closed")
    case.updated_at = LONG_AGO
    db.commit()
    assert service.sweep(db, biz)["cases_archived"] == 0


def test_only_main_admin_deletes_and_only_archived_items(client, auth_headers, db, test_data):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    admin, manager = test_data["main_admin"], test_data["manager"]
    task = give(client, auth_headers, admin, case, [admin])

    assert client.delete(f"/archive/tasks/{task['id']}",
                         headers=auth_headers(manager)).status_code == 403
    # Not archived yet: refused even for the main admin.
    assert client.delete(f"/archive/tasks/{task['id']}",
                         headers=auth_headers(admin)).status_code == 409
    finish(client, auth_headers, admin, task)
    client.post(f"/archive/tasks/{task['id']}/archive", headers=auth_headers(admin))
    assert client.delete(f"/archive/tasks/{task['id']}",
                         headers=auth_headers(admin)).status_code == 204
    assert db.query(CaseTask).filter(CaseTask.id == task["id"]).count() == 0


def test_retention_deletes_old_archived_items_but_never_financial_records(db, test_data):
    biz = db.get(Business, test_data["business_a"].id)
    biz.delete_archived_after_months = 6
    plain = make_case(db, biz, status="closed")
    kept = make_case(db, biz, status="closed")
    for c in (plain, kept):
        c.is_archived = True
        c.archived_at = datetime.now(timezone.utc) - timedelta(days=400)
    db.add(FinancialDocument(
        business_id=biz.id, case_id=kept.id, document_type="invoice", status="draft",
        subtotal=Decimal("10.00"), discount=Decimal("0.00"), tax=Decimal("0.00"),
        total=Decimal("10.00"),
    ))
    db.commit()
    plain_id, kept_id = plain.id, kept.id

    result = service.sweep(db, biz)
    assert result["deleted"] == 1 and result["kept"] == 1
    assert db.query(FuneralCase).filter(FuneralCase.id == plain_id).count() == 0
    assert db.query(FuneralCase).filter(FuneralCase.id == kept_id).count() == 1


def test_settings_are_main_admin_only(client, auth_headers, test_data):
    body = {"archive_after_days": 30, "delete_archived_after_months": 24}
    assert client.put("/archive/settings", json=body,
                      headers=auth_headers(test_data["manager"])).status_code == 403
    r = client.put("/archive/settings", json=body, headers=auth_headers(test_data["main_admin"]))
    assert r.status_code == 200 and r.json()["delete_archived_after_months"] == 24
    got = client.get("/archive/settings", headers=auth_headers(test_data["manager"])).json()
    assert got["archive_after_days"] == 30 and got["can_change"] is False


def test_old_finished_orders_are_archived_and_old_read_notifications_removed(
    client, auth_headers, db, test_data
):
    from app.models.inventory import PurchaseOrder, Supplier
    from app.models.notification import Notification

    biz = db.get(Business, test_data["business_a"].id)
    supplier = Supplier(business_id=biz.id, name="S", email="s@x.test", is_active=True)
    db.add(supplier)
    db.commit()
    h = auth_headers(test_data["main_admin"])
    item = client.post("/inventory/items", headers=h, json={
        "sku": "C-1", "name": "Candles", "category": "other", "supplier_id": str(supplier.id),
        "reorder_level": "1", "reorder_quantity": "5", "opening_quantity": "4"}).json()
    old = PurchaseOrder(business_id=biz.id, item_id=item["id"], supplier_id=supplier.id,
                        number="PO-1", quantity=2, status="received", created_at=LONG_AGO)
    db.add(old)
    db.add(Notification(business_id=biz.id, user_id=test_data["manager"].id, kind="x", title="old",
                        read_at=datetime.now(timezone.utc) - timedelta(days=90)))
    db.add(Notification(business_id=biz.id, user_id=test_data["manager"].id, kind="x", title="new",
                        read_at=datetime.now(timezone.utc)))
    db.commit()
    result = service.sweep(db, biz)
    assert result["orders_archived"] == 1
    db.refresh(old)
    assert old.archived_at is not None
    assert [n.title for n in db.query(Notification).filter(Notification.kind == "x")] == ["new"]
    assert client.get("/inventory/orders", headers=h).json() == []
    assert len(client.get("/archive?kind=orders", headers=h).json()) == 1
