from uuid import UUID

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.orm import Session

from app.database import get_db

from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase

from app.models.case_contact import CaseContact

from app.models.case_document import CaseDocument

from app.models.case_service import CaseService

from app.models.case_task import CaseTask

from app.models.case_financial import CaseFinancial

from app.models.case_payment import CasePayment

from app.models.membership import Membership

from app.models.covered_dependent import CoveredDependent

from app.schemas.funeral_case import (
    FuneralCaseCreate,
    FuneralCaseUpdate,
    FuneralCaseResponse,
)

from app.schemas.case_summary import (
    CaseSummaryResponse,
    CaseContactSummary,
    CaseTaskSummary,
    CaseDocumentSummary,
    CaseServiceSummary,
    CasePaymentSummary,
    CaseFinancialSummary,
)

from app.services.membership_status import is_membership_covered


router = APIRouter(
    prefix="/cases",
    tags=["Funeral Cases"],
)


# ============================================================
# MEMBERSHIP / COVERAGE VALIDATION HELPERS
# ============================================================

def validate_case_coverage_links(
    db: Session,
    business_id,
    membership_id: UUID | None,
    covered_dependent_id: UUID | None,
    coverage_date,
):
    """
    Validate membership/dependent relationships for a funeral case.

    This function does NOT reject an uncovered member.

    An uncovered case can still be created because staff need to
    record and manage the funeral even when the business will not
    provide cover benefits.

    Returns:
        membership
        covered_dependent
        membership_covered
        dependent_covered
    """

    membership = None
    covered_dependent = None
    membership_covered = False
    dependent_covered = False

    # --------------------------------------------------------
    # DEPENDENT CANNOT EXIST WITHOUT A MEMBERSHIP
    # --------------------------------------------------------

    if covered_dependent_id is not None and membership_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A covered dependent requires a membership."
            ),
        )

    # --------------------------------------------------------
    # MEMBERSHIP VALIDATION
    # --------------------------------------------------------

    if membership_id is not None:
        membership = (
            db.query(Membership)
            .filter(
                Membership.id == membership_id,
                Membership.business_id == business_id,
            )
            .first()
        )

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Membership not found for this business",
            )

        membership_covered = is_membership_covered(
            db,
            membership,
            today=coverage_date,
        )

    # --------------------------------------------------------
    # COVERED DEPENDENT VALIDATION
    # --------------------------------------------------------

    if covered_dependent_id is not None:
        covered_dependent = (
            db.query(CoveredDependent)
            .filter(
                CoveredDependent.id == covered_dependent_id,
                CoveredDependent.business_id == business_id,
            )
            .first()
        )

        if not covered_dependent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Covered dependent not found for this business"
                ),
            )

        if (
            membership is None
            or covered_dependent.membership_id != membership.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Covered dependent does not belong to the selected membership"
                ),
            )

        # ----------------------------------------------------
        # DEPENDENT STATUS / COVER DATES
        # ----------------------------------------------------

        dependent_covered = (
            covered_dependent.status == "active"
            and covered_dependent.cover_start_date <= coverage_date
            and (
                covered_dependent.cover_end_date is None
                or coverage_date <= covered_dependent.cover_end_date
            )
        )

    return (
        membership,
        covered_dependent,
        membership_covered,
        dependent_covered,
    )


def get_case_coverage_date(
    funeral_date,
    date_of_death,
):
    """
    Determine the date used when evaluating funeral cover.

    Prefer date of death because cover should be determined at
    the time of death.

    Fall back to funeral date when date of death is unavailable.

    If neither exists, use today's date.
    """

    if date_of_death is not None:
        return date_of_death

    if funeral_date is not None:
        return funeral_date

    from datetime import date

    return date.today()


# ============================================================
# LIST CASES
# ============================================================

@router.get(
    "",
    response_model=list[FuneralCaseResponse],
)
def list_cases(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.view")),
):
    cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == current_user["business_id"]
        )
        .order_by(FuneralCase.created_at.desc())
        .all()
    )

    return cases


# ============================================================
# CREATE CASE
# ============================================================

@router.post(
    "",
    response_model=FuneralCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case(
    data: FuneralCaseCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.create")),
):
    business_id = current_user["business_id"]

    # --------------------------------------------------------
    # PREVENT DUPLICATE CASE NUMBERS
    # --------------------------------------------------------

    existing_case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.case_number == data.case_number,
        )
        .first()
    )

    if existing_case:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case number already exists for this business",
        )

    # --------------------------------------------------------
    # DETERMINE COVERAGE DATE
    # --------------------------------------------------------

    coverage_date = get_case_coverage_date(
        data.funeral_date,
        data.date_of_death,
    )

    # --------------------------------------------------------
    # VALIDATE MEMBERSHIP / DEPENDENT LINKS
    # --------------------------------------------------------

    validate_case_coverage_links(
        db=db,
        business_id=business_id,
        membership_id=data.membership_id,
        covered_dependent_id=data.covered_dependent_id,
        coverage_date=coverage_date,
    )

    # --------------------------------------------------------
    # CREATE CASE
    # --------------------------------------------------------

    case = FuneralCase(
        business_id=business_id,
        **data.model_dump(),
    )

    db.add(case)
    db.commit()
    db.refresh(case)

    return case


# ============================================================
# CASE SUMMARY
# ============================================================

