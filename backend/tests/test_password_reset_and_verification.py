import re
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.auth_token import AuthToken
from app.models.user import User
from app.security import create_access_token, verify_password
from app.services import account_tokens, message_delivery

PASSWORD = "TestPassword123!"
NEW_PASSWORD = "BrandNewPassw0rd!"


@pytest.fixture
def outbox(monkeypatch):
    """Collect the emails the app would send, instead of sending them."""
    sent = []

    def fake_deliver(to, subject, body, *, link_text=None):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(account_tokens, "deliver", fake_deliver)
    return sent


def token_from(email) -> str:
    match = re.search(r"#token=(\S+)", email["body"])
    assert match, "the email has no link"
    return match.group(1)


def forgot(client, email):
    return client.post("/auth/forgot-password", json={"email": email})


def reset(client, token, password=NEW_PASSWORD):
    return client.post(
        "/auth/reset-password", json={"token": token, "new_password": password}
    )


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def fresh(db, user):
    db.expire_all()
    return db.get(User, user.id)


def audits(db, action):
    return db.query(AuditLog).filter(AuditLog.action == action).all()


# ============================================================
# FORGOT PASSWORD
# ============================================================

def test_unknown_email_gets_the_same_answer_and_nothing_is_sent(
    client, db, outbox
):
    known = forgot(client, "nobody-here@example.com")

    assert known.status_code == 202
    assert outbox == []
    assert db.query(AuthToken).count() == 0
    assert known.json()["message"].startswith("If an account uses that email")


def test_known_email_gets_the_same_answer_and_one_email(client, test_data, outbox):
    user = test_data["staff"]

    unknown = forgot(client, "nobody-here@example.com").json()
    response = forgot(client, user.email)

    assert response.status_code == 202
    assert response.json() == unknown
    assert len(outbox) == 1
    assert outbox[0]["to"] == user.email
    assert "#token=" in outbox[0]["body"]
    assert "/reset-password#token=" in outbox[0]["body"]


def test_email_is_matched_ignoring_capitals(client, test_data, outbox):
    forgot(client, test_data["staff"].email.upper())

    assert len(outbox) == 1


def test_only_a_hash_of_the_token_is_stored(client, db, test_data, outbox):
    forgot(client, test_data["staff"].email)
    raw = token_from(outbox[0])

    stored = db.query(AuthToken).one()

    assert raw not in (stored.token_hash, stored.purpose)
    assert len(stored.token_hash) == 64


def test_an_inactive_account_is_not_emailed(client, db, test_data, outbox):
    user = test_data["staff"]
    user.is_active = False
    db.commit()

    response = forgot(client, user.email)

    assert response.status_code == 202
    assert outbox == []


def test_one_account_cannot_be_flooded(client, test_data, outbox):
    for _ in range(6):
        assert forgot(client, test_data["staff"].email).status_code == 202

    assert len(outbox) == account_tokens.MAX_RESET_EMAILS_PER_HOUR


def test_asking_again_cancels_the_earlier_link(client, test_data, outbox):
    forgot(client, test_data["staff"].email)
    forgot(client, test_data["staff"].email)

    first, second = token_from(outbox[0]), token_from(outbox[1])

    assert reset(client, first).status_code == 400
    assert reset(client, second).status_code == 200


# ============================================================
# RESET
# ============================================================

def test_reset_changes_the_password(client, db, test_data, outbox):
    user = test_data["staff"]
    forgot(client, user.email)

    response = reset(client, token_from(outbox[0]))

    assert response.status_code == 200
    assert login(client, user.email, NEW_PASSWORD).status_code == 200
    assert login(client, user.email, PASSWORD).status_code == 401


def test_a_link_works_once(client, test_data, outbox):
    forgot(client, test_data["staff"].email)
    token = token_from(outbox[0])

    assert reset(client, token).status_code == 200
    assert reset(client, token, "AnotherPassw0rd!").status_code == 400


