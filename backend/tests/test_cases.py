import uuid

from datetime import date
from decimal import Decimal

from app.models.covered_dependent import CoveredDependent
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_contribution import MembershipContribution
from app.models.membership_plan import MembershipPlan


def create_member(db, business, prefix="MEMBER"):
    member = Member(
        business_id=business.id,
        member_number=f"{prefix}-{uuid.uuid4().hex[:8].upper()}",
        first_name="Test",
        last_name="Member",
        id_number=f"ID-{uuid.uuid4().hex[:10].upper()}",
        date_of_birth=date(1990, 1, 1),
        phone="0712345678",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        address="Test Address",
        join_date=date(2026, 1, 1),
        status="active",
    )

    db.add(member)
    db.flush()

    return member


def create_membership(
    db,
    business,
    member,
    *,
    membership_status="active",
):
    plan = MembershipPlan(
        business_id=business.id,
        name=f"Standard Cover {uuid.uuid4().hex[:8]}",
        description="Standard funeral cover",
        monthly_contribution=Decimal("500.00"),
        is_active=True,
    )

    db.add(plan)
    db.flush()

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"MEM-{uuid.uuid4().hex[:8].upper()}",
        start_date=date(2026, 1, 1),
        status=membership_status,
        next_due_date=date(2026, 10, 1),
        lapsed_at=(
            date(2026, 9, 1)
            if membership_status == "lapsed"
            else None
        ),
    )

    db.add(membership)
    db.flush()

    return membership


def create_covered_dependent(
    db,
    business,
    membership,
    *,
    status="active",
    cover_start_date=date(2026, 1, 1),
    cover_end_date=None,
):
    dependent = CoveredDependent(
        business_id=business.id,
        membership_id=membership.id,
        first_name="Lerato",
        last_name="Mokoena",
        relationship="child",
        id_number=f"DEP-{uuid.uuid4().hex[:10].upper()}",
        date_of_birth=date(2015, 5, 10),
        phone="0712345678",
        status=status,
        cover_start_date=cover_start_date,
        cover_end_date=cover_end_date,
    )

    db.add(dependent)
    db.flush()

    return dependent


def create_uncovered_membership(
    db,
    business,
):
    member = create_member(db, business)
    membership = create_membership(db, business, member)

    contribution = MembershipContribution(
        business_id=business.id,
        membership_id=membership.id,
        contribution_period=date(2026, 10, 1),
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        due_date=date(2026, 7, 1),
        status="overdue",
        paid_at=None,
    )

    db.add(contribution)
    db.flush()

    business_cover_during_arrears = business.cover_during_arrears
    business.cover_during_arrears = False
    business.grace_period_days = 30
    business.lapse_after_days = 90

    db.flush()

    return membership, contribution, business_cover_during_arrears


# ============================================================
# PRIVATE / NON-MEMBER CASES
# ============================================================

