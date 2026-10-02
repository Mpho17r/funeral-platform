from datetime import date

from app.models.membership_contribution import MembershipContribution


def create_membership(db, test_data):
    from app.models.member import Member
    from app.models.membership import Membership
    from app.models.membership_plan import MembershipPlan

    member = Member(
        business_id=test_data["business_a"].id,
        member_number="MEM-TEST-001",
        first_name="Test",
        last_name="Member",
        join_date=date(2027, 1, 1),
        status="active",
    )

    plan = MembershipPlan(
        business_id=test_data["business_a"].id,
        name="Test Family Plan",
        description="Test membership plan",
        monthly_contribution="500.00",
        is_active=True,
    )

    db.add_all([member, plan])
    db.flush()

    membership = Membership(
        business_id=test_data["business_a"].id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number="MEMBERSHIP-TEST-001",
        start_date=date(2027, 1, 1),
        status="active",
        next_due_date=date(2027, 2, 1),
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


def create_contribution(
    client,
    membership,
    headers,
    contribution_period,
    due_date,
    amount_due="500.00",
    status="due",
):
    return client.post(
        "/membership-contributions",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_period": contribution_period,
            "amount_due": amount_due,
            "due_date": due_date,
            "status": status,
        },
    )


def test_main_admin_can_create_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-01-01",
        due_date="2020-01-15",
    )

    assert response.status_code == 201

    data = response.json()

    assert data["business_id"] == str(test_data["business_a"].id)
    assert data["membership_id"] == str(membership.id)
    assert data["contribution_period"] == "2027-01-01"
    assert data["amount_due"] == "500.00"
    assert data["amount_paid"] == "0.00"
    assert data["due_date"] == "2020-01-15"
    assert data["status"] == "overdue"


def test_future_due_date_creates_due_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-06-01",
        due_date="2099-06-15",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "due"


def test_today_due_date_creates_due_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    today = date.today().isoformat()

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-07-01",
        due_date=today,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "due"


def test_past_due_date_creates_overdue_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-08-01",
        due_date="2020-01-01",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "overdue"


def test_new_contribution_cannot_start_as_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-09-01",
        due_date="2027-09-15",
        status="paid",
    )

    assert response.status_code == 422


def test_new_contribution_cannot_start_as_partially_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-10-01",
        due_date="2027-10-15",
        status="partially_paid",
    )

    assert response.status_code == 422


def test_duplicate_contribution_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    first_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-11-01",
        due_date="2027-11-15",
    )

    assert first_response.status_code == 201

    second_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-11-01",
        due_date="2027-11-15",
    )

    assert second_response.status_code == 409


def test_business_user_can_list_contributions(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    admin_headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        admin_headers,
        contribution_period="2027-12-01",
        due_date="2027-12-15",
    )

    assert create_response.status_code == 201

    staff_headers = auth_headers(test_data["staff"])

    response = client.get(
        "/membership-contributions",
        headers=staff_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_main_admin_can_update_amount_due_and_due_date(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2028-01-01",
        due_date="2028-01-15",
    )

    assert create_response.status_code == 201

    contribution_id = create_response.json()["id"]

    response = client.patch(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
        json={
            "amount_due": "750.00",
            "due_date": "2028-01-20",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["amount_due"] == "750.00"
    assert data["due_date"] == "2028-01-20"


def test_amount_due_cannot_be_lower_than_amount_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2028-02-01",
        due_date="2028-02-15",
        amount_due="500.00",
    )

    assert create_response.status_code == 201

    contribution_id = create_response.json()["id"]

    from app.models.membership_payment import MembershipPayment

    payment = MembershipPayment(
        business_id=test_data["business_a"].id,
        membership_id=membership.id,
        contribution_id=contribution_id,
        amount=300,
        payment_method="cash",
        reference="TEST-AMOUNT-PAID-001",
        payment_date=date(2028, 2, 15),
    )

    db.add(payment)

    contribution = db.get(
        MembershipContribution,
        contribution_id,
    )

    contribution.amount_paid = 300
    contribution.status = "partially_paid"

    db.commit()

    response = client.patch(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
        json={
            "amount_due": "200.00",
        },
    )

    assert response.status_code == 400


def test_contribution_status_cannot_be_manually_changed(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2028-03-01",
        due_date="2028-03-15",
        amount_due="500.00",
    )

    assert create_response.status_code == 201
    contribution_id = create_response.json()["id"]

    response = client.patch(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
        json={"status": "paid"},
    )

    assert response.status_code == 422

def test_update_contribution_rejects_unknown_fields(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        "/membership-contributions/00000000-0000-0000-0000-000000000000",
        json={
            "amount_due": "250.00",
            "unsupported_field": "not allowed",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_non_main_admin_cannot_create_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["staff"])

    response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2028-04-01",
        due_date="2028-04-15",
    )

    assert response.status_code == 403


def test_business_user_cannot_access_another_business_contribution(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)

    admin_headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        admin_headers,
        contribution_period="2028-05-01",
        due_date="2028-05-15",
    )

    assert create_response.status_code == 201

    contribution_id = create_response.json()["id"]

    other_business_headers = auth_headers(
        test_data["other_business_manager"]
    )

    response = client.get(
        f"/membership-contributions/{contribution_id}",
        headers=other_business_headers,
    )

    assert response.status_code == 404


def test_contribution_status_cannot_be_manually_changed_to_partially_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-07-01",
        due_date="2027-07-01",
    )

    assert create_response.status_code == 201
    contribution_id = create_response.json()["id"]

    update_response = client.patch(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
        json={"status": "partially_paid"},
    )

    assert update_response.status_code == 422

def test_paid_contribution_cannot_become_underpaid_when_amount_due_increases(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-08-01",
        due_date="2027-08-01",
        amount_due="200.00",
    )

    assert create_response.status_code == 201

    contribution_id = create_response.json()["id"]

    payment_response = client.post(
        "/membership-payments",
        headers=headers,
        json={
            "membership_id": str(membership.id),
            "contribution_id": contribution_id,
            "amount": "200.00",
            "payment_method": "cash",
            "reference": "TEST-CONTRIBUTION-STATUS-001",
            "payment_date": "2027-08-01",
        },
    )

    assert payment_response.status_code == 201

    contribution_response = client.get(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
    )

    assert contribution_response.status_code == 200
    assert contribution_response.json()["status"] == "paid"

    update_response = client.patch(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
        json={
            "amount_due": "300.00",
        },
    )

    assert update_response.status_code == 200

    updated = update_response.json()

    assert updated["amount_due"] == "300.00"
    assert updated["amount_paid"] == "200.00"
    assert updated["status"] == "partially_paid"


def test_contribution_becomes_overdue_when_due_date_is_changed_to_past(
    client,
    db,
    test_data,
    auth_headers,
):
    membership = create_membership(db, test_data)
    headers = auth_headers(test_data["main_admin"])

    create_response = create_contribution(
        client,
        membership,
        headers,
        contribution_period="2027-09-01",
        due_date="2027-09-01",
        amount_due="200.00",
    )

    assert create_response.status_code == 201

    contribution_id = create_response.json()["id"]

    assert create_response.json()["status"] == "due"

    update_response = client.patch(
        f"/membership-contributions/{contribution_id}",
        headers=headers,
        json={
            "due_date": "2020-01-01",
        },
    )

    assert update_response.status_code == 200

    updated = update_response.json()

    assert updated["due_date"] == "2020-01-01"
    assert updated["amount_paid"] == "0.00"
    assert updated["status"] == "overdue"