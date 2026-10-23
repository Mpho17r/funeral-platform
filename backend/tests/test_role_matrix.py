"""
Who can reach what, role by role.

Each work-area role (operations, mortuary, finance) sees its own part of the
business and nothing that belongs to another team. Everyone can talk to
everyone. If this test fails after a change, someone gained or lost access
by accident.
"""

import pytest

from tests.test_workspace_groups import make_staff

ALL_ROLES = (
    "main_admin", "manager", "staff", "operations", "mortuary", "finance",
)

# endpoint -> roles that must get in (everyone else must be refused)
MUST_ACCESS = {
    "/mortuary/overview": {"main_admin", "manager", "staff", "operations", "mortuary"},
    "/mortuary/locations": {"main_admin", "manager", "staff", "operations", "mortuary"},
    "/operations/overview": set(ALL_ROLES),
    "/services": {"main_admin", "manager", "staff", "operations", "mortuary"},
    "/run-sheet": {"main_admin", "manager", "staff", "operations", "mortuary"},
    "/finance/overview": {"main_admin", "manager", "staff", "finance"},
    "/expenses": {"main_admin", "manager", "finance"},
    "/reconciliation": {"main_admin", "manager", "finance"},
    "/membership-payments": {"main_admin", "manager", "staff", "finance"},
    "/claims": {"main_admin", "manager", "staff", "finance"},
    "/members": {"main_admin", "manager", "staff", "operations", "finance"},
    "/users": {"main_admin", "manager"},
    "/audit-logs": {"main_admin", "manager"},
    "/data-export/backup-status": {"main_admin"},
}

# Open to every signed-in person: they all work together.
OPEN_TO_ALL = (
    "/chat/conversations", "/notifications", "/search?q=ab", "/tasks",
    "/groups", "/branches", "/dashboard/summary",
)


@pytest.fixture
def people(db, test_data):
    biz = test_data["business_a"]
    base = test_data["staff"]
    return {
        "main_admin": test_data["main_admin"],
        "manager": test_data["manager"],
        "staff": base,
        "operations": make_staff(db, base, biz, role="operations", name="Ops"),
        "mortuary": make_staff(db, base, biz, role="mortuary", name="Morgue"),
        "finance": make_staff(db, base, biz, role="finance", name="Money"),
    }


@pytest.mark.parametrize("endpoint", sorted(MUST_ACCESS))
def test_each_role_reaches_only_its_own_areas(
    client, people, auth_headers, endpoint
):
    for role in ALL_ROLES:
        code = client.get(endpoint, headers=auth_headers(people[role])).status_code
        if role in MUST_ACCESS[endpoint]:
            assert code == 200, f"{role} should reach {endpoint}, got {code}"
        else:
            assert code == 403, f"{role} should be refused {endpoint}, got {code}"


@pytest.mark.parametrize("endpoint", OPEN_TO_ALL)
def test_shared_tools_work_for_everyone(client, people, auth_headers, endpoint):
    for role in ALL_ROLES:
        code = client.get(endpoint, headers=auth_headers(people[role])).status_code
        assert code == 200, f"{role} should reach {endpoint}, got {code}"


def test_everyone_is_in_the_whole_organization_group_and_can_post(
    client, people, auth_headers
):
    org_id = None
    for role in ALL_ROLES:
        groups = [
            c for c in client.get(
                "/chat/conversations", headers=auth_headers(people[role])
            ).json()
            if c["scope"] == "organization"
        ]
        assert len(groups) == 1, f"{role} is missing from the organization group"
        org_id = org_id or groups[0]["id"]
        assert groups[0]["id"] == org_id

        sent = client.post(
            f"/chat/conversations/{org_id}/messages",
            json={"body": f"Hello from {role}"},
            headers=auth_headers(people[role]),
        )
        assert sent.status_code == 201, f"{role} cannot post: {sent.text}"


def test_work_area_roles_only_manage_their_own_money_and_mortuary(
    client, people, auth_headers
):
    """Reading is not the same as changing: check the write side too."""
    expense = {
        "category": "other", "description": "x", "amount": "10.00",
        "expense_date": "2026-01-01", "payment_method": "cash",
    }
    for role, expected in (
        ("finance", 201), ("operations", 403), ("mortuary", 403), ("staff", 403),
    ):
        r = client.post("/expenses", json=expense, headers=auth_headers(people[role]))
        assert r.status_code == expected, f"{role} POST /expenses -> {r.status_code}"

    location = {"name": "Cold room A", "kind": "cold_room", "capacity": 4}
    for role, expected in (
        ("mortuary", 201), ("finance", 403), ("operations", 403),
    ):
        r = client.post(
            "/mortuary/locations", json=location, headers=auth_headers(people[role])
        )
        assert r.status_code in (expected, 409), f"{role} POST location -> {r.status_code}"
        if expected == 403:
            assert r.status_code == 403
