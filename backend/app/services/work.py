"""Tasks for a general business: they belong to the business, not a case.

KAI can pick who gets a task: it reads the wording of the task and each
person's job title and role, matches the two, then prefers whoever has the
least on their plate and is at work today.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.case_task import CaseTask
from app.models.user import User
from app.services import business_type as kinds
from app.services.audit_service import create_audit_log
from app.services.autopilot import pick_person
from app.services.staff_roles import category_for_text, profile, suitability
from app.services.task_access import due_date_from, set_assignees


def why_chosen(person: User, text: str) -> str:
    wanted = category_for_text(text)
    fit = suitability(person.job_title, person.role, wanted)
    title = (person.job_title or "").strip()
    if wanted != "general" and fit == 2 and title:
        return f"This looks like {wanted} work and {person.full_name} is our {title}."
    if wanted != "general" and fit == 1:
        return f"This looks like {wanted} work, which suits {person.full_name}'s role."
    return f"{person.full_name} has the lightest workload right now."


def create_task(
    db: Session,
    *,
    business: Business,
    actor_id: UUID,
    title: str,
    description: str | None = None,
    due_at: datetime | None = None,
    assignee_ids: list[UUID] | None = None,
    let_kai_choose: bool = False,
    by_kai: bool = False,
) -> dict:
    case = kinds.workspace_case(db, business.id)
    people = list(assignee_ids or [])
    reason = None
    chosen = False
    if not people and let_kai_choose:
        person = pick_person(
            db,
            business,
            permission="tasks.view",
            branch_id=None,
            area="general",
            text=f"{title} {description or ''}",
        )
        if person is not None:
            people = [person.id]
            reason = why_chosen(person, f"{title} {description or ''}")
            chosen = True

    task = CaseTask(
        business_id=business.id,
        case_id=case.id,
        title=title[:200],
        description=description,
        status="pending",
        due_at=due_at,
        due_date=due_date_from(due_at),
        by_kai=by_kai,
    )
    db.add(task)
    db.flush()
    set_assignees(db, task, people, business_id=business.id, actor_id=actor_id)
    create_audit_log(
        db,
        business_id=business.id,
        user_id=actor_id,
        action="work.task_created",
        entity_type="case_task",
        entity_id=task.id,
        details={"title": task.title, "assignees": [str(p) for p in people], "by_kai": chosen},
        notes="A business task was created.",
    )
    names = []
    if people:
        names = [
            u.full_name
            for u in db.query(User).filter(User.id.in_(people)).all()
        ]
    return {
        "id": str(task.id),
        "title": task.title,
        "assignees": names,
        "chosen_by_kai": chosen,
        "reason": reason,
    }


def team(db: Session, business: Business) -> list[dict]:
    from app.services.autopilot import present_today, workload

    loads = workload(db, business.id)
    present = present_today(db, business.id)
    out = []
    for person in (
        db.query(User)
        .filter(User.business_id == business.id, User.is_active.is_(True))
        .order_by(User.full_name)
    ):
        out.append(
            {
                "id": str(person.id),
                "name": person.full_name,
                "job_title": person.job_title,
                "role": person.role,
                "detected": profile(person.job_title, person.role),
                "open": loads.get(person.id, 0),
                "present": person.id in present,
            }
        )
    return out
