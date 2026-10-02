from uuid import uuid4

from app.models.user import User
from app.security import verify_password


def create_user(
    db,
    business,
    *,
    full_name="Created User",
    email=None,
    role="staff",
    is_active=True,
    password="TestPassword123!",
):
    from app.security import hash_password

    user = User(
        business_id=business.id,
        full_name=full_name,
        email=email or f"user-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# LIST USERS
# ---------------------------------------------------------------------------


def test_list_users_returns_business_users(
    client,
    test_data,
    auth_headers,
):
    response = client.get(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 3

    emails = {user["email"] for user in data}

    assert test_data["main_admin"].email in emails
    assert test_data["manager"].email in emails
    assert test_data["staff"].email in emails
    assert test_data["other_business_manager"].email not in emails


def test_list_users_is_ordered_by_created_at(
    client,
    db,
    test_data,
    auth_headers,
):
    first = create_user(
        db,
        test_data["business_a"],
        full_name="First User",
    )

    second = create_user(
        db,
        test_data["business_a"],
        full_name="Second User",
    )

    response = client.get(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    ids = [user["id"] for user in data]

    assert ids.index(str(first.id)) < ids.index(str(second.id))


# ---------------------------------------------------------------------------
# GET USER
# ---------------------------------------------------------------------------


def test_get_user_returns_expected_user(
    client,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.get(
        f"/users/{user.id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(user.id)
    assert data["business_id"] == str(test_data["business_a"].id)
    assert data["full_name"] == user.full_name
    assert data["email"] == user.email
    assert data["role"] == "staff"
    assert data["is_active"] is True


def test_get_missing_user_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.get(
        f"/users/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_get_user_from_other_business_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.get(
        f"/users/{test_data['other_business_manager'].id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# CREATE USER
# ---------------------------------------------------------------------------


def test_create_staff_user(
    client,
    db,
    test_data,
    auth_headers,
):
    email = f"new-staff-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "New Staff",
            "email": email,
            "password": "NewPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["full_name"] == "New Staff"
    assert data["email"] == email
    assert data["role"] == "staff"
    assert data["is_active"] is True
    assert data["business_id"] == str(test_data["business_a"].id)

    created = db.query(User).filter(User.email == email).first()

    assert created is not None
    assert created.password_hash != "NewPassword123!"
    assert verify_password("NewPassword123!", created.password_hash)


def test_create_manager_user(
    client,
    db,
    test_data,
    auth_headers,
):
    email = f"new-manager-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "New Manager",
            "email": email,
            "password": "NewPassword123!",
            "role": "manager",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["full_name"] == "New Manager"
    assert data["email"] == email
    assert data["role"] == "manager"
    assert data["is_active"] is True


def test_created_user_belongs_to_current_business(
    client,
    db,
    test_data,
    auth_headers,
):
    email = f"business-owned-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/users",
        headers=auth_headers(test_data["manager"]),
        json={
            "full_name": "Business Staff",
            "email": email,
            "password": "NewPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 201

    created = db.query(User).filter(User.email == email).first()

    assert created is not None
    assert created.business_id == test_data["business_a"].id


def test_create_user_defaults_to_staff_role(
    client,
    test_data,
    auth_headers,
):
    email = f"default-role-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Default Role User",
            "email": email,
            "password": "NewPassword123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "staff"


def test_create_user_rejects_duplicate_email(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Duplicate User",
            "email": test_data["staff"].email,
            "password": "NewPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_create_user_rejects_main_admin_role(
    client,
    test_data,
    auth_headers,
):
    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Invalid Admin",
            "email": f"invalid-admin-{uuid4().hex[:8]}@example.com",
            "password": "NewPassword123!",
            "role": "main_admin",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Only manager and staff accounts can be created here"
    )


# ---------------------------------------------------------------------------
# UPDATE USER
# ---------------------------------------------------------------------------


def test_update_user_full_name(
    client,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.patch(
        f"/users/{user.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Updated Staff Name",
        },
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Staff Name"


def test_update_staff_to_manager_by_main_admin(
    client,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.patch(
        f"/users/{user.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "role": "manager",
        },
    )

    assert response.status_code == 200
    assert response.json()["role"] == "manager"


def test_manager_can_update_staff_to_staff_only(
    client,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.patch(
        f"/users/{user.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "full_name": "Manager Updated Staff",
        },
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Manager Updated Staff"


def test_manager_can_deactivate_staff(
    client,
    db,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.patch(
        f"/users/{user.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    db.refresh(user)

    assert user.is_active is False


def test_main_admin_can_reactivate_staff(
    client,
    db,
    test_data,
    auth_headers,
):
    user = test_data["staff"]
    user.is_active = False
    db.commit()

    response = client.patch(
        f"/users/{user.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "is_active": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_update_user_from_other_business_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        f"/users/{test_data['other_business_manager'].id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Cross Business Change",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_main_admin_cannot_change_user_to_invalid_role(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        f"/users/{test_data['staff'].id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "role": "super_admin",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Only manager and staff roles can be assigned here"
    )


def test_main_admin_cannot_change_staff_to_main_admin(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        f"/users/{test_data['staff'].id}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "role": "main_admin",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Only manager and staff roles can be assigned here"
    )


def test_update_missing_user_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        f"/users/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Missing User",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# ---------------------------------------------------------------------------
# SELF UPDATE RULES
# ---------------------------------------------------------------------------


def test_user_can_update_own_full_name(
    client,
    db,
    test_data,
    auth_headers,
):
    from app.models.permission import Permission
    from app.models.user_permission import UserPermission

    user = test_data["staff"]

    permission = (
        db.query(Permission)
        .filter(Permission.key == "users.edit")
        .first()
    )

    assert permission is not None

    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="allow",
        )
    )
    db.commit()

    response = client.patch(
        f"/users/{user.id}",
        headers=auth_headers(user),
        json={
            "full_name": "My New Name",
        },
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "My New Name"


# ---------------------------------------------------------------------------
# DELETE / DEACTIVATE
# ---------------------------------------------------------------------------


def test_delete_user_deactivates_user(
    client,
    db,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.delete(
        f"/users/{user.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 204

    db.refresh(user)

    assert user.is_active is False


def test_deactivated_user_remains_in_database(
    client,
    db,
    test_data,
    auth_headers,
):
    user = test_data["staff"]

    response = client.delete(
        f"/users/{user.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 204

    db.refresh(user)

    assert user.id is not None
    assert user.is_active is False


def test_delete_missing_user_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.delete(
        f"/users/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_delete_other_business_user_returns_404(
    client,
    test_data,
    auth_headers,
):
    response = client.delete(
        f"/users/{test_data['other_business_manager'].id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404


def test_create_user_ignores_injected_business_id(
    client,
    db,
    test_data,
    auth_headers,
):
    email = f"injected-business-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Injected Business User",
            "email": email,
            "password": "NewPassword123!",
            "role": "staff",
            "business_id": str(test_data["business_b"].id),
        },
    )

    assert response.status_code == 201

    created = db.query(User).filter(User.email == email).first()

    assert created is not None
    assert created.business_id == test_data["business_a"].id
