import uuid

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.audit_log import AuditLog
from app.models.covered_dependent import CoveredDependent
from app.models.death_record import DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_claim import MembershipClaim
from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit
from app.models.permission import Permission
from app.models.user_permission import UserPermission
from app.services.waiting_periods import (
    CAUSE_PENDING,
    IN_WAITING,
    NOT_APPLICABLE,
    SERVED,
    add_months,
    cause_category,
    evaluate_upgrade_waiting,
    evaluate_waiting_period,
    upgrade_waiting_still_running,
)


# ============================================================
# HELPERS
# ============================================================

START = date(2026, 1, 1)


def make_plan(
    db,
    business,
    *,
    natural=0,
    accidental=0,
    suicide=0,
    upgrade=0,
    contribution="200.00",
    limit="15000.00",
    name=None,
):
    suffix = uuid.uuid4().hex[:6].upper()

    plan = MembershipPlan(
        business_id=business.id,
        name=name or f"Plan {suffix}",
        monthly_contribution=Decimal(contribution),
        is_active=True,
        waiting_natural_months=natural,
        waiting_accidental_months=accidental,
        waiting_suicide_months=suicide,
        waiting_upgrade_months=upgrade,
    )
    db.add(plan)
    db.flush()

    db.add(
        MembershipPlanBenefit(
            business_id=business.id,
            plan_id=plan.id,
            name=f"Cover {limit}",
            benefit_type="monetary",
            monetary_limit=Decimal(limit),
            is_included=True,
            is_active=True,
        )
    )
    db.commit()

    return plan


def make_membership(db, business, plan, *, start=START):
    suffix = uuid.uuid4().hex[:8].upper()

    member = Member(
        business_id=business.id,
        member_number=f"M-{suffix}",
        first_name="Wait",
        last_name="Member",
        join_date=start,
        status="active",
    )
    db.add(member)
    db.flush()

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"MS-{suffix}",
        start_date=start,
        status="active",
    )
    db.add(membership)
    db.commit()

    return membership


def make_case(
    db,
    business,
    membership,
    *,
    died=date(2026, 10, 1),
    dependent=None,
):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"WP-{uuid.uuid4().hex[:8].upper()}",
        membership_id=membership.id,
        covered_dependent_id=dependent.id if dependent else None,
        deceased_full_name="Waiting Test",
        date_of_death=died,
        status="open",
    )
    db.add(case)
    db.commit()

    return case


def add_record(db, case, manner="natural", cause=None):
    record = DeathRecord(
        business_id=case.business_id,
        case_id=case.id,
        manner_of_death=manner,
        unnatural_cause=cause,
    )
    db.add(record)
    db.commit()

    return record


def add_dependent(db, business, membership, *, cover_start):
    dependent = CoveredDependent(
        business_id=business.id,
        membership_id=membership.id,
        first_name="Dep",
        last_name="Endent",
        relationship="child",
        id_number=f"DEP-{uuid.uuid4().hex[:10].upper()}",
        date_of_birth=date(2015, 5, 10),
        phone="0712345678",
        status="active",
        cover_start_date=cover_start,
    )
    db.add(dependent)
    db.commit()

    return dependent


def coverage(client, headers, case):
    response = client.get(
        f"/cases/{case.id}/coverage",
        headers=headers,
    )
    assert response.status_code == 200, response.text

    return response.json()


def actions(db, business):
    return {
        row.action
        for row in db.query(AuditLog)
        .filter(AuditLog.business_id == business.id)
        .all()
    }


def plan_stub(natural=0, accidental=0, suicide=0, upgrade=0):
    return SimpleNamespace(
        waiting_natural_months=natural,
        waiting_accidental_months=accidental,
        waiting_suicide_months=suicide,
        waiting_upgrade_months=upgrade,
    )


def record_stub(manner, cause=None):
    return SimpleNamespace(manner_of_death=manner, unnatural_cause=cause)


