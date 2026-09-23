from uuid import uuid4

from app.models.audit_log import AuditLog


def test_main_admin_can_update_own_business_branding(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=headers,
        json={
            "logo_url": "[https://example.com/logo-a.png](https://example.com/logo-a.png)",
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "watermark_url": "[https://example.com/watermark-a.png](https://example.com/watermark-a.png)",
            "watermark_opacity": 0.08,
            "theme_preference": "dark",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["logo_url"] == "[https://example.com/logo-a.png](https://example.com/logo-a.png)"
    assert data["primary_color"] == "#123456"
    assert data["secondary_color"] == "#abcdef"
    assert data["watermark_url"] == "[https://example.com/watermark-a.png](https://example.com/watermark-a.png)"
    assert data["watermark_opacity"] == 0.08
    assert data["theme_preference"] == "dark"


def test_business_branding_is_returned_by_get_business(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    update_response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=headers,
        json={
            "logo_url": "[https://example.com/logo.png](https://example.com/logo.png)",
            "primary_color": "#111111",
            "secondary_color": "#222222",
            "watermark_url": "[https://example.com/watermark.png](https://example.com/watermark.png)",
            "watermark_opacity": 0.05,
            "theme_preference": "light",
        },
    )

    assert update_response.status_code == 200

    response = client.get(
        f"/businesses/{business.id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["primary_color"] == "#111111"
    assert data["secondary_color"] == "#222222"
    assert data["watermark_url"] == "[https://example.com/watermark.png](https://example.com/watermark.png)"
    assert data["watermark_opacity"] == 0.05
    assert data["theme_preference"] == "light"


def test_main_admin_cannot_update_another_business_branding(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    other_business = test_data["business_b"]

    response = client.patch(
        f"/businesses/{other_business.id}/branding",
        headers=headers,
        json={
            "logo_url": "[https://example.com/hacked.png](https://example.com/hacked.png)",
            "primary_color": "#ff0000",
            "secondary_color": "#00ff00",
            "watermark_url": "[https://example.com/hacked-watermark.png](https://example.com/hacked-watermark.png)",
            "watermark_opacity": 0.5,
            "theme_preference": "dark",
        },
    )

    assert response.status_code == 403


def test_manager_cannot_update_business_branding(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["manager"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=headers,
        json={
            "logo_url": "[https://example.com/logo.png](https://example.com/logo.png)",
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "watermark_url": None,
            "watermark_opacity": 0.05,
            "theme_preference": "system",
        },
    )

    assert response.status_code == 403


def test_staff_cannot_update_business_branding(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["staff"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=headers,
        json={
            "logo_url": "[https://example.com/logo.png](https://example.com/logo.png)",
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "watermark_url": None,
            "watermark_opacity": 0.05,
            "theme_preference": "system",
        },
    )

    assert response.status_code == 403


def test_branding_opacity_must_be_between_zero_and_one(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        headers=headers,
        json={
            "logo_url": None,
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "watermark_url": None,
            "watermark_opacity": 1.5,
            "theme_preference": "system",
        },
    )

    assert response.status_code == 422


# ============================================================
# MEMBERSHIP COVER POLICY
# ============================================================


def test_main_admin_can_update_own_membership_cover_policy(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 14,
            "cover_during_arrears": False,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["grace_period_days"] == 14
    assert data["cover_during_arrears"] is False
    assert data["lapse_after_days"] == 60
    assert data["reinstatement_policy"] == "manual"


def test_membership_cover_policy_is_returned_by_get_business(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    update_response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 21,
            "cover_during_arrears": True,
            "lapse_after_days": 90,
            "reinstatement_policy": "automatic",
        },
    )

    assert update_response.status_code == 200

    response = client.get(
        f"/businesses/{business.id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["grace_period_days"] == 21
    assert data["cover_during_arrears"] is True
    assert data["lapse_after_days"] == 90
    assert data["reinstatement_policy"] == "automatic"


def test_main_admin_cannot_update_another_business_membership_cover_policy(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    other_business = test_data["business_b"]

    response = client.patch(
        f"/businesses/{other_business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 14,
            "cover_during_arrears": False,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 403


def test_manager_cannot_update_membership_cover_policy(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["manager"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 14,
            "cover_during_arrears": False,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 403


def test_staff_cannot_update_membership_cover_policy(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["staff"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 14,
            "cover_during_arrears": False,
            "lapse_after_days": 60,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 403


def test_lapse_period_cannot_be_less_than_grace_period(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 30,
            "cover_during_arrears": False,
            "lapse_after_days": 29,
            "reinstatement_policy": "automatic",
        },
    )

    assert response.status_code == 422


def test_reinstatement_policy_must_be_valid(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 30,
            "cover_during_arrears": True,
            "lapse_after_days": 90,
            "reinstatement_policy": "invalid_policy",
        },
    )

    assert response.status_code == 422


def test_membership_cover_policy_creates_audit_log(
    client,
    test_data,
    auth_headers,
    db,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    previous_policy = {
        "grace_period_days": business.grace_period_days,
        "cover_during_arrears": business.cover_during_arrears,
        "lapse_after_days": business.lapse_after_days,
        "reinstatement_policy": business.reinstatement_policy,
    }

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 10,
            "cover_during_arrears": False,
            "lapse_after_days": 45,
            "reinstatement_policy": "manual",
        },
    )

    assert response.status_code == 200

    db.expire_all()

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == business.id,
            AuditLog.action == "business.cover_policy_updated",
            AuditLog.entity_type == "business",
            AuditLog.entity_id == business.id,
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )

    assert audit_log is not None

    assert audit_log.user_id == test_data["main_admin"].id

    assert audit_log.details["previous"] == previous_policy

    assert audit_log.details["new"] == {
        "grace_period_days": 10,
        "cover_during_arrears": False,
        "lapse_after_days": 45,
        "reinstatement_policy": "manual",
    }

    assert audit_log.notes == (
        "Membership cover policy updated by Main Admin."
    )


def test_membership_cover_policy_does_not_create_audit_log_for_rejected_request(
    client,
    test_data,
    auth_headers,
    db,
):
    headers = auth_headers(test_data["main_admin"])
    business = test_data["business_a"]

    before_count = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == business.id,
            AuditLog.action == "business.cover_policy_updated",
        )
        .count()
    )

    response = client.patch(
        f"/businesses/{business.id}/cover-policy",
        headers=headers,
        json={
            "grace_period_days": 60,
            "cover_during_arrears": False,
            "lapse_after_days": 30,
            "reinstatement_policy": "automatic",
        },
    )

    assert response.status_code == 422

    after_count = (
        db.query(AuditLog)
        .filter(
            AuditLog.business_id == business.id,
            AuditLog.action == "business.cover_policy_updated",
        )
        .count()
    )

    assert after_count == before_count
