from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from app.config import settings
from app.models.business import Business
from app.models.user import User
from app.security import create_access_token, hash_password


def make_token(
    *,
    user_id,
    business_id,
    role="staff",
    auth_type="business_user",
    expires_delta=timedelta(minutes=60),
    include_user_id=True,
    include_business_id=True,
    include_role=True,
    include_auth_type=True,
):
    payload = {
        "exp": datetime.now(timezone.utc) + expires_delta,
    }

    if include_user_id:
        payload["sub"] = str(user_id)

    if include_business_id:
        payload["business_id"] = str(business_id)

    if include_role:
        payload["role"] = role

    if include_auth_type:
        payload["auth_type"] = auth_type

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def test_login_returns_access_token(client, test_data):
    user = test_data["staff"]

    response = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": test_data["password"],
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_rejects_invalid_password(client, test_data):
    user = test_data["staff"]

    response = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_inactive_user(client, db, test_data):
    user = test_data["staff"]
    user.is_active = False
    db.commit()

    response = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": test_data["password"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


def test_auth_me_accepts_valid_token(client, test_data):
    user = test_data["staff"]

    token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"] == str(user.id)
    assert body["business_id"] == str(user.business_id)
    assert body["role"] == "staff"
    assert body["auth_type"] == "business_user"


def test_auth_me_requires_authentication(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_auth_me_rejects_tampered_token(client, test_data):
    user = test_data["staff"]

    token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
    )

    header, payload, signature = token.split(".")

    import base64
    import json

    padding = "=" * (-len(payload) % 4)
    decoded_payload = json.loads(
        base64.urlsafe_b64decode(payload + padding)
    )

    decoded_payload["role"] = "main_admin"

    tampered_payload = base64.urlsafe_b64encode(
        json.dumps(
            decoded_payload,
            separators=(",", ":"),
        ).encode()
    ).decode().rstrip("=")

    tampered_token = f"{header}.{tampered_payload}.{signature}"

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token"


def test_auth_me_rejects_expired_token(client, test_data):
    user = test_data["staff"]

    token = make_token(
        user_id=user.id,
        business_id=user.business_id,
        role=user.role,
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_auth_me_rejects_wrong_authentication_layer(client, test_data):
    user = test_data["staff"]

    token = make_token(
        user_id=user.id,
        business_id=user.business_id,
        role=user.role,
        auth_type="platform_admin",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication layer"


def test_auth_me_rejects_token_with_missing_required_claim(
    client,
    test_data,
):
    user = test_data["staff"]

    token = make_token(
        user_id=user.id,
        business_id=user.business_id,
        role=user.role,
        include_role=False,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token"


def test_auth_me_rejects_nonexistent_user(client, test_data):
    token = make_token(
        user_id=uuid4(),
        business_id=test_data["business_a"].id,
        role="staff",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User account not found"


def test_auth_me_rejects_user_business_mismatch(client, test_data):
    user = test_data["staff"]

    token = make_token(
        user_id=user.id,
        business_id=test_data["business_b"].id,
        role="staff",
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User account not found"


def test_auth_me_rejects_deactivated_user_even_with_old_token(
    client,
    db,
    test_data,
):
    user = test_data["staff"]

    token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
    )

    user.is_active = False
    db.commit()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


def test_auth_me_uses_current_database_role_after_role_change(
    client,
    db,
    test_data,
):
    user = test_data["staff"]

    token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role="staff",
    )

    user.role = "manager"
    db.commit()

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "manager"


def test_registration_creates_main_admin(client):
    email = f"new-owner-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "business_name": "New Funeral Business",
            "business_phone": "0123456789",
            "business_email": "business@example.com",
            "business_address": "Johannesburg",
            "full_name": "New Business Owner",
            "email": email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 201

    token = response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["role"] == "main_admin"


def test_registration_does_not_allow_role_injection(client):
    email = f"injected-role-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "business_name": "Role Injection Business",
            "full_name": "Injected User",
            "email": email,
            "password": "TestPassword123!",
            "role": "staff",
        },
    )

    assert response.status_code == 201

    token = response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["role"] == "main_admin"


def test_registration_does_not_allow_business_id_injection(
    client,
    test_data,
):
    email = f"injected-business-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "business_name": "Injected Business ID Test",
            "full_name": "Injected User",
            "email": email,
            "password": "TestPassword123!",
            "business_id": str(test_data["business_b"].id),
        },
    )

    assert response.status_code == 201

    token = response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["business_id"] != str(
        test_data["business_b"].id
    )


def test_registration_rejects_duplicate_email(
    client,
    test_data,
):
    response = client.post(
        "/auth/register",
        json={
            "business_name": "Duplicate Email Business",
            "full_name": "Duplicate Email User",
            "email": test_data["staff"].email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"
