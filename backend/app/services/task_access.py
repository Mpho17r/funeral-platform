"""Who a task is given to, and who may work on it.

A task can be shared by several people. Anyone it is given to can
update its status, write a report and upload files, even without the
general permission to manage tasks. Managing (creating, re-assigning,
deleting) still needs `tasks.manage`.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.case_task import CaseTask, CaseTaskAssignee
from app.models.user import User
from app.services.notifications import notify
from app.services.permission_service import has_permission

SA = timezone(timedelta(hours=2))


def due_date_from(due_at: datetime | None):
    if due_at is None:
        return None
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=SA)
    return due_at.astimezone(SA).date()


def is_assignee(task: CaseTask, user_id) -> bool:
    return UUID(str(user_id)) in task.assignee_ids or (
        task.assigned_to is not None and task.assigned_to == UUID(str(user_id))
    )


def can_work_on(db: Session, user: dict, task: CaseTask) -> bool:
    if is_assignee(task, user["user_id"]):
        return True
    return has_permission(
        db,
        user_id=user["user_id"],
        role=user["role"],
        permission_key="tasks.manage",
    )


def set_assignees(
    db: Session,
    task: CaseTask,
    user_ids: list[UUID],
    *,
    business_id: UUID,
    actor_id,
) -> list[UUID]:
    """Make exactly these people the task's assignees. People newly
    given the task are told. Returns the new assignees."""

    wanted: list[UUID] = []
    for raw in user_ids:
        uid = UUID(str(raw))
        if uid not in wanted:
            wanted.append(uid)

    if wanted:
        found = {
            row[0]
            for row in db.query(User.id).filter(
                User.business_id == business_id, User.id.in_(wanted)
            )
        }
        if found != set(wanted):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user does not belong to this business",
            )

    before = set(task.assignee_ids)
    task.assignee_rows[:] = [
        row for row in task.assignee_rows if row.user_id in wanted
    ]
    for uid in wanted:
        if uid not in before:
            task.assignee_rows.append(CaseTaskAssignee(user_id=uid))
    task.assigned_to = wanted[0] if wanted else None

    added = [uid for uid in wanted if uid not in before]
    if added:
        others = [str(u) for u in wanted if u not in added and str(u) != str(actor_id)]
        notify(
            db,
            business_id=business_id,
            user_ids=added,
            kind="task_assigned",
            title=(
                "A task was shared with you" if len(wanted) > 1
                else "A task was given to you"
            ),
            body=task.title,
            link="/tasks",
            actor_id=actor_id,
        )
        del others
    return added
