from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import (
    AuditLogFilters,
    AuditLogItem,
    AuditLogListResponse,
)


router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit trail"],
)

# South Africa is UTC+2 all year, and days on the screen are local days.
SAST = timezone(timedelta(hours=2))


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


@router.get(
    "",
    response_model=AuditLogListResponse,
)
def list_audit_logs(
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    user_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("audit.view")),
):
    """Newest first. Only this business's entries are ever returned."""

    business_id = get_business_id(current_user)

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The start date is after the end date",
        )

    base = select(AuditLog).where(AuditLog.business_id == business_id)

    if action is not None:
        base = base.where(AuditLog.action == action)

    if entity_type is not None:
        base = base.where(AuditLog.entity_type == entity_type)

    if entity_id is not None:
        base = base.where(AuditLog.entity_id == entity_id)

    if user_id is not None:
        base = base.where(AuditLog.user_id == user_id)

    if date_from is not None:
        base = base.where(
            AuditLog.created_at
            >= datetime.combine(date_from, time.min, tzinfo=SAST)
        )

    if date_to is not None:
        base = base.where(
            AuditLog.created_at
            < datetime.combine(
                date_to + timedelta(days=1), time.min, tzinfo=SAST
            )
        )

    total = db.scalar(select(func.count()).select_from(base.subquery()))

    rows = db.scalars(
        base.order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    ).all()

    names = {
        user.id: user.full_name
        for user in db.scalars(
            select(User).where(
                User.business_id == business_id,
                User.id.in_({row.user_id for row in rows if row.user_id}),
            )
        ).all()
    }

    return AuditLogListResponse(
        total=total or 0,
        limit=limit,
        offset=offset,
        items=[
            AuditLogItem(
                id=row.id,
                created_at=row.created_at,
                user_id=row.user_id,
                user_name=names.get(row.user_id),
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                notes=row.notes,
                details=row.details,
            )
            for row in rows
        ],
    )


@router.get(
    "/filters",
    response_model=AuditLogFilters,
)
def audit_log_filters(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("audit.view")),
):
    """The actions and record types that have been logged, for the
    filter lists on the screen."""

    business_id = get_business_id(current_user)

    return AuditLogFilters(
        actions=list(
            db.scalars(
                select(AuditLog.action)
                .where(AuditLog.business_id == business_id)
                .distinct()
                .order_by(AuditLog.action)
            ).all()
        ),
        entity_types=list(
            db.scalars(
                select(AuditLog.entity_type)
                .where(AuditLog.business_id == business_id)
                .distinct()
                .order_by(AuditLog.entity_type)
            ).all()
        ),
    )
