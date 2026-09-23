from uuid import uuid4


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
            "logo_url": "https://example.com/logo-a.png",
            "primary_color": "#123456",
            "secondary_color": "#abcdef",
            "watermark_url": "https://example.com/watermark-a.png",
            "watermark_opacity": 0.08,
            "theme_preference": "dark",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["logo_url"] == "https://example.com/logo-a.png"
    assert data["primary_color"] == "#123456"
    assert data["secondary_color"] == "#abcdef"
    assert data["watermark_url"] == "https://example.com/watermark-a.png"
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
            "logo_url": "https://example.com/logo.png",
            "primary_color": "#111111",
            "secondary_color": "#222222",
            "watermark_url": "https://example.com/watermark.png",
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
    assert data["watermark_url"] == "https://example.com/watermark.png"
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
            "logo_url": "https://example.com/hacked.png",
            "primary_color": "#ff0000",
            "secondary_color": "#00ff00",
            "watermark_url": "https://example.com/hacked-watermark.png",
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
            "logo_url": "https://example.com/logo.png",
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
            "logo_url": "https://example.com/logo.png",
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
