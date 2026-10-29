"""What the family owes follows the invoice, not just the services."""

from decimal import Decimal

from app.models.business import Business
from app.models.case_financial import CaseFinancial
from tests.test_branches import make_case
from tests.test_financial_documents import (
    create_document, issue, make_payment, make_service,
)


def account(db, case):
    db.expire_all()
    return db.query(CaseFinancial).filter(CaseFinancial.case_id == case.id).one()


def setup(db, test_data, price=100):
    biz = db.get(Business, test_data["business_a"].id)
    case = make_case(db, biz)
    make_service(db, biz, case, price=price)
    db.add(CaseFinancial(
        business_id=biz.id, case_id=case.id, status="unpaid",
        subtotal=Decimal(price), discount=Decimal("0"), tax=Decimal("0"),
        total=Decimal(price), amount_paid=Decimal("0"), balance=Decimal(price),
        credit=Decimal("0"),
    ))
    db.commit()
    return biz, case


def test_a_line_only_on_the_invoice_raises_the_amount_due(client, auth_headers, db, test_data):
    biz, case = setup(db, test_data)
    headers = auth_headers(test_data["manager"])
    doc = create_document(
        client, headers, case, "invoice", discount="0", tax="0",
        due_date="2030-01-01",
        lines=[{"description": "Coffin", "quantity": "1", "unit_price": "100.00"},
               {"description": "Extra car (not in services)", "quantity": "1", "unit_price": "400.00"}],
    )
    # Even as a draft, the account already follows the invoice.
    assert account(db, case).total == Decimal("500.00")
    assert issue(client, headers, doc["id"]).status_code == 200
    f = account(db, case)
    assert f.total == Decimal("500.00") and f.balance == Decimal("500.00")


def test_payments_are_measured_against_the_invoice(client, auth_headers, db, test_data):
    biz, case = setup(db, test_data)
    headers = auth_headers(test_data["manager"])
    create_document(client, headers, case, "invoice", discount="0", tax="0",
                    due_date="2030-01-01",
                    lines=[{"description": "All in", "quantity": "1", "unit_price": "800.00"}])
    r = client.post(f"/cases/{case.id}/payments", headers=headers,
                    json={"amount": "300.00", "payment_method": "eft",
                          "payment_date": "2026-10-02", "reference": "R-1"})
    assert r.status_code == 201, r.text
    f = account(db, case)
    assert f.total == Decimal("800.00") and f.balance == Decimal("500.00")


def test_voiding_the_invoice_returns_to_the_services(client, auth_headers, db, test_data):
    biz, case = setup(db, test_data)
    headers = auth_headers(test_data["manager"])
    doc = create_document(client, headers, case, "invoice", discount="0", tax="0",
                          due_date="2030-01-01",
                          lines=[{"description": "Big", "quantity": "1", "unit_price": "900.00"}])
    assert issue(client, headers, doc["id"]).status_code == 200
    assert account(db, case).total == Decimal("900.00")
    r = client.post(f"/financial-documents/{doc['id']}/void", headers=headers,
                    json={"reason": "Wrong amount"})
    assert r.status_code == 200, r.text
    assert account(db, case).total == Decimal("100.00")


def test_vat_on_the_invoice_is_what_is_owed(client, auth_headers, db, test_data):
    biz, case = setup(db, test_data)
    biz.tax_enabled, biz.tax_rate = True, Decimal("15.00")
    db.commit()
    headers = auth_headers(test_data["manager"])
    create_document(client, headers, case, "invoice", discount="0", tax="0",
                    due_date="2030-01-01",
                    lines=[{"description": "Hearse", "quantity": "1", "unit_price": "1000.00"}])
    f = account(db, case)
    assert f.subtotal == Decimal("1000.00") and f.tax == Decimal("150.00")
    assert f.total == Decimal("1150.00")
