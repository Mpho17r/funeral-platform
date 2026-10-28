from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_main_admin, require_permission
from app.models.business import Business
from app.models.case_task import CaseTask
from app.models.funeral_case import FuneralCase
from app.services import archive as service
from app.services.permission_service import has_permission

router = APIRouter(prefix="/archive", tags=["Archive"])


def _can(db: Session, user: dict, permission: str) -> bool:
    return has_permission(
        db, user_id=user["user_id"], role=user["role"], permission_key=permission
    )


def _fail(error: service.ArchiveError):
    raise HTTPException(error.status_code, error.detail)


@router.get("")
def list_archive(
    kind: str = Query("cases", pattern="^(cases|tasks)$"),
    q: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Archived cases or tasks, newest first."""

    business_id = user["business_id"]
    text = (q or "").strip()

    if kind == "cases":
        if not _can(db, user, "cases.view"):
            raise HTTPException(403, "You cannot view cases.")
        query = db.query(FuneralCase).filter(
            FuneralCase.business_id == business_id,
            FuneralCase.is_archived.is_(True),
        )
        if text:
            like = f"%{text}%"
            query = query.filter(
                FuneralCase.deceased_full_name.ilike(like)
                | FuneralCase.case_number.ilike(like)
            )
        rows = query.order_by(FuneralCase.archived_at.desc()).limit(limit).all()
        return [
            {
                "id": str(c.id),
                "title": c.deceased_full_name,
                "subtitle": c.case_number,
                "status": c.status,
                "archived_at": c.archived_at,
                "href": f"/cases/{c.id}",
            }
            for c in rows
        ]

    if not _can(db, user, "tasks.view"):
        raise HTTPException(403, "You cannot view tasks.")
    from app.api.task_workspace import _visible_query

    scope = "branch" if _can(db, user, "tasks.manage") else "mine"
    query = _visible_query(db, user, scope).filter(CaseTask.archived_at.is_not(None))
    if text:
        query = query.filter(CaseTask.title.ilike(f"%{text}%"))
    rows = query.order_by(CaseTask.archived_at.desc()).limit(limit).all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "subtitle": c.deceased_full_name,
            "status": t.status,
            "archived_at": t.archived_at,
            "href": f"/cases/{c.id}/tasks",
        }
        for t, c in rows
    ]


def _task(db: Session, user: dict, task_id: UUID) -> CaseTask:
    task = (
        db.query(CaseTask)
        .filter(CaseTask.id == task_id, CaseTask.business_id == user["business_id"])
        .first()
    )
    if task is None:
        raise HTTPException(404, "Task not found")
    mine = str(user["user_id"]) in {str(i) for i in task.assignee_ids} or (
        task.assigned_to is not None and str(task.assigned_to) == str(user["user_id"])
    )
    if not mine and not _can(db, user, "tasks.manage"):
        raise HTTPException(403, "You can only archive your own tasks.")
    return task


@router.post("/tasks/{task_id}/archive")
def archive_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("tasks.view")),
):
    task = _task(db, user, task_id)
    try:
        service.archive_task(db, task, user["user_id"])
    except service.ArchiveError as error:
        _fail(error)
    db.commit()
    return {"ok": True, "archived_at": task.archived_at}


@router.post("/tasks/{task_id}/restore")
def restore_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("tasks.view")),
):
    task = _task(db, user, task_id)
    try:
        service.restore_task(db, task, user["user_id"])
    except service.ArchiveError as error:
        _fail(error)
    db.commit()
    return {"ok": True}


@router.delete("/{kind}/{item_id}", status_code=204)
def delete_for_good(
    kind: str,
    item_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_main_admin),
):
    """Main admin only, and only for archived items."""

    business_id = user["business_id"]
    try:
        if kind == "tasks":
            task = (
                db.query(CaseTask)
                .filter(CaseTask.id == item_id, CaseTask.business_id == business_id)
                .first()
            )
            if task is None:
                raise HTTPException(404, "Task not found")
            service.delete_archived_task(db, task, user["user_id"])
        elif kind == "cases":
            case = (
                db.query(FuneralCase)
                .filter(FuneralCase.id == item_id, FuneralCase.business_id == business_id)
                .first()
            )
            if case is None:
                raise HTTPException(404, "Case not found")
            service.delete_archived_case(db, case, user["user_id"])
        else:
            raise HTTPException(404, "Unknown kind")
    except service.ArchiveError as error:
        db.rollback()
        _fail(error)
    db.commit()


class ArchiveSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archive_after_days: int = Field(ge=0, le=365)
    # None = never delete. Otherwise 1 month up to 10 years.
    delete_archived_after_months: int | None = Field(default=None, ge=1, le=120)


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    business = db.get(Business, user["business_id"])
    return {
        "archive_after_days": business.archive_after_days,
        "delete_archived_after_months": business.delete_archived_after_months,
        "can_change": user["role"] == "main_admin",
    }


@router.put("/settings")
def put_settings(
    data: ArchiveSettings,
    db: Session = Depends(get_db),
    user: dict = Depends(require_main_admin),
):
    from app.services.audit_service import create_audit_log

    business = db.get(Business, user["business_id"])
    before = {
        "archive_after_days": business.archive_after_days,
        "delete_archived_after_months": business.delete_archived_after_months,
    }
    business.archive_after_days = data.archive_after_days
    business.delete_archived_after_months = data.delete_archived_after_months
    create_audit_log(
        db,
        business_id=business.id,
        user_id=user["user_id"],
        action="business.archive_settings_updated",
        entity_type="business",
        entity_id=business.id,
        details={"before": before, "after": data.model_dump()},
        notes="Archive settings were changed.",
    )
    db.commit()
    return {
        "archive_after_days": business.archive_after_days,
        "delete_archived_after_months": business.delete_archived_after_months,
        "can_change": True,
    }
