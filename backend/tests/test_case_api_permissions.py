from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def grant_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            RolePermission(
                role=role,
                permission_id=permission.id,
            )
        )
        db.commit()


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )
    else:
        existing.effect = "deny"

    db.commit()


def create_case_payload(case_number="PERM-001"):
    return {
        "case_number": case_number,
        "deceased_full_name": "Permission Test Funeral",
        "date_of_death": "2026-09-10",
        "funeral_date": "2026-09-15",
        "status": "open",
    }


# ---------------------------------------------------------------------------
# VIEW
# ---------------------------------------------------------------------------

def test_staff_with_cases_view_can_list_cases(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.get(
        "/cases",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200


def test_staff_without_cases_view_cannot_list_cases(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    deny_permission(db, staff.id, "cases.view")

    response = client.get(
        "/cases",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.view"


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

def test_staff_with_cases_create_can_create_case(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/cases",
        json=create_case_payload("CREATE-001"),
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text


def test_staff_without_cases_create_cannot_create_case(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    deny_permission(db, staff.id, "cases.create")

    response = client.post(
        "/cases",
        json=create_case_payload("CREATE-002"),
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.create"


# ---------------------------------------------------------------------------
# EDIT
# ---------------------------------------------------------------------------

def test_staff_with_cases_edit_can_update_case(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    create_response = client.post(
        "/cases",
        json=create_case_payload("EDIT-001"),
        headers=auth_headers(staff),
    )
    assert create_response.status_code == 201, create_response.text

    case_id = create_response.json()["id"]

    response = client.patch(
        f"/cases/{case_id}",
        json={"deceased_full_name": "Updated Permission Test"},
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["deceased_full_name"] == "Updated Permission Test"


def test_staff_without_cases_edit_cannot_update_case(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    create_response = client.post(
        "/cases",
        json=create_case_payload("EDIT-002"),
        headers=auth_headers(staff),
    )
    assert create_response.status_code == 201, create_response.text

    case_id = create_response.json()["id"]

    deny_permission(db, staff.id, "cases.edit")

    response = client.patch(
        f"/cases/{case_id}",
        json={"deceased_full_name": "Blocked Update"},
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.edit"


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_staff_without_cases_delete_cannot_delete_case(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    create_response = client.post(
        "/cases",
        json=create_case_payload("DELETE-001"),
        headers=auth_headers(staff),
    )
    assert create_response.status_code == 201, create_response.text

    case_id = create_response.json()["id"]

    response = client.delete(
        f"/cases/{case_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.delete"


def test_manager_with_cases_delete_can_delete_case(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    create_response = client.post(
        "/cases",
        json=create_case_payload("DELETE-002"),
        headers=auth_headers(manager),
    )
    assert create_response.status_code == 201, create_response.text

    case_id = create_response.json()["id"]

    response = client.delete(
        f"/cases/{case_id}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# EXPLICIT USER DENY
# ---------------------------------------------------------------------------

def test_explicit_user_deny_overrides_cases_create_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    deny_permission(db, staff.id, "cases.create")

    response = client.post(
        "/cases",
        json=create_case_payload("DENY-001"),
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.create"


def test_explicit_user_deny_overrides_cases_edit_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    create_response = client.post(
        "/cases",
        json=create_case_payload("DENY-002"),
        headers=auth_headers(staff),
    )
    assert create_response.status_code == 201, create_response.text

    case_id = create_response.json()["id"]

    deny_permission(db, staff.id, "cases.edit")

    response = client.patch(
        f"/cases/{case_id}",
        json={"deceased_full_name": "Blocked Update"},
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.edit"


# ---------------------------------------------------------------------------
# MAIN ADMIN BYPASS
# ---------------------------------------------------------------------------

def test_main_admin_can_manage_cases_without_explicit_permissions(
    client,
    test_data,
    auth_headers,
):
    admin = test_data["main_admin"]

    create_response = client.post(
        "/cases",
        json=create_case_payload("ADMIN-001"),
        headers=auth_headers(admin),
    )
    assert create_response.status_code == 201, create_response.text

    case_id = create_response.json()["id"]

    update_response = client.patch(
        f"/cases/{case_id}",
        json={"deceased_full_name": "Admin Updated"},
        headers=auth_headers(admin),
    )
    assert update_response.status_code == 200

    delete_response = client.delete(
        f"/cases/{case_id}",
        headers=auth_headers(admin),
    )
    assert delete_response.status_code == 204
