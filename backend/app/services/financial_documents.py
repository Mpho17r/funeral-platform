"""Quote and invoice rules.

Pure business rules with no HTTP concerns, so the same rules can later
serve portals, automation and integrations.
"""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

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
    """Recompute subtotal and total from the lines.

    Raises DocumentError(422) if the discount would exceed the
    subtotal, so callers get a clean error instead of a constraint
    violation.
    """

    lines = get_lines(db, document)

    subtotal = money(
        sum((line.line_total for line in lines), Decimal("0"))
    )

    discount = money(document.discount)
    tax = money(document.tax)

    if discount > subtotal:
        raise DocumentError(
            422,
            "Discount cannot be greater than the subtotal",
        )

    document.subtotal = subtotal
    document.discount = discount
    document.tax = tax
    document.total = money(subtotal - discount + tax)

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
