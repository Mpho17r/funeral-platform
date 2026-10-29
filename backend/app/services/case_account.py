"""The case account follows the invoice.

What a family has to pay is on the case's invoice. Before this, the
account (what is owed, paid and left) was added up from the services
alone, so a line added only on the invoice never changed the amount due.

Now, when the case has a live invoice (the issued one, otherwise the
latest draft), the account takes its subtotal, discount and tax from it.
With no invoice the account is built from the services, as before. When
an invoice is voided and no other is live, the account goes back to the
services.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.case_financial import CaseFinancial
from app.models.case_service import CaseService
from app.models.financial_document import FinancialDocument

ZERO = Decimal("0.00")


def live_invoice(
    db: Session, case_id: UUID, business_id: UUID
) -> FinancialDocument | None:
    base = db.query(FinancialDocument).filter(
        FinancialDocument.case_id == case_id,
        FinancialDocument.business_id == business_id,
        FinancialDocument.document_type == "invoice",
    )
    issued = base.filter(FinancialDocument.status == "issued").first()
    if issued is not None:
        return issued
    return (
        base.filter(FinancialDocument.status == "draft")
        .order_by(FinancialDocument.created_at.desc())
        .first()
    )


def apply_invoice_basis(db: Session, financial: CaseFinancial) -> bool:
    """Copy the live invoice's amounts onto the account.

    Returns True when the amounts came from an invoice (so the tax on it
    is final and must not be recalculated).
    """

    db.flush()
    invoice = live_invoice(db, financial.case_id, financial.business_id)

    if invoice is not None:
        financial.subtotal = invoice.subtotal
        financial.discount = invoice.discount
        financial.tax = invoice.tax
        return True

    voided = (
        db.query(FinancialDocument.id)
        .filter(
            FinancialDocument.case_id == financial.case_id,
            FinancialDocument.business_id == financial.business_id,
            FinancialDocument.document_type == "invoice",
            FinancialDocument.status == "void",
        )
        .first()
    )
    if voided is not None:
        services = (
            db.query(CaseService)
            .filter(
                CaseService.case_id == financial.case_id,
                CaseService.business_id == financial.business_id,
            )
            .all()
        )
        financial.subtotal = sum(
            (s.total_price or ZERO for s in services), ZERO
        ).quantize(Decimal("0.01"))
        financial.discount = ZERO
        financial.tax = ZERO
    return False


def refresh_case_account(db: Session, case_id: UUID, business_id: UUID) -> None:
    """Bring the account in line after an invoice changes."""

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.case_id == case_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )
    if financial is None:
        return
    from app.api.financials import recalculate_financial

    recalculate_financial(db, financial)
