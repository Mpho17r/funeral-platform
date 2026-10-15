from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.models.audit_log import AuditLog
from app.models.user import User
from app.security import create_access_token, hash_password


PASSWORD = "TestPassword123!"


# ============================================================
# HELPERS
# ============================================================

def login(client, user, password=PASSWORD):
    return client.post(
        "/auth/login",
        json={"email": user.email, "password": password},
    )


def fail_times(client, user, times):
    last = None

    for _ in range(times):
        last = login(client, user, "wrong-password")

    return last


def fresh(db, user):
    db.expire_all()

    return db.get(User, user.id)


def audits(db, action):
    return (
        db.query(AuditLog)
        .filter(AuditLog.action == action)
        .order_by(AuditLog.created_at)
        .all()
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# WRONG PASSWORDS
# ============================================================

def test_wrong_password_is_a_generic_401(client, test_data):
    response = login(client, test_data["staff"], "nope-nope-nope")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_unknown_email_looks_the_same_as_a_wrong_password(
    client, test_data
):
    unknown = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )
    wrong = login(client, test_data["staff"], "whatever123")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_failures_are_counted(client, db, test_data):
    staff = test_data["staff"]

    fail_times(client, staff, 2)

    assert fresh(db, staff).failed_login_count == 2
    assert fresh(db, staff).locked_until is None


def test_a_correct_password_resets_the_count(client, db, test_data):
    staff = test_data["staff"]

    fail_times(client, staff, 3)
    assert login(client, staff).status_code == 200

    user = fresh(db, staff)

    assert user.failed_login_count == 0
    assert user.last_login_at is not None


def test_failed_attempts_are_audited_without_secrets(
    client, db, test_data
):
    staff = test_data["staff"]

    fail_times(client, staff, 2)

    rows = audits(db, "auth.login_failed")

    assert len(rows) == 2
    assert rows[-1].entity_id == staff.id
    assert rows[-1].business_id == staff.business_id
    assert rows[-1].details == {"failed_attempts": 2}
    assert "wrong-password" not in str(rows[-1].details)
    assert staff.email not in str(rows[-1].details)


def test_unknown_email_writes_no_audit_row(client, db):
    client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )

    assert audits(db, "auth.login_failed") == []


def test_successful_login_is_audited(client, db, test_data):
    login(client, test_data["staff"])

    rows = audits(db, "auth.login_succeeded")

    assert len(rows) == 1
    assert rows[0].user_id == test_data["staff"].id


# ============================================================
# LOCKOUT
# ============================================================

def test_account_locks_after_the_limit(client, db, test_data):
    staff = test_data["staff"]
    limit = settings.login_max_failed_attempts

    fail_times(client, staff, limit - 1)
    last = login(client, staff, "wrong-password")

    assert last.status_code == 429
    assert "locked" in last.json()["detail"]
    assert int(last.headers["Retry-After"]) == (
        settings.login_lockout_minutes * 60
    )
    assert fresh(db, staff).locked_until is not None


def test_locking_is_audited_once(client, db, test_data):
    fail_times(client, test_data["staff"], settings.login_max_failed_attempts)

    rows = audits(db, "auth.account_locked")

    assert len(rows) == 1
    assert rows[0].details["locked_minutes"] == (
        settings.login_lockout_minutes
    )


def test_correct_password_is_refused_while_locked(client, db, test_data):
    staff = test_data["staff"]

    fail_times(client, staff, settings.login_max_failed_attempts)
    response = login(client, staff)

    assert response.status_code == 429
    assert "Try again in" in response.json()["detail"]


def test_attempts_while_locked_are_not_counted_or_logged(
    client, db, test_data
):
    staff = test_data["staff"]

    fail_times(client, staff, settings.login_max_failed_attempts)
    before = fresh(db, staff).failed_login_count
    failures = len(audits(db, "auth.login_failed"))

    fail_times(client, staff, 3)

    assert fresh(db, staff).failed_login_count == before
    assert len(audits(db, "auth.login_failed")) == failures


