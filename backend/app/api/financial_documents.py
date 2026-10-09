from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.case_payment import CasePayment
from app.models.case_service import CaseService
from app.models.financial_document import (
    FinancialDocument,
    FinancialDocumentLine,
    PaymentReceipt,
)
from app.models.funeral_case import FuneralCase
from app.schemas.financial_document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentVoid,
    LineCreate,
    LineResponse,
    LineUpdate,
    ReceiptResponse,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.financial_documents import (
    INVOICE_DUE_DAYS,
    QUOTE_VALID_DAYS,
    DocumentError,
    calculate_line_total,
    ensure_draft,
    ensure_transition,
    get_lines,
    money,
    next_document_number,
    next_position,
    next_receipt_number,
    recalculate_document,
)


router = APIRouter(
    tags=["Quotes, Invoices and Receipts"],
)


# How many times issuing retries when two requests race for the same
# next number. The unique (business, number) index is the real guard.
NUMBER_RETRIES = 5

# Fields whose changes are recorded in the audit trail. Notes are
# redacted by the audit service, which records only that they changed.
AUDITED_DOCUMENT_FIELDS = (
    "discount",
    "tax",
    "valid_until",
    "due_date",
    "notes",
)


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def get_user_id(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


def fail(db: Session, error: DocumentError):
    """Discard any half-applied change, then report the rule that failed."""
    db.rollback()

    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


def get_case_or_404(
    db: Session,
    case_id: UUID,
    business_id: UUID,
) -> FuneralCase:
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


def get_document_or_404(
    db: Session,
    document_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> FinancialDocument:
    query = db.query(FinancialDocument).filter(
        FinancialDocument.id == document_id,
        FinancialDocument.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    document = query.first()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial document not found",
        )

    return document


def get_line_or_404(
    db: Session,
    document: FinancialDocument,
    line_id: UUID,
) -> FinancialDocumentLine:
    line = (
        db.query(FinancialDocumentLine)
        .filter(
            FinancialDocumentLine.id == line_id,
            FinancialDocumentLine.document_id == document.id,
            FinancialDocumentLine.business_id == document.business_id,
        )
        .first()
    )

    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document line not found",
        )

    return line


def document_response(
    db: Session,
    document: FinancialDocument,
) -> DocumentResponse:
    response = DocumentResponse.model_validate(document)

    response.lines = [
        LineResponse.model_validate(line)
        for line in get_lines(db, document)
    ]

    return response


def validate_type_fields(
    document_type: str,
    *,
    valid_until: date | None,
    due_date: date | None,
) -> None:
    """Quotes carry a validity date, invoices carry a due date."""

    if document_type == "invoice" and valid_until is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="valid_until applies to quotes only",
        )

    if document_type == "quote" and due_date is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date applies to invoices only",
        )


def validate_case_service(
    db: Session,
    *,
    case_service_id: UUID | None,
    case_id: UUID,
    business_id: UUID,
) -> None:
    """A line may only point at a service on the same case and business."""

    if case_service_id is None:
        return

    service = (
        db.query(CaseService.id)
        .filter(
            CaseService.id == case_service_id,
            CaseService.case_id == case_id,
            CaseService.business_id == business_id,
        )
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Case service not found on this case",
        )


def build_line(
    document: FinancialDocument,
    data: LineCreate,
    position: int,
) -> FinancialDocumentLine:
    return FinancialDocumentLine(
        business_id=document.business_id,
        document_id=document.id,
        position=position,
        description=data.description.strip(),
        quantity=data.quantity,
        unit_price=data.unit_price,
        line_total=calculate_line_total(
            data.quantity,
            data.unit_price,
        ),
        case_service_id=data.case_service_id,
    )


