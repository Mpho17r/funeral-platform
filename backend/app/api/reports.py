from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.schemas.reports import (
    CasesReport,
    FinancialReport,
    MembershipReport,
)
from app.services import reports as report_service
from app.services.reports import ReportError


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


def prepare(
    db: Session,
    current_user: dict,
    date_from: date | None,
    date_to: date | None,
    branch_id: UUID | None,
) -> UUID:
    """Check the filters and return the business to report on."""

    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=403,
            detail="User is not associated with a business",
        )

    business_id = UUID(str(business_id))

    try:
        report_service.validate_period(date_from, date_to)
        report_service.validate_branch(db, business_id, branch_id)
    except ReportError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    return business_id


@router.get("/cases", response_model=CasesReport)
def cases_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    business_id = prepare(
        db, current_user, date_from, date_to, branch_id
    )

    return report_service.cases_report(
        db,
        business_id=business_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )


@router.get("/financial", response_model=FinancialReport)
def financial_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    business_id = prepare(
        db, current_user, date_from, date_to, branch_id
    )

    return report_service.financial_report(
        db,
        business_id=business_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )


@router.get("/membership", response_model=MembershipReport)
def membership_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    business_id = prepare(
        db, current_user, date_from, date_to, branch_id
    )

    return report_service.membership_report(
        db,
        business_id=business_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )
