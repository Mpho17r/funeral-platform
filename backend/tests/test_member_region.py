"""Members can be placed in a region and viewed by it."""


def make(client, headers, number, **extra):
    return client.post(
        "/members",
        json={"member_number": number, "first_name": "Zodwa",
              "last_name": "Dlamini", **extra},
        headers=headers,
    )


def test_region_is_saved_cleaned_and_returned(client, auth_headers, test_data):
    h = auth_headers(test_data["main_admin"])
    r = make(client, h, "R-1", region="  Soweto   North ")
    assert r.status_code == 201, r.text
    assert r.json()["region"] == "Soweto North"
    blank = make(client, h, "R-2", region="   ")
    assert blank.json()["region"] is None


def test_region_can_be_changed_and_listed(client, auth_headers, test_data):
    h = auth_headers(test_data["main_admin"])
    member = make(client, h, "R-3").json()
    r = client.patch(f"/members/{member['id']}", json={"region": "Polokwane"},
                     headers=h)
    assert r.status_code == 200, r.text
    rows = client.get("/members", headers=h).json()
    assert {m["id"]: m["region"] for m in rows}[member["id"]] == "Polokwane"


def test_anonymising_a_member_clears_the_region(
    client, auth_headers, db, test_data
):
    from tests.test_member_privacy import anonymise, archive, make_member

    member = make_member(db, test_data["business_a"])
    member.region = "Soweto"
    db.commit()
    assert archive(
        client, auth_headers, test_data["manager"], member
    ).status_code == 204
    r = anonymise(client, auth_headers, test_data["main_admin"], member)
    assert r.status_code == 200, r.text
    db.refresh(member)
    assert member.region is None