def audit_document(
    db: Session,
    *,
    document: FinancialDocument,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    details = {
        "case_id": str(document.case_id),
        "document_type": document.document_type,
        "number": document.number,
        "status": document.status,
    }

    if extra:
        details.update(extra)

    create_audit_log(
        db,
        business_id=document.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="financial_document",
        entity_id=document.id,
        details=details,
        notes=notes,
    )


# ============================================================
# DOCUMENTS: CREATE (always a draft)
# ============================================================

@router.post(
    "/cases/{case_id}/financial-documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    case_id: UUID,
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    case = get_case_or_404(db, case_id, business_id)

    if case.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived cases cannot receive new documents",
        )

    validate_type_fields(
        data.document_type,
        valid_until=data.valid_until,
        due_date=data.due_date,
    )

    for line in data.lines:
        validate_case_service(
            db,
            case_service_id=line.case_service_id,
            case_id=case.id,
            business_id=business_id,
        )

    document = FinancialDocument(
        business_id=business_id,
        case_id=case.id,
        document_type=data.document_type,
        status="draft",
        # Discount and tax are applied after the lines exist. The
        # database requires discount <= subtotal, and the subtotal is
        # zero until the lines are in.
        discount=Decimal("0.00"),
        tax=Decimal("0.00"),
        valid_until=data.valid_until,
        due_date=data.due_date,
        notes=data.notes,
        created_by=get_user_id(current_user),
    )

    db.add(document)
    db.flush()

    for position, line in enumerate(data.lines):
        db.add(build_line(document, line, position))

    db.flush()

    document.discount = money(data.discount)
    document.tax = money(data.tax)

    try:
        recalculate_document(db, document)
    except DocumentError as error:
        fail(db, error)

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.created",
        notes="Financial document draft was created.",
        extra={
            "total": str(document.total),
            "line_count": len(data.lines),
        },
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


# ============================================================
# DOCUMENTS: READ
# ============================================================

@router.get(
    "/cases/{case_id}/financial-documents",
    response_model=list[DocumentResponse],
)
def list_case_documents(
    case_id: UUID,
    document_type: str | None = None,
    document_status: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.view")
    ),
):
    business_id = get_business_id(current_user)

    get_case_or_404(db, case_id, business_id)

    query = db.query(FinancialDocument).filter(
        FinancialDocument.business_id == business_id,
        FinancialDocument.case_id == case_id,
    )

    if document_type is not None:
        query = query.filter(
            FinancialDocument.document_type == document_type
        )

    if document_status is not None:
        query = query.filter(
            FinancialDocument.status == document_status
        )

    documents = query.order_by(
        FinancialDocument.created_at.desc()
    ).all()

    return [document_response(db, doc) for doc in documents]


@router.get(
    "/financial-documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    document_type: str | None = None,
    document_status: str | None = None,
    case_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.view")
    ),
):
    business_id = get_business_id(current_user)

    query = db.query(FinancialDocument).filter(
        FinancialDocument.business_id == business_id,
    )

    if document_type is not None:
        query = query.filter(
            FinancialDocument.document_type == document_type
        )

    if document_status is not None:
        query = query.filter(
            FinancialDocument.status == document_status
        )

    if case_id is not None:
        query = query.filter(FinancialDocument.case_id == case_id)

    documents = query.order_by(
        FinancialDocument.created_at.desc()
    ).all()

    return [document_response(db, doc) for doc in documents]


@router.get(
    "/financial-documents/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.view")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(db, document_id, business_id)

    return document_response(db, document)


# ============================================================
# DOCUMENTS: EDIT AND DELETE (drafts only)
# ============================================================

@router.patch(
    "/financial-documents/{document_id}",
    response_model=DocumentResponse,
)
def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_draft(document)
    except DocumentError as error:
        fail(db, error)

    updates = data.model_dump(exclude_unset=True)

    validate_type_fields(
        document.document_type,
        valid_until=updates.get("valid_until"),
        due_date=updates.get("due_date"),
    )

    # Discount and tax are required columns, so null is not a change.
    for required in ("discount", "tax"):
        if required in updates and updates[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{required} cannot be null",
            )

    old_values = snapshot_fields(document, AUDITED_DOCUMENT_FIELDS)

    for field, value in updates.items():
        setattr(document, field, value)

    try:
        recalculate_document(db, document)
    except DocumentError as error:
        fail(db, error)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(document, AUDITED_DOCUMENT_FIELDS),
    )

    if changes:
        audit_document(
            db,
            document=document,
            current_user=current_user,
            action="financial_document.updated",
            notes="Financial document draft was updated.",
            extra={"changes": changes},
        )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


@router.delete(
    "/financial-documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_draft(document)
    except DocumentError as error:
        fail(db, error)

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.deleted",
        notes="Financial document draft was deleted.",
        extra={"total": str(document.total)},
    )

    db.delete(document)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# LINES (drafts only)
# ============================================================

@router.post(
    "/financial-documents/{document_id}/lines",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_line(
    document_id: UUID,
    data: LineCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_draft(document)
    except DocumentError as error:
        fail(db, error)

    validate_case_service(
        db,
        case_service_id=data.case_service_id,
        case_id=document.case_id,
        business_id=business_id,
    )

    line = build_line(document, data, next_position(db, document))

    db.add(line)
    db.flush()

    try:
        recalculate_document(db, document)
    except DocumentError as error:
        fail(db, error)

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.line_added",
        notes="A line was added to a financial document draft.",
        extra={
            "line_id": str(line.id),
            "line_total": str(line.line_total),
            "document_total": str(document.total),
        },
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


@router.patch(
    "/financial-documents/{document_id}/lines/{line_id}",
    response_model=DocumentResponse,
)
def update_line(
    document_id: UUID,
    line_id: UUID,
    data: LineUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_draft(document)
    except DocumentError as error:
        fail(db, error)

    line = get_line_or_404(db, document, line_id)

    updates = data.model_dump(exclude_unset=True)

    for required in ("description", "quantity", "unit_price"):
        if required in updates and updates[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{required} cannot be null",
            )

    old_values = snapshot_fields(
        line,
        ("description", "quantity", "unit_price", "line_total"),
    )

    if "description" in updates:
        line.description = updates["description"].strip()

    # Normalised to two decimals so audit values compare like for like.
    if "quantity" in updates:
        line.quantity = money(updates["quantity"])

    if "unit_price" in updates:
        line.unit_price = money(updates["unit_price"])

    line.line_total = calculate_line_total(
        line.quantity,
        line.unit_price,
    )

    try:
        recalculate_document(db, document)
    except DocumentError as error:
        fail(db, error)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(
            line,
            ("description", "quantity", "unit_price", "line_total"),
        ),
    )

    if changes:
        audit_document(
            db,
            document=document,
            current_user=current_user,
            action="financial_document.line_updated",
            notes="A line on a financial document draft was updated.",
            extra={
                "line_id": str(line.id),
                "changes": changes,
                "document_total": str(document.total),
            },
        )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


@router.delete(
    "/financial-documents/{document_id}/lines/{line_id}",
    response_model=DocumentResponse,
)
def remove_line(
    document_id: UUID,
    line_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_draft(document)
    except DocumentError as error:
        fail(db, error)

    line = get_line_or_404(db, document, line_id)

    removed = {
        "line_id": str(line.id),
        "line_total": str(line.line_total),
    }

    db.delete(line)
    db.flush()

    try:
        recalculate_document(db, document)
    except DocumentError as error:
        fail(db, error)

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.line_removed",
        notes="A line was removed from a financial document draft.",
        extra={
            **removed,
            "document_total": str(document.total),
        },
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


# ============================================================
# WORKFLOW: ISSUE
# ============================================================

@router.post(
    "/financial-documents/{document_id}/issue",
    response_model=DocumentResponse,
)
def issue_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.issue")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_transition(
            document.document_type,
            document.status,
            "issued",
        )
    except DocumentError as error:
        fail(db, error)

    lines = get_lines(db, document)

    if not lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A document needs at least one line before it "
            "can be issued",
        )

    if document.document_type == "invoice":
        existing = (
            db.query(FinancialDocument.number)
            .filter(
                FinancialDocument.case_id == document.case_id,
                FinancialDocument.business_id == business_id,
                FinancialDocument.document_type == "invoice",
                FinancialDocument.status == "issued",
            )
            .first()
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"This case already has an issued invoice "
                    f"({existing[0]}). Void it before issuing another."
                ),
            )

    now = datetime.now(timezone.utc)
    today = now.date()

    for attempt in range(NUMBER_RETRIES):
        number = next_document_number(
            db,
            business_id,
            document.document_type,
        )

        try:
            with db.begin_nested():
                document.number = number
                document.status = "issued"
                document.issued_at = now
                document.issued_by = get_user_id(current_user)

                if (
                    document.document_type == "quote"
                    and document.valid_until is None
                ):
                    document.valid_until = today + timedelta(
                        days=QUOTE_VALID_DAYS
                    )

                if (
                    document.document_type == "invoice"
                    and document.due_date is None
                ):
                    document.due_date = today + timedelta(
                        days=INVOICE_DUE_DAYS
                    )

                db.flush()

            break

        except IntegrityError as error:
            message = str(error.orig)

            if "one_issued_invoice_per_case" in message:
                db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This case already has an issued invoice",
                )

            # Someone else took this number. Reload and try the next.
            db.refresh(document)

            if attempt == NUMBER_RETRIES - 1:
                db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not assign a document number. "
                    "Please try again.",
                )

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.issued",
        notes="Financial document was issued.",
        extra={"total": str(document.total)},
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


