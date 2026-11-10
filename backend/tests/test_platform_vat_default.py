"""Platform subscription VAT defaults safely when Saccharum is unregistered."""


def test_platform_pricing_defaults_to_no_vat(client, db):
    pricing = client.get("/pricing")
    assert pricing.status_code == 200
    assert pricing.json()["vat_percent"] == 0

    quote = client.get(
        "/pricing/quote?plan=funeral-beginner&staff=5&branches=1"
    ).json()
    assert quote["vat_percent"] == 0
    assert quote["vat_cents"] == 0
    assert quote["total_incl_vat_cents"] == quote["total_cents"]
