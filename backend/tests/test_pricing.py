"""Plan price + a price per extra staff account / branch, plus VAT."""

from datetime import date, timedelta

import pytest

from app.models.business import Business
from app.models.pricing import PricingPlan, UsageSnapshot
from app.services import pricing as pricing_service
from tests.test_branches import make_branch
from tests.test_platform_admin import operator  # noqa: F401  (fixture)
from tests.test_workspace_groups import make_staff

STANDARD = dict(
    base_price_cents=29900,
    included_staff=5,
    included_branches=1,
    extra_staff_cents=2500,
    extra_branch_cents=2500,
)


@pytest.fixture
def prices(db):
    """The funeral plan test businesses start on, set to the known figures."""
    row = pricing_service.get_pricing(db)
    row.price_note = None
    row.vat_percent = 15
    plan = pricing_service.plans_for(db, "funeral")[0]
    for key, value in STANDARD.items():
        setattr(plan, key, value)
    plan.name = "Standard"
    db.commit()
    return plan


def total(prices, staff, branches, override=None):
    return pricing_service.quote(
        prices, staff=staff, branches=branches, base_override_cents=override
    )["total_cents"]


# ============================================================
# THE PRICE
# ============================================================

@pytest.mark.parametrize(
    "staff, branches, expected",
    [
        (0, 0, 29900),       # nothing yet: still the standard price
        (1, 0, 29900),
        (5, 1, 29900),       # exactly what is included
        (6, 1, 32400),       # one extra staff: +R25
        (10, 1, 42400),      # five extra staff: +R125
        (5, 2, 32400),       # one extra branch: +R25
        (7, 3, 39900),       # two extra staff + two extra branches
    ],
)
def test_price_is_standard_plus_25_per_extra(prices, staff, branches, expected):
    assert total(prices, staff, branches) == expected


def test_a_special_base_price_still_adds_extras(prices):
    assert total(prices, 7, 1, override=20000) == 25000


def test_only_extras_that_exist_appear_as_lines(prices):
    plain = pricing_service.quote(prices, staff=3, branches=1)
    busy = pricing_service.quote(prices, staff=8, branches=3)

    assert [line["label"] for line in plain["lines"]] == ["Standard plan"]  # plan name + " plan"
    assert [line["label"] for line in busy["lines"]] == [
        "Standard plan", "Extra staff", "Extra branches",
    ]
    assert busy["lines"][1]["quantity"] == 3
    assert busy["lines"][2]["quantity"] == 2


def test_a_negative_count_is_treated_as_zero(prices):
    assert total(prices, -4, -1) == 29900


def test_the_next_one_costs_only_after_the_included_ones(prices):
    assert pricing_service.next_costs(prices, 4, 0) == {
        "next_staff_cents": 0, "next_staff_incl_vat_cents": 0,
        "next_branch_cents": 0, "next_branch_incl_vat_cents": 0,
    }
    assert pricing_service.next_costs(prices, 5, 1, 15) == {
        "next_staff_cents": 2500, "next_staff_incl_vat_cents": 2875,
        "next_branch_cents": 2500, "next_branch_incl_vat_cents": 2875,
    }


# ============================================================
# PRICES PEOPLE CAN SEE AND THE OWNER CAN CHANGE
# ============================================================

def test_plans_are_public_and_need_no_sign_in(client, db):
    response = client.get("/pricing")

    assert response.status_code == 200
    body = response.json()
    assert body["vat_percent"] == 15
    funeral = {p["code"]: p for p in body["plans"]["funeral"]}
    general = {p["code"]: p for p in body["plans"]["general"]}

    beginner = funeral["funeral-beginner"]
    assert (beginner["base_price_cents"], beginner["included_staff"],
            beginner["included_branches"], beginner["extra_staff_cents"]) == (80000, 5, 1, 6000)
    standard = funeral["funeral-standard"]
    assert (standard["base_price_cents"], standard["included_staff"],
            standard["included_branches"]) == (100000, 7, 2)
    startup = general["general-startup"]
    assert (startup["base_price_cents"], startup["included_staff"]) == (45000, 3)
    gstandard = general["general-standard"]
    assert (gstandard["base_price_cents"], gstandard["included_staff"]) == (95000, 6)


