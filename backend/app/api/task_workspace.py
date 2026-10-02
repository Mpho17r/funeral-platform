from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase
from app.models.user import User
from app.schemas.case_task import WorkspaceTaskResponse


router = APIRouter(
    prefix="/tasks",
    tags=["Task Workspace"],
)


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User business information is missing",
        )

    try:
        return UUID(str(business_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid business ID",
        )


@router.get(
    "",
    response_model=list[WorkspaceTaskResponse],
)
def list_workspace_tasks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("tasks.view")
    ),
):
    business_id = get_business_id(current_user)

    rows = (
        db.query(
            CaseTask,
            FuneralCase.case_number,
            FuneralCase.deceased_full_name,
            User.full_name,
        )
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
        )
        .order_by(
            CaseTask.due_date.is_(None),
            CaseTask.due_date.asc(),
            CaseTask.created_at.desc(),
        )
        .all()
    )

    return [
        WorkspaceTaskResponse(
            id=task.id,
            business_id=task.business_id,
            case_id=task.case_id,
            case_number=case_number,
            deceased_full_name=deceased_full_name,
            title=task.title,
            description=task.description,
            status=task.status,
            due_date=task.due_date,
            assigned_to=task.assigned_to,
            assigned_to_name=assigned_to_name,
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
        )
        for (
            task,
            case_number,
            deceased_full_name,
            assigned_to_name,
        ) in rows
    ]
