"""Price list helpers and quote/invoice building from a case's services."""

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
    get_lines,
    next_position,
    recalculate_document,
)

# A cancelled service is never billed.
UNBILLED_STATUSES = ("cancelled",)
# Documents that no longer count as "already billed".
DEAD_DOCUMENT_STATUSES = ("void", "declined")


def billable_services(db: Session, case_id: UUID, business_id: UUID):
    return (
        db.query(CaseService)
        .filter(
            CaseService.case_id == case_id,
            CaseService.business_id == business_id,
            CaseService.status.notin_(UNBILLED_STATUSES),
        )
        .order_by(CaseService.created_at, CaseService.id)
        .all()
    )


def already_billed_ids(
    db: Session, case_id: UUID, business_id: UUID, document_type: str
) -> set:
    rows = (
        db.query(FinancialDocumentLine.case_service_id)
        .join(
            FinancialDocument,
            FinancialDocument.id == FinancialDocumentLine.document_id,
        )
        .filter(
            FinancialDocument.case_id == case_id,
            FinancialDocument.business_id == business_id,
            FinancialDocument.document_type == document_type,
            FinancialDocument.status.notin_(DEAD_DOCUMENT_STATUSES),
            FinancialDocumentLine.case_service_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in rows}


def line_from_service(
    document: FinancialDocument, service: CaseService, position: int
) -> FinancialDocumentLine:
    return FinancialDocumentLine(
        business_id=document.business_id,
        document_id=document.id,
        position=position,
        description=service.service_name[:255],
        quantity=Decimal(service.quantity),
        unit_price=service.unit_price,
        line_total=calculate_line_total(service.quantity, service.unit_price),
        case_service_id=service.id,
    )


def sync_draft_with_services(
    db: Session, document: FinancialDocument
) -> dict:
    """Make a draft document match the case's services.

    Adds services that are missing, refreshes quantity and price on lines
    that came from a service, and drops lines whose service was cancelled
    or deleted. Lines typed in by hand are left alone.
    """

    services = {
        s.id: s
        for s in billable_services(db, document.case_id, document.business_id)
    }
    billed_elsewhere = already_billed_ids(
        db, document.case_id, document.business_id, document.document_type
    )

    added = updated = removed = 0
    on_this_document = set()

    for line in get_lines(db, document):
        if line.case_service_id is None:
            continue
        service = services.get(line.case_service_id)
        if service is None:
            db.delete(line)
            removed += 1
            continue
        on_this_document.add(service.id)
        if (
            Decimal(line.quantity) != Decimal(service.quantity)
            or Decimal(line.unit_price) != Decimal(service.unit_price)
            or line.description != service.service_name[:255]
        ):
            line.description = service.service_name[:255]
            line.quantity = Decimal(service.quantity)
            line.unit_price = service.unit_price
            line.line_total = calculate_line_total(
                service.quantity, service.unit_price
            )
            updated += 1

    db.flush()

    for service in services.values():
        if service.id in on_this_document:
            continue
        if service.id in billed_elsewhere:
            continue
        db.add(
            line_from_service(document, service, next_position(db, document))
        )
        db.flush()
        added += 1

    recalculate_document(db, document)

    return {"added": added, "updated": updated, "removed": removed}
