"""Expenses and daily reconciliation."""

from datetime import date, timedelta

from app.models.audit_log import AuditLog
from tests.test_reports import (
    deny,
    make_case,
    make_member,
    make_membership,
    make_membership_payment,
    make_payment,
    make_plan,
)

TODAY = date.today()


def add_expense(client, auth_headers, user, **over):
    body = {
        "category": "transport_and_fuel",
        "description": "Hearse diesel",
        "amount": "850.00",
        "expense_date": TODAY.isoformat(),
        "payment_method": "cash",
    }
    body.update(over)
    return client.post("/expenses", json=body, headers=auth_headers(user))


def test_record_list_and_summary(client, auth_headers, test_data):
    admin = test_data["main_admin"]
    assert add_expense(client, auth_headers, admin).status_code == 201
    add_expense(client, auth_headers, admin, category="staff",
                description="Casual labour", amount="300.00")

    listing = client.get("/expenses", headers=auth_headers(admin)).json()
    assert listing["total"] == 1150.0 and len(listing["items"]) == 2

    summary = client.get(
        "/expenses/summary", headers=auth_headers(admin)
    ).json()
    assert summary["today"] == 1150.0 and summary["month"] == 1150.0
    assert summary["by_category"][0]["category"] == "transport_and_fuel"
    assert len(summary["trend"]) == 6


def test_validation(client, auth_headers, test_data):
    admin = test_data["main_admin"]
    assert add_expense(client, auth_headers, admin,
                       category="nonsense").status_code == 422
    assert add_expense(client, auth_headers, admin,
                       amount="0").status_code == 422
    assert add_expense(client, auth_headers, admin,
                       payment_method="bitcoin").status_code == 422


def test_link_to_case_filters_and_checks_tenant(
    client, db, auth_headers, test_data
):
    admin = test_data["main_admin"]
    case = make_case(db, test_data["business_a"], total="1000.00")
    other = make_case(db, test_data["business_b"], total="1000.00")

    ok = add_expense(client, auth_headers, admin, case_id=str(case.id))
    assert ok.status_code == 201
    add_expense(client, auth_headers, admin)

    bad = add_expense(client, auth_headers, admin, case_id=str(other.id))
    assert bad.status_code == 404

    only = client.get(
        "/expenses", params={"case_id": str(case.id)},
        headers=auth_headers(admin),
    ).json()
    assert len(only["items"]) == 1


def test_edit_is_audited_and_void_keeps_history(
    client, db, auth_headers, test_data
):
    admin = test_data["main_admin"]
    expense = add_expense(client, auth_headers, admin).json()

    edited = client.patch(
        f"/expenses/{expense['id']}", json={"amount": "900.00"},
        headers=auth_headers(admin),
    )
    assert edited.status_code == 200 and edited.json()["amount"] == 900.0

    short = client.post(
        f"/expenses/{expense['id']}/void", json={"reason": "x"},
        headers=auth_headers(admin),
    )
    assert short.status_code == 422

    voided = client.post(
        f"/expenses/{expense['id']}/void",
        json={"reason": "Entered twice"}, headers=auth_headers(admin),
    )
    assert voided.status_code == 200 and voided.json()["status"] == "voided"

    again = client.post(
        f"/expenses/{expense['id']}/void",
        json={"reason": "Entered twice"}, headers=auth_headers(admin),
    )
    assert again.status_code == 409
    assert client.patch(
        f"/expenses/{expense['id']}", json={"amount": "1.00"},
        headers=auth_headers(admin),
    ).status_code == 409

    hidden = client.get("/expenses", headers=auth_headers(admin)).json()
    assert hidden["items"] == [] and hidden["total"] == 0
    shown = client.get(
        "/expenses", params={"include_voided": True},
        headers=auth_headers(admin),
    ).json()
    assert len(shown["items"]) == 1

    actions = {
        a.action for a in db.query(AuditLog).filter(
            AuditLog.entity_id == expense["id"]
        )
    }
    assert {"expense.created", "expense.updated", "expense.voided"} <= actions


