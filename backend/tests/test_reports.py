import uuid

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.branch import Branch
from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_claim import MembershipClaim
from app.models.membership_payment import MembershipPayment
from app.models.membership_plan import MembershipPlan
from app.models.permission import Permission
from app.models.user_permission import UserPermission


# ============================================================
# HELPERS
# ============================================================

def make_branch(db, business, name, code, *, main=False):
    branch = Branch(
        business_id=business.id,
        name=name,
        code=code,
        is_main=main,
        is_active=True,
    )
    db.add(branch)
    db.commit()

    return branch


def make_case(
    db,
    business,
    branch=None,
    *,
    status="open",
    total="0.00",
    paid="0.00",
    created_days_ago=0,
    funeral_date=None,
    archived=False,
    membership=None,
):
    created = datetime.now(timezone.utc) - timedelta(
        days=created_days_ago
    )

    case = FuneralCase(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        membership_id=membership.id if membership else None,
        case_number=f"RP-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Private Name",
        status=status,
        funeral_date=funeral_date,
        is_archived=archived,
        created_at=created,
    )
    db.add(case)
    db.flush()

    total = Decimal(total)
    paid = Decimal(paid)

    db.add(
        CaseFinancial(
            business_id=business.id,
            case_id=case.id,
            total=total,
            subtotal=total,
            amount_paid=paid,
            balance=max(total - paid, Decimal("0.00")),
        )
    )
    db.commit()

    return case


def make_payment(
    db,
    case,
    amount,
    *,
    method="cash",
    on=date(2026, 10, 5),
):
    payment = CasePayment(
        business_id=case.business_id,
        case_id=case.id,
        amount=Decimal(amount),
        payment_method=method,
        payment_date=on,
    )
    db.add(payment)
    db.commit()

    return payment


