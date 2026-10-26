"""Quote and invoice rules.

Pure business rules with no HTTP concerns, so the same rules can later
serve portals, automation and integrations.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business import Business
from app.services.vat import calculate_vat, STANDARD_VAT_RATE

from app.models.financial_document import (
    FinancialDocument,
    FinancialDocumentLine,
    PaymentReceipt,
)


CENT = Decimal("0.01")

QUOTE_VALID_DAYS = 30

INVOICE_DUE_DAYS = 14

NUMBER_PREFIX = {
    "quote": "QUO",
    "invoice": "INV",
}

TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "quote": {
        "draft": {"issued"},
        "issued": {"accepted", "declined", "void"},
        "accepted": {"converted", "void"},
        "declined": set(),
        "converted": set(),
        "void": set(),
    },
    "invoice": {
        "draft": {"issued"},
        "issued": {"void"},
        "void": set(),
    },
}


class DocumentError(Exception):
    """A financial document rule was violated."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_line_total(quantity, unit_price) -> Decimal:
    return money(Decimal(str(quantity)) * Decimal(str(unit_price)))


def ensure_transition(
    document_type: str,
    current: str,
    target: str,
) -> None:
    allowed = TRANSITIONS[document_type].get(current, set())

    if target not in allowed:
        raise DocumentError(
            409,
            f"A {document_type} that is '{current}' cannot become "
            f"'{target}'",
        )


def ensure_draft(document: FinancialDocument) -> None:
    if document.status != "draft":
        raise DocumentError(
            409,
            "Only draft documents can be changed. Issued documents "
            "are permanent and can only be voided.",
        )


def get_lines(
    db: Session,
    document: FinancialDocument,
) -> list[FinancialDocumentLine]:
    return (
        db.query(FinancialDocumentLine)
        .filter(
            FinancialDocumentLine.document_id == document.id,
            FinancialDocumentLine.business_id == document.business_id,
        )
        .order_by(
            FinancialDocumentLine.position,
            FinancialDocumentLine.created_at,
            FinancialDocumentLine.id,
        )
        .all()
    )


def recalculate_document(
    db: Session,
    document: FinancialDocument,
) -> FinancialDocument:
    """Recompute document totals and VAT from its lines.

    Tax treatment is stored on each line. VAT registration, pricing
    convention and the rate are snapshotted on the draft so later settings
    changes do not rewrite an issued document's tax history.
    """
    lines = get_lines(db, document)
    subtotal = money(sum((line.line_total for line in lines), Decimal("0")))
    discount = money(document.discount)

    if discount > subtotal:
        raise DocumentError(422, "Discount cannot be greater than the subtotal")

    business = db.get(Business, document.business_id)
    if business is None:
        raise DocumentError(404, "Business not found")

    if document.vat_registered_snapshot is None:
        document.vat_registered_snapshot = bool(business.vat_registered)
    if document.prices_include_vat_snapshot is None:
        document.prices_include_vat_snapshot = bool(business.prices_include_vat)
    if document.vat_rate_snapshot is None:
        document.vat_rate_snapshot = STANDARD_VAT_RATE

    # For VAT-registered businesses, VAT is system-calculated and ignores
    # any legacy/manual tax value submitted by the client.
    vat_enabled = bool(document.vat_registered_snapshot)
    total_line_tax = Decimal("0.00")
    manual_tax = money(document.tax)

    allocated_discount = []
    allocated_so_far = Decimal("0.00")
    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            line_discount = money(discount - allocated_so_far)
        elif subtotal > 0:
            line_discount = money(discount * line.line_total / subtotal)
            allocated_so_far += line_discount
        else:
            line_discount = Decimal("0.00")
        allocated_discount.append(line_discount)

    for line, line_discount in zip(lines, allocated_discount):
        discounted_amount = money(line.line_total - line_discount)
        calculation = calculate_vat(
            discounted_amount,
            vat_registered=vat_enabled,
            prices_include_vat=bool(document.prices_include_vat_snapshot),
            treatment=line.tax_treatment,
            rate=Decimal(str(document.vat_rate_snapshot)),
        )
        line.vat_rate = calculation.vat_rate
        line.taxable_value = calculation.taxable_value
        line.tax_amount = calculation.vat_amount
        total_line_tax += calculation.vat_amount

    document.subtotal = subtotal
    document.discount = discount
    if vat_enabled:
        document.tax = money(total_line_tax)
        if document.prices_include_vat_snapshot:
            # The entered prices already include VAT.
            document.total = money(subtotal - discount)
        else:
            document.total = money(subtotal - discount + document.tax)
    else:
        # Keep legacy non-VAT tax handling backward-compatible; the new UI
        # will not treat this manual amount as VAT.
        document.tax = manual_tax
        document.total = money(subtotal - discount + manual_tax)

    return document


def next_position(db: Session, document: FinancialDocument) -> int:
    highest = (
        db.query(func.max(FinancialDocumentLine.position))
        .filter(FinancialDocumentLine.document_id == document.id)
        .scalar()
    )

    return 0 if highest is None else highest + 1


def next_document_number(
    db: Session,
    business_id: UUID,
    document_type: str,
) -> str:
    """Next number for issued documents of this type, e.g.
    INV-2026-00004.

    Numbers are assigned only when a document is issued, so drafts
    that are discarded never leave gaps. The unique
    (business_id, number) index is the real guard; callers retry on a
    collision.
    """

    year = datetime.now(timezone.utc).year
    prefix = NUMBER_PREFIX[document_type]

    issued_so_far = (
        db.query(func.count(FinancialDocument.id))
        .filter(
            FinancialDocument.business_id == business_id,
            FinancialDocument.document_type == document_type,
            FinancialDocument.number.isnot(None),
        )
        .scalar()
    )

    return f"{prefix}-{year}-{issued_so_far + 1:05d}"


def next_receipt_number(db: Session, business_id: UUID) -> str:
    year = datetime.now(timezone.utc).year

    issued_so_far = (
        db.query(func.count(PaymentReceipt.id))
        .filter(PaymentReceipt.business_id == business_id)
        .scalar()
    )

    return f"REC-{year}-{issued_so_far + 1:05d}"
