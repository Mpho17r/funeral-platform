def test_main_admin_can_create_business(client, test_data, auth_headers):
    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/businesses",
        headers=headers,
        json={
            "name": "New Funeral Services",
            "slug": "new-funeral-services",
            "logo_url": "https://example.com/logo.png",
            "primary_color": "#112233",
            "secondary_color": "#445566",
            "watermark_url": "https://example.com/watermark.png",
            "watermark_opacity": 0.25,
            "theme_preference": "dark",
            "phone": "0123456789",
            "email": "info@example.com",
            "address": "123 Main Street",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["name"] == "New Funeral Services"
    assert data["slug"] == "new-funeral-services"
    assert data["logo_url"] == "https://example.com/logo.png"
    assert data["primary_color"] == "#112233"
    assert data["secondary_color"] == "#445566"
    assert data["watermark_url"] == "https://example.com/watermark.png"
    assert data["watermark_opacity"] == 0.25
    assert data["theme_preference"] == "dark"
    assert data["phone"] == "0123456789"
    assert data["email"] == "info@example.com"
    assert data["address"] == "123 Main Street"
    assert data["is_active"] is True


def test_business_creation_applies_defaults(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])

    response = client.post(
        "/businesses",
        headers=headers,
        json={
            "name": "Default Funeral Services",
            "slug": "default-funeral-services",
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["primary_color"] == "#000000"
    assert data["secondary_color"] == "#64748b"
    assert data["watermark_opacity"] == 0.05
    assert data["theme_preference"] == "system"

    assert data["logo_url"] is None
    assert data["watermark_url"] is None

    assert data["grace_period_days"] == 30
    assert data["cover_during_arrears"] is True
    assert data["lapse_after_days"] == 90
    assert data["reinstatement_policy"] == "automatic"

    assert data["is_active"] is True


def test_non_main_admin_cannot_create_business(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["manager"])

    response = client.post(
        "/businesses",
        headers=headers,
        json={
            "name": "Unauthorized Funeral Services",
            "slug": "unauthorized-funeral-services",
        },
    )

    assert response.status_code == 403


def test_duplicate_business_slug_is_rejected(
    client,
    test_data,
    auth_headers,
):
    headers = auth_headers(test_data["main_admin"])

    existing_slug = test_data["business_a"].slug

    response = client.post(
        "/businesses",
        headers=headers,
        json={
            "name": "Duplicate Slug Business",
            "slug": existing_slug,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A business with this slug already exists."


def test_main_admin_can_retrieve_own_business(
    client,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    response = client.get(
        f"/businesses/{business.id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == str(business.id)
    assert data["name"] == business.name
    assert data["slug"] == business.slug


def test_existing_logo_can_be_retrieved(
    client,
    test_data,
    auth_headers,
    monkeypatch,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    fake_logo = b"fake-logo-data"

    def fake_get_business_branding_file(business_id, file_type):
        assert business_id == business.id
        assert file_type == "logo"

        path = __import__("pathlib").Path(
            "storage/test-logo.png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fake_logo)
        return path

    monkeypatch.setattr(
        "app.api.businesses.get_business_branding_file",
        fake_get_business_branding_file,
    )

    response = client.get(
        f"/businesses/{business.id}/branding/logo",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == fake_logo


def test_missing_logo_returns_404(
    client,
    test_data,
    auth_headers,
    monkeypatch,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    monkeypatch.setattr(
        "app.api.businesses.get_business_branding_file",
        lambda business_id, file_type: None,
    )

    response = client.get(
        f"/businesses/{business.id}/branding/logo",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Business logo not found"


def test_existing_watermark_can_be_retrieved(
    client,
    test_data,
    auth_headers,
    monkeypatch,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    fake_watermark = b"fake-watermark-data"

    def fake_get_business_branding_file(business_id, file_type):
        assert business_id == business.id
        assert file_type == "watermark"

        path = __import__("pathlib").Path(
            "storage/test-watermark.png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fake_watermark)
        return path

    monkeypatch.setattr(
        "app.api.businesses.get_business_branding_file",
        fake_get_business_branding_file,
    )

    response = client.get(
        f"/businesses/{business.id}/branding/watermark",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == fake_watermark


def test_missing_watermark_returns_404(
    client,
    test_data,
    auth_headers,
    monkeypatch,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])

    monkeypatch.setattr(
        "app.api.businesses.get_business_branding_file",
        lambda business_id, file_type: None,
    )

    response = client.get(
        f"/businesses/{business.id}/branding/watermark",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Business watermark not found"