# ============================================================
# WORKFLOW: QUOTE DECISIONS AND CONVERSION
# ============================================================

def get_quote_for_decision(
    db: Session,
    document_id: UUID,
    business_id: UUID,
) -> FinancialDocument:
    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    if document.document_type != "quote":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only quotes can be accepted, declined or converted",
        )

    return document


@router.post(
    "/financial-documents/{document_id}/accept",
    response_model=DocumentResponse,
)
def accept_quote(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_quote_for_decision(db, document_id, business_id)

    try:
        ensure_transition("quote", document.status, "accepted")
    except DocumentError as error:
        fail(db, error)

    now = datetime.now(timezone.utc)

    if (
        document.valid_until is not None
        and document.valid_until < now.date()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This quote has expired and can no longer be "
            "accepted",
        )

    document.status = "accepted"
    document.accepted_at = now

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.accepted",
        notes="Quote was accepted.",
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


@router.post(
    "/financial-documents/{document_id}/decline",
    response_model=DocumentResponse,
)
def decline_quote(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    business_id = get_business_id(current_user)

    document = get_quote_for_decision(db, document_id, business_id)

    try:
        ensure_transition("quote", document.status, "declined")
    except DocumentError as error:
        fail(db, error)

    document.status = "declined"

    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.declined",
        notes="Quote was declined.",
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


@router.post(
    "/financial-documents/{document_id}/convert",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def convert_quote_to_invoice(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.manage")
    ),
):
    """Turn an accepted quote into a draft invoice.

    The quote is marked converted and stays on record. The invoice is
    a draft, so it can still be reviewed before it is issued.
    """

    business_id = get_business_id(current_user)

    quote = get_quote_for_decision(db, document_id, business_id)

    try:
        ensure_transition("quote", quote.status, "converted")
    except DocumentError as error:
        fail(db, error)

    invoice = FinancialDocument(
        business_id=business_id,
        case_id=quote.case_id,
        document_type="invoice",
        status="draft",
        discount=Decimal("0.00"),
        tax=Decimal("0.00"),
        notes=quote.notes,
        source_quote_id=quote.id,
        created_by=get_user_id(current_user),
    )

    db.add(invoice)
    db.flush()

    for source in get_lines(db, quote):
        db.add(
            FinancialDocumentLine(
                business_id=business_id,
                document_id=invoice.id,
                position=source.position,
                description=source.description,
                quantity=source.quantity,
                unit_price=source.unit_price,
                line_total=source.line_total,
                case_service_id=source.case_service_id,
            )
        )

    db.flush()

    invoice.discount = quote.discount
    invoice.tax = quote.tax

    try:
        recalculate_document(db, invoice)
    except DocumentError as error:
        fail(db, error)

    quote.status = "converted"

    audit_document(
        db,
        document=quote,
        current_user=current_user,
        action="financial_document.converted",
        notes="Quote was converted into a draft invoice.",
        extra={"invoice_id": str(invoice.id)},
    )

    audit_document(
        db,
        document=invoice,
        current_user=current_user,
        action="financial_document.created",
        notes="Draft invoice was created from a quote.",
        extra={
            "source_quote_id": str(quote.id),
            "total": str(invoice.total),
        },
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This quote has already been converted",
        )

    db.refresh(invoice)

    return document_response(db, invoice)


# ============================================================
# WORKFLOW: VOID
# ============================================================

@router.post(
    "/financial-documents/{document_id}/void",
    response_model=DocumentResponse,
)
def void_document(
    document_id: UUID,
    data: DocumentVoid,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("financial_documents.void")
    ),
):
    business_id = get_business_id(current_user)

    document = get_document_or_404(
        db, document_id, business_id, lock=True
    )

    try:
        ensure_transition(
            document.document_type,
            document.status,
            "void",
        )
    except DocumentError as error:
        fail(db, error)

    document.status = "void"
    document.voided_at = datetime.now(timezone.utc)
    document.voided_by = get_user_id(current_user)
    document.void_reason = data.reason.strip()

    # The reason lives on the document. The audit entry records that
    # one was given, not its text.
    audit_document(
        db,
        document=document,
        current_user=current_user,
        action="financial_document.voided",
        notes="Financial document was voided.",
        extra={"reason_recorded": True},
    )

    db.commit()
    db.refresh(document)

    return document_response(db, document)


# ============================================================
# RECEIPTS
# ============================================================

def get_payment_or_404(
    db: Session,
    payment_id: UUID,
    business_id: UUID,
) -> CasePayment:
    payment = (
        db.query(CasePayment)
        .filter(
            CasePayment.id == payment_id,
            CasePayment.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return payment


@router.post(
    "/cases/payments/{payment_id}/receipt",
    response_model=ReceiptResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_receipt(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("receipts.issue")),
):
    """Issue the receipt for a payment.

    The receipt snapshots the payment. From then on the payment can no
    longer be edited or deleted.
    """

    business_id = get_business_id(current_user)

    payment = get_payment_or_404(db, payment_id, business_id)

    already = (
        db.query(PaymentReceipt.receipt_number)
        .filter(PaymentReceipt.payment_id == payment.id)
        .first()
    )

    if already is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A receipt has already been issued for this "
            f"payment ({already[0]})",
        )

    case = get_case_or_404(db, payment.case_id, business_id)

    receipt = None

    for attempt in range(NUMBER_RETRIES):
        candidate = PaymentReceipt(
            business_id=business_id,
            case_id=case.id,
            payment_id=payment.id,
            receipt_number=next_receipt_number(db, business_id),
            case_number=case.case_number,
            amount=payment.amount,
            payment_method=payment.payment_method,
            payment_reference=payment.reference,
            payment_date=payment.payment_date,
            issued_by=get_user_id(current_user),
        )

        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()

            receipt = candidate
            break

        except IntegrityError:
            # Either the number was taken, or the payment now has a
            # receipt. Look before deciding which.
            db.expire_all()

            if (
                db.query(PaymentReceipt.id)
                .filter(PaymentReceipt.payment_id == payment_id)
                .first()
                is not None
            ):
                db.rollback()

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A receipt has already been issued for "
                    "this payment",
                )

    if receipt is None:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not assign a receipt number. "
            "Please try again.",
        )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=get_user_id(current_user),
        action="receipt.issued",
        entity_type="payment_receipt",
        entity_id=receipt.id,
        details={
            "case_id": str(case.id),
            "payment_id": str(payment.id),
            "receipt_number": receipt.receipt_number,
            "amount": str(receipt.amount),
        },
        notes="Payment receipt was issued.",
    )

    db.commit()
    db.refresh(receipt)

    return receipt


