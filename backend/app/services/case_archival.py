from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.funeral_case import FuneralCase
from app.services.audit_service import create_audit_log


ARCHIVABLE_CASE_STATUSES = {
    "closed",
    "cancelled",
}


def archive_case(
    db: Session,
    *,
    case: FuneralCase,
    business_id: UUID,
    user_id: UUID | None,
) -> FuneralCase:
    """
    Archive a closed or cancelled case without deleting any case data.

    Archival is a record-state operation and is intentionally separate
    from the case's operational status.
    """

    if case.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case is already archived",
        )

    if case.status not in ARCHIVABLE_CASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Case with status '{case.status}' cannot be archived. "
                "Only closed or cancelled cases can be archived."
            ),
        )

    case.is_archived = True
    case.archived_at = datetime.now(timezone.utc)
    case.archived_by = user_id

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="case.archived",
        entity_type="case",
        entity_id=case.id,
        details={
            "status": case.status,
            "archived": True,
        },
        notes=f"Case {case.case_number} was archived.",
    )

    return case


def restore_case(
    db: Session,
    *,
    case: FuneralCase,
    business_id: UUID,
    user_id: UUID | None,
) -> FuneralCase:
    """
    Restore an archived case without changing its operational status.
    """

    if not case.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case is not archived",
        )

    case.is_archived = False
    case.archived_at = None
    case.archived_by = None

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="case.restored",
        entity_type="case",
        entity_id=case.id,
        details={
            "status": case.status,
            "archived": False,
        },
        notes=f"Case {case.case_number} was restored.",
    )

    return case