def test_vat_is_added_on_top_of_the_plan_price(client, db):
    q = client.get("/pricing/quote?plan=funeral-beginner&staff=5&branches=1").json()

    assert q["total_cents"] == 80000
    assert q["vat_percent"] == 15
    assert q["vat_cents"] == 12000
    assert q["total_incl_vat_cents"] == 92000


def test_extra_staff_on_the_beginner_plan_cost_R60_each_plus_vat(client, db):
    q = client.get("/pricing/quote?plan=funeral-beginner&staff=8&branches=1").json()

    assert q["total_cents"] == 80000 + 3 * 6000
    assert q["total_incl_vat_cents"] == 98000 * 115 // 100


def test_vat_is_rounded_to_the_cent(db):
    assert pricing_service.vat_split(1, 15) == (0, 1)
    assert pricing_service.vat_split(10, 15) == (2, 12)   # 1.5 rounds up
    assert pricing_service.vat_split(0, 15) == (0, 0)


def test_the_owner_can_change_the_vat_rate_and_note(client, operator, prices):
    client.put("/platform/pricing", headers=operator,
               json={"vat_percent": 20, "price_note": "Excl. VAT"})
    seen = client.get("/pricing").json()
    assert seen["vat_percent"] == 20 and seen["price_note"] == "Excl. VAT"

    q = client.get("/pricing/quote?plan=funeral-beginner&staff=1").json()
    assert q["vat_cents"] == q["total_cents"] // 5


def test_a_blank_note_removes_it(client, operator, prices):
    client.put("/platform/pricing", headers=operator, json={"price_note": "x"})
    client.put("/platform/pricing", headers=operator, json={"price_note": "  "})

    assert client.get("/pricing").json()["price_note"] is None


@pytest.mark.parametrize(
    "body",
    [{"vat_percent": -1}, {"vat_percent": 101}, {"price_note": "x" * 201},
     {"currency": "USD"}, {"base_price_cents": 5}],
)
def test_nonsense_settings_are_refused(client, operator, prices, body):
    assert client.put("/platform/pricing", headers=operator, json=body).status_code == 422


def test_the_owner_can_edit_a_plan(client, operator, db, prices):
    plan = pricing_service.plans_for(db, "general")[0]
    response = client.put(
        f"/platform/plans/{plan.id}", headers=operator,
        json={"base_price_cents": 50000, "included_staff": 4, "tagline": "  New  "},
    )

    assert response.status_code == 200
    seen = {p["code"]: p for p in client.get("/pricing").json()["plans"]["general"]}
    assert seen[plan.code]["base_price_cents"] == 50000
    assert seen[plan.code]["included_staff"] == 4
    assert seen[plan.code]["tagline"] == "New"
    assert seen[plan.code]["extra_staff_cents"] == 5000   # untouched


def test_a_switched_off_plan_is_hidden_from_the_public(client, operator, db, prices):
    plan = pricing_service.plans_for(db, "general")[-1]
    client.put(f"/platform/plans/{plan.id}", headers=operator, json={"is_active": False})

    codes = [p["code"] for p in client.get("/pricing").json()["plans"]["general"]]
    assert plan.code not in codes
    assert client.get(f"/pricing/quote?plan={plan.code}&staff=1").status_code == 404
    assert any(p["code"] == plan.code for p in client.get("/platform/plans", headers=operator).json())


@pytest.mark.parametrize(
    "body",
    [{"base_price_cents": -1}, {"extra_staff_cents": -100},
     {"base_price_cents": 10_000_001}, {"included_staff": -1},
     {"included_branches": 5000}, {"name": ""}, {"code": "x"}],
)
def test_nonsense_plan_edits_are_refused(client, operator, db, prices, body):
    plan = pricing_service.plans_for(db, "funeral")[0]
    assert client.put(f"/platform/plans/{plan.id}", headers=operator, json=body).status_code == 422


def test_a_business_cannot_change_prices_or_plans(client, auth_headers, db, test_data, prices):
    headers = auth_headers(test_data["main_admin"])
    plan = pricing_service.plans_for(db, "funeral")[0]

    assert client.put("/platform/pricing", headers=headers, json={"vat_percent": 1}).status_code == 401
    assert client.put(f"/platform/plans/{plan.id}", headers=headers, json={"base_price_cents": 1}).status_code == 401
    assert client.put("/platform/pricing", json={}).status_code in (401, 403)


