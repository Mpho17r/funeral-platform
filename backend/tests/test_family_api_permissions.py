import pytest
from fastapi.testclient import TestClient

from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def grant_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            RolePermission(
                role=role,
                permission_id=permission.id,
            )
        )
        db.commit()


def revoke_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is not None:
        db.delete(existing)
        db.commit()


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

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


def create_case(db, business_id, case_number, deceased_full_name):
    case = FuneralCase(
        business_id=business_id,
        case_number=case_number,
        deceased_full_name=deceased_full_name,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_contact(
    db,
    business_id,
    case_id,
    contact_type,
    first_name,
    last_name,
    relationship=None,
):
    contact = CaseContact(
        business_id=business_id,
        case_id=case_id,
        contact_type=contact_type,
        first_name=first_name,
        last_name=last_name,
        relationship=relationship,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def test_staff_with_families_view_can_list(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    grant_permission(
        db,
        "staff",
        "families.view",
    )

    case = create_case(
        db,
        test_data["business_a"].id,
        "FAM-2026-0001",
        "Thabo Mokoena",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        case.id,
        "family",
        "Lerato",
        "Mokoena",
        "Spouse",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["case_number"] == "FAM-2026-0001"
    assert data[0]["deceased_full_name"] == "Thabo Mokoena"
    assert data[0]["member_count"] == 1
    assert data[0]["members"][0]["full_name"] == "Lerato Mokoena"


def test_staff_without_families_view_cannot_list(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(
        db,
        "staff",
        "families.view",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: families.view"
    )


def test_main_admin_can_list_families(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"].id,
        "FAM-2026-0002",
        "Maria Mokoena",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        case.id,
        "family",
        "John",
        "Mokoena",
        "Son",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_families_list_excludes_non_family_contacts(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    grant_permission(
        db,
        "staff",
        "families.view",
    )

    case = create_case(
        db,
        test_data["business_a"].id,
        "FAM-2026-0003",
        "Peter Mokoena",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        case.id,
        "family",
        "Sarah",
        "Mokoena",
        "Wife",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        case.id,
        "supplier",
        "John",
        "Supplier",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["member_count"] == 1
    assert data[0]["members"][0]["full_name"] == "Sarah Mokoena"


def test_families_list_groups_family_and_next_of_kin_contacts(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    grant_permission(
        db,
        "staff",
        "families.view",
    )

    case = create_case(
        db,
        test_data["business_a"].id,
        "FAM-2026-0004",
        "David Mokoena",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        case.id,
        "family",
        "Alice",
        "Mokoena",
        "Mother",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        case.id,
        "next_of_kin",
        "Brian",
        "Mokoena",
        "Brother",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["member_count"] == 2

    names = {
        member["full_name"]
        for member in data[0]["members"]
    }

    assert names == {
        "Alice Mokoena",
        "Brian Mokoena",
    }


def test_explicit_user_deny_overrides_families_view(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    grant_permission(
        db,
        "staff",
        "families.view",
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "families.view",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: families.view"
    )


def test_staff_cannot_see_another_business_families(
    client: TestClient,
    db,
    test_data,
    auth_headers,
):
    grant_permission(
        db,
        "staff",
        "families.view",
    )

    business_a_case = create_case(
        db,
        test_data["business_a"].id,
        "FAM-2026-0005",
        "Business A Deceased",
    )

    create_contact(
        db,
        test_data["business_a"].id,
        business_a_case.id,
        "family",
        "Business",
        "A Family",
    )

    business_b_case = create_case(
        db,
        test_data["business_b"].id,
        "FAM-2026-0006",
        "Business B Deceased",
    )

    create_contact(
        db,
        test_data["business_b"].id,
        business_b_case.id,
        "family",
        "Business",
        "B Family",
    )

    response = client.get(
        "/families",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["case_number"] == "FAM-2026-0005"
    assert data[0]["members"][0]["full_name"] == "Business A Family"
