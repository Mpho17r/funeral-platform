import uuid

from datetime import datetime, timezone

from sqlalchemy import text as sqlalchemy_text

from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase
from app.models.user_permission import UserPermission


def create_case(db, business, case_number):
    case = FuneralCase(
        business_id=business.id,
        case_number=case_number,
        deceased_full_name=f"Deceased {case_number}",
        date_of_death=datetime(2026, 9, 10, tzinfo=timezone.utc),
        funeral_date=datetime(2026, 9, 15, tzinfo=timezone.utc),
        status="open",
    )
    db.add(case)
    db.flush()
    return case


def create_contact(
    db,
    business,
    case,
    *,
    contact_type="family",
    first_name="Test",
    last_name="Contact",
    relationship="sibling",
):
    contact = CaseContact(
        business_id=business.id,
        case_id=case.id,
        contact_type=contact_type,
        first_name=first_name,
        last_name=last_name,
        phone="0712345678",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        relationship=relationship,
        organization="Test Organization",
        address="Test Address",
        notes="Test Notes",
    )


    db.add(contact)
    db.flush()
    return contact


def test_staff_can_list_families(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business, "FAMILY-001")
    create_contact(
        db,
        business,
        case,
        first_name="Lerato",
        last_name="Mokoena",
    )
    db.commit()

    response = client.get(
        "/families",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 1
    assert data[0]["case_id"] == str(case.id)
    assert data[0]["case_number"] == "FAMILY-001"
    assert data[0]["deceased_full_name"] == "Deceased FAMILY-001"
    assert data[0]["member_count"] == 1
    assert data[0]["members"][0]["first_name"] == "Lerato"
    assert data[0]["members"][0]["last_name"] == "Mokoena"


def test_manager_can_list_families(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business, "FAMILY-002")
    create_contact(db, business, case)
    db.commit()

    response = client.get(
        "/families",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_families_view_permission_is_required(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business, "FAMILY-003")
    create_contact(db, business, case)
    db.commit()

    response = client.get(
        "/families",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text

    permission = db.execute(
        sqlalchemy_text(
            """
            SELECT id
            FROM permissions
            WHERE key = 'families.view'
            """
        )
    ).scalar_one()


    db.add(
        UserPermission(
            user_id=staff.id,
            permission_id=permission,
            effect="deny",
        )
    )
    db.commit()

    response = client.get(
        "/families",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403, response.text


def test_families_are_grouped_by_case_and_member_count_is_correct(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case_one = create_case(db, business, "FAMILY-004")
    case_two = create_case(db, business, "FAMILY-005")

    create_contact(
        db,
        business,
        case_one,
        first_name="First",
        last_name="Member",
    )
    create_contact(
        db,
        business,
        case_one,
        first_name="Second",
        last_name="Member",
    )
    create_contact(
        db,
        business,
        case_two,
        first_name="Third",
        last_name="Member",
    )

    db.commit()

    response = client.get(
        "/families",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 2

    families_by_case = {
        item["case_number"]: item
        for item in data
    }

    assert families_by_case["FAMILY-004"]["member_count"] == 2
    assert len(families_by_case["FAMILY-004"]["members"]) == 2

    assert families_by_case["FAMILY-005"]["member_count"] == 1
    assert len(families_by_case["FAMILY-005"]["members"]) == 1


def test_only_family_and_next_of_kin_contacts_are_returned(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business, "FAMILY-006")

    create_contact(
        db,
        business,
        case,
        contact_type="family",
        first_name="Family",
        last_name="Member",
    )
    create_contact(
        db,
        business,
        case,
        contact_type="next_of_kin",
        first_name="Next",
        last_name="OfKin",
    )
    create_contact(
        db,
        business,
        case,
        contact_type="supplier",
        first_name="Excluded",
        last_name="Contact",
    )

    db.commit()

    response = client.get(
        "/families",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 1
    assert data[0]["member_count"] == 2

    names = {
        member["full_name"]
        for member in data[0]["members"]
    }

    assert names == {
        "Family Member",
        "Next OfKin",
    }


def test_families_are_tenant_isolated(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    manager_a = test_data["manager"]
    business_b = test_data["business_b"]
    manager_b = test_data["other_business_manager"]

    case_a = create_case(db, business_a, "FAMILY-A-001")
    case_b = create_case(db, business_b, "FAMILY-B-001")

    create_contact(
        db,
        business_a,
        case_a,
        first_name="Business",
        last_name="A",
    )
    create_contact(
        db,
        business_b,
        case_b,
        first_name="Business",
        last_name="B",
    )

    db.commit()

    response_a = client.get(
        "/families",
        headers=auth_headers(manager_a),
    )

    assert response_a.status_code == 200, response_a.text

    data_a = response_a.json()

    assert len(data_a) == 1
    assert data_a[0]["case_number"] == "FAMILY-A-001"
    assert data_a[0]["members"][0]["full_name"] == "Business A"

    response_b = client.get(
        "/families",
        headers=auth_headers(manager_b),
    )

    assert response_b.status_code == 200, response_b.text

    data_b = response_b.json()

    assert len(data_b) == 1
    assert data_b[0]["case_number"] == "FAMILY-B-001"
    assert data_b[0]["members"][0]["full_name"] == "Business B"


def test_families_returns_empty_list_when_no_family_contacts_exist(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    response = client.get(
        "/families",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text
    assert response.json() == []
