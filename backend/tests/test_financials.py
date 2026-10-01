from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.case_service import CaseService
from app.models.funeral_case import FuneralCase


def create_case(db, business, case_number=None):
    case = FuneralCase(
        business_id=business.id,
        case_number=case_number or f"FIN-{uuid4().hex[:8].upper()}",
        deceased_full_name="Financial Behavioral Test Person",
        status="in_progress",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_financial(
    db,
    business,
    case,
    *,
    subtotal="1000.00",
    discount="0.00",
    tax="0.00",
):
    subtotal = Decimal(subtotal)
    discount = Decimal(discount)
    tax = Decimal(tax)
    total = max(subtotal - discount + tax, Decimal("0.00"))

    financial = CaseFinancial(
        business_id=business.id,
        case_id=case.id,
        status="draft" if total == 0 else "unpaid",
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=total,
        amount_paid=Decimal("0.00"),
        balance=total,
        credit=Decimal("0.00"),
        notes="Financial behavioral test",
    )
    db.add(financial)
    db.commit()
    db.refresh(financial)
    return financial


def create_payment(
    db,
    business,
    case,
    *,
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


def create_service(
    db,
    business,
    case,
    *,
    quantity=1,
    unit_price="1000.00",
):
    quantity = int(quantity)
    unit_price = Decimal(unit_price)

    service = CaseService(
        business_id=business.id,
        case_id=case.id,
        service_type="service",
        service_name="Funeral Service",
        description="Financial recalculation test",
        status="pending",
        quantity=quantity,
        unit_price=unit_price,
        total_price=Decimal(quantity) * unit_price,
        scheduled_date=date(2026, 9, 15),
        provider="Test Provider",
        notes="Financial test service",
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


# ============================================================
# FINANCIAL CALCULATIONS
# ============================================================

def test_create_financial_calculates_total(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 1500,
            "discount": 100,
            "tax": 150,
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("1500.00")
    assert Decimal(data["discount"]) == Decimal("100.00")
    assert Decimal(data["tax"]) == Decimal("150.00")
    assert Decimal(data["total"]) == Decimal("1550.00")
    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert Decimal(data["balance"]) == Decimal("1550.00")
    assert Decimal(data["credit"]) == Decimal("0.00")
    assert data["status"] == "unpaid"


def test_zero_value_financial_starts_as_draft(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 0,
            "discount": 0,
            "tax": 0,
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert Decimal(data["total"]) == Decimal("0.00")
    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert Decimal(data["credit"]) == Decimal("0.00")
    assert data["status"] == "draft"


def test_financial_with_no_payment_is_unpaid(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 1000,
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "unpaid"


def test_partial_payment_sets_partially_paid_status(
    client,
    db,
    test_data,
    auth_headers,
):
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
        amount="400.00",
        reference="FIN-PARTIAL-001",
    )

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["amount_paid"]) == Decimal("400.00")
    assert Decimal(data["balance"]) == Decimal("600.00")
    assert Decimal(data["credit"]) == Decimal("0.00")
    assert data["status"] == "partially_paid"


def test_exact_payment_sets_paid_status(
    client,
    db,
    test_data,
    auth_headers,
):
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
        amount="1000.00",
        reference="FIN-PAID-001",
    )

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["amount_paid"]) == Decimal("1000.00")
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert Decimal(data["credit"]) == Decimal("0.00")
    assert data["status"] == "paid"


def test_overpayment_sets_overpaid_status_and_credit(
    client,
    db,
    test_data,
    auth_headers,
):
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
        amount="1200.00",
        reference="FIN-OVERPAID-001",
    )

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["amount_paid"]) == Decimal("1200.00")
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert Decimal(data["credit"]) == Decimal("200.00")
    assert data["status"] == "overpaid"


