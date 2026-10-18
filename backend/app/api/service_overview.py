from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_service import CaseService
from app.models.funeral_case import FuneralCase


router = APIRouter(prefix="/services", tags=["Services"])


@router.get("")
def list_all_services(
    q: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=50),
    service_type: str | None = Query(default=None, max_length=50),
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: UUID | None = None,
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    """Every service booked on any case, newest first. The place to see
    what is coming up across the whole business; each row links back to
    its case."""

    business_id = current_user["business_id"]

    base = (
        db.query(CaseService, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CaseService.case_id)
        .filter(
            CaseService.business_id == business_id,
            FuneralCase.business_id == business_id,
        )
    )

    if not include_archived:
        base = base.filter(FuneralCase.is_archived.is_(False))

    if branch_id is not None:
        base = base.filter(FuneralCase.branch_id == branch_id)

    if status:
        base = base.filter(CaseService.status == status)

    if service_type:
        base = base.filter(CaseService.service_type == service_type)

    if date_from:
        base = base.filter(func.date(CaseService.scheduled_date) >= date_from)

    if date_to:
        base = base.filter(func.date(CaseService.scheduled_date) <= date_to)

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        base = base.filter(
            or_(
                CaseService.service_name.ilike(pattern),
                CaseService.provider.ilike(pattern),
                FuneralCase.case_number.ilike(pattern),
                FuneralCase.deceased_full_name.ilike(pattern),
            )
        )

    total = base.count()

    rows = (
        base.order_by(
            CaseService.scheduled_date.is_(None),
            CaseService.scheduled_date.asc(),
            CaseService.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [
            {
                "id": str(service.id),
                "case_id": str(service.case_id),
                "case_number": case.case_number,
                "deceased_full_name": case.deceased_full_name,
                "service_type": service.service_type,
                "service_name": service.service_name,
                "status": service.status,
                "quantity": service.quantity,
                "total_price": str(service.total_price),
                "scheduled_date": (
                    service.scheduled_date.isoformat()
                    if service.scheduled_date
                    else None
                ),
                "provider": service.provider,
            }
            for service, case in rows
        ],
    }


@router.get("/options")
def service_filter_options(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("services.view")),
):
    """The statuses and types in use, to fill the filter lists."""

    business_id = current_user["business_id"]

    def distinct(column):
        return sorted(
            v for (v,) in db.query(column)
            .filter(CaseService.business_id == business_id)
            .distinct()
            if v
        )

    return {
        "statuses": distinct(CaseService.status),
        "types": distinct(CaseService.service_type),
    }
