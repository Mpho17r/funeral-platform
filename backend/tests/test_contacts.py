import uuid

from datetime import date, datetime, timedelta, timezone

from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase


def create_case(db, business, case_number=None):
    case = FuneralCase(
        business_id=business.id,
        case_number=case_number or f"CONTACT-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Test Deceased",
        date_of_death=date(2026, 9, 10),
        funeral_date=date(2026, 9, 15),
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
    contact_type="next_of_kin",
    first_name="Test",
    last_name="Contact",
    phone="0712345678",
    email="contact@example.com",
    relationship="spouse",
    organization=None,
    address=None,
    notes=None,
    created_at=None,
):
    contact = CaseContact(
        business_id=business.id,
        case_id=case.id,
        contact_type=contact_type,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        relationship=relationship,
        organization=organization,
        address=address,
        notes=notes,
        created_at=created_at or datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(contact)
    db.flush()
    return contact


# ============================================================
# CREATE CONTACT
# ============================================================

def test_create_contact_with_all_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Lerato",
            "last_name": "Mokoena",
            "phone": "0712345678",
            "email": "lerato@example.com",
            "relationship": "spouse",
            "organization": "Mokoena Family",
            "address": "123 Test Street",
            "notes": "Primary family contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["business_id"] == str(business.id)
    assert data["case_id"] == str(case.id)
    assert data["contact_type"] == "next_of_kin"
    assert data["first_name"] == "Lerato"
    assert data["last_name"] == "Mokoena"
    assert data["phone"] == "0712345678"
    assert data["email"] == "lerato@example.com"
    assert data["relationship"] == "spouse"
    assert data["organization"] == "Mokoena Family"
    assert data["address"] == "123 Test Street"
    assert data["notes"] == "Primary family contact"
    assert data["id"]
    assert data["created_at"]
    assert data["updated_at"]


def test_create_contact_with_required_fields_only(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "service_provider",
            "first_name": "John",
            "last_name": "Doe",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["contact_type"] == "service_provider"
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["phone"] is None
    assert data["email"] is None
    assert data["relationship"] is None
    assert data["organization"] is None
    assert data["address"] is None
    assert data["notes"] is None


def test_created_contact_is_persisted(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Persisted",
            "last_name": "Contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201

    contact_id = response.json()["id"]

    stored = db.query(CaseContact).filter(
        CaseContact.id == contact_id
    ).first()

    assert stored is not None
    assert stored.business_id == business.id
    assert stored.case_id == case.id
    assert stored.first_name == "Persisted"
    assert stored.last_name == "Contact"


def test_create_contact_rejects_blank_contact_type(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "",
            "first_name": "Test",
            "last_name": "Contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_create_contact_rejects_blank_first_name(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "",
            "last_name": "Contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_create_contact_rejects_blank_last_name(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Test",
            "last_name": "",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_create_contact_rejects_oversized_contact_type(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "x" * 51,
            "first_name": "Test",
            "last_name": "Contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_create_contact_rejects_oversized_first_name(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "x" * 101,
            "last_name": "Contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_create_contact_rejects_oversized_email(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Test",
            "last_name": "Contact",
            "email": "x" * 256,
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_create_contact_for_missing_case_returns_404(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    missing_case_id = uuid.uuid4()

    response = client.post(
        f"/cases/{missing_case_id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Test",
            "last_name": "Contact",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_create_contact_for_other_business_case_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    case_b = create_case(db, business_b)
    db.commit()

    response = client.post(
        f"/cases/{case_b.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Blocked",
            "last_name": "Contact",
        },
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


# ============================================================
# LIST CONTACTS
# ============================================================

def test_list_case_contacts(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    create_contact(db, business, case)
    create_contact(
        db,
        business,
        case,
        first_name="Second",
        last_name="Contact",
    )
    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert len(data) == 2
    assert data[0]["first_name"] == "Test"
    assert data[1]["first_name"] == "Second"


def test_list_case_contacts_returns_empty_list_when_none_exist(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_case_contacts_orders_oldest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)

    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    new_time = datetime.now(timezone.utc) - timedelta(days=1)

    create_contact(
        db,
        business,
        case,
        first_name="Older",
        last_name="Contact",
        created_at=old_time,
    )

    create_contact(
        db,
        business,
        case,
        first_name="Newer",
        last_name="Contact",
        created_at=new_time,
    )

    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200

    data = response.json()

    assert [item["first_name"] for item in data] == [
        "Older",
        "Newer",
    ]


def test_list_contacts_for_missing_case_returns_404(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    response = client.get(
        f"/cases/{uuid.uuid4()}/contacts",
        headers=auth_headers(manager),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_list_contacts_for_other_business_case_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    case_b = create_case(db, business_b)
    db.commit()

    response = client.get(
        f"/cases/{case_b.id}/contacts",
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


# ============================================================
# GET SINGLE CONTACT
# ============================================================

def test_get_single_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == str(contact.id)
    assert data["business_id"] == str(business.id)
    assert data["case_id"] == str(case.id)
    assert data["first_name"] == "Test"
    assert data["last_name"] == "Contact"


def test_get_missing_contact_returns_404(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    response = client.get(
        f"/cases/contacts/{uuid.uuid4()}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_get_other_business_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    case_b = create_case(db, business_b)
    contact_b = create_contact(db, business_b, case_b)
    db.commit()

    response = client.get(
        f"/cases/contacts/{contact_b.id}",
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


# ============================================================
# UPDATE CONTACT
# ============================================================

def test_update_contact_partial_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "first_name": "Updated",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Contact"
    assert data["phone"] == "0712345678"


def test_update_contact_multiple_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "first_name": "Updated",
            "last_name": "Person",
            "phone": "0799999999",
            "email": "updated@example.com",
            "relationship": "child",
            "organization": "Updated Org",
            "address": "Updated Address",
            "notes": "Updated notes",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Person"
    assert data["phone"] == "0799999999"
    assert data["email"] == "updated@example.com"
    assert data["relationship"] == "child"
    assert data["organization"] == "Updated Org"
    assert data["address"] == "Updated Address"
    assert data["notes"] == "Updated notes"


def test_update_contact_can_clear_nullable_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "phone": None,
            "email": None,
            "relationship": None,
            "organization": None,
            "address": None,
            "notes": None,
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["phone"] is None
    assert data["email"] is None
    assert data["relationship"] is None
    assert data["organization"] is None
    assert data["address"] is None
    assert data["notes"] is None


def test_update_contact_updates_updated_at(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    original_updated_at = contact.updated_at

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "first_name": "Changed",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    updated_data = response.json()

    updated_at = datetime.fromisoformat(
        updated_data["updated_at"].replace("Z", "+00:00")
    )

    assert updated_at >= original_updated_at


def test_update_missing_contact_returns_404(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    response = client.patch(
        f"/cases/contacts/{uuid.uuid4()}",
        json={
            "first_name": "Updated",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_update_other_business_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    case_b = create_case(db, business_b)
    contact_b = create_contact(db, business_b, case_b)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact_b.id}",
        json={
            "first_name": "Blocked",
        },
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_update_contact_rejects_invalid_first_name(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "first_name": "",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_update_contact_rejects_oversized_email(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "email": "x" * 256,
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


# ============================================================
# DELETE CONTACT
# ============================================================

def test_delete_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.delete(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 204
    assert response.content == b""

    stored = db.query(CaseContact).filter(
        CaseContact.id == contact.id
    ).first()

    assert stored is None


def test_deleted_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    delete_response = client.delete(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(manager),
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(manager),
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Contact not found"


def test_delete_missing_contact_returns_404(
    client,
    test_data,
    auth_headers,
):
    manager = test_data["manager"]

    response = client.delete(
        f"/cases/contacts/{uuid.uuid4()}",
        headers=auth_headers(manager),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_delete_other_business_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    case_b = create_case(db, business_b)
    contact_b = create_contact(db, business_b, case_b)
    db.commit()

    response = client.delete(
        f"/cases/contacts/{contact_b.id}",
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"
