"""Name, job title and branch shown for the signed-in user."""

from app.models.audit_log import AuditLog
from app.models.user import User


def create_user(client, headers, **extra):
    body = {
        "full_name": "Thandi Jones",
        "email": "thandi.jones@example.com",
        "password": "TestPassword123!",
        "role": "manager",
    }
    body.update(extra)

    return client.post("/users", headers=headers, json=body)


# ============================================================
# /auth/me
# ============================================================

def test_me_returns_name_email_and_title(
    client, db, test_data, auth_headers
):
    user = test_data["manager"]
    user.job_title = "Operations Manager"
    db.commit()

    response = client.get(
        "/auth/me", headers=auth_headers(user)
    )

    assert response.status_code == 200
    body = response.json()

    assert body["full_name"] == user.full_name
    assert body["email"] == user.email
    assert body["job_title"] == "Operations Manager"
    assert body["role"] == "manager"


def test_me_keeps_the_token_details_other_screens_rely_on(
    client, test_data, auth_headers
):
    user = test_data["main_admin"]

    body = client.get(
        "/auth/me", headers=auth_headers(user)
    ).json()

    assert body["user_id"] == str(user.id)
    assert body["business_id"] == str(user.business_id)
    assert body["auth_type"] == "business_user"
    assert body["role"] == "main_admin"


def test_me_job_title_is_empty_until_set(
    client, test_data, auth_headers
):
    body = client.get(
        "/auth/me", headers=auth_headers(test_data["staff"])
    ).json()

    assert body["job_title"] is None


def test_me_names_the_branch(client, db, test_data, auth_headers):
    from app.services.branch_service import create_main_branch

    user = test_data["manager"]
    branch = create_main_branch(db, user.business_id)
    user.branch_id = branch.id
    db.commit()

    body = client.get(
        "/auth/me", headers=auth_headers(user)
    ).json()

    assert body["branch_id"] == str(branch.id)
    assert body["branch_name"] == branch.name


def test_me_without_a_branch_has_no_branch_name(
    client, test_data, auth_headers
):
    body = client.get(
        "/auth/me", headers=auth_headers(test_data["staff"])
    ).json()

    assert body["branch_name"] is None


def test_me_requires_sign_in(client):
    assert client.get("/auth/me").status_code in (401, 403)


# ============================================================
# CREATE AND EDIT
# ============================================================

def test_admin_sets_a_job_title_when_creating_a_user(
    client, test_data, auth_headers
):
    response = create_user(
        client,
        auth_headers(test_data["main_admin"]),
        job_title="  Operations   Manager ",
    )

    assert response.status_code == 201, response.text
    # Tidied: trimmed and single-spaced.
    assert response.json()["job_title"] == "Operations Manager"


def test_a_user_can_be_created_without_a_title(
    client, test_data, auth_headers
):
    response = create_user(
        client, auth_headers(test_data["main_admin"])
    )

    assert response.status_code == 201
    assert response.json()["job_title"] is None


def test_blank_title_is_stored_as_empty(
    client, test_data, auth_headers
):
    response = create_user(
        client,
        auth_headers(test_data["main_admin"]),
        job_title="   ",
    )

    assert response.status_code == 201
    assert response.json()["job_title"] is None


def test_title_longer_than_100_characters_is_rejected(
    client, test_data, auth_headers
):
    response = create_user(
        client,
        auth_headers(test_data["main_admin"]),
        job_title="x" * 101,
    )

    assert response.status_code == 422


def test_admin_changes_and_clears_a_title(
    client, db, test_data, auth_headers
):
    headers = auth_headers(test_data["main_admin"])
    staff = test_data["staff"]

    changed = client.patch(
        f"/users/{staff.id}",
        headers=headers,
        json={"job_title": "Funeral Director"},
    )

    assert changed.status_code == 200, changed.text
    assert changed.json()["job_title"] == "Funeral Director"

    # An edit that does not mention the title leaves it alone.
    other = client.patch(
        f"/users/{staff.id}",
        headers=headers,
        json={"full_name": "Renamed Staff"},
    )

    assert other.json()["job_title"] == "Funeral Director"

    cleared = client.patch(
        f"/users/{staff.id}",
        headers=headers,
        json={"job_title": None},
    )

    assert cleared.status_code == 200
    assert cleared.json()["job_title"] is None


def test_a_user_can_set_their_own_title(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]

    response = client.patch(
        f"/users/{manager.id}",
        headers=auth_headers(manager),
        json={"job_title": "Branch Lead"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["job_title"] == "Branch Lead"

    me = client.get(
        "/auth/me", headers=auth_headers(manager)
    ).json()

    assert me["job_title"] == "Branch Lead"


def test_changing_a_title_does_not_change_the_role(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]

    client.patch(
        f"/users/{staff.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={"job_title": "Owner"},
    )

    db.expire_all()

    assert db.get(User, staff.id).role == "staff"


def test_staff_cannot_set_someone_elses_title(
    client, test_data, auth_headers
):
    response = client.patch(
        f"/users/{test_data['manager'].id}",
        headers=auth_headers(test_data["staff"]),
        json={"job_title": "Boss"},
    )

    assert response.status_code == 403


def test_users_list_includes_titles(
    client, test_data, auth_headers
):
    headers = auth_headers(test_data["main_admin"])
    create_user(client, headers, job_title="Driver Supervisor")

    users = client.get("/users", headers=headers).json()

    assert "Driver Supervisor" in [
        item["job_title"] for item in users
    ]


# ============================================================
# AUDIT
# ============================================================

def test_title_change_is_in_the_audit_trail(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]

    client.patch(
        f"/users/{staff.id}",
        headers=auth_headers(test_data["main_admin"]),
        json={"job_title": "Embalmer"},
    )

    entries = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "user",
            AuditLog.entity_id == staff.id,
        )
        .all()
    )

    assert entries
    assert "Embalmer" in str(
        [entry.details for entry in entries]
    )