# ============================================================
# DATE ARITHMETIC
# ============================================================

def test_add_months_basic():
    assert add_months(date(2026, 1, 15), 6) == date(2026, 7, 15)
    assert add_months(date(2026, 1, 15), 0) == date(2026, 1, 15)
    assert add_months(date(2026, 11, 5), 3) == date(2027, 2, 5)
    assert add_months(date(2026, 3, 1), 24) == date(2028, 3, 1)


def test_add_months_clamps_to_end_of_short_months():
    assert add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert add_months(date(2023, 8, 31), 6) == date(2024, 2, 29)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


# ============================================================
# CAUSE CATEGORY
# ============================================================

@pytest.mark.parametrize(
    "manner,cause,expected",
    [
        ("natural", None, "natural"),
        ("unnatural", "accident", "accidental"),
        ("unnatural", "homicide", "accidental"),
        ("unnatural", "suicide", "suicide"),
        ("unnatural", "undetermined", None),
        ("unnatural", None, None),
        ("pending", None, None),
    ],
)
def test_cause_category(manner, cause, expected):
    assert cause_category(record_stub(manner, cause)) == expected


def test_cause_category_without_a_record_is_unknown():
    assert cause_category(None) is None


# ============================================================
# ENGINE: KNOWN CAUSE
# ============================================================

def evaluate(plan, died, record, start=START):
    return evaluate_waiting_period(
        plan,
        cover_start=start,
        coverage_date=died,
        record=record,
    )


def test_no_waiting_period_configured_is_not_applicable():
    result = evaluate(
        plan_stub(), date(2026, 1, 2), record_stub("natural")
    )

    assert result.status == NOT_APPLICABLE
    assert result.ends_on is None


def test_natural_death_inside_the_waiting_period():
    result = evaluate(
        plan_stub(natural=6), date(2026, 6, 30), record_stub("natural")
    )

    assert result.status == IN_WAITING
    assert result.cause_category == "natural"
    assert result.ends_on == date(2026, 7, 1)
    assert "1 July 2026" in result.message


def test_natural_death_on_the_last_day_is_still_waiting():
    result = evaluate(
        plan_stub(natural=6), date(2026, 6, 30), record_stub("natural")
    )

    assert result.status == IN_WAITING


def test_natural_death_on_the_end_date_is_served():
    result = evaluate(
        plan_stub(natural=6), date(2026, 7, 1), record_stub("natural")
    )

    assert result.status == SERVED


def test_accidental_death_with_no_accidental_waiting_period():
    result = evaluate(
        plan_stub(natural=6),
        date(2026, 2, 1),
        record_stub("unnatural", "accident"),
    )

    assert result.status == NOT_APPLICABLE
    assert result.cause_category == "accidental"


def test_suicide_uses_its_own_period():
    plan = plan_stub(natural=6, suicide=12)

    inside = evaluate(
        plan, date(2026, 10, 1), record_stub("unnatural", "suicide")
    )
    after = evaluate(
        plan, date(2027, 1, 1), record_stub("unnatural", "suicide")
    )

    assert inside.status == IN_WAITING
    assert inside.ends_on == date(2027, 1, 1)
    assert after.status == SERVED


def test_homicide_is_treated_as_accidental():
    result = evaluate(
        plan_stub(natural=6, accidental=3),
        date(2026, 2, 1),
        record_stub("unnatural", "homicide"),
    )

    assert result.status == IN_WAITING
    assert result.cause_category == "accidental"
    assert result.months == 3


# ============================================================
# ENGINE: UNKNOWN CAUSE
# ============================================================

def test_unknown_cause_when_every_period_is_running_is_waiting():
    result = evaluate(
        plan_stub(natural=6, accidental=3, suicide=12),
        date(2026, 2, 1),
        None,
    )

    assert result.status == IN_WAITING
    assert result.cause_category is None
    assert result.ends_on == date(2026, 4, 1)