@router.get(
    "/{case_id}/summary",
    response_model=CaseSummaryResponse,
)
def get_case_summary(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.view")),
):
    business_id = current_user["business_id"]

    # --------------------------------------------------------
    # GET CASE
    # --------------------------------------------------------

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    # --------------------------------------------------------
    # CONTACTS
    # --------------------------------------------------------

    contacts_count = (
        db.query(CaseContact)
        .filter(
            CaseContact.case_id == case_id,
            CaseContact.business_id == business_id,
        )
        .count()
    )

    # --------------------------------------------------------
    # DOCUMENTS
    # --------------------------------------------------------

    documents_count = (
        db.query(CaseDocument)
        .filter(
            CaseDocument.case_id == case_id,
            CaseDocument.business_id == business_id,
        )
        .count()
    )

    # --------------------------------------------------------
    # SERVICES
    # --------------------------------------------------------

    services = (
        db.query(CaseService)
        .filter(
            CaseService.case_id == case_id,
            CaseService.business_id == business_id,
        )
        .all()
    )

    services_count = len(services)

    services_pending = sum(
        1
        for service in services
        if service.status == "pending"
    )

    services_confirmed = sum(
        1
        for service in services
        if service.status == "confirmed"
    )

    # --------------------------------------------------------
    # TASKS
    # --------------------------------------------------------

    tasks = (
        db.query(CaseTask)
        .filter(
            CaseTask.case_id == case_id,
            CaseTask.business_id == business_id,
        )
        .all()
    )

    tasks_count = len(tasks)

    tasks_pending = sum(
        1
        for task in tasks
        if task.status == "pending"
    )

    tasks_completed = sum(
        1
        for task in tasks
        if task.status == "completed"
    )

    # --------------------------------------------------------
    # PAYMENTS
    # --------------------------------------------------------

    payments = (
        db.query(CasePayment)
        .filter(
            CasePayment.case_id == case_id,
            CasePayment.business_id == business_id,
        )
        .all()
    )

    payments_count = len(payments)

    payments_amount_paid = sum(
        (payment.amount for payment in payments),
        Decimal("0.00"),
    )

    # --------------------------------------------------------
    # FINANCIAL
    # --------------------------------------------------------

    financial = (
        db.query(CaseFinancial)
        .filter(
            CaseFinancial.case_id == case_id,
            CaseFinancial.business_id == business_id,
        )
        .first()
    )

    financial_summary = None

    if financial:
        financial_summary = CaseFinancialSummary(
            total=financial.total,
            amount_paid=financial.amount_paid,
            balance=financial.balance,
            credit=financial.credit,
            status=financial.status,
        )

    # --------------------------------------------------------
    # BUILD RESPONSE
    # --------------------------------------------------------

    return CaseSummaryResponse(
        case=FuneralCaseResponse.model_validate(case),

        contacts=CaseContactSummary(
            total=contacts_count,
        ),

        tasks=CaseTaskSummary(
            total=tasks_count,
            pending=tasks_pending,
            completed=tasks_completed,
        ),

        documents=CaseDocumentSummary(
            total=documents_count,
        ),

        services=CaseServiceSummary(
            total=services_count,
            pending=services_pending,
            confirmed=services_confirmed,
        ),

        payments=CasePaymentSummary(
            total=payments_count,
            amount_paid=payments_amount_paid,
        ),

        financial=financial_summary,
    )


# ============================================================
# GET SINGLE CASE
# ============================================================

@router.get(
    "/{case_id}",
    response_model=FuneralCaseResponse,
)
def get_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.view")),
):
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == current_user["business_id"],
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


# ============================================================
# UPDATE CASE
# ============================================================

@router.patch(
    "/{case_id}",
    response_model=FuneralCaseResponse,
)
def update_case(
    case_id: UUID,
    data: FuneralCaseUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.edit")),
):
    business_id = current_user["business_id"]

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    updates = data.model_dump(
        exclude_unset=True
    )

    # --------------------------------------------------------
    # PREVENT DUPLICATE CASE NUMBERS
    # --------------------------------------------------------

    if "case_number" in updates:
        existing_case = (
            db.query(FuneralCase)
            .filter(
                FuneralCase.business_id == business_id,
                FuneralCase.case_number == updates["case_number"],
                FuneralCase.id != case_id,
            )
            .first()
        )

        if existing_case:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Case number already exists for this business",
            )

    # --------------------------------------------------------
    # DETERMINE FINAL MEMBERSHIP / DEPENDENT VALUES
    # --------------------------------------------------------

    final_membership_id = (
        updates["membership_id"]
        if "membership_id" in updates
        else case.membership_id
    )

    final_dependent_id = (
        updates["covered_dependent_id"]
        if "covered_dependent_id" in updates
        else case.covered_dependent_id
    )

    final_funeral_date = (
        updates["funeral_date"]
        if "funeral_date" in updates
        else case.funeral_date
    )

    final_date_of_death = (
        updates["date_of_death"]
        if "date_of_death" in updates
        else case.date_of_death
    )

    # --------------------------------------------------------
    # VALIDATE MEMBERSHIP / DEPENDENT LINKS
    # --------------------------------------------------------

    coverage_date = get_case_coverage_date(
        final_funeral_date,
        final_date_of_death,
    )

    validate_case_coverage_links(
        db=db,
        business_id=business_id,
        membership_id=final_membership_id,
        covered_dependent_id=final_dependent_id,
        coverage_date=coverage_date,
    )

    # --------------------------------------------------------
    # APPLY UPDATES
    # --------------------------------------------------------

    for field, value in updates.items():
        setattr(case, field, value)

    db.commit()
    db.refresh(case)

    return case


# ============================================================
# DELETE CASE
# ============================================================

@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.delete")),
):
    business_id = current_user["business_id"]

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    db.delete(case)
    db.commit()

    return None