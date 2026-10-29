"""Tell people when work given to them is late.

Each late task or service tells each responsible person once, the first
time it is found late. Finished work and archived work never alert.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.case_service import CaseService
from app.models.case_task import CaseTask
from app.models.notification import Notification
from app.services.notifications import notify


def _already_told(db: Session, user_id, kind: str, link: str) -> bool:
    return (
        db.query(Notification.id)
        .filter(
            Notification.user_id == user_id,
            Notification.kind == kind,
            Notification.link == link,
        )
        .first()
        is not None
    )


def _tell(db, *, business_id, people, kind, title, body, link) -> int:
    count = 0
    for person in people:
        if _already_told(db, person, kind, link):
            continue
        count += notify(
            db,
            business_id=business_id,
            user_ids=[person],
            kind=kind,
            title=title,
            body=body,
            link=link,
        )
    return count


def run(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    sent = 0

    tasks = (
        db.query(CaseTask)
        .filter(
            CaseTask.status != "completed",
            CaseTask.archived_at.is_(None),
            CaseTask.due_at.is_not(None),
            CaseTask.due_at < now,
        )
        .all()
    )
    for task in tasks:
        people = set(task.assignee_ids)
        if task.assigned_to:
            people.add(task.assigned_to)
        sent += _tell(
            db,
            business_id=task.business_id,
            people=people,
            kind="task_overdue",
            title="A task is overdue",
            body=task.title,
            link=f"/tasks?overdue={task.id}",
        )

    services = (
        db.query(CaseService)
        .filter(
            CaseService.status.notin_(("completed", "cancelled")),
            CaseService.archived_at.is_(None),
            CaseService.due_at.is_not(None),
            CaseService.due_at < now,
        )
        .all()
    )
    for service in services:
        sent += _tell(
            db,
            business_id=service.business_id,
            people=set(service.assignee_ids),
            kind="service_overdue",
            title="A service is overdue",
            body=service.service_name,
            link=f"/cases/{service.case_id}/services?overdue={service.id}",
        )

    db.commit()
    return sent
