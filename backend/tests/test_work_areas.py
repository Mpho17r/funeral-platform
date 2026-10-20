"""Job-focused roles: mortuary, finance and operations see only their work."""

import pytest

from app.models.user import User
from app.security import hash_password
from app.services.permission_seed import sync_permission_system
from tests.test_reports import deny, make_case, make_payment, make_plan, make_member, make_membership


@pytest.fixture
def seeded(db):
    sync_permission_system(db)


def worker(db, test_data, role, email):
    user = User(
        business_id=test_data["business_a"].id,
        full_name=f"{role.title()} Worker",
        email=email,
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def access(client, auth_headers, user):
    r = client.get("/users/me/access", headers=auth_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


def test_each_role_reports_its_work_area(
    client, db, test_data, auth_headers, seeded
):
    for role in ("mortuary", "finance", "operations"):
        user = worker(db, test_data, role, f"{role}@example.com")
        body = access(client, auth_headers, user)
        assert body["role"] == role and body["work_area"] == role

    assert access(client, auth_headers, test_data["staff"])["work_area"] == "general"
    assert access(client, auth_headers, test_data["manager"])["work_area"] == "general"


def test_access_lists_role_permissions_with_overrides(
    client, db, test_data, auth_headers, seeded
):
    user = worker(db, test_data, "mortuary", "m@example.com")
    perms = access(client, auth_headers, user)["permissions"]
    assert "mortuary.manage" in perms
    assert "payments.view" not in perms and "financials.view" not in perms

    deny(db, user, "mortuary.manage")
    assert "mortuary.manage" not in access(client, auth_headers, user)["permissions"]


def test_main_admin_holds_everything(client, test_data, auth_headers, seeded):
    perms = access(client, auth_headers, test_data["main_admin"])["permissions"]
    assert "financials.view" in perms and "audit.view" in perms


def test_mortuary_worker_is_locked_out_of_money_and_membership(
    client, db, test_data, auth_headers, seeded
):
    user = worker(db, test_data, "mortuary", "m@example.com")
    h = auth_headers(user)

    for path in ("/membership-payments", "/membership-contributions", "/memberships",
                 "/reports/financial", "/reports/overview?date_from=2026-01-01&date_to=2026-01-31",
                 "/reports/debtors", "/audit-logs", "/users"):
        assert client.get(path, headers=h).status_code == 403, path

    assert client.get("/mortuary/board", headers=h).status_code == 200


def test_finance_worker_cannot_touch_mortuary(
    client, db, test_data, auth_headers, seeded
):
    user = worker(db, test_data, "finance", "f@example.com")
    h = auth_headers(user)

    assert client.get("/mortuary/board", headers=h).status_code == 403
    assert client.get("/reports/arrears", headers=h).status_code == 200
    assert client.get("/memberships", headers=h).status_code == 200


def test_operations_worker_opens_cases_but_not_finance(
    client, db, test_data, auth_headers, seeded
):
    user = worker(db, test_data, "operations", "o@example.com")
    h = auth_headers(user)

    assert client.get("/cases", headers=h).status_code == 200
    for path in ("/membership-payments", "/reports/financial", "/membership-contributions"):
        assert client.get(path, headers=h).status_code == 403, path


def test_dashboard_money_only_for_people_with_financial_access(
    client, db, test_data, auth_headers, seeded
):
    biz = test_data["business_a"]
    make_case(db, biz, total="900.00", paid="300.00")

    ops = worker(db, test_data, "operations", "o@example.com")
    body = client.get("/dashboard/summary", headers=auth_headers(ops)).json()
    for key in ("outstanding_balance", "total_revenue", "amount_paid", "total_credit"):
        assert body[key] is None
    assert body["total_cases"] == 1

    fin = worker(db, test_data, "finance", "f@example.com")
    body = client.get("/dashboard/summary", headers=auth_headers(fin)).json()
    assert float(body["total_revenue"]) == 900.0
    assert float(body["amount_paid"]) == 300.0


def test_manager_can_create_work_area_users_staff_cannot(
    client, db, test_data, auth_headers, seeded
):
    payload = {
        "full_name": "New Mortuary", "email": "newm@example.com",
        "password": "StrongPass123!", "role": "mortuary",
    }
    r = client.post("/users", json=payload, headers=auth_headers(test_data["manager"]))
    assert r.status_code in (200, 201), r.text
    assert r.json()["role"] == "mortuary"

    r = client.post("/users", json={**payload, "email": "x@example.com"},
                    headers=auth_headers(test_data["staff"]))
    assert r.status_code == 403


def test_manager_cannot_create_another_manager(
    client, db, test_data, auth_headers, seeded
):
    r = client.post(
        "/users",
        json={"full_name": "M2", "email": "m2@example.com",
              "password": "StrongPass123!", "role": "manager"},
        headers=auth_headers(test_data["manager"]),
    )
    assert r.status_code == 403


def test_case_summary_hides_money_from_mortuary_but_not_finance(
    client, db, test_data, auth_headers, seeded
):
    case = make_case(db, test_data["business_a"], total="900.00", paid="300.00")
    make_payment(db, case, "300.00")

    mort = worker(db, test_data, "mortuary", "m@example.com")
    body = client.get(f"/cases/{case.id}/summary", headers=auth_headers(mort)).json()
    assert body["financial"] is None
    assert body["payments"]["amount_paid"] is None

    fin = worker(db, test_data, "finance", "f@example.com")
    body = client.get(f"/cases/{case.id}/summary", headers=auth_headers(fin)).json()
    assert float(body["financial"]["total"]) == 900.0
    assert float(body["payments"]["amount_paid"]) == 300.0
