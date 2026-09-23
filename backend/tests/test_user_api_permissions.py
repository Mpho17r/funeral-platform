def test_main_admin_can_list_users(client, test_data, auth_headers):
    headers = auth_headers(test_data["main_admin"])

    response = client.get("/users", headers=headers)

    assert response.status_code == 200


def test_manager_can_list_users(client, test_data, auth_headers):
    headers = auth_headers(test_data["manager"])

    response = client.get("/users", headers=headers)

    assert response.status_code == 200


def test_staff_cannot_list_users(client, test_data, auth_headers):
    headers = auth_headers(test_data["staff"])

    response = client.get("/users", headers=headers)

    assert response.status_code == 403


def test_main_admin_can_create_manager(client, test_data, auth_headers):
    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/users",
        headers=headers,
        json={
            "full_name": "Created Manager",
            "email": "created-manager@example.com",
            "password": "TestPassword123!",
            "role": "manager",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "manager"


def test_main_admin_can_create_staff(client, test_data, auth_headers):
    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/users",
        headers=headers,
        json={
            "full_name": "Created Staff",
            "email": "created-staff@example.com",
            "password": "TestPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "staff"


def test_manager_can_create_staff(client, test_data, auth_headers):
    headers = auth_headers(test_data["manager"])

    response = client.post(
        "/users",
        headers=headers,
        json={
            "full_name": "Manager Created Staff",
            "email": "manager-created-staff@example.com",
            "password": "TestPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "staff"


def test_manager_cannot_create_manager(client, test_data, auth_headers):
    headers = auth_headers(test_data["manager"])

    response = client.post(
        "/users",
        headers=headers,
        json={
            "full_name": "Unauthorized Manager",
            "email": "unauthorized-manager@example.com",
            "password": "TestPassword123!",
            "role": "manager",
        },
    )

    assert response.status_code == 403


def test_staff_cannot_create_user(client, test_data, auth_headers):
    headers = auth_headers(test_data["staff"])

    response = client.post(
        "/users",
        headers=headers,
        json={
            "full_name": "Unauthorized User",
            "email": "unauthorized-user@example.com",
            "password": "TestPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 403


def test_manager_cannot_access_other_business_user(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["manager"])

    response = client.get(
        f"/users/{test_data['other_business_manager'].id}",
        headers=headers,
    )

    assert response.status_code == 404


def test_manager_cannot_modify_main_admin(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/users/{test_data['main_admin'].id}",
        headers=headers,
        json={
            "full_name": "Unauthorized Change",
        },
    )

    assert response.status_code == 403


def test_main_admin_cannot_modify_another_main_admin(
    client,
    db,
    test_data,
    auth_headers,
):
    from app.models.user import User
    from app.security import hash_password

    second_admin = User(
        business_id=test_data["business_a"].id,
        full_name="Second Main Admin",
        email="second-main-admin-unique@example.com",
        password_hash=hash_password("TestPassword123!"),
        role="main_admin",
        is_active=True,
    )

    db.add(second_admin)
    db.commit()
    db.refresh(second_admin)

    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/users/{second_admin.id}",
        headers=headers,
        json={
            "full_name": "Unauthorized Admin Change",
        },
    )

    assert response.status_code == 403

def test_main_admin_cannot_change_own_role(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/users/{test_data['main_admin'].id}",
        headers=headers,
        json={
            "role": "manager",
        },
    )

    assert response.status_code == 400


def test_main_admin_cannot_deactivate_self(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])

    response = client.patch(
        f"/users/{test_data['main_admin'].id}",
        headers=headers,
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 400
