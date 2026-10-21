"""The finance dashboard feed."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.communication import CommunicationMessage
from app.models.membership_contribution import MembershipContribution
from tests.test_owner_overview import make_arrears
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


def get(client, auth_headers, user, **params):
    return client.get(
        "/finance/overview", params=params, headers=auth_headers(user)
    )


def test_money_this_month_and_today(client, db, test_data, auth_headers):
    biz = test_data["business_a"]
    case = make_case(db, biz, total="1000.00")
    make_payment(db, case, "400.00", on=TODAY)
    ms = make_membership(db, biz, make_member(db, biz), make_plan(db, biz))
    make_membership_payment(db, ms, "150.00", TODAY)

    body = get(client, auth_headers, test_data["main_admin"]).json()
    c = body["collected"]
    assert c["today"] == 550.0 and c["month"] == 550.0
    assert c["month_cases"] == 400.0 and c["month_memberships"] == 150.0


def test_due_soon_overdue_and_collection_rate(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    plan = make_plan(db, biz)

    def contribution(due, owed, paid, status):
        ms = make_membership(db, biz, make_member(db, biz), plan)
        db.add(MembershipContribution(
            business_id=biz.id, membership_id=ms.id,
            contribution_period=due.replace(day=1),
            amount_due=Decimal(owed), amount_paid=Decimal(paid),
            due_date=due, status=status,
        ))

    contribution(TODAY + timedelta(days=3), "100.00", "0.00", "due")
    contribution(TODAY + timedelta(days=30), "100.00", "0.00", "due")
    contribution(TODAY - timedelta(days=5), "200.00", "50.00",
                 "partially_paid")
    db.commit()

    k = get(client, auth_headers, test_data["main_admin"]).json()[
        "contributions"
    ]
    assert k["due_soon_count"] == 1 and k["due_soon_amount"] == 100.0
    assert k["overdue_count"] == 1 and k["overdue_amount"] == 150.0


def test_memberships_arrears_and_debtors(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    make_arrears(db, biz, 30, "250.00", "Late Payer")
    make_case(db, biz, total="900.00", paid="100.00")

    body = get(client, auth_headers, test_data["main_admin"]).json()
    assert body["memberships"]["in_arrears"] == 1
    assert body["arrears"]["rows"][0]["member_name"] == "Late Payer Member"
    assert body["arrears"]["total_unpaid"] == 250.0
    assert body["debtors"]["total_owed"] == 800.0
    assert len(body["trend"]) == 6


def test_recent_payments_mix_both_kinds_newest_first(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    case = make_case(db, biz, total="500.00")
    make_payment(db, case, "100.00", on=TODAY - timedelta(days=2))
    ms = make_membership(db, biz, make_member(db, biz), make_plan(db, biz))
    make_membership_payment(db, ms, "75.00", TODAY)

    rows = get(client, auth_headers, test_data["main_admin"]).json()[
        "recent_payments"
    ]
    assert [(r["kind"], r["amount"]) for r in rows] == [
        ("membership", 75.0), ("case", 100.0),
    ]


def test_queued_reminders_and_open_claims_are_counted(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    member = make_member(db, biz)
    db.add(CommunicationMessage(
        business_id=biz.id, member_id=member.id, kind="payment_overdue",
        channel="whatsapp", status="queued", body="Hi", recipient="0821110000",
    ))
    db.commit()

    body = get(client, auth_headers, test_data["main_admin"]).json()
    assert body["reminders_queued"] == 1
    assert body["claims_open"] == 0


def test_branch_filter_and_other_business(
    client, db, test_data, auth_headers
):
    make_payment(
        db, make_case(db, test_data["business_b"], total="900.00"),
        "900.00", on=TODAY,
    )
    body = get(client, auth_headers, test_data["main_admin"]).json()
    assert body["collected"]["month"] == 0.0
    r = get(client, auth_headers, test_data["main_admin"],
            branch_id="00000000-0000-0000-0000-000000000001")
    assert r.status_code == 200


def test_permission(client, db, test_data, auth_headers):
    deny(db, test_data["manager"], "financials.view")
    assert get(client, auth_headers, test_data["manager"]).status_code == 403
