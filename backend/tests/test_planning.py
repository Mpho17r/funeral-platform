"""Recurring items record themselves on schedule; budgets warn."""

from datetime import date, timedelta

from app.models.expense import Expense
from app.models.income import IncomeEntry
from app.models.notification import Notification
from app.services import planning
from tests.test_business_mode import go_general
from tests.test_sales import admin_h


def test_monthly_dates_keep_the_day_where_they_can():
    assert planning.advance(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert planning.advance(date(2026, 2, 28), "monthly", 31) == date(2026, 3, 31)
    assert planning.advance(date(2026, 12, 15), "monthly") == date(2027, 1, 15)
    assert planning.advance(date(2026, 1, 1), "weekly") == date(2026, 1, 8)
    assert planning.advance(date(2024, 2, 29), "yearly", 29) == date(2025, 2, 28)


def test_recurring_expense_catches_up_once_and_never_doubles(
    client, auth_headers, db, test_data
):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    start = date.today() - timedelta(days=70)

    r = client.post(
        "/planning/recurring",
        json={
            "kind": "expense",
            "category": "rent",
            "description": "Office rent",
            "amount": 1000,
            "frequency": "monthly",
            "start_date": start.isoformat(),
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    item = r.json()

    count = db.query(Expense).filter(Expense.category == "rent").count()
    assert count >= 2  # the missed months were recorded
    assert date.fromisoformat(item["next_date"]) > date.today()

    # Running again the same day adds nothing.
    assert planning.record_due(db) == 0
    assert db.query(Expense).filter(Expense.category == "rent").count() == count


def test_recurring_income_and_stop(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    r = client.post(
        "/planning/recurring",
        json={
            "kind": "income",
            "category": "services",
            "description": "Retainer",
            "amount": 500,
            "frequency": "weekly",
            "start_date": date.today().isoformat(),
        },
        headers=h,
    ).json()
    assert db.query(IncomeEntry).filter(IncomeEntry.category == "services").count() == 1

    assert client.patch(
        f"/planning/recurring/{r['id']}", json={"active": False}, headers=h
    ).json()["active"] is False
    planning.record_due(db, date.today() + timedelta(days=30))
    assert db.query(IncomeEntry).filter(IncomeEntry.category == "services").count() == 1


def test_budget_warns_then_says_over(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)

    assert client.put("/planning/budgets/supplies", json={"amount": 1000}, headers=h).status_code == 200
    today = date.today()

    def spend(amount):
        r = client.post(
            "/expenses",
            json={
                "category": "supplies",
                "description": "Stuff",
                "amount": amount,
                "expense_date": today.isoformat(),
                "payment_method": "cash",
            },
            headers=h,
        )
        assert r.status_code == 201, r.text

    spend(850)
    row = client.get("/planning/budgets", headers=h).json()["items"][0]
    assert row["state"] == "warning" and row["left"] == 150.0
    planning.budget_alerts(db)
    db.commit()
    assert db.query(Notification).filter(Notification.kind == "budget").count() >= 1

    spend(200)
    assert client.get("/planning/budgets", headers=h).json()["items"][0]["state"] == "over"

    # An alert is sent once per state, not on every run.
    planning.budget_alerts(db)
    before = db.query(Notification).filter(Notification.kind == "budget").count()
    planning.budget_alerts(db)
    assert db.query(Notification).filter(Notification.kind == "budget").count() == before

    # 0 removes it.
    client.put("/planning/budgets/supplies", json={"amount": 0}, headers=h)
    assert client.get("/planning/budgets", headers=h).json()["items"] == []


def test_bad_input_is_refused(client, auth_headers, db, test_data):
    go_general(db, test_data)
    h = admin_h(auth_headers, test_data)
    bad = {
        "kind": "expense", "category": "coffins_and_stock", "description": "x",
        "amount": 5, "frequency": "monthly", "start_date": date.today().isoformat(),
    }
    assert client.post("/planning/recurring", json=bad, headers=h).status_code == 422
    assert client.put("/planning/budgets/nonsense", json={"amount": 5}, headers=h).status_code == 422
