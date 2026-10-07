from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.funeral_case import FuneralCase
from app.services.audit_service import create_audit_log


CASE_STATUS_OPEN = "open"
CASE_STATUS_CONFIRMED = "confirmed"
CASE_STATUS_IN_PROGRESS = "in_progress"
CASE_STATUS_COMPLETED = "completed"
CASE_STATUS_CLOSED = "closed"
CASE_STATUS_CANCELLED = "cancelled"


ALLOWED_CASE_STATUSES = {
    CASE_STATUS_OPEN,
    CASE_STATUS_CONFIRMED,
    CASE_STATUS_IN_PROGRESS,
    CASE_STATUS_COMPLETED,
    CASE_STATUS_CLOSED,
    CASE_STATUS_CANCELLED,
}


CASE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    CASE_STATUS_OPEN: {
        CASE_STATUS_CONFIRMED,
        CASE_STATUS_CANCELLED,
    },
    CASE_STATUS_CONFIRMED: {
        CASE_STATUS_IN_PROGRESS,
        CASE_STATUS_CANCELLED,
    },
    CASE_STATUS_IN_PROGRESS: {
        CASE_STATUS_COMPLETED,
        CASE_STATUS_CANCELLED,
    },
    CASE_STATUS_COMPLETED: {
        CASE_STATUS_CLOSED,
    },
    CASE_STATUS_CLOSED: set(),
    CASE_STATUS_CANCELLED: set(),
}


def validate_case_status_transition(
    current_status: str,
    new_status: str,
) -> None:
    if current_status not in ALLOWED_CASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case has an unsupported current status: {current_status}",
        )

    if new_status not in ALLOWED_CASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid case status: {new_status}",
        )

    if current_status == new_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case is already in status '{current_status}'",
        )

    allowed_next_statuses = CASE_STATUS_TRANSITIONS[current_status]

    if new_status not in allowed_next_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid case status transition: "
                f"{current_status} → {new_status}"
            ),
        )


def transition_case_status(
    db: Session,
    *,
    case: FuneralCase,
    business_id: UUID,
    user_id: UUID | None,
    new_status: str,
) -> FuneralCase:
    new_status = new_status.strip().lower()

    validate_case_status_transition(
        current_status=case.status,
        new_status=new_status,
    )

    old_status = case.status

    case.status = new_status

    create_audit_log(
        db,
        business_id=business_id,
        user_id=user_id,
        action="case.status_changed",
        entity_type="case",
        entity_id=case.id,
        details={
            "old_status": old_status,
            "new_status": new_status,
        },
        notes=f"Case status changed from {old_status} to {new_status}.",
    )

    return case
