"""Global search."""

from app.models.case_contact import CaseContact
from tests.test_reports import (
    deny,
    make_case,
    make_member,
    make_membership,
    make_plan,
)


def find(client, auth_headers, user, q):
    response = client.get(
        "/search", params={"q": q}, headers=auth_headers(user)
    )
    assert response.status_code == 200
    return {g["key"]: g["items"] for g in response.json()["groups"]}


def test_finds_cases_members_and_memberships(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    admin = test_data["main_admin"]

    case = make_case(db, biz)
    case.deceased_full_name = "Nomvula Zondiwe"
    member = make_member(db, biz)
    member.first_name = "Zondiwe"
    member.phone = "082 555 0101"
    plan = make_plan(db, biz)
    membership = make_membership(db, biz, member, plan)
    db.commit()

    found = find(client, auth_headers, admin, "zondiwe")
    assert found["cases"][0]["href"] == f"/cases/{case.id}"
    assert found["members"][0]["title"].startswith("Zondiwe")
    assert found["memberships"][0]["title"] == membership.membership_number

    # Case number and phone (spaces ignored) also find things.
    assert "cases" in find(client, auth_headers, admin, case.case_number)
    assert "members" in find(client, auth_headers, admin, "0825550101")


def test_family_contact_links_to_the_funeral(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    case = make_case(db, biz)
    case.deceased_full_name = "Late Person"
    db.add(
        CaseContact(
            business_id=biz.id,
            case_id=case.id,
            contact_type="family",
            first_name="Thandiwe",
            last_name="Qwabe",
            phone="0831112222",
        )
    )
    db.commit()

    found = find(client, auth_headers, test_data["main_admin"], "qwabe")
    item = found["contacts"][0]
    assert item["href"] == f"/cases/{case.id}"
    assert "Late Person" in item["subtitle"]


def test_short_and_wildcard_queries(client, db, test_data, auth_headers):
    admin = test_data["main_admin"]
    make_case(db, test_data["business_a"])

    assert find(client, auth_headers, admin, "a") == {}
    assert find(client, auth_headers, admin, "  ") == {}
    # A typed % is a literal character, not "match everything".
    assert find(client, auth_headers, admin, "%%") == {}


def test_other_business_is_invisible(client, db, test_data, auth_headers):
    case = make_case(db, test_data["business_b"])
    case.deceased_full_name = "Secretive Neighbour"
    db.commit()

    found = find(
        client, auth_headers, test_data["main_admin"], "secretive"
    )
    assert found == {}


def test_results_follow_permissions(client, db, test_data, auth_headers):
    biz = test_data["business_a"]
    manager = test_data["manager"]
    case = make_case(db, biz)
    case.deceased_full_name = "Guarded Person"
    member = make_member(db, biz)
    member.first_name = "Guarded"
    db.commit()

    both = find(client, auth_headers, manager, "guarded")
    assert "cases" in both and "members" in both

    deny(db, manager, "cases.view")
    after = find(client, auth_headers, manager, "guarded")
    assert "cases" not in after
    assert "members" in after


def test_requires_login(client):
    assert client.get("/search", params={"q": "abc"}).status_code in (401, 403)
