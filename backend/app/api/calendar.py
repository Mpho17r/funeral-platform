from datetime import timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.dependencies.roles import get_current_user
from app.models.case_service import CaseService
from app.models.case_task import CaseTask, CaseTaskAssignee
from app.models.funeral_case import FuneralCase
from app.models.user import User
from app.schemas.calendar import CalendarEventResponse
from app.services.permission_service import has_permission


router = APIRouter(
    prefix="/calendar",
    tags=["Calendar Workspace"],
)


def get_business_id(current_user: dict):
    return current_user["business_id"]


@router.get(
    "",
    response_model=list[CalendarEventResponse],
)
def list_calendar_events(
    mine: bool = Query(
        False,
        description="Only my own schedule: my tasks, and the funerals "
        "and services of the cases I have tasks on.",
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = get_business_id(current_user)
    user_id = UUID(str(current_user["user_id"]))
    role = current_user["role"]

    def allowed(key: str) -> bool:
        return has_permission(db, user_id=user_id, role=role, permission_key=key)

    # Funeral homes see funerals and services; every business sees its tasks.
    can_cases = allowed("cases.view")
    if not (can_cases or allowed("tasks.view")):
        raise HTTPException(403, "You do not have permission to view the calendar")

    events: list[CalendarEventResponse] = []

    my_task_ids = (
        db.query(CaseTaskAssignee.task_id)
        .filter(CaseTaskAssignee.user_id == user_id)
    )
    is_mine_task = (CaseTask.assigned_to == user_id) | CaseTask.id.in_(
        my_task_ids
    )
    my_case_ids = (
        db.query(CaseTask.case_id)
        .filter(CaseTask.business_id == business_id, is_mine_task)
    )

    case_query = db.query(FuneralCase).filter(
        FuneralCase.business_id == business_id,
        FuneralCase.funeral_date.is_not(None),
    )
    if mine:
        case_query = case_query.filter(FuneralCase.id.in_(my_case_ids))
    cases = (
        case_query.order_by(FuneralCase.funeral_date.asc()).all()
        if can_cases
        else []
    )

    for case in cases:
        events.append(
            CalendarEventResponse(
                id=f"case-{case.id}",
                event_type="funeral",
                title=f"Funeral — {case.deceased_full_name}",
                date=case.funeral_date,
                case_id=case.id,
                case_number=case.case_number,
                deceased_full_name=case.deceased_full_name,
                description=case.notes,
                venue=case.funeral_venue,
                status=case.status,
            )
        )

    if has_permission(
        db,
        user_id=user_id,
        role=role,
        permission_key="services.view",
    ):
        service_query = (
            db.query(CaseService, FuneralCase)
            .join(
                FuneralCase,
                FuneralCase.id == CaseService.case_id,
            )
            .filter(
                CaseService.business_id == business_id,
                FuneralCase.business_id == business_id,
                CaseService.scheduled_date.is_not(None),
            )
        )
        if mine:
            service_query = service_query.filter(
                FuneralCase.id.in_(my_case_ids)
            )
        services = service_query.order_by(
            CaseService.scheduled_date.asc()
        ).all()

        for service, case in services:
            events.append(
                CalendarEventResponse(
                    id=f"service-{service.id}",
                    event_type="service",
                    title=service.service_name,
                    date=service.scheduled_date,
                    case_id=case.id,
                    case_number=case.case_number,
                    deceased_full_name=case.deceased_full_name,
                    description=service.description,
                    status=service.status,
                )
            )

    if has_permission(
        db,
        user_id=user_id,
        role=role,
        permission_key="tasks.view",
    ):
        task_query = (
            db.query(CaseTask, FuneralCase, User.full_name)
            .join(
                FuneralCase,
                FuneralCase.id == CaseTask.case_id,
            )
            .outerjoin(
                User,
                User.id == CaseTask.assigned_to,
            )
            .filter(
                CaseTask.business_id == business_id,
                FuneralCase.business_id == business_id,
                CaseTask.archived_at.is_(None),
            )
        )
        if mine:
            task_query = task_query.filter(is_mine_task)
        tasks = task_query.order_by(CaseTask.created_at.asc()).all()
        zone = ZoneInfo(settings.scheduler_timezone)

        for task, case, assigned_to_name in tasks:
            def make(kind: str, day, title: str, due_at=None):
                return CalendarEventResponse(
                    id=f"{kind}-{task.id}",
                    event_type=kind,
                    title=title,
                    date=day,
                    case_id=case.id,
                    case_number=case.case_number,
                    deceased_full_name=case.deceased_full_name,
                    description=task.description,
                    assigned_to=task.assigned_to,
                    assigned_to_name=assigned_to_name,
                    status=task.status,
                    due_at=due_at,
                )

            created = task.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            given_on = created.astimezone(zone).date()

            due_day = task.due_date or (
                task.due_at.astimezone(zone).date() if task.due_at else None
            )

            if due_day is not None:
                events.append(make("task", due_day, task.title, task.due_at))
            # The day it was given, shown only when that is a different day.
            if due_day is None or given_on != due_day:
                events.append(
                    make("task_given", given_on, f"Given: {task.title}")
                )

    events.sort(key=lambda event: event.date)

    return events
