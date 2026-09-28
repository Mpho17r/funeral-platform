import uuid

from datetime import date
from decimal import Decimal

from app.models.case_service import CaseService
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


def create_case(db, business, case_number=None):
    case = FuneralCase(
        business_id=business.id,
        case_number=case_number
        or f"SERVICE-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Test Deceased",
        date_of_death=date(2026, 9, 10),
        funeral_date=date(2026, 9, 15),
        status="open",
    )
    db.add(case)
    db.flush()
    return case


def create_service(
    db,
    business,
    case,
    *,
    quantity=2,
    unit_price=Decimal("1500.00"),
):
    service = CaseService(
        business_id=business.id,
        case_id=case.id,
        service_type="transport",
        service_name="Hearse Transport",
        description="Test service",
        status="pending",
        quantity=quantity,
        unit_price=unit_price,
        total_price=Decimal(quantity) * unit_price,
        scheduled_date=date(2026, 9, 15),
        provider="Test Provider",
        notes="Test notes",
    )
    db.add(service)
    db.flush()
    return service


# ============================================================
# LIST SERVICES
# ============================================================

def test_staff_with_services_view_can_list_services(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "services.view")

    case = create_case(db, business)
    create_service(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/services",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["service_name"] == "Hearse Transport"


def test_staff_with_services_view_denied_cannot_list_services(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    deny_permission(db, staff.id, "services.view")

    case = create_case(db, business)
    db.commit()

    response = client.get(
        f"/cases/{case.id}/services",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: services.view"
    )


# ============================================================
# GET SINGLE SERVICE
# ============================================================

def test_staff_with_services_view_can_get_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "services.view")

    case = create_case(db, business)
    service = create_service(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/services/{service.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(service.id)


def test_staff_with_services_view_denied_cannot_get_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    deny_permission(db, staff.id, "services.view")

    case = create_case(db, business)
    service = create_service(db, business, case)
    db.commit()

    response = client.get(
        f"/cases/services/{service.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: services.view"
    )


# ============================================================
# CREATE SERVICE
# ============================================================

def test_staff_with_services_manage_can_create_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "services.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/services",
        json={
            "service_type": "catering",
            "service_name": "Funeral Catering",
            "description": "Family catering",
            "status": "pending",
            "quantity": 3,
            "unit_price": "750.00",
            "scheduled_date": "2026-09-15",
            "provider": "Test Caterer",
            "notes": "Test notes",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["service_name"] == "Funeral Catering"
    assert data["quantity"] == 3
    assert Decimal(data["unit_price"]) == Decimal("750.00")
    assert Decimal(data["total_price"]) == Decimal("2250.00")


def test_staff_with_services_manage_denied_cannot_create_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    deny_permission(db, staff.id, "services.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/services",
        json={
            "service_type": "catering",
            "service_name": "Blocked Service",
            "quantity": 1,
            "unit_price": "100.00",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: services.manage"
    )


# ============================================================
# UPDATE SERVICE
# ============================================================

def test_staff_with_services_manage_can_update_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "services.manage")

    case = create_case(db, business)
    service = create_service(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/services/{service.id}",
        json={
            "service_name": "Updated Hearse Transport",
            "quantity": 4,
            "unit_price": "2000.00",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["service_name"] == "Updated Hearse Transport"
    assert data["quantity"] == 4
    assert Decimal(data["unit_price"]) == Decimal("2000.00")
    assert Decimal(data["total_price"]) == Decimal("8000.00")


def test_staff_with_services_manage_denied_cannot_update_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    deny_permission(db, staff.id, "services.manage")

    case = create_case(db, business)
    service = create_service(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/services/{service.id}",
        json={
            "service_name": "Blocked Update",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: services.manage"
    )


# ============================================================
# DELETE SERVICE
# ============================================================

def test_staff_with_services_manage_can_delete_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    grant_permission(db, "staff", "services.manage")

    case = create_case(db, business)
    service = create_service(db, business, case)
    service_id = service.id
    db.commit()

    response = client.delete(
        f"/cases/services/{service_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 204

    deleted = (
        db.query(CaseService)
        .filter(CaseService.id == service_id)
        .first()
    )

    assert deleted is None


def test_staff_with_services_manage_denied_cannot_delete_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    staff = test_data["staff"]

    deny_permission(db, staff.id, "services.manage")

    case = create_case(db, business)
    service = create_service(db, business, case)
    db.commit()

    response = client.delete(
        f"/cases/services/{service.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: services.manage"
    )


# ============================================================
# TENANT ISOLATION
# ============================================================

def test_business_a_cannot_get_business_b_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business_a = test_data["business_a"]
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    grant_permission(db, "manager", "services.view")

    case_b = create_case(db, business_b)
    service_b = create_service(db, business_b, case_b)
    db.commit()

    response = client.get(
        f"/cases/services/{service_b.id}",
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


def test_business_a_cannot_update_business_b_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case_b = create_case(db, business_b)
    service_b = create_service(db, business_b, case_b)
    db.commit()

    response = client.patch(
        f"/cases/services/{service_b.id}",
        json={
            "service_name": "Cross Tenant Update",
        },
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


def test_business_a_cannot_delete_business_b_service(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case_b = create_case(db, business_b)
    service_b = create_service(db, business_b, case_b)
    service_id = service_b.id
    db.commit()

    response = client.delete(
        f"/cases/services/{service_id}",
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"

    assert (
        db.query(CaseService)
        .filter(CaseService.id == service_id)
        .first()
        is not None
    )


def test_business_a_cannot_create_service_on_business_b_case(
    client,
    db,
    test_data,
    auth_headers,
):
    business_b = test_data["business_b"]
    manager_a = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case_b = create_case(db, business_b)
    db.commit()

    response = client.post(
        f"/cases/{case_b.id}/services",
        json={
            "service_type": "transport",
            "service_name": "Cross Tenant Service",
            "quantity": 1,
            "unit_price": "500.00",
        },
        headers=auth_headers(manager_a),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


# ============================================================
# VALIDATION / SERVER-SIDE CALCULATION
# ============================================================

def test_total_price_cannot_be_overridden_on_create(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/services",
        json={
            "service_type": "transport",
            "service_name": "Hearse",
            "quantity": 2,
            "unit_price": "1000.00",
            "total_price": "1.00",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert Decimal(data["total_price"]) == Decimal("2000.00")


def test_negative_unit_price_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/services",
        json={
            "service_type": "transport",
            "service_name": "Invalid Service",
            "quantity": 1,
            "unit_price": "-100.00",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_zero_quantity_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case = create_case(db, business)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/services",
        json={
            "service_type": "transport",
            "service_name": "Invalid Quantity",
            "quantity": 0,
            "unit_price": "100.00",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 422


def test_total_price_recalculates_when_service_is_updated(
    client,
    db,
    test_data,
    auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]

    grant_permission(db, "manager", "services.manage")

    case = create_case(db, business)
    service = create_service(db, business, case)
    db.commit()

    response = client.patch(
        f"/cases/services/{service.id}",
        json={
            "quantity": 5,
            "unit_price": "250.00",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert Decimal(data["total_price"]) == Decimal("1250.00")
