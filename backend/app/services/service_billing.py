"""Keeps quotes and invoices in step with the services on a case.

Staff add services to a case once. This module makes sure those services
reach the quote or invoice on their own, so nobody retypes them:

* a draft document picks up new services, price and quantity changes,
  and drops cancelled or deleted ones;
* a new draft can be built from everything on the case in one go.

Issued documents are frozen by design and are never touched here.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.case_service import CaseService
from app.models.financial_document import (
    FinancialDocument,
    FinancialDocumentLine,
)
from app.services.financial_documents import (
    calculate_line_total,
    money,
    next_position,
    recalculate_document,
)

# A service counts as already billed when it sits on a document in one of
# these states. Void and declined documents free the service again.
LIVE_STATUSES = ("draft", "issued", "accepted", "converted")


def _draft_documents(db: Session, case_id: UUID) -> list[FinancialDocument]:
    return (
        db.query(FinancialDocument)
        .filter(
            FinancialDocument.case_id == case_id,
            FinancialDocument.status == "draft",
        )
        .all()
    )


def _line_for(
    db: Session, document: FinancialDocument, service_id: UUID
) -> FinancialDocumentLine | None:
    return (
        db.query(FinancialDocumentLine)
        .filter(
            FinancialDocumentLine.document_id == document.id,
            FinancialDocumentLine.case_service_id == service_id,
        )
        .first()
    )


def _fit_discount(db: Session, document: FinancialDocument) -> None:
    """Recalculate, trimming a discount that no longer fits the subtotal."""

    db.flush()
    lines = (
        db.query(FinancialDocumentLine)
        .filter(FinancialDocumentLine.document_id == document.id)
        .all()
    )
    subtotal = money(sum((l.line_total for l in lines), Decimal("0")))
    if money(document.discount) > subtotal:
        document.discount = subtotal
    recalculate_document(db, document)


def _write_line(
    line: FinancialDocumentLine, service: CaseService
) -> None:
    line.description = service.service_name[:255]
    line.quantity = Decimal(service.quantity or 1)
    line.unit_price = money(service.unit_price or 0)
    line.line_total = calculate_line_total(line.quantity, line.unit_price)


def sync_service_into_drafts(db: Session, service: CaseService) -> int:
    """Add or refresh this service on every draft quote/invoice of its case.

    Returns how many draft documents were changed.
    """

    changed = 0
    for document in _draft_documents(db, service.case_id):
        line = _line_for(db, document, service.id)

        if service.status == "cancelled":
            if line is not None:
                db.delete(line)
                changed += 1
        elif line is None:
            line = FinancialDocumentLine(
                business_id=document.business_id,
                document_id=document.id,
                position=next_position(db, document),
                case_service_id=service.id,
                description=service.service_name[:255],
                quantity=Decimal(service.quantity or 1),
                unit_price=money(service.unit_price or 0),
                line_total=Decimal("0.00"),
            )
            _write_line(line, service)
            db.add(line)
            changed += 1
        else:
            _write_line(line, service)
            changed += 1

        _fit_discount(db, document)

    return changed


def remove_service_from_drafts(db: Session, service: CaseService) -> None:
    for document in _draft_documents(db, service.case_id):
        line = _line_for(db, document, service.id)
        if line is not None:
            db.delete(line)
            _fit_discount(db, document)


def unbilled_services(
    db: Session, case_id: UUID, document_type: str
) -> list[CaseService]:
    """Active services not yet on a live document of this type."""

    billed = (
        db.query(FinancialDocumentLine.case_service_id)
        .join(
            FinancialDocument,
            FinancialDocument.id == FinancialDocumentLine.document_id,
        )
        .filter(
            FinancialDocument.case_id == case_id,
            FinancialDocument.document_type == document_type,
            FinancialDocument.status.in_(LIVE_STATUSES),
            FinancialDocumentLine.case_service_id.isnot(None),
        )
    )

    return (
        db.query(CaseService)
        .filter(
            CaseService.case_id == case_id,
            CaseService.status != "cancelled",
            CaseService.id.notin_(billed),
        )
        .order_by(CaseService.created_at)
        .all()
    )


def add_missing_lines(
    db: Session,
    document: FinancialDocument,
    services: list[CaseService],
) -> int:
    position = next_position(db, document)
    for service in services:
        line = FinancialDocumentLine(
            business_id=document.business_id,
            document_id=document.id,
            position=position,
            case_service_id=service.id,
            description=service.service_name[:255],
            quantity=Decimal(service.quantity or 1),
            unit_price=money(service.unit_price or 0),
            line_total=Decimal("0.00"),
        )
        _write_line(line, service)
        db.add(line)
        position += 1
    _fit_discount(db, document)
    return len(services)