# ============================================================
# CHOOSING A PLAN
# ============================================================

def test_a_business_without_a_choice_gets_its_first_plan(db, test_data, prices):
    plan = pricing_service.plan_for(db, test_data["business_a"])
    assert plan.business_type == "funeral" and plan.code == "funeral-beginner"


def test_the_owner_can_choose_a_plan_for_their_kind_of_business(
    client, auth_headers, test_data, db, prices
):
    headers = auth_headers(test_data["main_admin"])
    response = client.put("/subscription/plan", headers=headers,
                          json={"plan_code": "funeral-standard"})

    assert response.status_code == 200
    body = client.get("/subscription", headers=headers).json()
    assert body["plan"]["code"] == "funeral-standard"
    assert body["plan_chosen"] is True
    assert {p["code"] for p in body["plans"]} >= {"funeral-beginner", "funeral-standard"}
    assert all(p["business_type"] == "funeral" for p in body["plans"])


def test_a_funeral_business_cannot_take_a_general_plan(client, auth_headers, test_data, prices):
    headers = auth_headers(test_data["main_admin"])
    assert client.put("/subscription/plan", headers=headers,
                      json={"plan_code": "general-startup"}).status_code == 404
    assert client.put("/subscription/plan", headers=headers,
                      json={"plan_code": "nonsense"}).status_code == 404


def test_only_the_people_who_run_the_business_can_choose(client, auth_headers, test_data, prices):
    for who in ("staff", "manager"):
        r = client.put("/subscription/plan", headers=auth_headers(test_data[who]),
                       json={"plan_code": "funeral-standard"})
        assert r.status_code == 403
    assert client.put("/subscription/plan", json={"plan_code": "x"}).status_code in (401, 403)


def test_the_bill_follows_the_chosen_plan_and_shows_vat(
    client, auth_headers, test_data, db, prices
):
    test_data["business_a"].subscription_status = "active"
    db.commit()
    headers = auth_headers(test_data["main_admin"])
    client.put("/subscription/plan", headers=headers, json={"plan_code": "funeral-enterprise"})

    bill = client.get("/subscription", headers=headers).json()["bill"]

    assert bill["plan"] == "Enterprise"
    assert bill["amount_due_cents"] == 180000
    assert bill["vat_cents"] == 27000
    assert bill["amount_due_incl_vat_cents"] == 207000


# ============================================================
# WHAT A BUSINESS SEES
# ============================================================

def test_everyone_sees_the_prices_and_what_the_next_one_costs(
    client, auth_headers, test_data, prices
):
    response = client.get("/subscription", headers=auth_headers(test_data["staff"]))

    body = response.json()
    assert body["plan"]["base_price_cents"] == 29900
    assert body["vat_percent"] == 15
    assert body["next_staff_cents"] == 0       # 3 of 5 included staff used
    assert body["next_branch_cents"] == 0


def test_only_the_people_who_run_the_business_see_the_bill(
    client, auth_headers, test_data, prices
):
    staff = client.get("/subscription", headers=auth_headers(test_data["staff"])).json()
    manager = client.get("/subscription", headers=auth_headers(test_data["manager"])).json()
    owner = client.get("/subscription", headers=auth_headers(test_data["main_admin"])).json()

    assert "bill" not in staff
    assert "bill" not in manager
    assert owner["bill"]["amount_due_cents"] == 29900


def test_the_bill_grows_with_extra_staff_and_branches(
    client, db, auth_headers, test_data, prices
):
    business = test_data["business_a"]
    for n in range(3):                       # 3 + 3 = 6 staff
        make_staff(db, test_data["staff"], business, name=f"Extra {n}")
    make_branch(db, business, "North", "NTH", main=True)
    make_branch(db, business, "South", "STH")  # 2 branches

    body = client.get(
        "/subscription", headers=auth_headers(test_data["main_admin"])
    ).json()

    assert body["next_staff_cents"] == 2500
    assert body["next_staff_incl_vat_cents"] == 2875
    assert body["next_branch_cents"] == 2500
    assert body["bill"]["now"]["staff"] == 6
    assert body["bill"]["now"]["branches"] == 2
    assert body["bill"]["now"]["total_cents"] == 29900 + 2500 + 2500
    assert body["bill"]["amount_due_cents"] == 34900