def test_unknown_cause_when_every_period_has_passed_is_served():
    result = evaluate(
        plan_stub(natural=6, accidental=3, suicide=12),
        date(2027, 6, 1),
        record_stub("pending"),
    )

    assert result.status == SERVED


def test_unknown_cause_when_the_answer_depends_on_it_is_pending():
    result = evaluate(
        plan_stub(natural=6, accidental=0, suicide=12),
        date(2026, 8, 1),
        record_stub("pending"),
    )

    assert result.status == CAUSE_PENDING
    assert "suicide" in result.message
    assert "natural" not in result.message


def test_unknown_cause_with_no_waiting_periods_is_not_applicable():
    result = evaluate(plan_stub(), date(2026, 8, 1), None)

    assert result.status == NOT_APPLICABLE


def test_undetermined_unnatural_cause_is_unknown():
    result = evaluate(
        plan_stub(natural=6, suicide=12),
        date(2026, 8, 1),
        record_stub("unnatural", "undetermined"),
    )

    assert result.status == CAUSE_PENDING


# ============================================================
# ENGINE: UPGRADE WAITING
# ============================================================

def membership_stub(previous=None, changed=None):
    return SimpleNamespace(
        previous_plan_id=previous,
        plan_changed_at=changed,
    )


def test_upgrade_waiting_is_inactive_without_an_upgrade():
    result = evaluate_upgrade_waiting(
        membership_stub(),
        plan_stub(upgrade=6),
        coverage_date=date(2026, 8, 1),
        category="natural",
    )

    assert result.active is False


def test_upgrade_waiting_runs_for_the_configured_months():
    previous = uuid.uuid4()
    membership = membership_stub(previous, date(2026, 5, 1))

    inside = evaluate_upgrade_waiting(
        membership,
        plan_stub(upgrade=6),
        coverage_date=date(2026, 10, 31),
        category="natural",
    )
    after = evaluate_upgrade_waiting(
        membership,
        plan_stub(upgrade=6),
        coverage_date=date(2026, 11, 1),
        category="natural",
    )

    assert inside.active is True
    assert inside.previous_plan_id == previous
    assert inside.ends_on == date(2026, 11, 1)
    assert after.active is False


def test_upgrade_waiting_does_not_hold_back_a_known_accident():
    result = evaluate_upgrade_waiting(
        membership_stub(uuid.uuid4(), date(2026, 5, 1)),
        plan_stub(upgrade=6),
        coverage_date=date(2026, 6, 1),
        category="accidental",
    )

    assert result.active is False


def test_upgrade_waiting_applies_while_the_cause_is_unknown():
    result = evaluate_upgrade_waiting(
        membership_stub(uuid.uuid4(), date(2026, 5, 1)),
        plan_stub(upgrade=6),
        coverage_date=date(2026, 6, 1),
        category=None,
    )

    assert result.active is True


def test_upgrade_with_zero_months_has_no_waiting():
    result = evaluate_upgrade_waiting(
        membership_stub(uuid.uuid4(), date(2026, 5, 1)),
        plan_stub(upgrade=0),
        coverage_date=date(2026, 5, 2),
        category="natural",
    )

    assert result.active is False


def test_upgrade_waiting_still_running_helper():
    membership = membership_stub(uuid.uuid4(), date(2026, 5, 1))
    plan = plan_stub(upgrade=6)

    assert upgrade_waiting_still_running(
        membership, plan, today=date(2026, 10, 31)
    )
    assert not upgrade_waiting_still_running(
        membership, plan, today=date(2026, 11, 1)
    )
    assert not upgrade_waiting_still_running(
        membership_stub(), plan, today=date(2026, 5, 2)
    )


# ============================================================
# COVERAGE ENDPOINT
# ============================================================

