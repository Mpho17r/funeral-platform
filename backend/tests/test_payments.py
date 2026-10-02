from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.funeral_case import FuneralCase


def create_case(db, business, case_number=None):
    case = FuneralCase(
        business_id=business.id,
        case_number=case_number or f"PAY-BEH-{uuid4().hex[:8].upper()}",
        deceased_full_name="Payment Behavioral Test",
        status="in_progress",
    )
    db.add(case)
    db.flush()
    return case


def create_financial(
    db,
    business,
    case,
    subtotal="1000.00",
    discount="0.00",
    tax="0.00",
):
    subtotal = Decimal(subtotal)
    discount = Decimal(discount)
    tax = Decimal(tax)
    total = max(Decimal("0.00"), subtotal - discount + tax)

    financial = CaseFinancial(
        business_id=business.id,
        case_id=case.id,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        amount_paid=Decimal("0.00"),
        total=total,
        balance=total,
        credit=Decimal("0.00"),
        status="unpaid" if total > 0 else "draft",
    )
    db.add(financial)
    db.flush()
    return financial


def create_payment(
    db,
    business,
    case,
    amount="100.00",
    payment_method="cash",
    reference=None,
    payment_date=None,
    notes=None,
):
    payment = CasePayment(
        business_id=business.id,
        case_id=case.id,
        amount=Decimal(amount),
        payment_method=payment_method,
        reference=reference,
        payment_date=payment_date or date.today(),
        notes=notes,
    )
    db.add(payment)
    db.flush()
    return payment


def test_create_payment_returns_expected_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "250.50",
            "payment_method": "cash",
            "reference": "BEHAVIOR-001",
            "payment_date": str(date.today()),
            "notes": "Initial payment",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["business_id"] == str(test_data["business_a"].id)
    assert data["case_id"] == str(case.id)
    assert data["amount"] == "250.50"
    assert data["payment_method"] == "cash"
    assert data["reference"] == "BEHAVIOR-001"
    assert data["payment_date"] == str(date.today())
    assert data["notes"] == "Initial payment"
    assert data["id"]


