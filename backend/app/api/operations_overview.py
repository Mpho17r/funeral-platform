"""Dashboard feed for the operations team."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.operations_overview import overview

router = APIRouter(prefix="/operations", tags=["Operations"])


@router.get("/overview")
def operations_overview(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.view")),
):
    return overview(
        db,
        business_id=UUID(str(current_user["business_id"])),
        branch_id=branch_id,
    )
