import uuid
from datetime import date

from app.models.audit_log import AuditLog
from app.models.covered_dependent import CoveredDependent
from app.models.member import Member
from app.models.membership import Membership
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


def create_plan_and_membership(db, business, member, prefix="MEM"):
    plan = MembershipPlan(
        business_id=business.id,
        name="Standard Cover",
        description="Standard funeral cover",
        monthly_contribution=500,
        is_active=True,
    )
    db.add(plan)
    db.flush()

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"{prefix}-{uuid.uuid4().hex[:8].upper()}",
        start_date=date(2026, 1, 1),
        status="active",
        next_due_date=date(2026, 10, 1),
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return plan, membership


def create_dependent(client, db, business, main_admin, auth_headers):
    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    response = client.post(
        "/covered-dependents",
        json={
            "membership_id": str(membership.id),
            "first_name": "Lerato",
            "last_name": "Mokoena",
            "relationship": "child",
            "date_of_birth": "2015-05-10",
            "phone": "0712345678",
            "status": "active",
            "cover_start_date": "2026-01-01",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 201, response.text

    return response.json(), membership


def test_main_admin_can_create_covered_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]

    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    response = client.post(
        "/covered-dependents",
        json={
            "membership_id": str(membership.id),
            "first_name": "Lerato",
            "last_name": "Mokoena",
            "relationship": "child",
            "date_of_birth": "2015-05-10",
            "phone": "0712345678",
            "status": "active",
            "cover_start_date": "2026-01-01",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["first_name"] == "Lerato"
    assert data["last_name"] == "Mokoena"
    assert data["relationship"] == "child"
    assert data["status"] == "active"
    assert data["membership_id"] == str(membership.id)
    assert data["business_id"] == str(business.id)

    audit = db.query(AuditLog).filter(
        AuditLog.action == "covered_dependent.created",
        AuditLog.entity_id == uuid.UUID(data["id"]),
    ).first()

    assert audit is not None
    assert audit.entity_type == "covered_dependent"
    assert audit.details["membership_id"] == str(membership.id)
    assert audit.details["first_name"] == "Lerato"
    assert audit.details["last_name"] == "Mokoena"
    assert audit.details["relationship"] == "child"
    assert audit.details["status"] == "active"


def test_business_user_can_list_and_get_covered_dependents(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]
    manager = test_data["manager"]

    data, _ = create_dependent(
        client,
        db,
        business,
        main_admin,
        auth_headers,
    )

    dependent_id = data["id"]

    list_response = client.get(
        "/covered-dependents",
        headers=auth_headers(manager),
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == dependent_id

    get_response = client.get(
        f"/covered-dependents/{dependent_id}",
        headers=auth_headers(manager),
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == dependent_id


def test_main_admin_can_update_and_audit_covered_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]

    data, _ = create_dependent(
        client,
        db,
        business,
        main_admin,
        auth_headers,
    )

    dependent_id = data["id"]

    response = client.patch(
        f"/covered-dependents/{dependent_id}",
        json={
            "relationship": "sibling",
            "status": "removed",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["relationship"] == "sibling"
    assert data["status"] == "removed"

    audit = db.query(AuditLog).filter(
        AuditLog.action == "covered_dependent.updated",
        AuditLog.entity_id == uuid.UUID(dependent_id),
    ).order_by(AuditLog.created_at.desc()).first()

    assert audit is not None
    assert audit.details["changes"]["relationship"]["before"] == "child"
    assert audit.details["changes"]["relationship"]["after"] == "sibling"
    assert audit.details["changes"]["status"]["before"] == "active"
    assert audit.details["changes"]["status"]["after"] == "removed"


def test_main_admin_can_delete_and_audit_covered_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]

    data, _ = create_dependent(
        client,
        db,
        business,
        main_admin,
        auth_headers,
    )

    dependent_id = data["id"]

    response = client.delete(
        f"/covered-dependents/{dependent_id}",
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 204

    assert db.query(CoveredDependent).filter(
        CoveredDependent.id == uuid.UUID(dependent_id)
    ).first() is None

    audit = db.query(AuditLog).filter(
        AuditLog.action == "covered_dependent.deleted",
        AuditLog.entity_id == uuid.UUID(dependent_id),
    ).first()

    assert audit is not None
    assert audit.entity_type == "covered_dependent"
    assert audit.details["membership_id"] == data["membership_id"]
    assert audit.details["first_name"] == "Lerato"


def test_manager_cannot_create_update_or_delete_covered_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]
    manager = test_data["manager"]

    data, membership = create_dependent(
        client,
        db,
        business,
        main_admin,
        auth_headers,
    )

    dependent_id = data["id"]

    create_as_manager = client.post(
        "/covered-dependents",
        json={
            "membership_id": str(membership.id),
            "first_name": "Jane",
            "last_name": "Mokoena",
            "relationship": "child",
            "status": "active",
            "cover_start_date": "2026-01-01",
        },
        headers=auth_headers(manager),
    )

    assert create_as_manager.status_code == 403

    update_as_manager = client.patch(
        f"/covered-dependents/{dependent_id}",
        json={"status": "removed"},
        headers=auth_headers(manager),
    )

    assert update_as_manager.status_code == 403

    delete_as_manager = client.delete(
        f"/covered-dependents/{dependent_id}",
        headers=auth_headers(manager),
    )

    assert delete_as_manager.status_code == 403


def test_duplicate_covered_dependent_returns_409(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]

    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    payload = {
        "membership_id": str(membership.id),
        "first_name": "John",
        "last_name": "Mokoena",
        "relationship": "child",
        "date_of_birth": "2015-05-10",
        "status": "active",
        "cover_start_date": "2026-01-01",
    }

    first = client.post(
        "/covered-dependents",
        json=payload,
        headers=auth_headers(main_admin),
    )

    assert first.status_code == 201, first.text

    second = client.post(
        "/covered-dependents",
        json=payload,
        headers=auth_headers(main_admin),
    )

    assert second.status_code == 409


def test_invalid_cover_end_date_returns_400(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    main_admin = test_data["main_admin"]

    member = create_member(db, business)
    _, membership = create_plan_and_membership(db, business, member)

    response = client.post(
        "/covered-dependents",
        json={
            "membership_id": str(membership.id),
            "first_name": "John",
            "last_name": "Mokoena",
            "relationship": "child",
            "status": "active",
            "cover_start_date": "2026-06-01",
            "cover_end_date": "2026-05-01",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 400


def test_cross_tenant_membership_cannot_create_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    main_admin_a = test_data["main_admin"]

    member_b = create_member(db, business_b, prefix="OTHER")
    _, membership_b = create_plan_and_membership(
        db,
        business_b,
        member_b,
        prefix="OTHER",
    )

    response = client.post(
        "/covered-dependents",
        json={
            "membership_id": str(membership_b.id),
            "first_name": "Cross",
            "last_name": "Tenant",
            "relationship": "child",
            "status": "active",
            "cover_start_date": "2026-01-01",
        },
        headers=auth_headers(main_admin_a),
    )

    assert response.status_code == 404


def test_other_business_cannot_access_dependent(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    main_admin_a = test_data["main_admin"]
    manager_b = test_data["other_business_manager"]

    data, _ = create_dependent(
        client,
        db,
        business_a,
        main_admin_a,
        auth_headers,
    )

    dependent_id = data["id"]

    list_response = client.get(
        "/covered-dependents",
        headers=auth_headers(manager_b),
    )

    assert list_response.status_code == 200
    assert list_response.json() == []

    get_response = client.get(
        f"/covered-dependents/{dependent_id}",
        headers=auth_headers(manager_b),
    )

    assert get_response.status_code == 404

    update_response = client.patch(
        f"/covered-dependents/{dependent_id}",
        json={"status": "removed"},
        headers=auth_headers(manager_b),
    )

    assert update_response.status_code == 403

    delete_response = client.delete(
        f"/covered-dependents/{dependent_id}",
        headers=auth_headers(manager_b),
    )

    assert delete_response.status_code == 403