def test_permissions(client, db, auth_headers, test_data):
    staff = test_data["staff"]
    manager = test_data["manager"]

    assert client.get("/expenses", headers=auth_headers(staff)).status_code == 403
    assert client.get(
        "/reconciliation", headers=auth_headers(staff)
    ).status_code == 403
    assert add_expense(client, auth_headers, staff).status_code == 403

    assert client.get("/expenses", headers=auth_headers(manager)).status_code == 200
    deny(db, manager, "expenses.manage")
    assert add_expense(client, auth_headers, manager).status_code == 403


def test_reconciliation_expected_counts_receipts_minus_expenses(
    client, db, auth_headers, test_data
):
    admin = test_data["main_admin"]
    biz = test_data["business_a"]
    case = make_case(db, biz, total="2000.00")
    make_payment(db, case, "1000.00", on=TODAY)
    ms = make_membership(db, biz, make_member(db, biz), make_plan(db, biz))
    make_membership_payment(db, ms, "200.00", TODAY)
    add_expense(client, auth_headers, admin, amount="300.00")

    body = client.get("/reconciliation", headers=auth_headers(admin)).json()
    cash = next(m for m in body["methods"] if m["payment_method"] == "cash")
    assert cash["receipts"] == 1200.0
    assert cash["expenses"] == 300.0
    assert cash["expected"] == 900.0 and cash["record"] is None
    assert body["open_days"][0]["open"] == 1


def reconcile(client, auth_headers, user, counted, notes=None, day=None):
    return client.post(
        "/reconciliation",
        json={
            "recon_date": (day or TODAY).isoformat(),
            "payment_method": "cash",
            "counted_amount": counted,
            "notes": notes,
        },
        headers=auth_headers(user),
    )


def test_reconcile_exact_difference_and_note_rule(
    client, db, auth_headers, test_data
):
    admin = test_data["main_admin"]
    case = make_case(db, test_data["business_a"], total="2000.00")
    make_payment(db, case, "500.00", on=TODAY)

    short = reconcile(client, auth_headers, admin, "480.00")
    assert short.status_code == 422

    short = reconcile(client, auth_headers, admin, "480.00",
                      notes="R20 float given as change")
    assert short.status_code == 200
    cash = short.json()["methods"][0]
    assert cash["record"]["variance"] == -20.0

    exact = reconcile(client, auth_headers, admin, "500.00")
    assert exact.status_code == 200
    assert exact.json()["methods"][0]["record"]["variance"] == 0.0

    hist = client.get(
        "/reconciliation/history", headers=auth_headers(admin)
    ).json()["items"]
    assert len(hist) == 1  # same day and method: updated, not duplicated

    after = client.get("/reconciliation", headers=auth_headers(admin)).json()
    assert after["open_days"] == []


def test_late_payment_flags_needs_review(client, db, auth_headers, test_data):
    admin = test_data["main_admin"]
    case = make_case(db, test_data["business_a"], total="2000.00")
    make_payment(db, case, "500.00", on=TODAY)
    reconcile(client, auth_headers, admin, "500.00")

    make_payment(db, case, "100.00", on=TODAY)

    body = client.get("/reconciliation", headers=auth_headers(admin)).json()
    assert body["methods"][0]["record"]["needs_review"] is True
    assert body["open_days"][0]["needs_review"] == 1


def test_future_day_refused_and_old_days_listed(
    client, db, auth_headers, test_data
):
    admin = test_data["main_admin"]
    tomorrow = TODAY + timedelta(days=1)
    assert reconcile(client, auth_headers, admin, "0.00",
                     day=tomorrow).status_code == 422

    case = make_case(db, test_data["business_a"], total="2000.00")
    make_payment(db, case, "250.00", on=TODAY - timedelta(days=3))
    body = client.get("/reconciliation", headers=auth_headers(admin)).json()
    assert body["open_days"][0]["date"] == (
        TODAY - timedelta(days=3)
    ).isoformat()


def test_voided_expense_leaves_expected(client, db, auth_headers, test_data):
    admin = test_data["main_admin"]
    expense = add_expense(client, auth_headers, admin, amount="400.00").json()
    client.post(
        f"/expenses/{expense['id']}/void", json={"reason": "Wrong day"},
        headers=auth_headers(admin),
    )
    body = client.get("/reconciliation", headers=auth_headers(admin)).json()
    assert body["methods"] == []
