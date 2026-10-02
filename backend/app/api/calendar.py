from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_service import CaseService
from app.models.case_task import CaseTask
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("cases.view")),
):
    business_id = get_business_id(current_user)
    user_id = UUID(str(current_user["user_id"]))
    role = current_user["role"]

    events: list[CalendarEventResponse] = []

    cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.funeral_date.is_not(None),
        )
        .order_by(FuneralCase.funeral_date.asc())
        .all()
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
        services = (
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
            .order_by(CaseService.scheduled_date.asc())
            .all()
        )

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
        tasks = (
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
            .order_by(CaseTask.due_date.asc())
            .all()
        )

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