def make_plan(db, business):
    plan = MembershipPlan(
        business_id=business.id,
        name=f"Plan {uuid.uuid4().hex[:6]}",
        monthly_contribution=Decimal("100.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()

    return plan


def make_member(db, business, branch=None, *, status="active"):
    member = Member(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        member_number=f"M-{uuid.uuid4().hex[:8].upper()}",
        first_name="Report",
        last_name="Member",
        join_date=date(2026, 1, 1),
        status=status,
    )
    db.add(member)
    db.commit()

    return member


def make_membership(db, business, member, plan, *, status="active"):
    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"MS-{uuid.uuid4().hex[:8].upper()}",
        start_date=date(2026, 1, 1),
        status=status,
    )
    db.add(membership)
    db.commit()

    return membership


def make_membership_payment(db, membership, amount, on):
    payment = MembershipPayment(
        business_id=membership.business_id,
        membership_id=membership.id,
        amount=Decimal(amount),
        payment_method="cash",
        payment_date=on,
    )
    db.add(payment)
    db.commit()

    return payment


def make_claim(db, membership, case, *, status, claimed, approved=None):
    claim = MembershipClaim(
        business_id=membership.business_id,
        claim_number=f"CL-{uuid.uuid4().hex[:8].upper()}",
        membership_id=membership.id,
        case_id=case.id,
        status=status,
        claimed_amount=Decimal(claimed),
        approved_amount=(
            Decimal(approved) if approved is not None else None
        ),
    )
    db.add(claim)
    db.commit()

    return claim


def deny(db, user, key):
    permission = (
        db.query(Permission).filter(Permission.key == key).first()
    )
    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()


def get(client, auth_headers, user, path, **params):
    return client.get(
        f"/reports/{path}",
        params=params,
        headers=auth_headers(user),
    )


# ============================================================
# CASES
# ============================================================

def test_cases_report_counts_by_status_and_branch(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business, "Soweto", "SWT")

    make_case(db, business, main, status="open")
    make_case(db, business, main, status="open")
    make_case(db, business, other, status="completed")
    make_case(db, business, None, status="open")

    response = get(client, auth_headers, test_data["manager"], "cases")

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["total_cases"] == 4
    assert data["from_membership"] == 0
    assert data["walk_in"] == 4
    assert {s["status"]: s["count"] for s in data["by_status"]} == {
        "open": 3,
        "completed": 1,
    }

    by_branch = {
        row["branch_name"]: row["cases"] for row in data["by_branch"]
    }
    assert by_branch == {"Main": 2, "Soweto": 1, "No branch": 1}
    assert data["by_branch"][-1]["branch_name"] == "No branch"


def test_cases_report_excludes_archived_cases(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]

    make_case(db, business, status="open")
    make_case(db, business, status="open", archived=True)

    data = get(
        client, auth_headers, test_data["manager"], "cases"
    ).json()

    assert data["total_cases"] == 1


def test_cases_report_period_and_funerals_held(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]

    make_case(db, business, created_days_ago=0, funeral_date=date(2026, 10, 5))
    make_case(db, business, created_days_ago=60, funeral_date=date(2026, 8, 5))

    today = datetime.now(timezone.utc).date()

    recent = get(
        client,
        auth_headers,
        test_data["manager"],
        "cases",
        date_from=(today - timedelta(days=7)).isoformat(),
        date_to=today.isoformat(),
    ).json()

    assert recent["total_cases"] == 1

    held = get(
        client,
        auth_headers,
        test_data["manager"],
        "cases",
        date_from="2026-08-01",
        date_to="2026-08-31",
    ).json()

    assert held["funerals_held"] == 1


def test_cases_report_splits_membership_and_walk_in(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    member = make_member(db, business)
    membership = make_membership(
        db, business, member, make_plan(db, business)
    )

    make_case(db, business, membership=membership)
    make_case(db, business)

    data = get(
        client, auth_headers, test_data["manager"], "cases"
    ).json()

    assert data["from_membership"] == 1
    assert data["walk_in"] == 1


def test_branch_filter_narrows_cases(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business, "Soweto", "SWT")

    make_case(db, business, main)
    make_case(db, business, other)
    make_case(db, business, other)

    data = get(
        client,
        auth_headers,
        test_data["manager"],
        "cases",
        branch_id=str(other.id),
    ).json()

    assert data["total_cases"] == 2
    assert [r["branch_name"] for r in data["by_branch"]] == ["Soweto"]


# ============================================================
# FINANCIAL
# ============================================================

def test_financial_report_billed_collected_outstanding(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]

    first = make_case(db, business, total="1000.00", paid="400.00")
    second = make_case(db, business, total="500.00", paid="500.00")

    make_payment(db, first, "400.00", method="cash")
    make_payment(db, second, "300.00", method="eft")
    make_payment(db, second, "200.00", method="cash")

    data = get(
        client, auth_headers, test_data["manager"], "financial"
    ).json()

    assert Decimal(data["billed"]) == Decimal("1500.00")
    assert Decimal(data["collected"]) == Decimal("900.00")
    assert Decimal(data["outstanding"]) == Decimal("600.00")
    assert data["cases_with_balance"] == 1

    methods = {
        m["payment_method"]: (Decimal(m["amount"]), m["payments"])
        for m in data["by_payment_method"]
    }
    assert methods == {
        "cash": (Decimal("600.00"), 2),
        "eft": (Decimal("300.00"), 1),
    }


def test_financial_collected_uses_payment_date(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    case = make_case(db, business, total="300.00", paid="300.00")

    make_payment(db, case, "100.00", on=date(2026, 9, 1))
    make_payment(db, case, "200.00", on=date(2026, 10, 1))

    data = get(
        client,
        auth_headers,
        test_data["manager"],
        "financial",
        date_from="2026-10-01",
        date_to="2026-10-31",
    ).json()

    assert Decimal(data["collected"]) == Decimal("200.00")


def test_financial_outstanding_age_buckets(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]

    make_case(db, business, total="100.00", created_days_ago=5)
    make_case(db, business, total="200.00", created_days_ago=45)
    make_case(db, business, total="300.00", created_days_ago=75)
    make_case(db, business, total="400.00", created_days_ago=200)
    make_case(db, business, total="400.00", created_days_ago=200)

    data = get(
        client, auth_headers, test_data["manager"], "financial"
    ).json()

    buckets = {
        b["bucket"]: (Decimal(b["amount"]), b["cases"])
        for b in data["outstanding_by_age"]
    }

    assert [b["bucket"] for b in data["outstanding_by_age"]] == [
        "0-30",
        "31-60",
        "61-90",
        "90+",
    ]
    assert buckets == {
        "0-30": (Decimal("100.00"), 1),
        "31-60": (Decimal("200.00"), 1),
        "61-90": (Decimal("300.00"), 1),
        "90+": (Decimal("800.00"), 2),
    }


def test_financial_excludes_cancelled_and_archived_cases(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]

    make_case(db, business, total="100.00")
    make_case(db, business, total="999.00", status="cancelled")
    make_case(db, business, total="888.00", archived=True)

    data = get(
        client, auth_headers, test_data["manager"], "financial"
    ).json()

    assert Decimal(data["billed"]) == Decimal("100.00")
    assert Decimal(data["outstanding"]) == Decimal("100.00")


def test_financial_by_branch_and_filter(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business, "Soweto", "SWT")

    a = make_case(db, business, main, total="1000.00", paid="250.00")
    b = make_case(db, business, other, total="600.00", paid="600.00")

    make_payment(db, a, "250.00")
    make_payment(db, b, "600.00")

    data = get(
        client, auth_headers, test_data["manager"], "financial"
    ).json()

    rows = {r["branch_name"]: r for r in data["by_branch"]}

    assert Decimal(rows["Main"]["billed"]) == Decimal("1000.00")
    assert Decimal(rows["Main"]["collected"]) == Decimal("250.00")
    assert Decimal(rows["Main"]["outstanding"]) == Decimal("750.00")
    assert Decimal(rows["Soweto"]["outstanding"]) == Decimal("0.00")

    filtered = get(
        client,
        auth_headers,
        test_data["manager"],
        "financial",
        branch_id=str(other.id),
    ).json()

    assert Decimal(filtered["billed"]) == Decimal("600.00")
    assert Decimal(filtered["collected"]) == Decimal("600.00")
    assert Decimal(filtered["outstanding"]) == Decimal("0.00")


def test_financial_report_empty_business(
    client, test_data, auth_headers
):
    data = get(
        client, auth_headers, test_data["manager"], "financial"
    ).json()

    assert Decimal(data["billed"]) == Decimal("0.00")
    assert Decimal(data["collected"]) == Decimal("0.00")
    assert Decimal(data["outstanding"]) == Decimal("0.00")
    assert data["by_payment_method"] == []
    assert data["by_branch"] == []
    assert len(data["outstanding_by_age"]) == 4


# ============================================================
# MEMBERSHIP
# ============================================================

def test_membership_report(client, db, test_data, auth_headers):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business, "Soweto", "SWT")
    plan = make_plan(db, business)

    m1 = make_member(db, business, main)
    m2 = make_member(db, business, other)
    make_member(db, business, other, status="lapsed")

    ms1 = make_membership(db, business, m1, plan)
    ms2 = make_membership(db, business, m2, plan, status="lapsed")

    make_membership_payment(db, ms1, "100.00", date(2026, 10, 1))
    make_membership_payment(db, ms2, "50.00", date(2026, 10, 2))
    make_membership_payment(db, ms2, "70.00", date(2026, 7, 2))

    case_one = make_case(db, business, main, membership=ms1)
    case_two = make_case(db, business, other, membership=ms2)

    make_claim(
        db, ms1, case_one, status="paid", claimed="5000.00", approved="4500.00"
    )
    make_claim(db, ms2, case_two, status="submitted", claimed="3000.00")

    data = get(
        client,
        auth_headers,
        test_data["manager"],
        "membership",
        date_from="2026-10-01",
        date_to="2026-10-31",
    ).json()

    assert data["total_members"] == 3
    assert {s["status"]: s["count"] for s in data["members_by_status"]} == {
        "active": 2,
        "lapsed": 1,
    }
    assert {
        s["status"]: s["count"] for s in data["memberships_by_status"]
    } == {"active": 1, "lapsed": 1}
    assert Decimal(data["contributions_collected"]) == Decimal("150.00")
    assert data["claims_total"] == 2

    claims = {c["status"]: c for c in data["claims_by_status"]}
    assert Decimal(claims["paid"]["claimed_amount"]) == Decimal("5000.00")
    assert Decimal(claims["paid"]["approved_amount"]) == Decimal("4500.00")
    assert Decimal(claims["submitted"]["approved_amount"]) == Decimal("0.00")

    rows = {r["branch_name"]: r for r in data["by_branch"]}
    assert rows["Main"]["members"] == 1
    assert Decimal(rows["Main"]["contributions"]) == Decimal("100.00")
    assert rows["Soweto"]["members"] == 2
    assert Decimal(rows["Soweto"]["contributions"]) == Decimal("50.00")


def test_membership_report_branch_filter(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business, "Soweto", "SWT")
    plan = make_plan(db, business)

    ms1 = make_membership(db, business, make_member(db, business, main), plan)
    ms2 = make_membership(db, business, make_member(db, business, other), plan)

    make_membership_payment(db, ms1, "100.00", date(2026, 10, 1))
    make_membership_payment(db, ms2, "50.00", date(2026, 10, 1))

    data = get(
        client,
        auth_headers,
        test_data["manager"],
        "membership",
        branch_id=str(other.id),
    ).json()

    assert data["total_members"] == 1
    assert Decimal(data["contributions_collected"]) == Decimal("50.00")


# ============================================================
# VALIDATION, PERMISSIONS, ISOLATION
# ============================================================

def test_start_after_end_is_rejected(client, test_data, auth_headers):
    for path in ("cases", "financial", "membership"):
        response = get(
            client,
            auth_headers,
            test_data["manager"],
            path,
            date_from="2026-10-31",
            date_to="2026-10-01",
        )

        assert response.status_code == 422, path
        assert "start date" in response.json()["detail"]


def test_unknown_branch_is_not_found(client, test_data, auth_headers):
    for path in ("cases", "financial", "membership"):
        response = get(
            client,
            auth_headers,
            test_data["manager"],
            path,
            branch_id=str(uuid.uuid4()),
        )

        assert response.status_code == 404, path


def test_other_business_branch_is_not_found(
    client, db, test_data, auth_headers
):
    foreign = make_branch(
        db, test_data["business_b"], "Foreign", "FRN", main=True
    )

    response = get(
        client,
        auth_headers,
        test_data["manager"],
        "financial",
        branch_id=str(foreign.id),
    )

    assert response.status_code == 404


def test_reports_never_include_another_business(
    client, db, test_data, auth_headers
):
    make_case(db, test_data["business_b"], total="5000.00")
    mine = make_case(
        db, test_data["business_a"], total="100.00", paid="100.00"
    )
    make_payment(db, mine, "100.00")

    other_case = make_case(
        db, test_data["business_b"], total="700.00", paid="700.00"
    )
    make_payment(db, other_case, "700.00")

    finance = get(
        client, auth_headers, test_data["manager"], "financial"
    ).json()
    cases = get(
        client, auth_headers, test_data["manager"], "cases"
    ).json()

    assert Decimal(finance["billed"]) == Decimal("100.00")
    assert Decimal(finance["collected"]) == Decimal("100.00")
    assert Decimal(finance["outstanding"]) == Decimal("0.00")
    assert cases["total_cases"] == 1


def test_reports_require_permission(client, db, test_data, auth_headers):
    manager = test_data["manager"]
    deny(db, manager, "reports.view")

    for path in ("cases", "financial", "membership"):
        response = get(client, auth_headers, manager, path)

        assert response.status_code == 403, path


def test_reports_need_a_login(client):
    for path in ("cases", "financial", "membership"):
        assert client.get(f"/reports/{path}").status_code in (401, 403)


def test_main_admin_can_view_reports(client, test_data, auth_headers):
    for path in ("cases", "financial", "membership"):
        response = get(
            client, auth_headers, test_data["main_admin"], path
        )

        assert response.status_code == 200, path