def test_default_plan_has_no_waiting_and_unchanged_reason(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is True
    assert (
        body["reason"]
        == "Membership and applicable dependent coverage are valid."
    )
    assert body["waiting_period"]["status"] == "not_applicable"
    assert body["upgrade_waiting"] is None
    assert body["benefit_plan_id"] == str(plan.id)
    assert body["coverage_date"] == "2026-10-01"


def test_natural_death_in_waiting_period_is_not_covered(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)
    membership = make_membership(
        db, business, plan, start=date(2026, 5, 1)
    )
    case = make_case(db, business, membership, died=date(2026, 10, 1))
    add_record(db, case, "natural")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is False
    assert body["waiting_period"]["status"] == "in_waiting"
    assert body["waiting_period"]["ends_on"] == "2026-11-01"
    assert "waiting period" in body["reason"]
    assert body["benefits"] == []


def test_natural_death_after_waiting_period_is_covered(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)
    case = make_case(db, business, make_membership(db, business, plan))
    add_record(db, case, "natural")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is True
    assert body["waiting_period"]["status"] == "served"
    assert len(body["benefits"]) == 1


def test_accident_inside_natural_waiting_is_covered(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)
    membership = make_membership(
        db, business, plan, start=date(2026, 9, 1)
    )
    case = make_case(db, business, membership)
    add_record(db, case, "unnatural", "accident")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is True
    assert body["waiting_period"]["status"] == "not_applicable"


def test_suicide_waiting_is_longer(client, test_data, auth_headers, db):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6, suicide=12)
    case = make_case(db, business, make_membership(db, business, plan))
    add_record(db, case, "unnatural", "suicide")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is False
    assert body["waiting_period"]["cause_category"] == "suicide"
    assert body["waiting_period"]["ends_on"] == "2027-01-01"


def test_no_death_record_and_cause_decides_the_answer(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=0, suicide=12)
    case = make_case(db, business, make_membership(db, business, plan))

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is True
    assert body["waiting_period"]["status"] == "cause_pending"
    assert "suicide" in body["reason"]


def test_waiting_period_for_a_dependent_runs_from_their_own_start(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)
    membership = make_membership(db, business, plan)
    dependent = add_dependent(
        db, business, membership, cover_start=date(2026, 8, 1)
    )
    case = make_case(db, business, membership, dependent=dependent)
    add_record(db, case, "natural")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is False
    assert body["waiting_period"]["cover_start_date"] == "2026-08-01"
    assert body["waiting_period"]["ends_on"] == "2027-02-01"


def test_dependent_started_long_ago_has_served_the_period(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)
    membership = make_membership(db, business, plan)
    dependent = add_dependent(
        db, business, membership, cover_start=date(2026, 1, 1)
    )
    case = make_case(db, business, membership, dependent=dependent)
    add_record(db, case, "natural")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is True


