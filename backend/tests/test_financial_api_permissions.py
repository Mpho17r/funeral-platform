from decimal import Decimal
from app.models.case_financial import CaseFinancial
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.user_permission import UserPermission


def create_case(db, business_id, case_number="FIN-2026-0001"):
    case = FuneralCase(
        business_id=business_id.id,
        case_number=case_number,
        deceased_full_name="Financial Test Deceased",
        status="in_progress",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_financial(db, business_id, case_id):
    financial = CaseFinancial(
        business_id=business_id.id,
        case_id=case_id,
        status="draft",
        subtotal=Decimal("1000.00"),
        discount=Decimal("100.00"),
        tax=Decimal("100.00"),
        total=Decimal("1000.00"),
        amount_paid=Decimal("0.00"),
        balance=Decimal("1000.00"),
        credit=Decimal("0.00"),
        notes="Financial permission test",
    )
    db.add(financial)
    db.commit()
    db.refresh(financial)
    return financial


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    override = UserPermission(
        user_id=user_id,
        permission_id=permission.id,
        effect="deny",
    )
    db.add(override)
    db.commit()


def test_staff_with_financials_view_can_get_case_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    headers = auth_headers(test_data["staff"])

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["case_id"] == str(case.id)


def test_staff_denied_financials_view_cannot_get_case_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "financials.view",
    )

    headers = auth_headers(test_data["staff"])

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=headers,
    )

    assert response.status_code == 403


def test_staff_with_financials_view_can_get_financial_by_id(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    headers = auth_headers(test_data["staff"])

    response = client.get(
        f"/cases/financial/{financial.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(financial.id)


def test_manager_with_financials_manage_can_create_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=headers,
        json={
            "subtotal": 1500,
            "discount": 100,
            "tax": 150,
            "notes": "Created through permission test",
        },
    )

    assert response.status_code == 201
    assert response.json()["case_id"] == str(case.id)


def test_staff_denied_financials_manage_cannot_create_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    deny_permission(
        db,
        test_data["staff"].id,
        "financials.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=headers,
        json={
            "subtotal": 1500,
            "discount": 100,
            "tax": 150,
        },
    )

    assert response.status_code == 403


def test_manager_with_financials_manage_can_update_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.patch(
        f"/cases/financial/{financial.id}",
        headers=headers,
        json={
            "discount": 200,
            "notes": "Updated financial record",
        },
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Updated financial record"


def test_staff_denied_financials_manage_cannot_update_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "financials.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.patch(
        f"/cases/financial/{financial.id}",
        headers=headers,
        json={
            "discount": 200,
        },
    )

    assert response.status_code == 403


def test_manager_with_financials_manage_can_recalculate_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/cases/{case.id}/financial/recalculate",
        headers=headers,
    )

    assert response.status_code == 200


def test_staff_denied_financials_manage_cannot_recalculate_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "financials.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.post(
        f"/cases/{case.id}/financial/recalculate",
        headers=headers,
    )

    assert response.status_code == 403


def test_manager_with_financials_manage_can_delete_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    financial_id = financial.id
    headers = auth_headers(test_data["manager"])

    response = client.delete(
        f"/cases/financial/{financial_id}",
        headers=headers,
    )

    assert response.status_code == 204

    deleted = (
        db.query(CaseFinancial)
        .filter(CaseFinancial.id == financial_id)
        .first()
    )
    assert deleted is None


def test_staff_denied_financials_manage_cannot_delete_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "financials.manage",
    )

    headers = auth_headers(test_data["staff"])

    response = client.delete(
        f"/cases/financial/{financial.id}",
        headers=headers,
    )

    assert response.status_code == 403


def test_other_business_manager_cannot_access_financial(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(
        db,
        test_data["business_a"],
        case_number="FIN-2026-OTHER-0001",
    )

    financial = create_financial(
        db,
        test_data["business_a"],
        case.id,
    )

    headers = auth_headers(test_data["other_business_manager"])

    response = client.get(
        f"/cases/financial/{financial.id}",
        headers=headers,
    )

    assert response.status_code == 404