def test_an_expired_link_is_refused(client, db, test_data, outbox):
    forgot(client, test_data["staff"].email)
    token = token_from(outbox[0])
    row = db.query(AuthToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    response = reset(client, token)

    assert response.status_code == 400
    assert login(client, test_data["staff"].email, PASSWORD).status_code == 200


def test_a_made_up_link_is_refused(client):
    assert reset(client, "x" * 43).status_code == 400


def test_a_verification_link_cannot_reset_a_password(client, db, test_data, outbox):
    user = test_data["staff"]
    raw = account_tokens.issue(db, user, account_tokens.VERIFY)
    db.commit()

    assert reset(client, raw).status_code == 400


def test_a_short_new_password_is_refused(client, test_data, outbox):
    forgot(client, test_data["staff"].email)

    assert reset(client, token_from(outbox[0]), "short").status_code == 422


def test_reset_ends_earlier_sessions(client, db, test_data, outbox):
    user = test_data["staff"]
    old = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
        auth_type="business_user",
    )
    payload = jwt.decode(
        old, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    payload["iat"] -= 3600
    old = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    headers = {"Authorization": f"Bearer {old}"}

    assert client.get("/auth/me", headers=headers).status_code == 200

    forgot(client, user.email)
    reset(client, token_from(outbox[0]))

    assert client.get("/auth/me", headers=headers).status_code == 401


def test_reset_lifts_a_lock_and_confirms_the_email(client, db, test_data, outbox):
    user = test_data["staff"]
    user.failed_login_count = 5
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
    db.commit()
    forgot(client, user.email)

    reset(client, token_from(outbox[0]))
    user = fresh(db, user)

    assert user.locked_until is None
    assert user.failed_login_count == 0
    assert user.email_verified_at is not None
    assert verify_password(NEW_PASSWORD, user.password_hash)


def test_reset_is_recorded_and_the_person_is_told(client, db, test_data, outbox):
    forgot(client, test_data["staff"].email)

    reset(client, token_from(outbox[0]))

    assert len(audits(db, "auth.password_reset_by_email")) == 1
    assert outbox[-1]["subject"] == "Your LINDA password was changed"
    assert NEW_PASSWORD not in outbox[-1]["body"]


def test_a_person_deactivated_after_asking_cannot_reset(client, db, test_data, outbox):
    user = test_data["staff"]
    forgot(client, user.email)
    token = token_from(outbox[0])
    user.is_active = False
    db.commit()

    assert reset(client, token).status_code == 400


# ============================================================
# EMAIL VERIFICATION
# ============================================================

def register(client, email="owner-new@example.com"):
    return client.post(
        "/auth/register",
        json={
            "business_name": "Verify Traders",
            "business_type": "general",
            "full_name": "New Owner",
            "email": email,
            "password": PASSWORD,
        },
    )


def test_registering_sends_a_confirmation_email(client, db, outbox):
    response = register(client)

    assert response.status_code == 201
    assert len(outbox) == 1
    assert outbox[0]["to"] == "owner-new@example.com"
    assert "/verify-email#token=" in outbox[0]["body"]


def test_a_new_owner_starts_unverified_and_the_link_verifies(client, db, outbox):
    registration = register(client)
    assert registration.status_code == 201
    assert registration.json()["verification_required"] is True
    assert "access_token" not in registration.json()

    email = registration.json()["email"]
    owner = db.query(User).filter(User.email == email).one()
    assert owner.email_verified_at is None
    assert login(client, email, PASSWORD).status_code == 403

    response = client.post(
        "/auth/verify-email", json={"token": token_from(outbox[0])}
    )

    assert response.status_code == 200
    signed_in = login(client, email, PASSWORD)
    assert signed_in.status_code == 200
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["email_verified"] is True
    assert len(audits(db, "auth.email_verified")) == 1


def test_a_verification_link_works_once(client, outbox):
    register(client)
    token = token_from(outbox[0])

    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400


def test_a_link_for_an_old_address_proves_nothing(client, db, outbox):
    register(client)
    token = token_from(outbox[0])
    user = db.query(User).filter(User.email == "owner-new@example.com").one()
    user.email = "someone-else@example.com"
    db.commit()

    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400


def test_a_reset_link_cannot_verify_an_email(client, db, test_data, outbox):
    forgot(client, test_data["staff"].email)

    response = client.post(
        "/auth/verify-email", json={"token": token_from(outbox[0])}
    )

    assert response.status_code == 400


def test_an_administrator_adding_staff_sends_them_a_confirmation(
    client, test_data, auth_headers, outbox
):
    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Fresh Hire",
            "email": "fresh.hire@example.com",
            "password": PASSWORD,
            "role": "staff",
        },
    )

    assert response.status_code == 201, response.text
    assert [m["to"] for m in outbox] == ["fresh.hire@example.com"]
    assert outbox[0]["subject"] == "You have been invited to LINDA"
    assert "/accept-invitation#token=" in outbox[0]["body"]


