"""Importing payment history from the old system."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.models.membership_plan import MembershipPlan

HEADER = (
    "membership_number,payment_date,amount,payment_method,reference,month,notes\n"
)


def upload(client, headers, text, path="/imports/payments/check"):
    return client.post(
        path,
        headers=headers,
        files={"file": ("pay.csv", text.encode(), "text/csv")},
    )


def setup_policy(db, test_data, number="P1", status="active"):
    biz = test_data["business_a"]
    plan = MembershipPlan(
        business_id=biz.id, name="Plan", monthly_contribution=Decimal("100"),
        is_active=True,
    )
    member = Member(
        business_id=biz.id, member_number="M" + number,
        first_name="A", last_name="B",
    )
    db.add_all([plan, member])
    db.flush()
    ms = Membership(
        business_id=biz.id, member_id=member.id, plan_id=plan.id,
        membership_number=number, start_date=date(2025, 1, 1),
        status=status,
    )
    db.add(ms)
    db.commit()
    return ms


def admin(test_data, auth_headers):
    return auth_headers(test_data["main_admin"])


def test_template_downloads(client, test_data, auth_headers):
    r = client.get(
        "/imports/payments/template", headers=admin(test_data, auth_headers)
    )
    assert r.status_code == 200 and r.text.startswith("membership_number")


def test_check_saves_nothing(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    body = upload(
        client, admin(test_data, auth_headers),
        HEADER + "P1,2025-02-01,100,eft,R1,2025-02,\n",
    ).json()
    assert body["ready"] == 1 and body["total_amount"] == "100.00"
    assert db.query(MembershipPayment).count() == 0


def test_import_applies_payment_to_month(client, db, test_data, auth_headers):
    ms = setup_policy(db, test_data)
    r = upload(
        client, admin(test_data, auth_headers),
        HEADER + "P1,2025-02-03,100,EFT,R1,2025-02,paid late\n",
        "/imports/payments",
    )
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1 and r.json()["months_created"] == 1

    c = db.query(MembershipContribution).one()
    assert c.status == "paid" and c.amount_paid == Decimal("100.00")
    assert c.paid_at == date(2025, 2, 3)  # the day it was paid, not today
    p = db.query(MembershipPayment).one()
    assert p.payment_method == "eft" and p.contribution_id == c.id


def test_partial_payments_add_up_then_overpay_rejected(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    csv = HEADER + (
        "P1,2025-02-01,60,cash,A,2025-02,\n"
        "P1,2025-02-10,40,cash,B,2025-02,\n"
        "P1,2025-02-15,10,cash,C,2025-02,\n"
    )
    body = upload(
        client, admin(test_data, auth_headers), csv, "/imports/payments"
    ).json()
    assert body["imported"] == 2 and body["skipped"] == 1
    assert "overpay" in body["rows"][2]["errors"][0]
    assert db.query(MembershipContribution).one().status == "paid"


def test_unpaid_old_month_puts_policy_in_arrears(
    client, db, test_data, auth_headers
):
    ms = setup_policy(db, test_data)
    long_ago = (date.today() - timedelta(days=20)).replace(day=1)
    # Part-paid month that is already past due.
    upload(
        client, admin(test_data, auth_headers),
        HEADER + f"P1,{long_ago},30,cash,A,{long_ago:%Y-%m},\n",
        "/imports/payments",
    )
    db.refresh(ms)
    assert ms.status in ("arrears", "lapsed")
    assert ms.arrears_since == long_ago


def test_paid_month_keeps_policy_active(client, db, test_data, auth_headers):
    ms = setup_policy(db, test_data)
    month = date.today().replace(day=1) - timedelta(days=40)
    month = month.replace(day=1)
    upload(
        client, admin(test_data, auth_headers),
        HEADER + f"P1,{month},100,cash,A,{month:%Y-%m},\n",
        "/imports/payments",
    )
    db.refresh(ms)
    assert ms.status == "active"


def test_unknown_membership_bad_values_and_future_date(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    future = date.today() + timedelta(days=5)
    csv = HEADER + (
        "NOPE,2025-02-01,100,cash,,2025-02,\n"
        "P1,not-a-date,100,cash,,2025-02,\n"
        "P1,2025-02-01,abc,cash,,2025-02,\n"
        "P1,2025-02-01,-5,cash,,2025-02,\n"
        "P1,2025-02-01,10.505,cash,,2025-02,\n"
        f"P1,{future},10,cash,,2025-02,\n"
        "P1,2025-02-01,10,cash,,2025-13,\n"
    )
    rows = upload(client, admin(test_data, auth_headers), csv).json()["rows"]
    assert len(rows) == 7 and not any(r["ok"] for r in rows)
    assert "No membership numbered" in rows[0]["errors"][0]
    assert "future" in rows[5]["errors"][0]


def test_amount_formats_and_method_words(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    csv = HEADER + (
        'P1,2025-02-01,"R 100,00",debit order,A,2025-02,\n'
        "P1,2025-03-01,100,Mystery,B,2025-03,\n"
        "P1,2025-04-01,100,,C,,\n"
    )
    body = upload(
        client, admin(test_data, auth_headers), csv, "/imports/payments"
    ).json()
    assert body["imported"] == 3
    methods = {
        p.reference: p.payment_method for p in db.query(MembershipPayment)
    }
    assert methods == {"A": "debit_order", "B": "other", "C": "other"}
    assert any("not applied" in w for w in body["rows"][2]["warnings"])


def test_reupload_is_safe_by_reference_and_by_triple(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    csv = HEADER + (
        "P1,2025-02-01,100,cash,R1,2025-02,\n"
        "P1,2025-03-01,100,cash,,2025-03,\n"
    )
    assert upload(client, h, csv, "/imports/payments").json()["imported"] == 2
    again = upload(client, h, csv, "/imports/payments").json()
    assert again["imported"] == 0 and again["skipped"] == 2
    assert db.query(MembershipPayment).count() == 2


def test_duplicates_within_the_file(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    csv = HEADER + (
        "P1,2025-02-01,50,cash,R1,2025-02,\n"
        "P1,2025-02-02,50,cash,R1,2025-02,\n"
        "P1,2025-03-01,50,cash,,,\n"
        "P1,2025-03-01,50,cash,,,\n"
    )
    rows = upload(client, admin(test_data, auth_headers), csv).json()["rows"]
    assert [r["ok"] for r in rows] == [True, False, True, False]


def test_bad_files_rejected(client, test_data, auth_headers):
    h = admin(test_data, auth_headers)
    assert upload(client, h, "amount\n1\n").status_code == 400
    assert upload(client, h, HEADER).status_code == 400
    assert upload(client, h, "").status_code == 400


def test_other_business_policy_is_not_matched(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    rows = upload(
        client, auth_headers(test_data["other_business_manager"]),
        HEADER + "P1,2025-02-01,100,cash,,2025-02,\n",
    ).json()["rows"]
    assert "No membership numbered" in rows[0]["errors"][0]


def test_permission_and_audit(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    csv = HEADER + "P1,2025-02-01,100,cash,R1,2025-02,\n"
    assert upload(
        client, auth_headers(test_data["staff"]), csv
    ).status_code == 403

    upload(client, auth_headers(test_data["manager"]), csv, "/imports/payments")
    log = db.query(AuditLog).filter_by(action="import.payments").one()
    assert log.details["payments_created"] == 1
    assert log.details["total_amount"] == "100.00"