def test_create_payment_updates_financial_amount_paid(
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

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "250.00",
            "payment_method": "cash",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 201

    db.refresh(financial)

    assert financial.amount_paid == Decimal("250.00")
    assert financial.balance == Decimal("750.00")
    assert financial.credit == Decimal("0.00")
    assert financial.status == "partially_paid"


def test_exact_payment_marks_financial_paid(
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

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "1000.00",
            "payment_method": "eft",
            "reference": "PAID-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 201

    db.refresh(financial)

    assert financial.amount_paid == Decimal("1000.00")
    assert financial.balance == Decimal("0.00")
    assert financial.credit == Decimal("0.00")
    assert financial.status == "paid"


def test_payment_above_total_marks_financial_overpaid(
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

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "1250.00",
            "payment_method": "eft",
            "reference": "OVERPAID-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 201

    db.refresh(financial)

    assert financial.amount_paid == Decimal("1250.00")
    assert financial.balance == Decimal("0.00")
    assert financial.credit == Decimal("250.00")
    assert financial.status == "overpaid"


def test_multiple_payments_accumulate(
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

    first = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "250.00",
            "payment_method": "cash",
            "reference": "MULTI-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    second = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "350.00",
            "payment_method": "card",
            "reference": "MULTI-002",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert first.status_code == 201
    assert second.status_code == 201

    db.refresh(financial)

    assert financial.amount_paid == Decimal("600.00")
    assert financial.balance == Decimal("400.00")
    assert financial.credit == Decimal("0.00")
    assert financial.status == "partially_paid"


def test_payment_requires_existing_financial_record(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "100.00",
            "payment_method": "cash",
            "reference": "NO-FINANCIAL-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Financial record not found for this case"


def test_payment_for_other_business_case_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "100.00",
            "payment_method": "cash",
            "reference": "CROSS-BUSINESS-001",
        },
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_invalid_payment_method_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "100.00",
            "payment_method": "bitcoin",
            "reference": "INVALID-METHOD-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 422


def test_payment_method_is_normalized(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "100.00",
            "payment_method": "  EFT  ",
            "reference": "NORMALIZE-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 201
    assert response.json()["payment_method"] == "eft"


def test_zero_payment_amount_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "0.00",
            "payment_method": "cash",
            "reference": "ZERO-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 422


def test_negative_payment_amount_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "-50.00",
            "payment_method": "cash",
            "reference": "NEGATIVE-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 422


def test_list_payments_returns_case_payments(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="100.00",
        reference="LIST-001",
    )
    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="200.00",
        reference="LIST-002",
    )
    db.commit()

    response = client.get(
        f"/cases/{case.id}/payments",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert {item["reference"] for item in data} == {
        "LIST-001",
        "LIST-002",
    }


def test_list_payments_is_newest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    older_date = date.today() - timedelta(days=2)
    newer_date = date.today()

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="100.00",
        reference="ORDER-OLD",
        payment_date=older_date,
    )
    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="200.00",
        reference="ORDER-NEW",
        payment_date=newer_date,
    )
    db.commit()

    response = client.get(
        f"/cases/{case.id}/payments",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert data[0]["reference"] == "ORDER-NEW"
    assert data[1]["reference"] == "ORDER-OLD"


def test_list_payments_only_returns_requested_case(
    client,
    db,
    test_data,
    auth_headers,
):
    case_one = create_case(db, test_data["business_a"])
    case_two = create_case(db, test_data["business_a"])

    create_financial(db, test_data["business_a"], case_one)
    create_financial(db, test_data["business_a"], case_two)

    create_payment(
        db,
        test_data["business_a"],
        case_one,
        reference="CASE-ONE-001",
    )
    create_payment(
        db,
        test_data["business_a"],
        case_two,
        reference="CASE-TWO-001",
    )
    db.commit()

    response = client.get(
        f"/cases/{case_one.id}/payments",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["reference"] == "CASE-ONE-001"


def test_missing_case_returns_404_when_listing_payments(
    client,
    db,
    test_data,
    auth_headers,
):
    missing_case_id = uuid4()

    response = client.get(
        f"/cases/{missing_case_id}/payments",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_get_payment_returns_expected_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="325.50",
        payment_method="eft",
        reference="GET-001",
        notes="Bank payment",
    )
    db.commit()

    response = client.get(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(payment.id)
    assert data["amount"] == "325.50"
    assert data["payment_method"] == "eft"
    assert data["reference"] == "GET-001"
    assert data["notes"] == "Bank payment"


def test_missing_payment_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    response = client.get(
        f"/cases/payments/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_other_business_cannot_get_payment(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        reference="ISOLATION-001",
    )
    db.commit()

    response = client.get(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_update_payment_amount_recalculates_financials(
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

    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="200.00",
        reference="UPDATE-001",
    )
    db.commit()

    response = client.patch(
        f"/cases/payments/{payment.id}",
        json={
            "amount": "700.00",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "700.00"

    db.refresh(financial)

    assert financial.amount_paid == Decimal("700.00")
    assert financial.balance == Decimal("300.00")
    assert financial.credit == Decimal("0.00")
    assert financial.status == "partially_paid"


def test_update_payment_other_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="200.00",
        payment_method="cash",
        reference="UPDATE-FIELDS-001",
    )
    db.commit()

    new_date = date.today() - timedelta(days=1)

    response = client.patch(
        f"/cases/payments/{payment.id}",
        json={
            "payment_method": "  CARD ",
            "reference": "UPDATE-FIELDS-002",
            "payment_date": str(new_date),
            "notes": "Updated payment",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["payment_method"] == "card"
    assert data["reference"] == "UPDATE-FIELDS-002"
    assert data["payment_date"] == str(new_date)
    assert data["notes"] == "Updated payment"


def test_duplicate_reference_on_update_returns_conflict(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)

    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="100.00",
        reference="EXISTING-001",
    )
    payment_to_update = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="200.00",
        reference="UPDATE-DUP-001",
    )
    db.commit()

    response = client.patch(
        f"/cases/payments/{payment_to_update.id}",
        json={
            "reference": "EXISTING-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 409
    assert "already exists for this business" in response.json()["detail"]


def test_missing_payment_cannot_be_updated(
    client,
    db,
    test_data,
    auth_headers,
):
    response = client.patch(
        f"/cases/payments/{uuid4()}",
        json={
            "amount": "500.00",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_delete_payment_recalculates_financials(
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

    first_payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="300.00",
        reference="DELETE-BEH-001",
    )
    create_payment(
        db,
        test_data["business_a"],
        case,
        amount="200.00",
        reference="DELETE-BEH-002",
    )
    db.commit()

    response = client.delete(
        f"/cases/payments/{first_payment.id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 204

    assert (
        db.query(CasePayment)
        .filter(CasePayment.id == first_payment.id)
        .first()
        is None
    )

    db.refresh(financial)

    assert financial.amount_paid == Decimal("200.00")
    assert financial.balance == Decimal("800.00")
    assert financial.credit == Decimal("0.00")
    assert financial.status == "partially_paid"


def test_deleting_final_payment_returns_financial_to_unpaid(
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

    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        amount="1000.00",
        reference="FINAL-PAYMENT-001",
    )
    db.commit()

    db.refresh(financial)
    assert financial.status == "unpaid"

    recalculate_response = client.post(
        f"/cases/{case.id}/payments",
        json={
            "amount": "0.01",
            "payment_method": "cash",
            "reference": "TEMP-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert recalculate_response.status_code == 201

    temp_payment_id = recalculate_response.json()["id"]

    delete_temp = client.delete(
        f"/cases/payments/{temp_payment_id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert delete_temp.status_code == 204

    db.refresh(financial)
    assert financial.amount_paid == Decimal("1000.00")
    assert financial.balance == Decimal("0.00")
    assert financial.status == "paid"

    delete_final = client.delete(
        f"/cases/payments/{payment.id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert delete_final.status_code == 204

    db.refresh(financial)

    assert financial.amount_paid == Decimal("0.00")
    assert financial.balance == Decimal("1000.00")
    assert financial.credit == Decimal("0.00")
    assert financial.status == "unpaid"


def test_missing_payment_cannot_be_deleted(
    client,
    db,
    test_data,
    auth_headers,
):
    response = client.delete(
        f"/cases/payments/{uuid4()}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"

def test_create_payment_for_missing_case_returns_404(
    client,
    db,
    test_data,
    auth_headers,
):
    response = client.post(
        f"/cases/{uuid4()}/payments",
        json={
            "amount": "100.00",
            "payment_method": "cash",
            "reference": "MISSING-CASE-001",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_update_payment_with_invalid_method_is_rejected(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"])
    create_financial(db, test_data["business_a"], case)
    payment = create_payment(
        db,
        test_data["business_a"],
        case,
        reference="INVALID-UPDATE-METHOD-001",
    )
    db.commit()

    response = client.patch(
        f"/cases/payments/{payment.id}",
        json={
            "payment_method": "bitcoin",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 422
