from datetime import date

from app.models.member import Member


def create_member(db, business, *, member_number="MEM-001", created_at=None):
    member = Member(
        business_id=business.id,
        member_number=member_number,
        first_name="Existing",
        last_name="Member",
        id_number="9001015009087",
        date_of_birth=date(1990, 1, 1),
        phone="0712345678",
        email="existing@example.com",
        address="1 Test Street",
        join_date=date(2026, 1, 1),
        status="active",
    )

    if created_at is not None:
        member.created_at = created_at

    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def member_payload(member_number="NEW-001"):
    return {
        "member_number": member_number,
        "first_name": "New",
        "last_name": "Member",
        "id_number": "9101015009088",
        "date_of_birth": "1991-01-01",
        "phone": "0723456789",
        "email": "newmember@example.com",
        "address": "2 Test Street",
        "join_date": "2026-01-01",
        "status": "active",
    }


def test_create_member_trims_fields_and_defaults_join_date(
    client,
    test_data,
    auth_headers,
):
    payload = member_payload("  NEW-TRIM-001  ")
    payload.pop("join_date")

    payload["first_name"] = "  New  "
    payload["last_name"] = "  Member  "

    response = client.post(
        "/members",
        json=payload,
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201
    data = response.json()

    assert data["member_number"] == "NEW-TRIM-001"
    assert data["first_name"] == "New"
    assert data["last_name"] == "Member"
    assert data["join_date"] == date.today().isoformat()


def test_create_member_rejects_duplicate_member_number_within_business(
    client,
    db,
    test_data,
    auth_headers,
):
    create_member(
        db,
        test_data["business_a"],
        member_number="DUP-001",
    )

    response = client.post(
        "/members",
        json=member_payload("DUP-001"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Member number already exists"


def test_same_member_number_is_allowed_in_different_businesses(
    client,
    db,
    test_data,
    auth_headers,
):
    create_member(
        db,
        test_data["business_b"],
        member_number="SHARED-001",
    )

    response = client.post(
        "/members",
        json=member_payload("SHARED-001"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201
    assert response.json()["member_number"] == "SHARED-001"
    assert response.json()["business_id"] == str(test_data["business_a"].id)


def test_create_member_rejects_invalid_status(
    client,
    test_data,
    auth_headers,
):
    payload = member_payload("INVALID-STATUS")
    payload["status"] = "not_a_real_status"

    response = client.post(
        "/members",
        json=payload,
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_list_members_is_tenant_isolated_and_ordered_newest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    older = create_member(
        db,
        test_data["business_a"],
        member_number="ORDER-OLD",
        created_at=date(2026, 1, 1),
    )
    newer = create_member(
        db,
        test_data["business_a"],
        member_number="ORDER-NEW",
        created_at=date(2026, 2, 1),
    )
    create_member(
        db,
        test_data["business_b"],
        member_number="OTHER-BUSINESS",
    )

    response = client.get(
        "/members",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    data = response.json()

    assert [item["member_number"] for item in data] == [
        "ORDER-NEW",
        "ORDER-OLD",
    ]
    assert all(
        item["business_id"] == str(test_data["business_a"].id)
        for item in data
    )
    assert data[0]["id"] == str(newer.id)
    assert data[1]["id"] == str(older.id)


def test_get_member_returns_404_for_missing_member(
    client,
    test_data,
    auth_headers,
):
    response = client.get(
        "/members/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"


def test_update_member_trims_fields_and_updates_values(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"],
        member_number="UPDATE-001",
    )

    response = client.patch(
        f"/members/{member.id}",
        json={
            "member_number": "  UPDATED-001  ",
            "first_name": "  Updated  ",
            "last_name": "  Person  ",
            "status": "arrears",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["member_number"] == "UPDATED-001"
    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Person"
    assert data["status"] == "arrears"


def test_update_member_rejects_duplicate_member_number(
    client,
    db,
    test_data,
    auth_headers,
):
    create_member(
        db,
        test_data["business_a"],
        member_number="UPDATE-DUP",
    )
    member = create_member(
        db,
        test_data["business_a"],
        member_number="UPDATE-OTHER",
    )

    response = client.patch(
        f"/members/{member.id}",
        json={
            "member_number": "UPDATE-DUP",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Member number already exists"


def test_update_member_returns_404_for_missing_member(
    client,
    test_data,
    auth_headers,
):
    response = client.patch(
        "/members/00000000-0000-0000-0000-000000000000",
        json={
            "first_name": "Missing",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"


def test_delete_member_returns_404_for_missing_member(
    client,
    test_data,
    auth_headers,
):
    response = client.delete(
        "/members/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"