def test_discount_and_tax_are_combined_correctly(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 5000,
            "discount": 750,
            "tax": 425,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert Decimal(data["total"]) == Decimal("4675.00")
    assert Decimal(data["balance"]) == Decimal("4675.00")


def test_negative_computed_total_is_clamped_to_zero(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 100,
            "discount": 500,
            "tax": 0,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert Decimal(data["total"]) == Decimal("0.00")
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert Decimal(data["credit"]) == Decimal("0.00")
    assert data["status"] == "draft"


# ============================================================
# PAYMENT SYNCHRONIZATION
# ============================================================

def test_single_payment_updates_amount_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="2000.00",
    )
    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="750.00",
        reference="FIN-PAY-001",
    )

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert Decimal(response.json()["amount_paid"]) == Decimal("750.00")


def test_multiple_payments_are_summed(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="3000.00",
    )

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="500.00",
        reference="FIN-MULTI-001",
    )
    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="750.00",
        reference="FIN-MULTI-002",
    )
    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="250.00",
        reference="FIN-MULTI-003",
    )

    response = client.get(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert Decimal(response.json()["amount_paid"]) == Decimal("1500.00")


def test_fetching_financial_recalculates_after_payment_changes(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="2000.00",
    )

    headers = auth_headers(test_data["manager"])

    first_response = client.get(
        f"/cases/{case.id}/financial",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert Decimal(first_response.json()["amount_paid"]) == Decimal("0.00")
    assert first_response.json()["status"] == "unpaid"

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="2000.00",
        reference="FIN-SYNC-001",
    )

    second_response = client.get(
        f"/cases/{case.id}/financial",
        headers=headers,
    )

    assert second_response.status_code == 200

    data = second_response.json()

    assert Decimal(data["amount_paid"]) == Decimal("2000.00")
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert data["status"] == "paid"


def test_client_cannot_override_amount_paid(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/financial",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 1000,
            "amount_paid": 900,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert Decimal(data["balance"]) == Decimal("1000.00")
    assert data["status"] == "unpaid"


# ============================================================
# SERVICE-BASED RECALCULATION
# ============================================================

def test_recalculate_sums_multiple_services_into_subtotal(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="0.00",
    )

    create_service(
        db,
        test_data["business_a"],
        case,
        quantity=2,
        unit_price="1000.00",
    )
    create_service(
        db,
        test_data["business_a"],
        case,
        quantity=1,
        unit_price="750.00",
    )

    response = client.post(
        f"/cases/{case.id}/financial/recalculate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("2750.00")
    assert Decimal(data["total"]) == Decimal("2750.00")
    assert Decimal(data["balance"]) == Decimal("2750.00")
    assert data["status"] == "unpaid"


def test_recalculate_updates_balance_and_status(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="0.00",
    )

    create_service(
        db,
        test_data["business_a"],
        case,
        quantity=2,
        unit_price="1000.00",
    )

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="1500.00",
        reference="FIN-SERVICE-PAY-001",
    )

    response = client.post(
        f"/cases/{case.id}/financial/recalculate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("2000.00")
    assert Decimal(data["total"]) == Decimal("2000.00")
    assert Decimal(data["amount_paid"]) == Decimal("1500.00")
    assert Decimal(data["balance"]) == Decimal("500.00")
    assert data["status"] == "partially_paid"


def test_recalculate_with_no_services_sets_subtotal_to_zero(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="2500.00",
    )

    response = client.post(
        f"/cases/{case.id}/financial/recalculate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("0.00")
    assert Decimal(data["total"]) == Decimal("0.00")
    assert Decimal(data["balance"]) == Decimal("0.00")
    assert data["status"] == "draft"


def test_recalculate_ignores_service_from_other_business(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="0.00",
    )

    create_service(
        db,
        test_data["business_a"],
        case,
        quantity=1,
        unit_price="1000.00",
    )

    other_business_service = CaseService(
        business_id=test_data["business_b"].id,
        case_id=case.id,
        service_type="service",
        service_name="Other Business Service",
        description="Must be ignored",
        status="pending",
        quantity=1,
        unit_price=Decimal("9000.00"),
        total_price=Decimal("9000.00"),
        scheduled_date=date(2026, 9, 15),
        provider="Other Provider",
        notes=None,
    )
    db.add(other_business_service)
    db.commit()

    response = client.post(
        f"/cases/{case.id}/financial/recalculate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("1000.00")
    assert Decimal(data["total"]) == Decimal("1000.00")


# ============================================================
# UPDATES AND DERIVED FIELDS
# ============================================================

def test_updating_financial_values_recalculates_totals(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )

    response = client.patch(
        f"/cases/financial/{financial.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 2000,
            "discount": 250,
            "tax": 150,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("2000.00")
    assert Decimal(data["discount"]) == Decimal("250.00")
    assert Decimal(data["tax"]) == Decimal("150.00")
    assert Decimal(data["total"]) == Decimal("1900.00")
    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert Decimal(data["balance"]) == Decimal("1900.00")
    assert data["status"] == "unpaid"


def test_updating_notes_preserves_calculated_values(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1500.00",
        discount="100.00",
        tax="150.00",
    )

    response = client.patch(
        f"/cases/financial/{financial.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "notes": "Updated notes only",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["notes"] == "Updated notes only"
    assert Decimal(data["subtotal"]) == Decimal("1500.00")
    assert Decimal(data["discount"]) == Decimal("100.00")
    assert Decimal(data["tax"]) == Decimal("150.00")
    assert Decimal(data["total"]) == Decimal("1550.00")
    assert Decimal(data["balance"]) == Decimal("1550.00")


def test_client_cannot_override_derived_financial_fields_on_update(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="1000.00",
    )

    response = client.patch(
        f"/cases/financial/{financial.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "status": "paid",
            "amount_paid": 9999,
            "total": 9999,
            "balance": 0,
            "credit": 9999,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "unpaid"
    assert Decimal(data["amount_paid"]) == Decimal("0.00")
    assert Decimal(data["total"]) == Decimal("1000.00")
    assert Decimal(data["balance"]) == Decimal("1000.00")
    assert Decimal(data["credit"]) == Decimal("0.00")


def test_update_after_payment_recalculates_from_actual_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case,
        subtotal="2000.00",
    )

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="500.00",
        reference="FIN-UPDATE-PAY-001",
    )

    response = client.patch(
        f"/cases/financial/{financial.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "subtotal": 3000,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert Decimal(data["subtotal"]) == Decimal("3000.00")
    assert Decimal(data["total"]) == Decimal("3000.00")
    assert Decimal(data["amount_paid"]) == Decimal("500.00")
    assert Decimal(data["balance"]) == Decimal("2500.00")
    assert data["status"] == "partially_paid"


# ============================================================
# LIFECYCLE AND ERROR HANDLING
# ============================================================

def test_duplicate_financial_returns_conflict(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    headers = auth_headers(test_data["manager"])

    first = client.post(
        f"/cases/{case.id}/financial",
        headers=headers,
        json={
            "subtotal": 1000,
        },
    )

    assert first.status_code == 201

    second = client.post(
        f"/cases/{case.id}/financial",
        headers=headers,
        json={
            "subtotal": 2000,
        },
    )

    assert second.status_code == 409


def test_missing_financial_returns_not_found(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    missing_id = uuid4()

    response = client.get(
        f"/cases/financial/{missing_id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404


def test_recalculate_missing_case_returns_not_found(
    client,
    db,
    test_data,
    auth_headers,
):
    missing_case_id = uuid4()

    response = client.post(
        f"/cases/{missing_case_id}/financial/recalculate",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Case not found"


def test_delete_financial_removes_record(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    financial = create_financial(
        db,
        test_data["business_a"],
        case,
    )

    financial_id = financial.id

    response = client.delete(
        f"/cases/financial/{financial_id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 204

    deleted = (
        db.query(CaseFinancial)
        .filter(CaseFinancial.id == financial_id)
        .first()
    )

    assert deleted is None
