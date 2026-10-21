"""Dashboard feed for the finance and membership team."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.finance_overview import overview

router = APIRouter(prefix="/finance", tags=["Finance"])


@router.get("/overview")
def finance_overview(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("financials.view")),
):
    return overview(
        db,
        business_id=UUID(str(current_user["business_id"])),
        branch_id=branch_id,
    )
