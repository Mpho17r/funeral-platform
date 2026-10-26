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

    now_value = now or datetime.now(timezone.utc)
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=timezone.utc)

    committal_at = arrangement.committal_at
    if committal_at is not None and committal_at.tzinfo is None:
        committal_at = committal_at.replace(tzinfo=timezone.utc)

    if committal_at is None:
        # No committal time recorded yet. A confirmed arrangement still
        # confirms the case, and one recorded as completed completes it,
        # but the case is never started on a guess.
        target_status = (
            "completed" if arrangement.status == "completed" else "confirmed"
        )
    elif committal_at > now_value:
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


# ------------------------------------------------------------------
# Keeping statuses fresh without waiting for the background job
# ------------------------------------------------------------------

_last_refresh: dict = {}
REFRESH_EVERY_SECONDS = 30


def refresh_case_statuses(
    db: Session, business_id: UUID, *, case_id: UUID | None = None
) -> int:
    """Advance any case whose arrangement says it should have moved on.

    Called when cases are looked at, so a case never stays stuck because
    the scheduled job is not running. Throttled per business. The branch
    limit is lifted for this housekeeping so every case is kept in step.
    Returns the number of status changes made.
    """
    import time

    key = (business_id, case_id)
    now_ts = time.monotonic()
    if now_ts - _last_refresh.get(key, -1e9) < REFRESH_EVERY_SECONDS:
        return 0
    _last_refresh[key] = now_ts

    query = (
        db.query(FuneralCase, FuneralArrangement)
        .join(
            FuneralArrangement,
            (FuneralArrangement.case_id == FuneralCase.id)
            & (FuneralArrangement.business_id == FuneralCase.business_id),
        )
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.notin_(tuple(TERMINAL_CASE_STATUSES)),
            FuneralArrangement.status.in_(("confirmed", "completed")),
        )
        .execution_options(all_branches=True)
    )
    if case_id is not None:
        query = query.filter(FuneralCase.id == case_id)

    changed = 0
    for case, arrangement in query.all():
        changes = sync_case_status_from_arrangement(
            db, case=case, arrangement=arrangement, user_id=None
        )
        changed += len(changes)
    if changed:
        db.commit()
    return changed
