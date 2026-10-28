from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
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
    current_user: dict = Depends(require_permission("cases.view")),
):
    business_id = get_business_id(current_user)
    user_id = UUID(str(current_user["user_id"]))
    role = current_user["role"]

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
    cases = case_query.order_by(FuneralCase.funeral_date.asc()).all()

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
                CaseTask.due_date.is_not(None),
            )
        )
        if mine:
            task_query = task_query.filter(is_mine_task)
        tasks = task_query.order_by(CaseTask.due_date.asc()).all()

        for task, case, assigned_to_name in tasks:
            events.append(
                CalendarEventResponse(
                    id=f"task-{task.id}",
                    event_type="task",
                    title=task.title,
                    date=task.due_date,
                    case_id=case.id,
                    case_number=case.case_number,
                    deceased_full_name=case.deceased_full_name,
                    description=task.description,
                    assigned_to=task.assigned_to,
                    assigned_to_name=assigned_to_name,
                    status=task.status,
                )
            )

    events.sort(key=lambda event: event.date)

    return events