def test_resend_sends_a_new_link_when_email_is_set_up(
    client, db, test_data, outbox, monkeypatch
):
    monkeypatch.setattr(message_delivery, "email_configured", lambda: True)
    user = test_data["staff"]
    user.email_verified_at = None
    db.commit()

    response = client.post(
        "/auth/resend-verification", json={"email": user.email}
    )

    assert response.status_code == 202
    assert "If the account exists" in response.json()["message"]
    assert len(outbox) == 1
    assert "/verify-email#token=" in outbox[0]["body"]


def test_resend_says_so_when_email_is_not_set_up(
    client, test_data, outbox, monkeypatch
):
    monkeypatch.setattr(message_delivery, "email_configured", lambda: False)

    response = client.post(
        "/auth/resend-verification", json={"email": test_data["staff"].email}
    )

    assert response.status_code == 202
    assert "If the account exists" in response.json()["message"]
    assert outbox == []


def test_resend_does_nothing_for_someone_already_verified(
    client, db, test_data, outbox, monkeypatch
):
    monkeypatch.setattr(message_delivery, "email_configured", lambda: True)
    user = test_data["staff"]
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()

    response = client.post(
        "/auth/resend-verification", json={"email": user.email}
    )

    assert response.status_code == 202
    assert "If the account exists" in response.json()["message"]
    assert outbox == []


def test_resend_is_limited(
    client, db, test_data, outbox, monkeypatch
):
    monkeypatch.setattr(message_delivery, "email_configured", lambda: True)
    user = test_data["staff"]
    user.email_verified_at = None
    db.commit()
    codes = [
        client.post(
            "/auth/resend-verification", json={"email": user.email}
        ).status_code
        for _ in range(account_tokens.MAX_VERIFY_EMAILS_PER_HOUR + 2)
    ]

    assert codes == [202] * len(codes)
    assert len(outbox) == account_tokens.MAX_VERIFY_EMAILS_PER_HOUR


def test_resend_requires_an_email_address(client):
    assert client.post("/auth/resend-verification").status_code == 422


def test_invited_team_member_sets_their_own_password(
    client, db, test_data, auth_headers, outbox
):
    response = client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "Invited Colleague",
            "email": "invite.accept@example.com",
            "role": "staff",
        },
    )
    assert response.status_code == 201
    invited = db.query(User).filter(
        User.email == "invite.accept@example.com"
    ).one()
    assert invited.email_verified_at is None
    assert login(client, invited.email, PASSWORD).status_code == 401

    accepted = client.post(
        "/auth/accept-invitation",
        json={
            "token": token_from(outbox[-1]),
            "new_password": NEW_PASSWORD,
        },
    )
    assert accepted.status_code == 200
    assert invited.email_verified_at is not None
    assert login(client, invited.email, NEW_PASSWORD).status_code == 200


def test_team_invitation_token_cannot_be_reused(
    client, test_data, auth_headers, outbox
):
    client.post(
        "/users",
        headers=auth_headers(test_data["main_admin"]),
        json={
            "full_name": "One Time Invite",
            "email": "one.time@example.com",
            "role": "staff",
        },
    )
    token = token_from(outbox[-1])
    first = client.post(
        "/auth/accept-invitation",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    second = client.post(
        "/auth/accept-invitation",
        json={"token": token, "new_password": "OtherPassw0rd!"},
    )
    assert first.status_code == 200
    assert second.status_code == 400