@router.get(
    "/cases/payments/{payment_id}/receipt",
    response_model=ReceiptResponse,
)
def get_payment_receipt(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("receipts.view")),
):
    business_id = get_business_id(current_user)

    receipt = (
        db.query(PaymentReceipt)
        .filter(
            PaymentReceipt.payment_id == payment_id,
            PaymentReceipt.business_id == business_id,
        )
        .first()
    )

    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )

    return receipt


@router.get(
    "/cases/{case_id}/receipts",
    response_model=list[ReceiptResponse],
)
def list_case_receipts(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("receipts.view")),
):
    business_id = get_business_id(current_user)

    get_case_or_404(db, case_id, business_id)

    return (
        db.query(PaymentReceipt)
        .filter(
            PaymentReceipt.case_id == case_id,
            PaymentReceipt.business_id == business_id,
        )
        .order_by(PaymentReceipt.issued_at.desc())
        .all()
    )


@router.get(
    "/receipts/{receipt_id}",
    response_model=ReceiptResponse,
)
def get_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("receipts.view")),
):
    business_id = get_business_id(current_user)

    receipt = (
        db.query(PaymentReceipt)
        .filter(
            PaymentReceipt.id == receipt_id,
            PaymentReceipt.business_id == business_id,
        )
        .first()
    )

    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )

    return receipt
