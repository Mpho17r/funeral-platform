"""Turning the membership scheme off hides it; turning it on restores it."""


def access(client, auth_headers, user):
    return client.get("/users/me/access", headers=auth_headers(user)).json()


def test_membership_can_be_switched_off_and_on(
    client, auth_headers, test_data
):
    admin = test_data["main_admin"]
    biz = test_data["business_a"].id

    before = access(client, auth_headers, admin)
    assert before["membership_enabled"] is True
    assert "memberships.view" in before["permissions"]

    r = client.patch(
        f"/businesses/{biz}/membership",
        json={"membership_enabled": False},
        headers=auth_headers(admin),
    )
    assert r.status_code == 200
    assert r.json()["membership_enabled"] is False

    off = access(client, auth_headers, admin)
    assert off["membership_enabled"] is False
    for key in ("memberships.view", "claims.view", "members.view"):
        assert key not in off["permissions"]
    # The funeral side is untouched.
    assert "cases.view" in off["permissions"]
    assert client.get("/memberships", headers=auth_headers(admin)).status_code == 403

    client.patch(
        f"/businesses/{biz}/membership",
        json={"membership_enabled": True},
        headers=auth_headers(admin),
    )
    assert "memberships.view" in access(client, auth_headers, admin)["permissions"]


def test_only_the_main_admin_can_switch_membership(
    client, auth_headers, test_data
):
    biz = test_data["business_a"].id
    r = client.patch(
        f"/businesses/{biz}/membership",
        json={"membership_enabled": False},
        headers=auth_headers(test_data["manager"]),
    )
    assert r.status_code == 403
