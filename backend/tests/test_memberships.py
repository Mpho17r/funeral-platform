from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan


def create_member_and_plan(db, business, *, plan_active=True):
    member = Member(
        business_id=business.id,
        member_number=f"BEHAV-M-{uuid4().hex[:8]}",
        first_name="Behavior",
        last_name="Test",
        join_date=date(2026, 1, 1),
        status="active",
    )
    plan = MembershipPlan(
        business_id=business.id,
        name=f"Behavior Plan {uuid4().hex[:8]}",
        monthly_contribution=Decimal("250.00"),
        is_active=plan_active,
    )
    db.add_all([member, plan])
    db.flush()
    return member, plan


def create_membership(db, business, *, member=None, plan=None, status="active"):
    if member is None or plan is None:
        member, plan = create_member_and_plan(db, business)

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"BEHAV-MS-{uuid4().hex[:8]}",
        start_date=date(2026, 1, 1),
        status=status,
        next_due_date=date(2026, 2, 1),
    )
    db.add(membership)
    db.flush()
    return membership


def membership_payload(member, plan, **overrides):
    payload = {
        "member_id": str(member.id),
        "plan_id": str(plan.id),
        "membership_number": f"NEW-MS-{uuid4().hex[:8]}",
        "start_date": "2026-09-15",
    }
    payload.update(overrides)
    return payload


def test_create_membership_persists_expected_fields(
    client, db, test_data, auth_headers
):
    member, plan = create_member_and_plan(
        db, test_data["business_a"]
    )
    db.commit()

    payload = membership_payload(
        member,
        plan,
        membership_number="  MEM-001  ",
        start_date="2026-09-15",
        next_due_date="2026-10-15",
    )

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json=payload,
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["business_id"] == str(test_data["business_a"].id)
    assert data["member_id"] == str(member.id)
    assert data["plan_id"] == str(plan.id)
    assert data["membership_number"] == "MEM-001"
    assert data["start_date"] == "2026-09-15"
    assert data["status"] == "active"
    assert data["next_due_date"] == "2026-10-15"

    membership = db.query(Membership).filter(
        Membership.id == data["id"]
    ).one()

    assert membership.membership_number == "MEM-001"
    assert membership.status == "active"


def test_create_membership_calculates_december_next_due_date(
    client, db, test_data, auth_headers
):
    member, plan = create_member_and_plan(
        db, test_data["business_a"]
    )
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json=membership_payload(
            member,
            plan,
            start_date="2026-12-31",
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["next_due_date"] == "2027-01-31"


def test_create_membership_calculates_leap_year_next_due_date(
    client, db, test_data, auth_headers
):
    member, plan = create_member_and_plan(
        db, test_data["business_a"]
    )
    db.commit()

    response = client.post(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
        json=membership_payload(
            member,
            plan,
            start_date="2028-01-31",
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["next_due_date"] == "2028-02-29"


def test_list_memberships_is_business_scoped_and_newest_first(
    client, db, test_data, auth_headers
):
    older = create_membership(db, test_data["business_a"])
    db.commit()

    newer = create_membership(db, test_data["business_a"])
    foreign = create_membership(db, test_data["business_b"])
    db.commit()

    response = client.get(
        "/memberships",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]

    assert ids[:2] == [str(newer.id), str(older.id)]
    assert str(foreign.id) not in ids


def test_get_membership_returns_existing_membership(
    client, db, test_data, auth_headers
):
    membership = create_membership(
        db, test_data["business_a"]
    )
    db.commit()

    response = client.get(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(membership.id)


def test_get_membership_returns_404_for_missing_membership(
    client, test_data, auth_headers
):
    response = client.get(
        f"/memberships/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership not found"


def test_update_membership_supports_partial_updates_and_trimming(
    client, db, test_data, auth_headers
):
    membership = create_membership(
        db, test_data["business_a"]
    )
    original_start_date = membership.start_date
    original_plan_id = membership.plan_id
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "membership_number": "  UPDATED-MS  ",
            "next_due_date": "2026-12-20",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["membership_number"] == "UPDATED-MS"
    assert data["next_due_date"] == "2026-12-20"
    assert data["start_date"] == str(original_start_date)
    assert data["plan_id"] == str(original_plan_id)


def test_update_membership_can_change_to_active_plan(
    client, db, test_data, auth_headers
):
    membership = create_membership(
        db, test_data["business_a"]
    )
    _, new_plan = create_member_and_plan(
        db, test_data["business_a"]
    )
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={"plan_id": str(new_plan.id)},
    )

    assert response.status_code == 200, response.text
    assert response.json()["plan_id"] == str(new_plan.id)


def test_update_membership_returns_404_for_missing_membership(
    client, test_data, auth_headers
):
    response = client.patch(
        f"/memberships/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
        json={"next_due_date": "2026-12-01"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership not found"


def test_update_membership_rejects_unknown_fields(
    client, db, test_data, auth_headers
):
    membership = create_membership(
        db, test_data["business_a"]
    )
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={"unexpected_field": "value"},
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "unexpected_field"
        for error in response.json()["detail"]
    )


def test_update_membership_rejects_null_plan_id(
    client, db, test_data, auth_headers
):
    membership = create_membership(
        db, test_data["business_a"]
    )
    db.commit()

    response = client.patch(
        f"/memberships/{membership.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={"plan_id": None},
    )

    assert response.status_code == 422


def test_cancel_membership_from_arrears_clears_lifecycle_fields(
    client, db, test_data, auth_headers
):
    membership = create_membership(
        db,
        test_data["business_a"],
        status="arrears",
    )
    membership.arrears_since = date(2026, 8, 1)
    db.commit()

    response = client.post(
        f"/memberships/{membership.id}/cancel",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "cancelled"
    assert data["cancelled_at"] == date.today().isoformat()
    assert data["arrears_since"] is None
    assert data["lapsed_at"] is None
