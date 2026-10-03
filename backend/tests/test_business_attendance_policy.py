def test_main_admin_can_update_attendance_policy(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/businesses/{business.id}/attendance-policy",
        headers=headers,
        json={
            "tea_break_minutes": 20,
            "lunch_break_minutes": 45,
            "idle_timeout_minutes": 10,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["tea_break_minutes"] == 20
    assert data["lunch_break_minutes"] == 45
    assert data["idle_timeout_minutes"] == 10


def test_attendance_policy_defaults_are_returned(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    response = client.get(
        f"/businesses/{business.id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["tea_break_minutes"] == 15
    assert data["lunch_break_minutes"] == 60
    assert data["idle_timeout_minutes"] == 15


def test_non_manager_cannot_update_attendance_policy(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["staff"])

    response = client.patch(
        f"/businesses/{business.id}/attendance-policy",
        headers=headers,
        json={
            "tea_break_minutes": 20,
            "lunch_break_minutes": 45,
            "idle_timeout_minutes": 10,
        },
    )

    assert response.status_code == 403


def test_attendance_policy_is_tenant_scoped(
    client,
    test_data,
    auth_headers,
):
    other_business = test_data["business_b"]
    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/businesses/{other_business.id}/attendance-policy",
        headers=headers,
        json={
            "tea_break_minutes": 20,
            "lunch_break_minutes": 45,
            "idle_timeout_minutes": 10,
        },
    )

    assert response.status_code == 403


def test_invalid_attendance_policy_is_rejected(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/businesses/{business.id}/attendance-policy",
        headers=headers,
        json={
            "tea_break_minutes": -1,
            "lunch_break_minutes": 45,
            "idle_timeout_minutes": 10,
        },
    )

    assert response.status_code == 422


def test_attendance_policy_upper_limit_is_enforced(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/businesses/{business.id}/attendance-policy",
        headers=headers,
        json={
            "tea_break_minutes": 481,
            "lunch_break_minutes": 60,
            "idle_timeout_minutes": 15,
        },
    )

    assert response.status_code == 422
