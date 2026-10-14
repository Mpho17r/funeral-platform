from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.schemas.coverage import CaseCoverageResponse
from app.services.coverage_decision import (
    calculate_case_coverage,
    get_case_for_business,
    get_coverage_date,
)


router = APIRouter(
    tags=["Case Coverage"],
)


@router.get(
    "/cases/{case_id}/coverage",
    response_model=CaseCoverageResponse,
)
def read_case_coverage(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.view")),
):
    """What cover the case has today, including any waiting period.

    Read only: nothing is changed or recorded.
    """

    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    business_id = UUID(str(business_id))

    case = get_case_for_business(db, case_id, business_id)

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    decision = calculate_case_coverage(db, case, business_id)

    # Evaluating coverage refreshes the membership status in memory;
    # this endpoint never saves that.
    db.rollback()

    return {
        "case_id": decision.case_id,
        "coverage_date": get_coverage_date(case),
        "membership_id": decision.membership_id,
        "covered_dependent_id": decision.covered_dependent_id,
        "covered": decision.covered,
        "reason": decision.reason,
        "plan_id": decision.plan_id,
        "plan_name": decision.plan_name,
        "benefit_plan_id": decision.benefit_plan_id,
        "benefit_plan_name": decision.benefit_plan_name,
        "waiting_period": decision.waiting_period,
        "upgrade_waiting": decision.upgrade_waiting,
        "benefits": [
            benefit
            for benefit in decision.benefits
            if benefit.is_active
        ],
    }
