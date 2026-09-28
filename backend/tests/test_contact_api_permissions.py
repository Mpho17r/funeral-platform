import uuid

from datetime import date

from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def grant_permission(db, role, permission_key):
    permission = db.query(Permission).filter(
        Permission.key == permission_key
    ).first()

    assert permission is not None

    existing = db.query(RolePermission).filter(
        RolePermission.role == role,
        RolePermission.permission_id == permission.id,
    ).first()

    if existing is None:
        db.add(
            RolePermission(
                role=role,
                permission_id=permission.id,
            )
        )
        db.commit()


def deny_permission(db, user_id, permission_key):
    permission = db.query(Permission).filter(
        Permission.key == permission_key
    ).first()

    assert permission is not None

    existing = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.permission_id == permission.id,
    ).first()

    if existing is None:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )
    else:
        existing.effect = "deny"

    db.commit()


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


def create_contact(db, business, case):
    contact = CaseContact(
        business_id=business.id,
        case_id=case.id,
        contact_type="next_of_kin",
        first_name="Test",
        last_name="Contact",
        phone="0712345678",
        email="contact@example.com",
        relationship="spouse",
    )
    db.add(contact)
    db.flush()
    return contact


# ============================================================
# GET CASE CONTACTS
# ============================================================

def test_staff_with_contacts_view_can_list_contacts(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")

    case = create_case(db, business)
    create_contact(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1


def test_staff_without_contacts_view_cannot_list_contacts(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: contacts.view"


# ============================================================
# GET SINGLE CONTACT
# ============================================================

def test_staff_with_contacts_view_can_get_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(contact.id)


def test_staff_without_contacts_view_cannot_get_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: contacts.view"


# ============================================================
# CREATE CONTACT
# ============================================================

def test_staff_with_contacts_manage_can_create_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "New",
            "last_name": "Contact",
            "relationship": "spouse",
            "phone": "0722222222",
            "email": "newcontact@example.com",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text
    assert response.json()["first_name"] == "New"
    assert response.json()["last_name"] == "Contact"


def test_staff_without_contacts_manage_cannot_create_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Blocked",
            "last_name": "Contact",
            "relationship": "spouse",
            "phone": "0722222222",
            "email": "blocked@example.com",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: contacts.manage"


# ============================================================
# UPDATE CONTACT
# ============================================================

def test_staff_with_contacts_manage_can_update_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "first_name": "Updated",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["first_name"] == "Updated"


def test_staff_without_contacts_manage_cannot_update_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/contacts/{contact.id}",
        json={
            "first_name": "Blocked",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: contacts.manage"


# ============================================================
# DELETE CONTACT
# ============================================================

def test_staff_with_contacts_manage_can_delete_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.delete(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 204


def test_staff_without_contacts_manage_cannot_delete_contact(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    response = client.delete(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: contacts.manage"


# ============================================================
# MAIN ADMIN
# ============================================================

def test_main_admin_can_manage_contacts_without_explicit_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    admin = test_data["main_admin"]

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Admin",
            "last_name": "Contact",
            "relationship": "parent",
            "phone": "0733333333",
            "email": "admincontact@example.com",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201, response.text


# ============================================================
# EXPLICIT USER DENY
# ============================================================

def test_explicit_user_deny_overrides_contacts_view_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")
    deny_permission(db, staff.id, "contacts.view")

    case = create_case(db, business)
    create_contact(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: contacts.view"


# ============================================================
# TENANT ISOLATION
# ============================================================

def test_staff_cannot_access_contacts_from_another_business(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")

    case = create_case(db, business_b)
    contact = create_contact(db, business_b, case)
    db.commit()

    response = client.get(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 404

# ============================================================
# FUNCTIONAL / EDGE-CASE COVERAGE
# ============================================================

def test_staff_cannot_create_contact_for_another_business_case(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    case = create_case(db, business_b)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Blocked",
            "last_name": "Contact",
            "relationship": "spouse",
            "phone": "0722222222",
            "email": "blocked@example.com",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_create_contact_persists_all_optional_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/contacts",
        json={
            "contact_type": "next_of_kin",
            "first_name": "Full",
            "last_name": "Contact",
            "phone": "0712345678",
            "email": "full@example.com",
            "relationship": "spouse",
            "organization": "Example Organisation",
            "address": "123 Test Street, Johannesburg",
            "notes": "Important family contact",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["contact_type"] == "next_of_kin"
    assert data["first_name"] == "Full"
    assert data["last_name"] == "Contact"
    assert data["phone"] == "0712345678"
    assert data["email"] == "full@example.com"
    assert data["relationship"] == "spouse"
    assert data["organization"] == "Example Organisation"
    assert data["address"] == "123 Test Street, Johannesburg"
    assert data["notes"] == "Important family contact"
    assert data["business_id"] == str(business.id)
    assert data["case_id"] == str(case.id)


def test_staff_cannot_list_contacts_for_another_business_case(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")

    case = create_case(db, business_b)
    create_contact(db, business_b, case)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/contacts",
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_list_contacts_for_missing_case_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")

    missing_case_id = uuid.uuid4()

    response = client.get(
        f"/cases/{missing_case_id}/contacts",
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_get_missing_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.view")

    missing_contact_id = uuid.uuid4()

    response = client.get(
        f"/cases/contacts/{missing_contact_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_update_contact_updates_multiple_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

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
            "organization": "Updated Organisation",
            "address": "456 Updated Street",
            "notes": "Updated notes",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Person"
    assert data["phone"] == "0799999999"
    assert data["email"] == "updated@example.com"
    assert data["relationship"] == "child"
    assert data["organization"] == "Updated Organisation"
    assert data["address"] == "456 Updated Street"
    assert data["notes"] == "Updated notes"


def test_update_missing_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    missing_contact_id = uuid.uuid4()

    response = client.patch(
        f"/cases/contacts/{missing_contact_id}",
        json={
            "first_name": "Updated",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_delete_missing_contact_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")

    missing_contact_id = uuid.uuid4()

    response = client.delete(
        f"/cases/contacts/{missing_contact_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_deleted_contact_cannot_be_retrieved(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "contacts.manage")
    grant_permission(db, "staff", "contacts.view")

    case = create_case(db, business)
    contact = create_contact(db, business, case)
    db.commit()

    delete_response = client.delete(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/cases/contacts/{contact.id}",
        headers=auth_headers(staff),
    )

    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Contact not found"