def test_growing_past_the_included_amount_is_never_blocked(db, test_data, prices):
    for n in range(10):
        make_staff(db, test_data["staff"], test_data["business_a"], name=f"S{n}")

    assert pricing_service.counts_now(db, test_data["business_a"].id)[0] == 13


def test_new_businesses_start_on_the_standard_plan_with_no_caps(client, db):
    client.post(
        "/auth/register",
        json={
            "business_name": "Plan Co", "business_type": "general",
            "full_name": "Owner", "email": "plan@example.com",
            "password": "TestPassword123!",
        },
    )

    business = db.query(Business).filter(Business.name == "Plan Co").one()

    assert business.subscription_tier == "standard"
    assert business.max_users is None and business.max_branches is None


# ============================================================
# THE DAILY RECORD AND THE MONTHLY STATEMENT
# ============================================================

def test_snapshots_cover_businesses_in_service_only(db, test_data, prices):
    a, b = test_data["business_a"], test_data["business_b"]
    b.subscription_status = "suspended"
    db.commit()

    saved = pricing_service.record_snapshots(db)

    assert saved == 1
    assert db.query(UsageSnapshot).one().business_id == a.id


def test_running_twice_in_a_day_keeps_one_line_with_the_larger_counts(
    db, test_data, prices
):
    business = test_data["business_a"]
    pricing_service.record_snapshots(db)
    make_staff(db, test_data["staff"], business, name="Later")
    pricing_service.record_snapshots(db)

    rows = db.query(UsageSnapshot).filter(UsageSnapshot.business_id == business.id).all()

    assert len(rows) == 1
    assert rows[0].staff == 4


def test_the_busiest_day_sets_the_months_bill(db, test_data, prices):
    business = test_data["business_a"]
    first = date.today().replace(day=1) - timedelta(days=20)  # last month
    year, month = first.year, first.month
    for day, staff in ((3, 4), (10, 9), (25, 5)):
        db.add(UsageSnapshot(
            business_id=business.id, day=date(year, month, day),
            staff=staff, branches=1,
        ))
    db.commit()

    s = pricing_service.statement(db, business, year, month)

    assert s["peak_staff"] == 9
    assert s["extra_staff"] == 4
    assert s["amount_due_cents"] == 29900 + 4 * 2500


def test_other_months_do_not_leak_into_a_statement(db, test_data, prices):
    business = test_data["business_a"]
    last_month_end = date.today().replace(day=1) - timedelta(days=1)
    db.add(UsageSnapshot(
        business_id=business.id, day=last_month_end, staff=40, branches=9,
    ))
    db.commit()
    this = date.today()

    s = pricing_service.statement(db, business, this.year, this.month)

    assert s["peak_staff"] == 3     # live count, not last month's 40


def test_the_running_month_includes_whoever_is_there_right_now(db, test_data, prices):
    business = test_data["business_a"]
    for n in range(4):
        make_staff(db, test_data["staff"], business, name=f"N{n}")
    now = date.today()

    s = pricing_service.statement(db, business, now.year, now.month)

    assert s["peak_staff"] == 7
    assert s["amount_due_cents"] == 29900 + 2 * 2500


def test_people_removed_before_month_end_still_count(db, test_data, prices):
    business = test_data["business_a"]
    extra = [make_staff(db, test_data["staff"], business, name=f"T{n}") for n in range(4)]
    pricing_service.record_snapshots(db)
    for user in extra:
        user.is_active = False
    db.commit()
    now = date.today()

    s = pricing_service.statement(db, business, now.year, now.month)

    assert s["peak_staff"] == 7


@pytest.mark.parametrize(
    "status, due",
    [("active", 29900), ("trial", 0), ("suspended", 0), ("cancelled", 0)],
)
def test_only_active_businesses_are_charged(db, test_data, prices, status, due):
    business = test_data["business_a"]
    business.subscription_status = status
    db.commit()
    now = date.today()

    s = pricing_service.statement(db, business, now.year, now.month)

    assert s["amount_due_cents"] == due
    assert s["list_total_cents"] == 29900     # what it would be, for reference
    assert (s["note"] is None) == (status == "active")