def test_private_case_can_be_created(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    response = client.post(
        "/cases",
        json={
            "case_number": "PRIVATE-001",
            "deceased_full_name": "Private Funeral",
            "date_of_death": "2026-09-10",
            "funeral_date": "2026-09-15",
            "status": "open",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["case_number"] == "PRIVATE-001"
    assert data["membership_id"] is None
    assert data["covered_dependent_id"] is None
    assert data["business_id"] == str(business.id)


# ============================================================
# MEMBER FUNERAL
# ============================================================

def test_member_funeral_can_be_created_with_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member = create_member(db, business)
    membership = create_membership(db, business, member)

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "MEMBER-001",
            "deceased_full_name": "Test Member",
            "membership_id": str(membership.id),
            "date_of_death": "2026-09-10",
            "funeral_date": "2026-09-15",
            "status": "open",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["covered_dependent_id"] is None


# ============================================================
# COVERED DEPENDENT FUNERAL
# ============================================================

def test_dependent_funeral_requires_and_accepts_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member = create_member(db, business)
    membership = create_membership(db, business, member)

    dependent = create_covered_dependent(
        db,
        business,
        membership,
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "DEPENDENT-001",
            "deceased_full_name": "Lerato Mokoena",
            "membership_id": str(membership.id),
            "covered_dependent_id": str(dependent.id),
            "date_of_death": "2026-09-10",
            "funeral_date": "2026-09-15",
            "status": "open",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["covered_dependent_id"] == str(dependent.id)


def test_dependent_cannot_be_attached_without_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member = create_member(db, business)
    membership = create_membership(db, business, member)

    dependent = create_covered_dependent(
        db,
        business,
        membership,
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "DEPENDENT-NO-MEMBER",
            "deceased_full_name": "Lerato Mokoena",
            "covered_dependent_id": str(dependent.id),
            "date_of_death": "2026-09-10",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "A covered dependent requires a membership."
    )


# ============================================================
# DEPENDENT MUST BELONG TO SELECTED MEMBERSHIP
# ============================================================

def test_dependent_from_different_membership_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member_a = create_member(db, business, prefix="A")
    membership_a = create_membership(
        db,
        business,
        member_a,
    )

    member_b = create_member(db, business, prefix="B")
    membership_b = create_membership(
        db,
        business,
        member_b,
    )

    dependent_b = create_covered_dependent(
        db,
        business,
        membership_b,
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "WRONG-MEMBERSHIP-001",
            "deceased_full_name": "Lerato Mokoena",
            "membership_id": str(membership_a.id),
            "covered_dependent_id": str(dependent_b.id),
            "date_of_death": "2026-09-10",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Covered dependent does not belong to the selected membership"
    )


# ============================================================
# TENANT ISOLATION
# ============================================================

def test_cross_tenant_membership_cannot_be_attached_to_case(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    member_b = create_member(
        db,
        business_b,
        prefix="OTHER",
    )

    membership_b = create_membership(
        db,
        business_b,
        member_b,
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "CROSS-TENANT-001",
            "deceased_full_name": "Cross Tenant",
            "membership_id": str(membership_b.id),
            "date_of_death": "2026-09-10",
        },
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Membership not found for this business"
    )


def test_cross_tenant_dependent_cannot_be_attached_to_case(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    member_a = create_member(
        db,
        business_a,
        prefix="A",
    )

    membership_a = create_membership(
        db,
        business_a,
        member_a,
    )

    member_b = create_member(
        db,
        business_b,
        prefix="B",
    )

    membership_b = create_membership(
        db,
        business_b,
        member_b,
    )

    dependent_b = create_covered_dependent(
        db,
        business_b,
        membership_b,
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "CROSS-TENANT-DEPENDENT-001",
            "deceased_full_name": "Cross Tenant",
            "membership_id": str(membership_a.id),
            "covered_dependent_id": str(dependent_b.id),
            "date_of_death": "2026-09-10",
        },
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Covered dependent not found for this business"
    )


# ============================================================
# UNCOVERED MEMBERSHIP
# ============================================================

def test_uncovered_membership_does_not_block_case_creation(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    membership, _, original_cover_during_arrears = (
        create_uncovered_membership(
            db,
            business,
        )
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "UNCOVERED-001",
            "deceased_full_name": "Uncovered Member",
            "membership_id": str(membership.id),
            "date_of_death": "2026-10-31",
            "funeral_date": "2026-11-05",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["covered_dependent_id"] is None

    # Restore the fixture object for clarity if the session is reused.
    business.cover_during_arrears = original_cover_during_arrears


# ============================================================
# DEPENDENT COVER DATES
# ============================================================

def test_expired_dependent_can_still_have_case_recorded(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member = create_member(db, business)

    membership = create_membership(
        db,
        business,
        member,
    )

    dependent = create_covered_dependent(
        db,
        business,
        membership,
        cover_start_date=date(2026, 1, 1),
        cover_end_date=date(2026, 8, 31),
    )

    db.commit()

    response = client.post(
        "/cases",
        json={
            "case_number": "EXPIRED-DEPENDENT-001",
            "deceased_full_name": "Expired Dependent",
            "membership_id": str(membership.id),
            "covered_dependent_id": str(dependent.id),
            "date_of_death": "2026-09-10",
            "funeral_date": "2026-09-15",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["membership_id"] == str(membership.id)
    assert data["covered_dependent_id"] == str(dependent.id)


# ============================================================
# UPDATE CASE
# ============================================================

def test_case_can_be_updated_to_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member = create_member(db, business)

    membership = create_membership(
        db,
        business,
        member,
    )

    db.commit()

    create_response = client.post(
        "/cases",
        json={
            "case_number": "UPDATE-001",
            "deceased_full_name": "Update Test",
        },
        headers=auth_headers(manager),
    )

    assert create_response.status_code == 201

    case_id = create_response.json()["id"]

    update_response = client.patch(
        f"/cases/{case_id}",
        json={
            "membership_id": str(membership.id),
        },
        headers=auth_headers(manager),
    )

    assert update_response.status_code == 200, update_response.text

    data = update_response.json()

    assert data["membership_id"] == str(membership.id)


def test_case_cannot_be_updated_with_dependent_without_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member = create_member(db, business)

    membership = create_membership(
        db,
        business,
        member,
    )

    dependent = create_covered_dependent(
        db,
        business,
        membership,
    )

    db.commit()

    create_response = client.post(
        "/cases",
        json={
            "case_number": "UPDATE-DEPENDENT-001",
            "deceased_full_name": "Update Dependent",
        },
        headers=auth_headers(manager),
    )

    assert create_response.status_code == 201

    case_id = create_response.json()["id"]

    update_response = client.patch(
        f"/cases/{case_id}",
        json={
            "covered_dependent_id": str(dependent.id),
        },
        headers=auth_headers(manager),
    )

    assert update_response.status_code == 400

    assert (
        update_response.json()["detail"]
        == "A covered dependent requires a membership."
    )


def test_case_update_rejects_dependent_from_wrong_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    member_a = create_member(db, business, prefix="A")

    membership_a = create_membership(
        db,
        business,
        member_a,
    )

    member_b = create_member(db, business, prefix="B")

    membership_b = create_membership(
        db,
        business,
        member_b,
    )

    dependent_b = create_covered_dependent(
        db,
        business,
        membership_b,
    )

    db.commit()

    create_response = client.post(
        "/cases",
        json={
            "case_number": "UPDATE-WRONG-DEPENDENT-001",
            "deceased_full_name": "Update Wrong Dependent",
            "membership_id": str(membership_a.id),
        },
        headers=auth_headers(manager),
    )

    assert create_response.status_code == 201

    case_id = create_response.json()["id"]

    update_response = client.patch(
        f"/cases/{case_id}",
        json={
            "covered_dependent_id": str(dependent_b.id),
        },
        headers=auth_headers(manager),
    )

    assert update_response.status_code == 400

    assert (
        update_response.json()["detail"]
        == "Covered dependent does not belong to the selected membership"
    )


# ============================================================
# DUPLICATE CASE NUMBERS
# ============================================================

def test_duplicate_case_number_still_returns_409(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    first = client.post(
        "/cases",
        json={
            "case_number": "DUPLICATE-001",
            "deceased_full_name": "First Funeral",
        },
        headers=auth_headers(manager),
    )

    assert first.status_code == 201, first.text

    second = client.post(
        "/cases",
        json={
            "case_number": "DUPLICATE-001",
            "deceased_full_name": "Second Funeral",
        },
        headers=auth_headers(manager),
    )

    assert second.status_code == 409

    assert (
        second.json()["detail"]
        == "Case number already exists for this business"
    )