def test_lock_ends_by_itself(client, db, test_data):
    staff = test_data["staff"]

    fail_times(client, staff, settings.login_max_failed_attempts)

    user = fresh(db, staff)
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert login(client, staff).status_code == 200

    user = fresh(db, staff)

    assert user.locked_until is None
    assert user.failed_login_count == 0


def test_count_starts_again_after_a_lock_ends(client, db, test_data):
    staff = test_data["staff"]

    fail_times(client, staff, settings.login_max_failed_attempts)

    user = fresh(db, staff)
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert login(client, staff, "wrong-password").status_code == 401
    assert fresh(db, staff).failed_login_count == 1


def test_one_account_locking_does_not_affect_another(
    client, db, test_data
):
    fail_times(client, test_data["staff"], settings.login_max_failed_attempts)

    assert login(client, test_data["manager"]).status_code == 200


def test_minutes_are_at_least_one(client, db, test_data):
    staff = test_data["staff"]

    user = fresh(db, staff)
    user.locked_until = datetime.now(timezone.utc) + timedelta(seconds=5)
    db.commit()

    assert "1 minute" in login(client, staff).json()["detail"]


# ============================================================
# INACTIVE ACCOUNTS
# ============================================================

def test_inactive_account_with_a_wrong_password_is_generic(
    client, db, test_data
):
    staff = test_data["staff"]
    user = fresh(db, staff)
    user.is_active = False
    db.commit()

    response = login(client, staff, "wrong-password")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_inactive_account_with_the_right_password_is_told(
    client, db, test_data
):
    staff = test_data["staff"]
    user = fresh(db, staff)
    user.is_active = False
    db.commit()

    response = login(client, staff)

    assert response.status_code == 403
    assert audits(db, "auth.login_succeeded") == []


# ============================================================
# CHANGE PASSWORD
# ============================================================

def change(client, headers, current=PASSWORD, new="BrandNewPass456!"):
    return client.post(
        "/auth/change-password",
        json={"current_password": current, "new_password": new},
        headers=headers,
    )


def test_change_password_works_and_returns_a_fresh_session(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]

    response = change(client, auth_headers(staff))

    assert response.status_code == 200
    assert login(client, staff).status_code == 401
    assert login(client, staff, "BrandNewPass456!").status_code == 200
    assert client.get(
        "/auth/me", headers=bearer(response.json()["access_token"])
    ).status_code == 200


