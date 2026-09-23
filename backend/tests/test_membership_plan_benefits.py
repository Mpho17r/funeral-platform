import uuid

from decimal import Decimal

from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit


def create_plan(db, business, name="Standard Cover"):
    plan = MembershipPlan(
        business_id=business.id,
        name=name,
        description="Standard funeral cover",
        monthly_contribution=Decimal("500.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def create_benefit(
    client,
    plan,
    headers,
    name="Funeral Cover",
    benefit_type="monetary",
    monetary_limit="15000.00",
    quantity_limit=None,
):
    payload = {
        "plan_id": str(plan.id),
        "name": name,
        "description": "Standard funeral benefit",
        "benefit_type": benefit_type,
        "monetary_limit": monetary_limit,
        "quantity_limit": quantity_limit,
        "is_included": True,
        "is_active": True,
    }

    return client.post(
        "/membership-plan-benefits",
        headers=headers,
        json=payload,
    )


def test_main_admin_can_create_monetary_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])
    response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["plan_id"] == str(plan.id)
    assert data["business_id"] == str(test_data["business_a"].id)
    assert data["name"] == "Funeral Cover"
    assert data["benefit_type"] == "monetary"
    assert Decimal(data["monetary_limit"]) == Decimal("15000.00")
    assert data["quantity_limit"] is None
    assert data["is_included"] is True
    assert data["is_active"] is True


def test_main_admin_can_create_quantity_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
        name="Covered Hearse Trips",
        benefit_type="quantity",
        monetary_limit=None,
        quantity_limit=2,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["benefit_type"] == "quantity"
    assert data["quantity_limit"] == 2
    assert data["monetary_limit"] is None


def test_included_service_benefit_can_be_created_without_limits(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
        name="Standard Coffin",
        benefit_type="included_service",
        monetary_limit=None,
        quantity_limit=None,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["benefit_type"] == "included_service"
    assert data["monetary_limit"] is None
    assert data["quantity_limit"] is None


def test_monetary_benefit_requires_monetary_limit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
        benefit_type="monetary",
        monetary_limit=None,
    )

    assert response.status_code == 422


def test_quantity_benefit_requires_quantity_limit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
        benefit_type="quantity",
        monetary_limit=None,
        quantity_limit=None,
    )

    assert response.status_code == 422


def test_invalid_benefit_type_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
        benefit_type="invalid_type",
        monetary_limit=None,
    )

    assert response.status_code == 422


def test_business_user_can_list_and_get_benefits(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    create_response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert create_response.status_code == 201

    benefit_id = create_response.json()["id"]

    list_response = client.get(
        "/membership-plan-benefits",
        headers=auth_headers(test_data["manager"]),
    )

    assert list_response.status_code == 200

    benefits = list_response.json()

    assert len(benefits) == 1
    assert benefits[0]["id"] == benefit_id

    filtered_response = client.get(
        f"/membership-plan-benefits?plan_id={plan.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert filtered_response.status_code == 200
    assert len(filtered_response.json()) == 1

    get_response = client.get(
        f"/membership-plan-benefits/{benefit_id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == benefit_id


def test_main_admin_can_update_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    create_response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert create_response.status_code == 201

    benefit_id = create_response.json()["id"]

    update_response = client.patch(
        f"/membership-plan-benefits/{benefit_id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "name": "Enhanced Funeral Cover",
            "monetary_limit": "20000.00",
        },
    )

    assert update_response.status_code == 200, update_response.text

    data = update_response.json()

    assert data["name"] == "Enhanced Funeral Cover"
    assert Decimal(data["monetary_limit"]) == Decimal("20000.00")


def test_manager_cannot_create_update_or_delete_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    create_as_manager = create_benefit(
        client,
        plan,
        auth_headers(test_data["manager"]),
    )

    assert create_as_manager.status_code == 403

    create_response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert create_response.status_code == 201

    benefit_id = create_response.json()["id"]

    update_response = client.patch(
        f"/membership-plan-benefits/{benefit_id}",
        headers=auth_headers(test_data["manager"]),
        json={"name": "Not Allowed"},
    )

    assert update_response.status_code == 403

    delete_response = client.delete(
        f"/membership-plan-benefits/{benefit_id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert delete_response.status_code == 403


def test_cross_tenant_plan_cannot_be_used(
    client,
    db,
    test_data,
    auth_headers,
):
    plan_b = create_plan(
        db,
        test_data["business_b"],
        name="Other Business Plan",
    )

    response = create_benefit(
        client,
        plan_b,
        auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404


def test_other_business_cannot_access_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    create_response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert create_response.status_code == 201

    benefit_id = create_response.json()["id"]

    other_manager = auth_headers(
        test_data["other_business_manager"]
    )

    list_response = client.get(
        "/membership-plan-benefits",
        headers=other_manager,
    )

    assert list_response.status_code == 200
    assert list_response.json() == []

    get_response = client.get(
        f"/membership-plan-benefits/{benefit_id}",
        headers=other_manager,
    )

    assert get_response.status_code == 404

    update_response = client.patch(
        f"/membership-plan-benefits/{benefit_id}",
        headers=other_manager,
        json={"name": "Cross Tenant"},
    )

    assert update_response.status_code == 403

    delete_response = client.delete(
        f"/membership-plan-benefits/{benefit_id}",
        headers=other_manager,
    )

    assert delete_response.status_code == 403


def test_main_admin_can_delete_benefit(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    create_response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert create_response.status_code == 201

    benefit_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/membership-plan-benefits/{benefit_id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert delete_response.status_code == 204

    deleted = db.query(MembershipPlanBenefit).filter(
        MembershipPlanBenefit.id == uuid.UUID(benefit_id)
    ).first()

    assert deleted is None


def test_staff_can_view_benefits_but_cannot_modify_them(
    client,
    db,
    test_data,
    auth_headers,
):
    plan = create_plan(db, test_data["business_a"])

    create_response = create_benefit(
        client,
        plan,
        auth_headers(test_data["main_admin"]),
    )

    assert create_response.status_code == 201

    benefit_id = create_response.json()["id"]

    staff_headers = auth_headers(test_data["staff"])

    list_response = client.get(
        "/membership-plan-benefits",
        headers=staff_headers,
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(
        f"/membership-plan-benefits/{benefit_id}",
        headers=staff_headers,
    )

    assert get_response.status_code == 200

    update_response = client.patch(
        f"/membership-plan-benefits/{benefit_id}",
        headers=staff_headers,
        json={"name": "Not Allowed"},
    )

    assert update_response.status_code == 403

    delete_response = client.delete(
        f"/membership-plan-benefits/{benefit_id}",
        headers=staff_headers,
    )

    assert delete_response.status_code == 403
