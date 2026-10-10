from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)

from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase
from app.models.user import User

from app.schemas.case_task import (
    CaseTaskCreate,
    CaseTaskUpdate,
    CaseTaskResponse,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Tasks"],
)


# Fields whose changes are recorded in the audit trail.
AUDITED_TASK_FIELDS = (
    "title",
    "description",
    "status",
    "due_date",
    "assigned_to",
    "completed_at",
)


# ============================================================
# HELPERS
# ============================================================

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


def verify_case(
    db: Session,
    case_id: UUID,
    business_id: UUID,
):
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


def verify_assigned_user(
    db: Session,
    assigned_to: UUID | None,
    business_id: UUID,
):

    if assigned_to is None:
        return

    user = (
        db.query(User)
        .filter(
            User.id == assigned_to,
            User.business_id == business_id,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned user does not belong to this business",
        )


# ============================================================
# CREATE TASK
# POST /cases/{case_id}/tasks
# ============================================================

@router.post(
    "/{case_id}/tasks",
    response_model=CaseTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(

    case_id: UUID,

    task_data: CaseTaskCreate,

    db: Session = Depends(get_db),

    current_user: dict = Depends(require_permission("tasks.manage")),
):

    business_id = get_business_id(
        current_user
    )

    # --------------------------------------------------------
    # Verify case
    # --------------------------------------------------------

    verify_case(
        db,
        case_id,
        business_id,
    )

    # --------------------------------------------------------
    # Verify assigned user
    # --------------------------------------------------------

    verify_assigned_user(
        db,
        task_data.assigned_to,
        business_id,
    )

    # --------------------------------------------------------
    # Create task
    # --------------------------------------------------------

    now = datetime.now(timezone.utc)

    completed_at = (
        now
        if task_data.status == "completed"
        else None
    )

    task = CaseTask(
        business_id=business_id,
        case_id=case_id,
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        due_date=task_data.due_date,
        assigned_to=task_data.assigned_to,
        completed_at=completed_at,
    )

    db.add(task)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="case.task_created",
        entity_type="case_task",
        entity_id=task.id,
        details={
            "case_id": str(case_id),
            "status": task.status,
            "assigned_to": (
                str(task.assigned_to)
                if task.assigned_to
                else None
            ),
        },
        notes="Case task was created.",
    )

    db.commit()
    db.refresh(task)

    return task


# ============================================================
# LIST TASKS FOR CASE
# GET /cases/{case_id}/tasks
# ============================================================

@router.get(
    "/{case_id}/tasks",
    response_model=list[CaseTaskResponse],
)
def list_case_tasks(

    case_id: UUID,

    db: Session = Depends(get_db),

    current_user: dict = Depends(require_permission("tasks.view")),
):

    business_id = get_business_id(
        current_user
    )

    # --------------------------------------------------------
    # Verify case
    # --------------------------------------------------------

    verify_case(
        db,
        case_id,
        business_id,
    )

    # --------------------------------------------------------
    # Get tasks
    # --------------------------------------------------------

    tasks = (
        db.query(CaseTask)
        .filter(
            CaseTask.case_id == case_id,
            CaseTask.business_id == business_id,
        )
        .order_by(
            CaseTask.created_at.desc()
        )
        .all()
    )

    return tasks


# ============================================================
# GET SINGLE TASK
# GET /cases/tasks/{task_id}
# ============================================================

@router.get(
    "/tasks/{task_id}",
    response_model=CaseTaskResponse,
)
def get_task(

    task_id: UUID,

    db: Session = Depends(get_db),

    current_user: dict = Depends(require_permission("tasks.view")),
):

    business_id = get_business_id(
        current_user
    )

    task = (
        db.query(CaseTask)
        .filter(
            CaseTask.id == task_id,
            CaseTask.business_id == business_id,
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return task


# ============================================================
# UPDATE TASK
# PATCH /cases/tasks/{task_id}
# ============================================================

@router.patch(
    "/tasks/{task_id}",
    response_model=CaseTaskResponse,
)
def update_task(

    task_id: UUID,

    task_data: CaseTaskUpdate,

    db: Session = Depends(get_db),

    current_user: dict = Depends(require_permission("tasks.manage")),
):

    business_id = get_business_id(
        current_user
    )

    # --------------------------------------------------------
    # Find task
    # --------------------------------------------------------

    task = (
        db.query(CaseTask)
        .filter(
            CaseTask.id == task_id,
            CaseTask.business_id == business_id,
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # --------------------------------------------------------
    # Get updates
    # --------------------------------------------------------

    updates = task_data.model_dump(
        exclude_unset=True
    )

    # --------------------------------------------------------
    # Validate assigned user
    # --------------------------------------------------------

    if "assigned_to" in updates:

        verify_assigned_user(
            db,
            updates["assigned_to"],
            business_id,
        )

    # --------------------------------------------------------
    # Apply updates
    # --------------------------------------------------------

    old_values = snapshot_fields(
        task,
        AUDITED_TASK_FIELDS,
    )

    for field, value in updates.items():

        setattr(
            task,
            field,
            value,
        )

    # --------------------------------------------------------
    # Completion handling
    # --------------------------------------------------------

    if "status" in updates:

        if updates["status"] == "completed":

            if task.completed_at is None:

                task.completed_at = (
                    datetime.now(timezone.utc)
                )

        else:

            task.completed_at = None

    # --------------------------------------------------------
    # Update timestamp
    # --------------------------------------------------------

    task.updated_at = (
        datetime.now(timezone.utc)
    )

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    changes = build_audit_changes(
        old_values,
        snapshot_fields(task, AUDITED_TASK_FIELDS),
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="case.task_updated",
            entity_type="case_task",
            entity_id=task.id,
            details={
                "case_id": str(task.case_id),
                "changes": changes,
            },
            notes="Case task was updated.",
        )

    db.commit()
    db.refresh(task)

    return task


# ============================================================
# DELETE TASK
# DELETE /cases/tasks/{task_id}
# ============================================================

@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(

    task_id: UUID,

    db: Session = Depends(get_db),

    current_user: dict = Depends(require_permission("tasks.manage")),
):

    business_id = get_business_id(
        current_user
    )

    # --------------------------------------------------------
    # Find task
    # --------------------------------------------------------

    task = (
        db.query(CaseTask)
        .filter(
            CaseTask.id == task_id,
            CaseTask.business_id == business_id,
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # --------------------------------------------------------
    # Audit, then delete
    # --------------------------------------------------------

    create_audit_log(
        db,
        business_id=business_id,
        user_id=UUID(str(current_user["user_id"])),
        action="case.task_deleted",
        entity_type="case_task",
        entity_id=task.id,
        details={
            "case_id": str(task.case_id),
            "status": task.status,
        },
        notes="Case task was deleted.",
    )

    db.delete(task)
    db.commit()

    return None