def test_upgrade_keeps_previous_plan_benefits_during_waiting(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    old_plan = make_plan(
        db, business, limit="10000.00", name="Basic", contribution="100.00"
    )
    new_plan = make_plan(
        db,
        business,
        limit="30000.00",
        name="Premium",
        contribution="300.00",
        upgrade=6,
    )
    membership = make_membership(db, business, new_plan)
    membership.previous_plan_id = old_plan.id
    membership.plan_changed_at = date(2026, 8, 1)
    db.commit()
    case = make_case(db, business, membership, died=date(2026, 10, 1))
    add_record(db, case, "natural")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is True
    assert body["plan_name"] == "Premium"
    assert body["benefit_plan_name"] == "Basic"
    assert body["benefits"][0]["monetary_limit"] == "10000.00"
    assert body["upgrade_waiting"]["ends_on"] == "2027-02-01"
    assert "upgraded" in body["reason"]


def test_upgrade_waiting_over_gives_the_new_plan(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    old_plan = make_plan(db, business, limit="10000.00")
    new_plan = make_plan(db, business, limit="30000.00", upgrade=6)
    membership = make_membership(db, business, new_plan)
    membership.previous_plan_id = old_plan.id
    membership.plan_changed_at = date(2026, 1, 15)
    db.commit()
    case = make_case(db, business, membership, died=date(2026, 10, 1))
    add_record(db, case, "natural")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["benefit_plan_id"] == str(new_plan.id)
    assert body["benefits"][0]["monetary_limit"] == "30000.00"
    assert body["upgrade_waiting"] is None


def test_accident_during_upgrade_waiting_gets_the_new_plan(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    old_plan = make_plan(db, business, limit="10000.00")
    new_plan = make_plan(db, business, limit="30000.00", upgrade=6)
    membership = make_membership(db, business, new_plan)
    membership.previous_plan_id = old_plan.id
    membership.plan_changed_at = date(2026, 8, 1)
    db.commit()
    case = make_case(db, business, membership)
    add_record(db, case, "unnatural", "accident")

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["benefits"][0]["monetary_limit"] == "30000.00"
    assert body["upgrade_waiting"] is None


def test_private_case_has_no_waiting_period(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = FuneralCase(
        business_id=business.id,
        case_number="PRIV-1",
        deceased_full_name="Private",
        date_of_death=date(2026, 10, 1),
        status="open",
    )
    db.add(case)
    db.commit()

    body = coverage(client, auth_headers(test_data["manager"]), case)

    assert body["covered"] is False
    assert body["waiting_period"] is None


def test_coverage_endpoint_is_scoped_to_the_business(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))

    response = client.get(
        f"/cases/{case.id}/coverage",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404


def test_coverage_endpoint_needs_authentication(
    client, test_data, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))

    assert client.get(f"/cases/{case.id}/coverage").status_code in (
        401,
        403,
    )


def test_coverage_endpoint_unknown_case_is_404(
    client, test_data, auth_headers
):
    response = client.get(
        f"/cases/{uuid.uuid4()}/coverage",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404


def test_coverage_endpoint_changes_nothing(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)
    case = make_case(db, business, make_membership(db, business, plan))

    # Signing in is audited, so sign in before taking the count.
    headers = auth_headers(test_data["staff"])
    before = db.query(AuditLog).count()

    coverage(client, headers, case)

    assert db.query(AuditLog).count() == before


# ============================================================
# PLANS API
# ============================================================

def test_plan_waiting_periods_default_to_zero(
    client, test_data, auth_headers
):
    response = client.post(
        "/membership-plans",
        json={"name": "Starter", "monthly_contribution": "99.00"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["waiting_natural_months"] == 0
    assert body["waiting_accidental_months"] == 0
    assert body["waiting_suicide_months"] == 0
    assert body["waiting_upgrade_months"] == 0


def test_manager_creates_plan_with_waiting_periods_and_audit(
    client, test_data, auth_headers, db
):
    response = client.post(
        "/membership-plans",
        json={
            "name": "Family",
            "monthly_contribution": "250.00",
            "waiting_natural_months": 6,
            "waiting_accidental_months": 0,
            "waiting_suicide_months": 12,
            "waiting_upgrade_months": 6,
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["waiting_natural_months"] == 6
    assert body["waiting_suicide_months"] == 12

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "membership_plan.created")
        .one()
    )
    assert log.details["waiting_suicide_months"] == 12
    assert log.entity_id == uuid.UUID(body["id"])


@pytest.mark.parametrize(
    "field",
    [
        "waiting_natural_months",
        "waiting_accidental_months",
        "waiting_suicide_months",
        "waiting_upgrade_months",
    ],
)
@pytest.mark.parametrize("value", [-1, 61])
def test_waiting_months_outside_zero_to_sixty_are_rejected(
    client, test_data, auth_headers, field, value
):
    response = client.post(
        "/membership-plans",
        json={
            "name": "Bad",
            "monthly_contribution": "99.00",
            field: value,
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_updating_waiting_periods_is_audited(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/membership-plans/{plan.id}",
        json={"waiting_natural_months": 6, "waiting_suicide_months": 12},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["waiting_natural_months"] == 6

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "membership_plan.updated")
        .one()
    )
    changes = log.details["changes"]

    assert changes["waiting_natural_months"] == {"old": 0, "new": 6}
    assert changes["waiting_suicide_months"] == {"old": 0, "new": 12}
    assert "name" not in changes


def test_update_with_no_real_change_writes_no_audit(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)

    response = client.patch(
        f"/membership-plans/{plan.id}",
        json={"waiting_natural_months": 6},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert (
        db.query(AuditLog)
        .filter(AuditLog.action == "membership_plan.updated")
        .count()
        == 0
    )


def test_null_waiting_months_in_an_update_are_ignored(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6)

    response = client.patch(
        f"/membership-plans/{plan.id}",
        json={"waiting_natural_months": None, "name": "Renamed"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json()["waiting_natural_months"] == 6
    assert response.json()["name"] == "Renamed"


def test_staff_cannot_change_waiting_periods(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)

    response = client.patch(
        f"/membership-plans/{plan.id}",
        json={"waiting_natural_months": 6},
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


# ============================================================
# MEMBERSHIP PLAN CHANGES
# ============================================================

def change_plan(client, headers, membership, plan):
    return client.patch(
        f"/memberships/{membership.id}",
        json={"plan_id": str(plan.id)},
        headers=headers,
    )


def test_upgrading_a_plan_remembers_the_previous_one(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    basic = make_plan(db, business, contribution="100.00")
    premium = make_plan(
        db, business, contribution="300.00", upgrade=6
    )
    membership = make_membership(db, business, basic)

    response = change_plan(
        client, auth_headers(test_data["manager"]), membership, premium
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["plan_id"] == str(premium.id)
    assert body["previous_plan_id"] == str(basic.id)
    assert body["plan_changed_at"] == date.today().isoformat()

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "membership.plan_changed")
        .one()
    )
    assert log.details["upgrade"] is True
    assert log.details["upgrade_waiting_months"] == 6
    assert log.details["from_plan_id"] == str(basic.id)
    assert log.details["to_plan_id"] == str(premium.id)


def test_downgrade_clears_the_previous_plan(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    basic = make_plan(db, business, contribution="100.00")
    premium = make_plan(db, business, contribution="300.00", upgrade=6)
    membership = make_membership(db, business, premium)

    response = change_plan(
        client, auth_headers(test_data["manager"]), membership, basic
    )

    assert response.status_code == 200
    body = response.json()

    assert body["previous_plan_id"] is None
    assert body["plan_changed_at"] == date.today().isoformat()

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "membership.plan_changed")
        .one()
    )
    assert log.details["upgrade"] is False


def test_second_upgrade_during_waiting_keeps_the_earned_plan(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    basic = make_plan(db, business, contribution="100.00")
    standard = make_plan(
        db, business, contribution="200.00", upgrade=6
    )
    premium = make_plan(
        db, business, contribution="300.00", upgrade=6
    )
    membership = make_membership(db, business, basic)
    headers = auth_headers(test_data["manager"])

    assert change_plan(client, headers, membership, standard).status_code == 200
    response = change_plan(client, headers, membership, premium)

    assert response.status_code == 200
    assert response.json()["plan_id"] == str(premium.id)
    assert response.json()["previous_plan_id"] == str(basic.id)


def test_second_upgrade_after_waiting_moves_the_baseline(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    standard = make_plan(
        db, business, contribution="200.00", upgrade=6
    )
    premium = make_plan(
        db, business, contribution="300.00", upgrade=6
    )
    basic = make_plan(db, business, contribution="100.00")
    membership = make_membership(db, business, standard)
    membership.previous_plan_id = basic.id
    membership.plan_changed_at = date(2025, 1, 1)
    db.commit()

    response = change_plan(
        client, auth_headers(test_data["manager"]), membership, premium
    )

    assert response.status_code == 200
    assert response.json()["previous_plan_id"] == str(standard.id)


def test_saving_the_same_plan_is_not_a_plan_change(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    basic = make_plan(db, business)
    membership = make_membership(db, business, basic)

    response = change_plan(
        client, auth_headers(test_data["manager"]), membership, basic
    )

    assert response.status_code == 200
    assert response.json()["previous_plan_id"] is None
    assert response.json()["plan_changed_at"] is None
    assert "membership.plan_changed" not in actions(db, business)


def test_plan_change_needs_the_memberships_edit_permission(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    basic = make_plan(db, business)
    premium = make_plan(db, business, contribution="300.00")
    membership = make_membership(db, business, basic)
    staff = test_data["staff"]

    permission = (
        db.query(Permission)
        .filter(Permission.key == "memberships.edit")
        .one()
    )
    db.add(
        UserPermission(
            user_id=staff.id,
            permission_id=permission.id,
            effect="deny",
        )
    )
    db.commit()

    response = change_plan(
        client, auth_headers(staff), membership, premium
    )

    assert response.status_code == 403

    db.expire_all()
    assert membership.plan_id == basic.id


# ============================================================
# DEATH RECORD: UNNATURAL CAUSE
# ============================================================

def record_payload(**extra):
    return {
        "deceased_id_type": "other",
        "manner_of_death": "unnatural",
        "forensic_status": "referred",
        **extra,
    }


def test_death_record_stores_and_returns_unnatural_cause(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))

    response = client.post(
        f"/cases/{case.id}/death-record",
        json=record_payload(unnatural_cause="accident"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201, response.text
    assert response.json()["unnatural_cause"] == "accident"


def test_unnatural_cause_needs_an_unnatural_manner(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))

    response = client.post(
        f"/cases/{case.id}/death-record",
        json={
            "deceased_id_type": "other",
            "manner_of_death": "natural",
            "unnatural_cause": "accident",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422
    assert "unnatural" in response.json()["detail"]


def test_unknown_unnatural_cause_is_rejected(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))

    response = client.post(
        f"/cases/{case.id}/death-record",
        json=record_payload(unnatural_cause="meteor"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_changing_manner_away_from_unnatural_clears_the_cause(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))
    headers = auth_headers(test_data["manager"])

    client.post(
        f"/cases/{case.id}/death-record",
        json=record_payload(unnatural_cause="suicide"),
        headers=headers,
    )

    response = client.patch(
        f"/cases/{case.id}/death-record",
        json={"manner_of_death": "natural", "forensic_status": "not_applicable"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["unnatural_cause"] is None


def test_unnatural_cause_change_is_audited(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business)
    case = make_case(db, business, make_membership(db, business, plan))
    headers = auth_headers(test_data["manager"])

    client.post(
        f"/cases/{case.id}/death-record",
        json=record_payload(),
        headers=headers,
    )
    client.patch(
        f"/cases/{case.id}/death-record",
        json={"unnatural_cause": "accident"},
        headers=headers,
    )

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "death_record.updated")
        .one()
    )

    assert log.details["changes"]["unnatural_cause"] == {
        "old": None,
        "new": "accident",
    }


def test_death_record_cause_drives_the_coverage_answer(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6, suicide=12)
    membership = make_membership(
        db, business, plan, start=date(2026, 8, 1)
    )
    case = make_case(db, business, membership)
    headers = auth_headers(test_data["manager"])

    client.post(
        f"/cases/{case.id}/death-record",
        json=record_payload(unnatural_cause="accident"),
        headers=headers,
    )
    assert coverage(client, headers, case)["covered"] is True

    client.patch(
        f"/cases/{case.id}/death-record",
        json={"unnatural_cause": "suicide"},
        headers=headers,
    )
    assert coverage(client, headers, case)["covered"] is False


# ============================================================
# CLAIMS
# ============================================================

def submit_and_review(client, headers, case, amount="10000.00"):
    claim = client.post(
        "/claims",
        json={"case_id": str(case.id), "claimed_amount": amount},
        headers=headers,
    )
    assert claim.status_code == 201, claim.text
    claim = claim.json()

    reviewed = client.post(
        f"/claims/{claim['id']}/review", headers=headers
    )
    assert reviewed.status_code == 200, reviewed.text

    return claim


def waiting_case(db, business, *, cause_known=True):
    plan = make_plan(db, business, natural=6)
    membership = make_membership(
        db, business, plan, start=date(2026, 8, 1)
    )
    case = make_case(db, business, membership)

    if cause_known:
        add_record(db, case, "natural")

    return case


def test_claim_in_waiting_period_needs_an_override(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = waiting_case(db, business)
    headers = auth_headers(test_data["manager"])
    claim = submit_and_review(client, headers, case)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "10000.00"},
        headers=headers,
    )

    assert response.status_code == 409
    assert "waiting period" in response.json()["detail"]
    assert "override" in response.json()["detail"]


def test_manager_cannot_override_a_waiting_period_without_permission(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = waiting_case(db, business)
    headers = auth_headers(test_data["manager"])
    claim = submit_and_review(client, headers, case)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "10000.00",
            "override_reason": "Family hardship",
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_main_admin_can_override_a_waiting_period_and_it_is_audited(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = waiting_case(db, business)
    headers = auth_headers(test_data["main_admin"])
    claim = submit_and_review(client, headers, case)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "10000.00",
            "override_reason": "Board approved an exception",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["override_used"] is True
    assert (
        body["decision_coverage"]["waiting_period"]["status"]
        == "in_waiting"
    )

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "claim.approved")
        .one()
    )
    assert any(
        "waiting period" in problem
        for problem in log.details["override_problems"]
    )


def test_claim_with_cause_still_pending_needs_an_override(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=0, suicide=12)
    case = make_case(db, business, make_membership(db, business, plan))
    add_record(db, case, "pending")
    headers = auth_headers(test_data["manager"])
    claim = submit_and_review(client, headers, case)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "10000.00"},
        headers=headers,
    )

    assert response.status_code == 409
    assert "cause of death" in response.json()["detail"]


def test_claim_is_approved_normally_once_cause_is_known_and_served(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    plan = make_plan(db, business, natural=6, suicide=12)
    membership = make_membership(
        db, business, plan, start=date(2025, 1, 1)
    )
    case = make_case(db, business, membership)
    add_record(db, case, "natural")
    headers = auth_headers(test_data["manager"])
    claim = submit_and_review(client, headers, case)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "10000.00"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["override_used"] is False


def test_claim_snapshot_records_the_waiting_period(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = waiting_case(db, business)
    headers = auth_headers(test_data["manager"])

    response = client.post(
        "/claims",
        json={"case_id": str(case.id), "claimed_amount": "10000.00"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    snapshot = response.json()["submission_coverage"]

    assert snapshot["covered"] is False
    assert snapshot["waiting_period"]["status"] == "in_waiting"
    assert snapshot["waiting_period"]["ends_on"] == "2027-02-01"
    assert db.query(MembershipClaim).count() == 1


def test_claim_during_upgrade_waiting_is_capped_at_the_old_plan(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    old_plan = make_plan(db, business, limit="10000.00")
    new_plan = make_plan(db, business, limit="30000.00", upgrade=6)
    membership = make_membership(
        db, business, new_plan, start=date(2025, 1, 1)
    )
    membership.previous_plan_id = old_plan.id
    membership.plan_changed_at = date(2026, 8, 1)
    db.commit()
    case = make_case(db, business, membership)
    add_record(db, case, "natural")
    headers = auth_headers(test_data["manager"])
    claim = submit_and_review(client, headers, case, "25000.00")

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "25000.00"},
        headers=headers,
    )

    assert response.status_code == 409
    assert "monetary limit of 10000.00" in response.json()["detail"]