def test_change_password_ends_older_sessions(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    old_headers = auth_headers(staff)

    user = fresh(db, staff)
    user.password_changed_at = datetime.now(timezone.utc) + timedelta(
        seconds=5
    )
    db.commit()

    response = client.get("/auth/me", headers=old_headers)

    assert response.status_code == 401
    assert "session has ended" in response.json()["detail"]


def test_a_token_without_an_issue_time_is_refused_after_a_change(
    client, db, test_data
):
    staff = test_data["staff"]

    user = fresh(db, staff)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()

    token = jwt.encode(
        {
            "sub": str(staff.id),
            "auth_type": "business_user",
            "business_id": str(staff.business_id),
            "role": "staff",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert client.get("/auth/me", headers=bearer(token)).status_code == 401


def test_sessions_are_unaffected_until_a_password_change(
    client, test_data, auth_headers
):
    headers = auth_headers(test_data["staff"])

    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 200


def test_wrong_current_password_is_refused_and_counted(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    headers = auth_headers(staff)

    response = change(client, headers, current="not-my-password")

    assert response.status_code == 400
    assert fresh(db, staff).failed_login_count == 1
    assert len(audits(db, "auth.password_change_failed")) == 1
    # The password did not change.
    assert login(client, staff).status_code == 200


def test_repeated_wrong_current_passwords_lock_the_account(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    headers = auth_headers(staff)

    for _ in range(settings.login_max_failed_attempts):
        change(client, headers, current="not-my-password")

    assert fresh(db, staff).locked_until is not None
    assert change(client, headers).status_code == 429


def test_new_password_must_differ_from_the_current_one(
    client, test_data, auth_headers
):
    response = change(
        client, auth_headers(test_data["staff"]), new=PASSWORD
    )

    assert response.status_code == 400


def test_new_password_has_a_minimum_length(
    client, test_data, auth_headers
):
    response = change(
        client, auth_headers(test_data["staff"]), new="short"
    )

    assert response.status_code == 422


def test_change_password_needs_a_session(client):
    response = client.post(
        "/auth/change-password",
        json={"current_password": "a", "new_password": "BrandNewPass456!"},
    )

    assert response.status_code in (401, 403)


def test_change_password_is_audited_without_the_password(
    client, db, test_data, auth_headers
):
    change(client, auth_headers(test_data["staff"]))

    rows = audits(db, "auth.password_changed")

    assert len(rows) == 1
    assert rows[0].details is None
    assert "BrandNewPass456" not in str(rows[0].__dict__)


# ============================================================
# UNLOCK AND RESET
# ============================================================

def lock(client, user):
    fail_times(client, user, settings.login_max_failed_attempts)


def test_manager_can_unlock_staff(client, db, test_data, auth_headers):
    staff = test_data["staff"]

    lock(client, staff)

    response = client.post(
        f"/users/{staff.id}/unlock",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json()["locked_until"] is None
    assert login(client, staff).status_code == 200
    assert len(audits(db, "user.unlocked")) == 1


def test_staff_cannot_unlock_anyone(client, test_data, auth_headers):
    response = client.post(
        f"/users/{test_data['manager'].id}/unlock",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_manager_cannot_unlock_another_manager_or_the_admin(
    client, test_data, auth_headers
):
    headers = auth_headers(test_data["manager"])

    assert client.post(
        f"/users/{test_data['main_admin'].id}/unlock", headers=headers
    ).status_code == 403


def test_unlock_stays_inside_the_business(
    client, test_data, auth_headers
):
    response = client.post(
        f"/users/{test_data['other_business_manager'].id}/unlock",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404


def test_users_list_shows_who_is_locked(
    client, test_data, auth_headers
):
    lock(client, test_data["staff"])

    rows = client.get(
        "/users", headers=auth_headers(test_data["manager"])
    ).json()

    staff = next(
        row for row in rows if row["id"] == str(test_data["staff"].id)
    )

    assert staff["locked_until"] is not None
    assert "password_hash" not in staff


def test_reset_password_lets_the_person_in_with_the_new_one(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]

    lock(client, staff)

    response = client.post(
        f"/users/{staff.id}/reset-password",
        json={"new_password": "ResetByManager789!"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert login(client, staff).status_code == 401
    assert login(client, staff, "ResetByManager789!").status_code == 200
    assert len(audits(db, "user.password_reset")) == 1


def test_reset_password_ends_the_persons_sessions(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    staff_headers = auth_headers(staff)

    user = fresh(db, staff)
    user.password_changed_at = None
    db.commit()

    # Make sure the reset lands after the token was issued.
    token = create_access_token(
        user_id=str(staff.id),
        business_id=str(staff.business_id),
        role="staff",
    )
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )

    user = fresh(db, staff)
    user.password_changed_at = datetime.fromtimestamp(
        payload["iat"] + 2, tz=timezone.utc
    )
    db.commit()

    assert client.get("/auth/me", headers=bearer(token)).status_code == 401
    assert client.get("/auth/me", headers=staff_headers).status_code == 401


def test_reset_password_is_audited_without_the_password(
    client, db, test_data, auth_headers
):
    client.post(
        f"/users/{test_data['staff'].id}/reset-password",
        json={"new_password": "ResetByManager789!"},
        headers=auth_headers(test_data["manager"]),
    )

    row = audits(db, "user.password_reset")[0]

    assert row.details is None
    assert row.user_id == test_data["manager"].id
    assert row.entity_id == test_data["staff"].id


def test_reset_password_rules(client, test_data, auth_headers):
    manager_headers = auth_headers(test_data["manager"])

    assert client.post(
        f"/users/{test_data['manager'].id}/reset-password",
        json={"new_password": "ResetByManager789!"},
        headers=manager_headers,
    ).status_code == 400

    assert client.post(
        f"/users/{test_data['main_admin'].id}/reset-password",
        json={"new_password": "ResetByManager789!"},
        headers=manager_headers,
    ).status_code == 403

    assert client.post(
        f"/users/{test_data['staff'].id}/reset-password",
        json={"new_password": "short"},
        headers=manager_headers,
    ).status_code == 422

    assert client.post(
        f"/users/{test_data['staff'].id}/reset-password",
        json={"new_password": "ResetByManager789!"},
        headers=auth_headers(test_data["staff"]),
    ).status_code == 403


# ============================================================
# USER AUDIT
# ============================================================

def test_creating_a_user_is_audited(client, db, test_data, auth_headers):
    response = client.post(
        "/users",
        json={
            "full_name": "New Person",
            "email": "new.person@example.com",
            "password": "NewPersonPass123!",
            "role": "staff",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201

    row = audits(db, "user.created")[0]

    assert str(row.entity_id) == response.json()["id"]
    assert row.user_id == test_data["manager"].id
    assert row.details["role"] == "staff"
    assert "new.person" not in str(row.details)
    assert "NewPersonPass" not in str(row.details)


def test_new_user_password_needs_eight_characters(
    client, test_data, auth_headers
):
    response = client.post(
        "/users",
        json={
            "full_name": "New Person",
            "email": "short.pass@example.com",
            "password": "short",
            "role": "staff",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_role_change_is_audited(client, db, test_data, auth_headers):
    response = client.patch(
        f"/users/{test_data['staff'].id}",
        json={"role": "manager"},
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    row = audits(db, "user.role_changed")[0]

    assert row.details["changes"]["role"] == {
        "old": "staff",
        "new": "manager",
    }


def test_deactivation_and_reactivation_are_audited(
    client, db, test_data, auth_headers
):
    headers = auth_headers(test_data["manager"])
    url = f"/users/{test_data['staff'].id}"

    client.patch(url, json={"is_active": False}, headers=headers)
    client.patch(url, json={"is_active": True}, headers=headers)

    assert len(audits(db, "user.deactivated")) == 1
    assert len(audits(db, "user.reactivated")) == 1


def test_delete_endpoint_audits_a_deactivation(
    client, db, test_data, auth_headers
):
    response = client.delete(
        f"/users/{test_data['staff'].id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 204
    assert len(audits(db, "user.deactivated")) == 1


def test_a_name_change_is_audited_as_an_update(
    client, db, test_data, auth_headers
):
    client.patch(
        f"/users/{test_data['staff'].id}",
        json={"full_name": "Renamed Person"},
        headers=auth_headers(test_data["manager"]),
    )

    row = audits(db, "user.updated")[0]

    assert row.details["changes"]["full_name"]["new"] == "Renamed Person"


def test_an_update_that_changes_nothing_writes_no_audit_row(
    client, db, test_data, auth_headers
):
    client.patch(
        f"/users/{test_data['staff'].id}",
        json={"full_name": test_data["staff"].full_name},
        headers=auth_headers(test_data["manager"]),
    )

    assert audits(db, "user.updated") == []


def test_updating_your_own_name_is_audited(
    client, db, test_data, auth_headers
):
    response = client.patch(
        f"/users/{test_data['manager'].id}",
        json={"full_name": "My New Name"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    row = audits(db, "user.updated")[0]

    assert row.user_id == test_data["manager"].id
    assert row.entity_id == test_data["manager"].id