def test_a_special_price_changes_the_statement_and_the_owners_list(
    client, db, operator, test_data, prices
):
    business = test_data["business_a"]

    r = client.patch(
        f"/platform/businesses/{business.id}/subscription",
        headers=operator, json={"base_price_override_cents": 15000},
    )
    assert r.status_code == 200
    assert r.json()["base_price_override_cents"] == 15000
    assert r.json()["monthly_cents"] == 15000

    r = client.patch(
        f"/platform/businesses/{business.id}/subscription",
        headers=operator, json={"base_price_override_cents": None},
    )
    assert r.json()["monthly_cents"] == 29900


def test_a_negative_special_price_is_refused(client, operator, test_data, prices):
    r = client.patch(
        f"/platform/businesses/{test_data['business_a'].id}/subscription",
        headers=operator, json={"base_price_override_cents": -5},
    )

    assert r.status_code == 422


def test_the_standard_tier_can_be_chosen(client, operator, test_data, prices):
    r = client.patch(
        f"/platform/businesses/{test_data['business_a'].id}/subscription",
        headers=operator, json={"tier": "standard", "apply_tier_defaults": True},
    )

    assert r.status_code == 200
    assert r.json()["tier"] == "standard"


# ============================================================
# THE OWNER'S STATEMENT SCREEN AND DOWNLOAD
# ============================================================

def test_statements_list_every_business_and_total_what_is_due(
    client, operator, test_data, prices
):
    body = client.get("/platform/statements", headers=operator).json()

    names = {r["business"] for r in body["rows"]}
    assert test_data["business_a"].name in names
    assert test_data["business_b"].name in names
    assert body["total_due_cents"] == sum(r["amount_due_cents"] for r in body["rows"])
    assert body["total_due_cents"] >= 2 * 29900


def test_statements_download_as_a_spreadsheet(client, operator, test_data, prices):
    response = client.get(
        "/platform/statements?format=csv&month=2026-11", headers=operator
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "linda-statements-2026-11.csv" in response.headers["content-disposition"]
    assert response.text.splitlines()[0].startswith("Business,Plan,Status,Peak staff")
    assert "299.00" in response.text and "343.85" in response.text


def test_a_business_name_cannot_run_as_a_spreadsheet_formula(
    client, db, operator, test_data, prices
):
    business = test_data["business_a"]
    business.name = "=HYPERLINK(\"http://evil\")"
    db.commit()

    text = client.get("/platform/statements?format=csv", headers=operator).text

    assert "\n=HYPERLINK" not in text
    assert "'=HYPERLINK" in text


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "nonsense", "1999-05", "2026-00"])
def test_a_bad_month_is_refused(client, operator, prices, month):
    assert client.get(f"/platform/statements?month={month}", headers=operator).status_code == 422


def test_statements_are_only_for_the_platform_owner(client, auth_headers, test_data, prices):
    r = client.get("/platform/statements", headers=auth_headers(test_data["main_admin"]))

    assert r.status_code == 401
    assert client.get("/platform/statements").status_code in (401, 403)


# ============================================================
# THE PRICING PAGE CALCULATOR
# ============================================================

def test_the_calculator_gives_the_same_price_as_the_bill(client, prices):
    body = client.get(f"/pricing/quote?plan={prices.code}&staff=8&branches=3").json()

    assert body["total_cents"] == 29900 + 3 * 2500 + 2 * 2500
    assert [line["label"] for line in body["lines"]] == [
        "Standard plan", "Extra staff", "Extra branches",
    ]
    assert body["total_incl_vat_cents"] == body["total_cents"] * 115 // 100


def test_the_calculator_needs_no_sign_in_and_defaults_to_one_branch(client, prices):
    q = client.get(f"/pricing/quote?plan={prices.code}&staff=5").json()
    assert q["total_cents"] == 29900


@pytest.mark.parametrize("query", ["staff=-1", "staff=10001", "staff=2&branches=-1",
                                   "staff=2&branches=1001", "staff=abc", "", "plan=funeral-beginner"])
def test_the_calculator_refuses_nonsense(client, prices, query):
    sep = "" if query.startswith("plan=") else "plan=funeral-beginner&"
    assert client.get(f"/pricing/quote?{sep}{query}").status_code == 422


def test_an_unknown_plan_is_not_found(client, prices):
    assert client.get("/pricing/quote?plan=nope&staff=1").status_code == 404
