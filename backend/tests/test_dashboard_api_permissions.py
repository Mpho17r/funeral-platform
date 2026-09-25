from app.models.permission import Permission
from app.models.user_permission import UserPermission


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


# ============================================================
# DASHBOARD VIEW
# ============================================================

def test_staff_with_dashboard_view_can_access_dashboard(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text


def test_staff_without_dashboard_view_cannot_access_dashboard(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    permission = (
        db.query(Permission)
        .filter(Permission.key == "dashboard.view")
        .first()
    )

    assert permission is not None

    user_permission = UserPermission(
        user_id=staff.id,
        permission_id=permission.id,
        effect="deny",
    )

    db.add(user_permission)
    db.commit()

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: dashboard.view"
    )


def test_explicit_dashboard_deny_overrides_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    deny_permission(
        db,
        staff.id,
        "dashboard.view",
    )

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: dashboard.view"
    )


def test_main_admin_can_access_dashboard_without_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    admin = test_data["main_admin"]

    response = client.get(
        "/dashboard/summary",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text
