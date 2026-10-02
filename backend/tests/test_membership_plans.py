from decimal import Decimal
import uuid

from app.models.membership_plan import MembershipPlan


def create_plan(
    db,
    business,
    *,
    name="Standard Cover",
    description="Standard funeral cover",
    monthly_contribution=Decimal("250.00"),
    is_active=True,
):
    plan = MembershipPlan(
        business_id=business.id,
        name=name,
        description=description,
        monthly_contribution=monthly_contribution,
        is_active=is_active,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def test_main_admin_can_create_membership_plan(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "name": "Premium Cover",
            "description": "Premium funeral cover",
            "monthly_contribution": "450.00",
            "is_active": True,
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["business_id"] == str(test_data["business_a"].id)
    assert data["name"] == "Premium Cover"
    assert data["description"] == "Premium funeral cover"
    assert data["monthly_contribution"] == "450.00"
    assert data["is_active"] is True


def test_membership_plan_creation_applies_defaults(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "name": "Basic Cover",
            "monthly_contribution": "100.00",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["description"] is None
    assert data["monthly_contribution"] == "100.00"
    assert data["is_active"] is True


def test_membership_plan_name_is_trimmed_on_create(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "name": "  Standard Cover  ",
            "monthly_contribution": "250.00",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Standard Cover"


def test_membership_plan_rejects_negative_contribution(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "name": "Invalid Plan",
            "monthly_contribution": "-1.00",
        },
    )

    assert response.status_code == 422


def test_membership_plan_requires_name(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/membership-plans",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "monthly_contribution": "250.00",
        },
    )

    assert response.status_code == 422


def test_membership_plan_list_is_tenant_isolated_and_newest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    older = create_plan(
        db,
        test_data["business_a"],
        name="Older Plan",
    )
    newer = create_plan(
        db,
        test_data["business_a"],
        name="Newer Plan",
    )
    create_plan(
        db,
        test_data["business_b"],
        name="Other Business Plan",
    )

    response = client.get(
        "/membership-plans",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200, response.text

    plans = response.json()

    assert [plan["id"] for plan in plans] == [
        str(newer.id),
        str(older.id),
    ]
    assert all(
        plan["business_id"] == str(test_data["business_a"].id)
        for plan in plans
    )


def test_business_user_can_get_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(
        db,
        test_data["business_a"],
        name="Family Cover",
    )

    response = client.get(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(plan.id)
    assert response.json()["name"] == "Family Cover"


def test_get_nonexistent_membership_plan_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.get(
        f"/membership-plans/{uuid.uuid4()}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership plan not found"


def test_main_admin_can_partially_update_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(
        db,
        test_data["business_a"],
        name="Standard Cover",
        description="Original description",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )

    response = client.patch(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "name": "  Enhanced Cover  ",
            "monthly_contribution": "350.00",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["name"] == "Enhanced Cover"
    assert data["monthly_contribution"] == "350.00"
    assert data["description"] == "Original description"
    assert data["is_active"] is True


def test_membership_plan_update_can_clear_description(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(
        db,
        test_data["business_a"],
        description="Original description",
    )

    response = client.patch(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "description": None,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["description"] is None


def test_update_nonexistent_membership_plan_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        f"/membership-plans/{uuid.uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
        json={"name": "Updated"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Membership plan not found"


def test_main_admin_can_delete_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(
        db,
        test_data["business_a"],
        name="Temporary Plan",
    )

    response = client.delete(
        f"/membership-plans/{plan.id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 204

    deleted = (
        db.query(MembershipPlan)
        .filter(MembershipPlan.id == plan.id)
        .first()
    )

    assert deleted is None


def test_other_business_cannot_update_or_delete_membership_plan(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(
        db,
        test_data["business_a"],
        name="Private Plan",
    )

    other_headers = auth_headers(test_data["other_business_manager"])

    update_response = client.patch(
        f"/membership-plans/{plan.id}",
        headers=other_headers,
        json={"name": "Cross Tenant"},
    )

    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "Membership plan not found"

    delete_response = client.delete(
        f"/membership-plans/{plan.id}",
        headers=other_headers,
    )

    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Membership plan not found"
