from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.role_permission import RolePermission


def create_case(db, business):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"PAY-{uuid4().hex[:8].upper()}",
        deceased_full_name="Payment Test Person",
        status="in_progress",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_financial(db, business, case, subtotal="10000.00"):
    financial = CaseFinancial(
        business_id=business.id,
        case_id=case.id,
        subtotal=Decimal(subtotal),
        discount=Decimal("0.00"),
        tax=Decimal("0.00"),
        amount_paid=Decimal("0.00"),
        total=Decimal(subtotal),
        balance=Decimal(subtotal),
        credit=Decimal("0.00"),
        status="unpaid",
    )
    db.add(financial)
    db.commit()
    db.refresh(financial)
    return financial


def create_payment(
    db,
    business,
    case,
    amount="100.00",
    reference=None,
):
    payment = CasePayment(
        business_id=business.id,
        case_id=case.id,
        amount=Decimal(amount),
        payment_method="cash",
        reference=reference,
        payment_date=date.today(),
        notes=None,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def grant_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )

    if permission is None:
        permission = Permission(
            key=permission_key,
            description=f"Test permission: {permission_key}",
            is_active=True,
        )
        db.add(permission)
        db.flush()

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

    if permission is None:
        return

    (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .delete(synchronize_session=False)
    )

    db.commit()


def test_staff_with_payments_view_can_list(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.view")

    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)
    create_payment(
        db,
        test_data["business_a"],
        case,
        reference="LIST-001",
    )

    response = client.get(
        f"/cases/{case.id}/payments",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["reference"] == "LIST-001"


def test_staff_without_payments_view_cannot_list(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.view")

    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.get(
        f"/cases/{case.id}/payments",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "payments.view" in response.json()["detail"]


def test_staff_with_payments_view_can_get_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.view")

    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        reference="GET-001",
    )

    response = client.get(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["reference"] == "GET-001"


def test_staff_with_payments_create_can_create(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.create")

    case = create_case(db, test_data["business_a"])
    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "250.00",
            "payment_method": "cash",
            "reference": "CREATE-001",
            "payment_date": str(date.today()),
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 201
    assert response.json()["reference"] == "CREATE-001"
    assert response.json()["amount"] == "250.00"

    db.refresh(financial)
    assert financial.amount_paid == Decimal("250.00")
    assert financial.balance == Decimal("750.00")
    assert financial.status == "partially_paid"


def test_staff_without_payments_create_cannot_create(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.create")

    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "250.00",
            "payment_method": "cash",
            "reference": "DENY-CREATE-001",
            "payment_date": str(date.today()),
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "payments.create" in response.json()["detail"]


def test_staff_with_payments_edit_can_update(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.edit")

    case = create_case(db, test_data["business_a"])
    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="100.00",
        reference="EDIT-001",
    )

    response = client.patch(
        f"/cases/payments/{payment.id}",
        json={
            "amount": "300.00",
            "reference": "EDIT-002",
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "300.00"
    assert response.json()["reference"] == "EDIT-002"

    db.refresh(financial)
    assert financial.amount_paid == Decimal("300.00")
    assert financial.balance == Decimal("700.00")


def test_staff_without_payments_edit_cannot_update(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.edit")

    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        reference="DENY-EDIT-001",
    )

    response = client.patch(
        f"/cases/payments/{payment.id}",
        json={"amount": "300.00"},
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "payments.edit" in response.json()["detail"]


def test_staff_with_payments_delete_can_delete(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.delete")

    case = create_case(db, test_data["business_a"])
    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="250.00",
        reference="DELETE-001",
    )

    response = client.delete(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204

    assert (
        db.query(CasePayment)
        .filter(CasePayment.id == payment.id)
        .first()
        is None
    )

    db.refresh(financial)
    assert financial.amount_paid == Decimal("0.00")
    assert financial.balance == Decimal("1000.00")
    assert financial.status == "unpaid"


def test_staff_without_payments_delete_cannot_delete(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(db, "staff", "payments.delete")

    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        reference="DENY-DELETE-001",
    )

    response = client.delete(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert "payments.delete" in response.json()["detail"]


def test_other_business_cannot_access_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "manager", "payments.view")

    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        reference="TENANT-001",
    )

    response = client.get(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404


def test_duplicate_payment_reference_returns_conflict(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(db, "staff", "payments.create")

    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="100.00",
        reference="DUPLICATE-001",
    )

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "200.00",
            "payment_method": "cash",
            "reference": "DUPLICATE-001",
            "payment_date": str(date.today()),
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 409
    assert "already exists for this business" in response.json()["detail"]
