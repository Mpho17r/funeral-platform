from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.models.case_contact import CaseContact
from app.models.case_financial import CaseFinancial
from app.models.funeral_case import FuneralCase


def create_case(
    db,
    business,
    *,
    case_number=None,
    deceased_full_name="Dashboard Test Person",
    status="open",
    funeral_date=None,
    funeral_venue="Test Chapel",
    created_at=None,
):
    case = FuneralCase(
        business_id=business.id,
        case_number=case_number or f"DASH-{uuid4().hex[:8].upper()}",
        deceased_full_name=deceased_full_name,
        status=status,
        funeral_date=funeral_date,
        funeral_venue=funeral_venue,
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=created_at or datetime.now(timezone.utc),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_financial(
    db,
    business,
    case,
    *,
    total="1000.00",
    amount_paid="0.00",
    balance=None,
    credit="0.00",
):
    total = Decimal(total)
    amount_paid = Decimal(amount_paid)
    balance = (
        Decimal(balance)
        if balance is not None
        else max(total - amount_paid, Decimal("0.00"))
    )
    credit = Decimal(credit)

    financial = CaseFinancial(
        business_id=business.id,
        case_id=case.id,
        status="unpaid",
        subtotal=total,
        discount=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=total,
        amount_paid=amount_paid,
        balance=balance,
        credit=credit,
        notes="Dashboard behavioral test",
    )
    db.add(financial)
    db.commit()
    db.refresh(financial)
    return financial


def create_contact(
    db,
    business,
    case,
    *,
    contact_type="next_of_kin",
    first_name="Dashboard",
    last_name="Contact",
):
    contact = CaseContact(
        business_id=business.id,
        case_id=case.id,
        contact_type=contact_type,
        first_name=first_name,
        last_name=last_name,
        phone="0712345678",
        email=f"{uuid4().hex[:8]}@example.com",
        relationship="spouse",
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


# ============================================================
# BASIC DASHBOARD RESPONSE
# ============================================================


def test_dashboard_returns_zero_values_when_business_has_no_records(
    client,
    test_data,
    auth_headers,
):
    admin = test_data["main_admin"]

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_cases"] == 0
    assert data["active_cases"] == 0
    assert data["upcoming_funeral_count"] == 0
    assert Decimal(data["outstanding_balance"]) == Decimal("0.00")
    assert Decimal(data["total_revenue"]) == Decimal("0.00")
    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert Decimal(data["total_credit"]) == Decimal("0.00")
    assert data["total_families"] == 0
    assert data["recent_cases"] == []
    assert data["upcoming_funerals"] == []


# ============================================================
# CASE METRICS
# ============================================================


def test_dashboard_counts_total_cases(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    create_case(db, business, status="open")
    create_case(db, business, status="closed")
    create_case(db, business, status="cancelled")

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["total_cases"] == 3


def test_dashboard_counts_only_open_confirmed_and_in_progress_as_active(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    for status in ["open", "confirmed", "in_progress"]:
        create_case(db, business, status=status)

    for status in ["closed", "cancelled", "draft"]:
        create_case(db, business, status=status)

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["total_cases"] == 6
    assert response.json()["active_cases"] == 3


# ============================================================
# FAMILY / CONTACT COUNT
# ============================================================


def test_dashboard_counts_family_and_next_of_kin_contacts(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    case = create_case(db, business)

    create_contact(
        db,
        business,
        case,
        contact_type="family",
        first_name="Family",
        last_name="One",
    )
    create_contact(
        db,
        business,
        case,
        contact_type="next_of_kin",
        first_name="Next",
        last_name="OfKin",
    )
    create_contact(
        db,
        business,
        case,
        contact_type="provider",
        first_name="Provider",
        last_name="One",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["total_families"] == 2


# ============================================================
# FINANCIAL TOTALS
# ============================================================


def test_dashboard_aggregates_financial_totals(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    case_one = create_case(db, business)
    case_two = create_case(db, business)

    create_financial(
        db,
        business,
        case_one,
        total="10000.00",
        amount_paid="6000.00",
        balance="4000.00",
        credit="0.00",
    )
    create_financial(
        db,
        business,
        case_two,
        total="5000.00",
        amount_paid="5500.00",
        balance="0.00",
        credit="500.00",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["total_revenue"]) == Decimal("15000.00")
    assert Decimal(data["amount_paid"]) == Decimal("11500.00")
    assert Decimal(data["outstanding_balance"]) == Decimal("4000.00")
    assert Decimal(data["total_credit"]) == Decimal("500.00")


def test_dashboard_financial_totals_are_scoped_to_current_business(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    admin = test_data["main_admin"]

    case_a = create_case(db, business_a)
    case_b = create_case(db, business_b)

    create_financial(
        db,
        business_a,
        case_a,
        total="2000.00",
        amount_paid="500.00",
        balance="1500.00",
        credit="100.00",
    )
    create_financial(
        db,
        business_b,
        case_b,
        total="9000.00",
        amount_paid="9000.00",
        balance="0.00",
        credit="900.00",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["total_revenue"]) == Decimal("2000.00")
    assert Decimal(data["amount_paid"]) == Decimal("500.00")
    assert Decimal(data["outstanding_balance"]) == Decimal("1500.00")
    assert Decimal(data["total_credit"]) == Decimal("100.00")


# ============================================================
# RECENT CASES
# ============================================================


def test_dashboard_recent_cases_are_newest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    now = datetime.now(timezone.utc)

    older = create_case(
        db,
        business,
        case_number="DASH-OLDER",
        deceased_full_name="Older Person",
        created_at=now - timedelta(days=2),
    )
    newer = create_case(
        db,
        business,
        case_number="DASH-NEWER",
        deceased_full_name="Newer Person",
        created_at=now,
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    recent = response.json()["recent_cases"]

    assert [case["id"] for case in recent[:2]] == [
        str(newer.id),
        str(older.id),
    ]


def test_dashboard_recent_cases_are_limited_to_five(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    now = datetime.now(timezone.utc)

    for index in range(6):
        create_case(
            db,
            business,
            case_number=f"DASH-RECENT-{index}",
            created_at=now + timedelta(seconds=index),
        )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    recent = response.json()["recent_cases"]

    assert len(recent) == 5
    assert recent[0]["case_number"] == "DASH-RECENT-5"
    assert recent[-1]["case_number"] == "DASH-RECENT-1"


def test_dashboard_recent_case_contains_expected_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    funeral_date = date.today() + timedelta(days=7)

    case = create_case(
        db,
        business,
        case_number="DASH-FIELDS",
        deceased_full_name="Expected Fields Person",
        status="confirmed",
        funeral_date=funeral_date,
        funeral_venue="Memorial Chapel",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    recent = response.json()["recent_cases"]

    assert len(recent) == 1
    assert recent[0]["id"] == str(case.id)
    assert recent[0]["case_number"] == "DASH-FIELDS"
    assert recent[0]["deceased_full_name"] == "Expected Fields Person"
    assert recent[0]["funeral_date"] == funeral_date.isoformat()
    assert recent[0]["status"] == "confirmed"
    assert recent[0]["created_at"] is not None


# ============================================================
# UPCOMING FUNERALS
# ============================================================


def test_dashboard_includes_funeral_today_and_within_thirty_days(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    today = date.today()

    today_case = create_case(
        db,
        business,
        case_number="DASH-TODAY",
        funeral_date=today,
        status="open",
    )
    future_case = create_case(
        db,
        business,
        case_number="DASH-FUTURE",
        funeral_date=today + timedelta(days=30),
        status="confirmed",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    upcoming = response.json()["upcoming_funerals"]

    assert response.json()["upcoming_funeral_count"] == 2
    assert [item["id"] for item in upcoming] == [
        str(today_case.id),
        str(future_case.id),
    ]


def test_dashboard_excludes_funeral_more_than_thirty_days_away(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    create_case(
        db,
        business,
        case_number="DASH-TOO-FAR",
        funeral_date=date.today() + timedelta(days=31),
        status="open",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["upcoming_funerals"] == []
    assert response.json()["upcoming_funeral_count"] == 0


def test_dashboard_excludes_cancelled_and_closed_upcoming_funerals(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    funeral_date = date.today() + timedelta(days=5)

    create_case(
        db,
        business,
        case_number="DASH-CANCELLED",
        funeral_date=funeral_date,
        status="cancelled",
    )
    create_case(
        db,
        business,
        case_number="DASH-CLOSED",
        funeral_date=funeral_date,
        status="closed",
    )
    included = create_case(
        db,
        business,
        case_number="DASH-INCLUDED",
        funeral_date=funeral_date,
        status="open",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    upcoming = response.json()["upcoming_funerals"]

    assert len(upcoming) == 1
    assert upcoming[0]["id"] == str(included.id)


def test_dashboard_upcoming_funerals_are_sorted_by_funeral_date(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    later = create_case(
        db,
        business,
        case_number="DASH-LATER",
        funeral_date=date.today() + timedelta(days=10),
    )
    earlier = create_case(
        db,
        business,
        case_number="DASH-EARLIER",
        funeral_date=date.today() + timedelta(days=2),
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    upcoming = response.json()["upcoming_funerals"]

    assert [item["id"] for item in upcoming] == [
        str(earlier.id),
        str(later.id),
    ]


def test_dashboard_upcoming_funerals_are_limited_to_five(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    today = date.today()

    for index in range(6):
        create_case(
            db,
            business,
            case_number=f"DASH-UPCOMING-{index}",
            funeral_date=today + timedelta(days=index),
        )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    upcoming = response.json()["upcoming_funerals"]

    assert len(upcoming) == 5
    assert upcoming[0]["case_number"] == "DASH-UPCOMING-0"
    assert upcoming[-1]["case_number"] == "DASH-UPCOMING-4"


def test_dashboard_upcoming_funeral_contains_expected_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    funeral_date = date.today() + timedelta(days=3)

    case = create_case(
        db,
        business,
        case_number="DASH-UPCOMING-FIELDS",
        deceased_full_name="Upcoming Fields Person",
        funeral_date=funeral_date,
        funeral_venue="Limpopo Chapel",
        status="confirmed",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    upcoming = response.json()["upcoming_funerals"]

    assert len(upcoming) == 1
    assert upcoming[0]["id"] == str(case.id)
    assert upcoming[0]["case_number"] == "DASH-UPCOMING-FIELDS"
    assert upcoming[0]["deceased_full_name"] == "Upcoming Fields Person"
    assert upcoming[0]["funeral_date"] == funeral_date.isoformat()
    assert upcoming[0]["funeral_venue"] == "Limpopo Chapel"


def test_dashboard_upcoming_funeral_allows_null_venue(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    create_case(
        db,
        business,
        case_number="DASH-NO-VENUE",
        funeral_date=date.today() + timedelta(days=4),
        funeral_venue=None,
        status="open",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    upcoming = response.json()["upcoming_funerals"]

    assert len(upcoming) == 1
    assert upcoming[0]["funeral_venue"] is None


# ============================================================
# TENANT ISOLATION
# ============================================================


def test_dashboard_case_counts_are_scoped_to_current_business(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    admin = test_data["main_admin"]

    create_case(db, business_a, status="open")
    create_case(db, business_b, status="open")
    create_case(db, business_b, status="confirmed")

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_cases"] == 1
    assert data["active_cases"] == 1


def test_dashboard_contacts_are_scoped_to_current_business(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    admin = test_data["main_admin"]

    case_a = create_case(db, business_a)
    case_b = create_case(db, business_b)

    create_contact(
        db,
        business_a,
        case_a,
        contact_type="family",
    )
    create_contact(
        db,
        business_b,
        case_b,
        contact_type="family",
    )
    create_contact(
        db,
        business_b,
        case_b,
        contact_type="next_of_kin",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["total_families"] == 1


def test_dashboard_recent_and_upcoming_cases_are_scoped_to_current_business(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    admin = test_data["main_admin"]

    case_a = create_case(
        db,
        business_a,
        case_number="DASH-BUSINESS-A",
        funeral_date=date.today() + timedelta(days=2),
    )
    create_case(
        db,
        business_b,
        case_number="DASH-BUSINESS-B",
        funeral_date=date.today() + timedelta(days=1),
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["recent_cases"]) == 1
    assert data["recent_cases"][0]["id"] == str(case_a.id)

    assert len(data["upcoming_funerals"]) == 1
    assert data["upcoming_funerals"][0]["id"] == str(case_a.id)
