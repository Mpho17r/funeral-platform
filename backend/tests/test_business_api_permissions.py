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


# ---------------------------------------------------------------------------
# BRANDING
# ---------------------------------------------------------------------------

def test_staff_with_branding_permission_can_update_branding(
    client, db, test_data, auth_headers
):
    grant_permission(db, "staff", "branding.manage")

    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=auth_headers(staff),
        json={
            "primary_color": "#123456",
            "secondary_color": "#654321",
            "watermark_opacity": 0.5,
            "theme_preference": "light",
        },
    )

    assert response.status_code == 200
    assert response.json()["primary_color"] == "#123456"


def test_staff_without_branding_permission_cannot_update_branding(
    client, test_data, auth_headers
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=auth_headers(staff),
        json={
            "primary_color": "#123456",
            "secondary_color": "#654321",
            "watermark_opacity": 0.5,
            "theme_preference": "light",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: branding.manage"
    )


def test_explicit_user_deny_overrides_branding_role_permission(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    grant_permission(db, "staff", "branding.manage")
    deny_permission(db, staff.id, "branding.manage")

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=auth_headers(staff),
        json={
            "primary_color": "#123456",
            "secondary_color": "#654321",
            "watermark_opacity": 0.5,
            "theme_preference": "light",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: branding.manage"
    )


def test_main_admin_can_update_branding_without_explicit_permission(
    client, test_data, auth_headers
):
    admin = test_data["main_admin"]
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=auth_headers(admin),
        json={
            "primary_color": "#abcdef",
            "secondary_color": "#fedcba",
            "watermark_opacity": 0.4,
            "theme_preference": "dark",
        },
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# COVER POLICY / SETTINGS
# ---------------------------------------------------------------------------

def test_staff_with_settings_permission_can_update_cover_policy(
    client, db, test_data, auth_headers
):
    grant_permission(db, "staff", "settings.manage")

    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=auth_headers(staff),
        json={
            "grace_period_days": 30,
            "cover_during_arrears": True,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 200


def test_staff_without_settings_permission_cannot_update_cover_policy(
    client, test_data, auth_headers
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=auth_headers(staff),
        json={
            "grace_period_days": 30,
            "cover_during_arrears": True,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: settings.manage"
    )


def test_explicit_user_deny_overrides_settings_role_permission(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    grant_permission(db, "staff", "settings.manage")
    deny_permission(db, staff.id, "settings.manage")

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=auth_headers(staff),
        json={
            "grace_period_days": 30,
            "cover_during_arrears": True,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: settings.manage"
    )


def test_main_admin_can_update_cover_policy_without_explicit_permission(
    client, test_data, auth_headers
):
    admin = test_data["main_admin"]
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=auth_headers(admin),
        json={
            "grace_period_days": 30,
            "cover_during_arrears": True,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# BRANDING FILE UPLOADS
# ---------------------------------------------------------------------------

def test_staff_with_branding_permission_can_upload_logo(
    client, db, test_data, auth_headers
):
    grant_permission(db, "staff", "branding.manage")

    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.post(
        f"/businesses/{business.id}/branding/logo",
        headers=auth_headers(staff),
        files={
            "file": (
                "logo.png",
                b"fake-logo-content",
                "image/png",
            )
        },
    )

    assert response.status_code == 200


def test_staff_without_branding_permission_cannot_upload_logo(
    client, test_data, auth_headers
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.post(
        f"/businesses/{business.id}/branding/logo",
        headers=auth_headers(staff),
        files={
            "file": (
                "logo.png",
                b"fake-logo-content",
                "image/png",
            )
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: branding.manage"
    )


def test_staff_with_branding_permission_can_upload_watermark(
    client, db, test_data, auth_headers
):
    grant_permission(db, "staff", "branding.manage")

    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.post(
        f"/businesses/{business.id}/branding/watermark",
        headers=auth_headers(staff),
        files={
            "file": (
                "watermark.png",
                b"fake-watermark-content",
                "image/png",
            )
        },
    )

    assert response.status_code == 200


def test_staff_without_branding_permission_cannot_upload_watermark(
    client, test_data, auth_headers
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    response = client.post(
        f"/businesses/{business.id}/branding/watermark",
        headers=auth_headers(staff),
        files={
            "file": (
                "watermark.png",
                b"fake-watermark-content",
                "image/png",
            )
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: branding.manage"
    )


# ---------------------------------------------------------------------------
# TENANT ISOLATION
# ---------------------------------------------------------------------------

def test_staff_cannot_update_another_business_branding(
    client, db, test_data, auth_headers
):
    grant_permission(db, "staff", "branding.manage")

    staff = test_data["staff"]
    other_business = test_data["business_b"]

    response = client.patch(
        f"/businesses/{other_business.id}/branding",
        headers=auth_headers(staff),
        json={
            "primary_color": "#123456",
            "secondary_color": "#654321",
            "watermark_opacity": 0.5,
            "theme_preference": "light",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have access to this business"
    )


def test_staff_cannot_update_another_business_cover_policy(
    client, db, test_data, auth_headers
):
    grant_permission(db, "staff", "settings.manage")

    staff = test_data["staff"]
    other_business = test_data["business_b"]

    response = client.patch(
        f"/businesses/{other_business.id}/cover-policy",
        headers=auth_headers(staff),
        json={
            "grace_period_days": 30,
            "cover_during_arrears": True,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have access to this business"
    )
