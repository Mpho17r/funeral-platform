from datetime import datetime, timezone


def test_unverified_password_login_is_denied_without_token(client, test_data):
    user = test_data["main_admin"]
    user.email_verified_at = None

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": test_data["password"]},
    )

    assert response.status_code == 403
    assert "verify your email" in response.json()["detail"].lower()
    assert "access_token" not in response.json()


def test_wrong_password_does_not_reveal_verification_state(client, test_data):
    user = test_data["main_admin"]
    user.email_verified_at = None

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_existing_unverified_session_cannot_access_protected_api(
    client, db, test_data, auth_headers
):
    user = test_data["main_admin"]
    headers = auth_headers(user)

    # Simulate a session issued before email verification became mandatory.
    user.email_verified_at = None
    db.commit()

    identity = client.get("/auth/me", headers=headers)
    assert identity.status_code == 200
    assert identity.json()["email_verified"] is False

    protected = client.get("/users/me/access", headers=headers)
    assert protected.status_code == 403
    assert "verify your email" in protected.json()["detail"].lower()


def test_resend_verification_is_public_and_does_not_enumerate_accounts(client):
    known = client.post(
        "/auth/resend-verification",
        json={"email": "unknown-address@example.com"},
    )
    unknown = client.post(
        "/auth/resend-verification",
        json={"email": "another-unknown@example.com"},
    )

    assert known.status_code == 202
    assert unknown.status_code == 202
    assert known.json() == unknown.json()


def test_registration_does_not_issue_a_session_before_verification(client):
    response = client.post(
        "/auth/register",
        json={
            "business_name": "Verification Test Business",
            "business_type": "general",
            "full_name": "Verification Test Owner",
            "email": "verification-owner@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["verification_required"] is True
    assert "access_token" not in payload

    login = client.post(
        "/auth/login",
        json={
            "email": "verification-owner@example.com",
            "password": "TestPassword123!",
        },
    )
    assert login.status_code == 403
