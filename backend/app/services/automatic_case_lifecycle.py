"""Automatic synchronization between funeral arrangements and case status.

The arrangement is the source of truth for the funeral's operational dates.
Case status is advanced through the existing audited lifecycle, never by
skipping states. A passed date can move a confirmed case to in_progress;
completion requires the arrangement itself to be recorded as completed.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.arrangement import FuneralArrangement
from app.models.funeral_case import FuneralCase
from app.services.case_lifecycle import transition_case_status


TERMINAL_CASE_STATUSES = {"completed", "closed", "cancelled"}


def sync_case_status_from_arrangement(
    db: Session,
    *,
    case: FuneralCase,
    arrangement: FuneralArrangement,
    now: datetime | None = None,
    user_id: UUID | None = None,
) -> list[tuple[str, str]]:
    """Advance a case according to its linked arrangement and elapsed time.

    Rules:
    - A confirmed arrangement confirms an open case.
    - Once the confirmed committal time has passed, the case becomes
      in_progress.
    - A completed arrangement completes the case, but only after committal.
    - Draft/cancelled arrangements and terminal cases never auto-advance.
    - Every status change uses the audited, validated transition service.

    The caller owns the transaction and must commit after related writes.
    """
    if case.is_archived or case.status in TERMINAL_CASE_STATUSES:
        return []

    if arrangement.case_id != case.id or arrangement.business_id != case.business_id:
        return []

    if arrangement.status not in {"confirmed", "completed"}:
        return []

    if arrangement.committal_at is None:
        return []

    now_value = now or datetime.now(timezone.utc)
    committal_at = arrangement.committal_at
    if committal_at.tzinfo is None:
        committal_at = committal_at.replace(tzinfo=timezone.utc)
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=timezone.utc)

    if committal_at > now_value:
        # A future funeral must not become in-progress or completed early.
        target_status = "confirmed"
    elif arrangement.status == "completed":
        target_status = "completed"
    else:
        target_status = "in_progress"

    transitions = {
        "open": ["confirmed", "in_progress", "completed"],
        "confirmed": ["in_progress", "completed"],
        "in_progress": ["completed"],
    }
    changed: list[tuple[str, str]] = []

    for next_status in transitions.get(case.status, []):
        if next_status == "in_progress" and target_status == "confirmed":
            break
        if next_status == "completed" and target_status != "completed":
            break

        old_status = case.status
        transition_case_status(
            db,
            case=case,
            business_id=case.business_id,
            user_id=user_id,
            new_status=next_status,
        )
        changed.append((old_status, next_status))
        if next_status == target_status:
            break

    return changed
