from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.schemas.reports import (
    CasesReport,
    FinancialReport,
    MembershipReport,
)
from app.services import owner_summary
from app.services import reports as report_service
from app.services.audit_service import create_audit_log
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


# ============================================================
# OWNER OVERVIEW AND WORK LISTS
# ============================================================

def _run(call, **kwargs):
    try:
        return call(**kwargs)
    except ReportError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )


@router.get("/overview")
def overview_report(
    date_from: date = Query(),
    date_to: date = Query(),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    """The period beside the one before it, a six-month trend and how
    things stand today."""

    business_id = prepare(db, current_user, date_from, date_to, branch_id)

    return _run(
        owner_summary.overview,
        db=db,
        business_id=business_id,
        date_from=date_from,
        date_to=date_to,
        branch_id=branch_id,
    )


@router.get("/arrears")
def arrears_list(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    """Memberships behind on contributions, longest first."""

    business_id = prepare(db, current_user, None, None, branch_id)

    return owner_summary.arrears_rows(
        db, business_id=business_id, branch_id=branch_id
    )


@router.get("/debtors")
def debtors_list(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    """Cases that still owe money, biggest balance first."""

    business_id = prepare(db, current_user, None, None, branch_id)

    return owner_summary.debtor_rows(
        db, business_id=business_id, branch_id=branch_id
    )


def _csv_response(name: str, content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"'
        },
    )


def _audit_export(db, current_user, report: str, rows: int) -> None:
    # A list of names and phone numbers leaving the system is recorded.
    create_audit_log(
        db,
        business_id=UUID(str(current_user["business_id"])),
        user_id=UUID(str(current_user["user_id"])),
        action="report.exported",
        entity_type="report",
        entity_id=None,
        details={"report": report, "rows": rows},
        notes=f"The {report} list was downloaded.",
    )
    db.commit()


@router.get("/arrears.csv")
def arrears_csv(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    business_id = prepare(db, current_user, None, None, branch_id)
    data = owner_summary.arrears_rows(
        db, business_id=business_id, branch_id=branch_id
    )
    _audit_export(db, current_user, "arrears", len(data["rows"]))

    return _csv_response(
        "members-in-arrears.csv",
        owner_summary.to_csv(
            ["Member", "Membership number", "Phone", "Plan",
             "Behind since", "Days behind", "Days until lapse",
             "Amount unpaid"],
            ["member_name", "membership_number", "phone", "plan",
             "arrears_since", "days_in_arrears", "days_until_lapse",
             "amount_unpaid"],
            data["rows"],
        ),
    )


@router.get("/debtors.csv")
def debtors_csv(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("reports.view")),
):
    business_id = prepare(db, current_user, None, None, branch_id)
    data = owner_summary.debtor_rows(
        db, business_id=business_id, branch_id=branch_id
    )
    _audit_export(db, current_user, "debtors", len(data["rows"]))

    return _csv_response(
        "cases-with-balance.csv",
        owner_summary.to_csv(
            ["Case", "Deceased", "Next of kin", "Kin phone",
             "Funeral date", "Case age (days)", "Total", "Balance owed"],
            ["case_number", "deceased_full_name", "next_of_kin_name",
             "next_of_kin_phone", "funeral_date", "age_days", "total",
             "balance"],
            data["rows"],
        ),
    )
