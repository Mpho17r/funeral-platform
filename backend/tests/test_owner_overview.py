"""The owner's overview, arrears and debtors lists, and their CSVs."""

from datetime import date, timedelta
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.membership_contribution import MembershipContribution
from app.services.owner_summary import previous_period
from tests.test_reports import (
    deny,
    get,
    make_branch,
    make_case,
    make_member,
    make_membership,
    make_membership_payment,
    make_payment,
    make_plan,
)

TODAY = date.today()
MONTH_START = TODAY.replace(day=1)


def overview(client, auth_headers, user, **extra):
    params = {
        "date_from": MONTH_START.isoformat(),
        "date_to": TODAY.isoformat(),
        **extra,
    }
    return get(client, auth_headers, user, "overview", **params)


# ---- periods ----------------------------------------------------------

def test_a_whole_month_compares_with_the_whole_month_before():
    assert previous_period(date(2026, 3, 1), date(2026, 3, 31)) == (
        date(2026, 2, 1), date(2026, 2, 28),
    )
    assert previous_period(date(2026, 1, 1), date(2026, 1, 31)) == (
        date(2025, 12, 1), date(2025, 12, 31),
    )


def test_other_ranges_compare_with_the_equal_stretch_before():
    assert previous_period(date(2026, 3, 10), date(2026, 3, 19)) == (
        date(2026, 2, 28), date(2026, 3, 9),
    )


# ---- overview ---------------------------------------------------------

def test_collected_adds_case_and_membership_money(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    case = make_case(db, biz, total="1000.00")
    make_payment(db, case, "400.00", on=TODAY)

    member = make_member(db, biz)
    ms = make_membership(db, biz, member, make_plan(db, biz))
    make_membership_payment(db, ms, "150.00", TODAY)

    body = overview(client, auth_headers, test_data["main_admin"]).json()
    cur = body["current"]
    assert cur["collected_cases"] == 400.00
    assert cur["collected_memberships"] == 150.00
    assert cur["collected"] == 550.00
    assert cur["cases_opened"] == 1


def test_previous_period_is_reported_beside_the_current(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    case = make_case(db, biz, total="500.00")
    before = MONTH_START - timedelta(days=3)
    make_payment(db, case, "200.00", on=before)

    body = overview(client, auth_headers, test_data["main_admin"]).json()
    assert body["current"]["collected"] == 0.00
    assert body["previous"]["collected"] == 200.00
    assert body["previous_to"] == (MONTH_START - timedelta(days=1)).isoformat()


def test_members_funerals_lapses_and_cancellations(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    plan = make_plan(db, biz)

    joined = make_member(db, biz)
    joined.join_date = TODAY
    old = make_member(db, biz)  # joined in January, not this month
    lapsed = make_membership(db, biz, make_member(db, biz), plan)
    lapsed.status, lapsed.lapsed_at = "lapsed", TODAY
    gone = make_membership(db, biz, make_member(db, biz), plan)
    gone.status, gone.cancelled_at = "cancelled", TODAY
    make_case(db, biz, funeral_date=TODAY)
    db.commit()

    cur = overview(client, auth_headers, test_data["main_admin"]).json()["current"]
    assert cur["new_members"] == 1
    assert cur["memberships_lapsed"] == 1
    assert cur["memberships_cancelled"] == 1
    assert cur["funerals_held"] == 1


def test_trend_is_six_months_oldest_first_and_counts_this_month(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    case = make_case(db, biz, total="100.00")
    make_payment(db, case, "100.00", on=TODAY)

    trend = overview(client, auth_headers, test_data["main_admin"]).json()["trend"]
    assert len(trend) == 6
    months = [t["month"] for t in trend]
    assert months == sorted(months)
    assert trend[-1]["month"] == MONTH_START.isoformat()
    assert trend[-1]["collected"] == 100.00
    assert trend[-1]["cases_opened"] == 1


def test_now_snapshot_counts_current_state(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    plan = make_plan(db, biz)
    make_membership(db, biz, make_member(db, biz), plan)
    make_membership(db, biz, make_member(db, biz), plan, status="arrears")
    make_membership(db, biz, make_member(db, biz), plan, status="lapsed")
    make_case(db, biz, total="900.00", paid="100.00")

    now = overview(client, auth_headers, test_data["main_admin"]).json()["now"]
    assert now["active_memberships"] == 1
    assert now["memberships_in_arrears"] == 1
    assert now["memberships_lapsed"] == 1
    assert now["outstanding"] == 800.00
    assert now["cases_with_balance"] == 1


def test_branch_filter_narrows_the_overview(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    one = make_branch(db, biz, "One", "ONE", main=True)
    two = make_branch(db, biz, "Two", "TWO")
    make_payment(db, make_case(db, biz, one, total="100.00"), "100.00", on=TODAY)
    make_payment(db, make_case(db, biz, two, total="300.00"), "300.00", on=TODAY)

    body = overview(
        client, auth_headers, test_data["main_admin"], branch_id=str(two.id)
    ).json()
    assert body["current"]["collected"] == 300.00
    assert body["current"]["cases_opened"] == 1


def test_overview_rejects_bad_requests(client, db, test_data, auth_headers):
    admin = test_data["main_admin"]
    r = get(client, auth_headers, admin, "overview",
            date_from="2026-05-02", date_to="2026-05-01")
    assert r.status_code == 422
    r = get(client, auth_headers, admin, "overview",
            date_from="2024-01-01", date_to="2026-01-01")
    assert r.status_code == 422
    assert get(client, auth_headers, admin, "overview").status_code == 422
    r = overview(client, auth_headers, admin,
                 branch_id="00000000-0000-0000-0000-000000000001")
    assert r.status_code == 404


def test_other_businesses_and_permission(client, db, test_data, auth_headers):
    make_payment(
        db, make_case(db, test_data["business_b"], total="900.00"),
        "900.00", on=TODAY,
    )
    manager = test_data["manager"]
    body = overview(client, auth_headers, manager).json()
    assert body["current"]["collected"] == 0.00
    assert body["now"]["outstanding"] == 0.00

    deny(db, manager, "reports.view")
    assert overview(client, auth_headers, manager).status_code == 403


# ---- arrears ----------------------------------------------------------

def make_arrears(db, biz, days, unpaid, name="Late Payer"):
    member = make_member(db, biz)
    member.first_name, member.last_name = name, "Member"
    ms = make_membership(
        db, biz, member, make_plan(db, biz), status="arrears"
    )
    ms.arrears_since = TODAY - timedelta(days=days)
    db.add(
        MembershipContribution(
            business_id=biz.id, membership_id=ms.id,
            contribution_period=ms.arrears_since.replace(day=1),
            amount_due=Decimal(unpaid), amount_paid=Decimal("0.00"),
            due_date=ms.arrears_since, status="overdue",
        )
    )
    db.commit()
    return ms


def test_arrears_list_longest_first_with_days_until_lapse(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    biz.lapse_after_days = 60
    db.commit()
    make_arrears(db, biz, 10, "100.00", "Recent")
    make_arrears(db, biz, 45, "250.00", "Longest")

    body = get(client, auth_headers, test_data["manager"], "arrears").json()
    assert body["total"] == 2 and body["total_unpaid"] == 350.00
    first = body["rows"][0]
    assert first["member_name"] == "Longest Member"
    assert first["days_in_arrears"] == 45
    assert first["days_until_lapse"] == 15
    assert first["amount_unpaid"] == 250.00


def test_arrears_excludes_active_and_archived_members(
    client, db, test_data, auth_headers
):
    from datetime import datetime, timezone

    biz = test_data["business_a"]
    ms = make_arrears(db, biz, 20, "100.00")
    from app.models.member import Member
    db.get(Member, ms.member_id).archived_at = datetime.now(timezone.utc)
    make_membership(db, biz, make_member(db, biz), make_plan(db, biz))
    db.commit()

    body = get(client, auth_headers, test_data["manager"], "arrears").json()
    assert body["total"] == 0


# ---- debtors ----------------------------------------------------------

def test_debtors_biggest_balance_first_excluding_cancelled(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    make_case(db, biz, total="300.00", paid="100.00")
    make_case(db, biz, total="900.00", paid="0.00")
    make_case(db, biz, total="500.00", paid="500.00")
    make_case(db, biz, total="700.00", status="cancelled")
    make_case(db, biz, total="800.00", archived=True)

    body = get(client, auth_headers, test_data["manager"], "debtors").json()
    assert [r["balance"] for r in body["rows"]] == [900.0, 200.0]
    assert body["total_owed"] == 1100.00


# ---- csv --------------------------------------------------------------

def test_csv_downloads_neutralise_formulas_and_are_audited(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    ms = make_arrears(db, biz, 12, "100.00", "=HYPERLINK(evil)")

    r = get(client, auth_headers, test_data["manager"], "arrears.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("Member,Membership number")
    assert "'=HYPERLINK(evil)" in lines[1]
    assert ",=HYPERLINK" not in lines[1] and not lines[1].startswith("=")

    make_case(db, biz, total="500.00")
    r = get(client, auth_headers, test_data["manager"], "debtors.csv")
    assert r.status_code == 200 and "500.00" in r.text

    logs = db.query(AuditLog).filter_by(action="report.exported").all()
    assert {l.details["report"] for l in logs} == {"arrears", "debtors"}


def test_lists_need_permission(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    deny(db, manager, "reports.view")
    for path in ("arrears", "debtors", "arrears.csv", "debtors.csv"):
        assert get(client, auth_headers, manager, path).status_code == 403
