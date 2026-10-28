"""My tasks, the branch's tasks, the whole organisation's tasks.

Anyone a task is given to can move its status, write a report and
upload files on it. A task can be shared by several people.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_task import CaseTask, CaseTaskAssignee, CaseTaskEntry
from app.models.funeral_case import FuneralCase
from app.models.user import User
from app.schemas.case_task import TASK_STATUSES
from app.services.audit_service import create_audit_log
from app.services.notifications import notify
from app.services.permission_service import has_permission
from app.services.task_access import SA, can_work_on, is_assignee

router = APIRouter(prefix="/tasks", tags=["Task Workspace"])

STORAGE_ROOT = Path("storage/task_files")
MAX_FILE_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".csv",
    ".doc", ".docx", ".xls", ".xlsx", ".mp3", ".m4a", ".wav",
}
SCOPES = ("mine", "branch", "organisation")


def _business_id(current_user: dict) -> UUID:
    raw = current_user.get("business_id")
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User business information is missing")
    try:
        return UUID(str(raw))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid business ID")


def _can(db: Session, user: dict, permission: str) -> bool:
    return has_permission(
        db, user_id=user["user_id"], role=user["role"], permission_key=permission
    )


def _names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    return {
        u.id: u.full_name
        for u in db.query(User).filter(User.id.in_(ids))
    }


def _row(task: CaseTask, case: FuneralCase, names: dict, me: UUID) -> dict:
    ids = list(task.assignee_ids)
    if task.assigned_to and task.assigned_to not in ids:
        ids.insert(0, task.assigned_to)
    return {
        "id": task.id,
        "business_id": task.business_id,
        "case_id": task.case_id,
        "case_number": case.case_number,
        "deceased_full_name": case.deceased_full_name,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "due_date": task.due_date,
        "due_at": task.due_at,
        "assigned_to": task.assigned_to,
        "assigned_to_name": names.get(task.assigned_to),
        "assignees": [{"id": i, "name": names.get(i, "Former colleague")} for i in ids],
        "assignee_ids": ids,
        "is_mine": me in ids,
        "shared": len(ids) > 1,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
    }


def _visible_query(db: Session, current_user: dict, scope: str):
    business_id = _business_id(current_user)
    me = UUID(str(current_user["user_id"]))
    query = (
        db.query(CaseTask, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CaseTask.case_id)
        .filter(
            CaseTask.business_id == business_id,
            FuneralCase.business_id == business_id,
        )
    )
    if scope == "mine":
        mine = db.query(CaseTaskAssignee.task_id).filter(CaseTaskAssignee.user_id == me)
        query = query.filter((CaseTask.assigned_to == me) | CaseTask.id.in_(mine))
    elif scope == "branch":
        if not _can(db, current_user, "tasks.manage"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only people who manage tasks can view the whole branch.",
            )
        person = db.get(User, me)
        if person is not None and person.branch_id is not None and _can(
            db, current_user, "branches.all_access"
        ):
            query = query.filter(FuneralCase.branch_id == person.branch_id)
    elif scope == "organisation":
        if not _can(db, current_user, "branches.all_access"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only people with access to every branch can view the organisation's tasks.",
            )
    return query


def _scopes_for(db: Session, current_user: dict) -> list[str]:
    out = ["mine"]
    if _can(db, current_user, "tasks.manage"):
        out.append("branch")
    if _can(db, current_user, "branches.all_access"):
        out.append("organisation")
    return out


def _build(db, current_user, scope, state):
    me = UUID(str(current_user["user_id"]))
    query = _visible_query(db, current_user, scope)
    if state == "open":
        query = query.filter(CaseTask.status != "completed")
    elif state == "done":
        query = query.filter(CaseTask.status == "completed")
    rows = query.order_by(
        CaseTask.due_at.is_(None),
        CaseTask.due_at.asc(),
        CaseTask.due_date.is_(None),
        CaseTask.due_date.asc(),
        CaseTask.created_at.desc(),
    ).limit(1000).all()

    ids: set[UUID] = set()
    for task, _ in rows:
        ids.update(task.assignee_ids)
        if task.assigned_to:
            ids.add(task.assigned_to)
    names = _names(db, ids)
    return [_row(task, case, names, me) for task, case in rows]


@router.get("")
def list_workspace_tasks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    """Every task the person can see (used by dashboards)."""

    return _build(db, current_user, "all", "all")


@router.get("/board")
def task_board(
    scope: str = Query("mine"),
    state: str = Query("all", pattern="^(all|open|done)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    """The tasks page: my tasks, the branch's, or the organisation's."""

    if scope not in SCOPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown scope")
    return {
        "scope": scope,
        "scopes": _scopes_for(db, current_user),
        "tasks": _build(db, current_user, scope, state),
    }


@router.get("/summary")
def my_task_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    """What to tell someone the moment they open the platform."""

    me = UUID(str(current_user["user_id"]))
    rows = (
        _visible_query(db, current_user, "mine")
        .filter(CaseTask.status != "completed")
        .all()
    )
    now = datetime.now(timezone.utc)
    today = datetime.now(SA).date()
    overdue = due_today = 0
    for task, _ in rows:
        due = task.due_at
        if due is not None and due.astimezone(SA).date() == today and due >= now:
            due_today += 1
        if (due is not None and due < now) or (
            due is None and task.due_date is not None and task.due_date < today
        ):
            overdue += 1
        elif due is None and task.due_date == today:
            due_today += 1
    names = _names(db, {i for t, _ in rows for i in t.assignee_ids})
    rows.sort(key=lambda r: (r[0].due_at is None, r[0].due_at or now, r[0].created_at))
    return {
        "open": len(rows),
        "overdue": overdue,
        "due_today": due_today,
        "not_started": sum(1 for t, _ in rows if t.status == "pending"),
        "items": [_row(t, c, names, me) for t, c in rows[:5]],
    }


# ------------------------------------------------------------
# One task
# ------------------------------------------------------------


def _task_or_404(db: Session, task_id: UUID, current_user: dict):
    business_id = _business_id(current_user)
    found = (
        db.query(CaseTask, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CaseTask.case_id)
        .filter(CaseTask.id == task_id, CaseTask.business_id == business_id)
        .first()
    )
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return found


def _entries(db: Session, task: CaseTask) -> list[dict]:
    rows = (
        db.query(CaseTaskEntry)
        .filter(CaseTaskEntry.task_id == task.id)
        .order_by(CaseTaskEntry.created_at.asc())
        .all()
    )
    names = _names(db, {r.user_id for r in rows if r.user_id})
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "text": r.text,
            "file_name": r.file_name,
            "size_bytes": r.size_bytes,
            "author_id": r.user_id,
            "author": names.get(r.user_id, "Former colleague"),
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/{task_id}")
def task_detail(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    task, case = _task_or_404(db, task_id, current_user)
    me = UUID(str(current_user["user_id"]))
    names = _names(db, set(task.assignee_ids) | ({task.assigned_to} if task.assigned_to else set()))
    detail = _row(task, case, names, me)
    detail["entries"] = _entries(db, task)
    detail["can_update"] = can_work_on(db, current_user, task)
    return detail


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=5000)


def _tell_the_others(db, task, current_user, title: str):
    others = set(task.assignee_ids)
    notify(
        db,
        business_id=task.business_id,
        user_ids=others,
        kind="task_update",
        title=title,
        body=task.title,
        link="/tasks",
        actor_id=current_user["user_id"],
    )


@router.post("/{task_id}/status")
def change_status(
    task_id: UUID,
    data: StatusChange,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    task, _case = _task_or_404(db, task_id, current_user)
    if not can_work_on(db, current_user, task):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This task is not given to you.")
    new = data.status.strip().lower()
    if new not in TASK_STATUSES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Status must be pending, in_progress or completed")
    if new != task.status:
        old = task.status
        task.status = new
        task.completed_at = datetime.now(timezone.utc) if new == "completed" else None
        task.updated_at = datetime.now(timezone.utc)
        create_audit_log(
            db,
            business_id=task.business_id,
            user_id=UUID(str(current_user["user_id"])),
            action="case.task_updated",
            entity_type="case_task",
            entity_id=task.id,
            details={"case_id": str(task.case_id), "changes": {"status": {"old": old, "new": new}}},
            notes="Task status was changed by an assignee.",
        )
        label = {"pending": "not started", "in_progress": "in progress", "completed": "done"}[new]
        _tell_the_others(db, task, current_user, f"A shared task is now {label}")
        db.commit()
    return {"ok": True, "status": task.status, "completed_at": task.completed_at}


@router.post("/{task_id}/report", status_code=status.HTTP_201_CREATED)
def add_report(
    task_id: UUID,
    data: ReportIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    task, _case = _task_or_404(db, task_id, current_user)
    if not can_work_on(db, current_user, task):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This task is not given to you.")
    entry = CaseTaskEntry(
        task_id=task.id,
        user_id=UUID(str(current_user["user_id"])),
        kind="report",
        text=data.text.strip(),
    )
    db.add(entry)
    task.updated_at = datetime.now(timezone.utc)
    _tell_the_others(db, task, current_user, "A report was added to a shared task")
    db.commit()
    return {"ok": True, "id": entry.id}


@router.post("/{task_id}/files", status_code=status.HTTP_201_CREATED)
def upload_file(
    task_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    task, _case = _task_or_404(db, task_id, current_user)
    if not can_work_on(db, current_user, task):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This task is not given to you.")
    name = Path(file.filename or "file").name[:200]
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file type is not allowed.")
    content = file.file.read(MAX_FILE_BYTES + 1)
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty.")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The file is larger than 15 MB.")

    entry_id = uuid4()
    folder = STORAGE_ROOT / str(task.business_id) / str(task.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{entry_id}{extension}"
    path.write_bytes(content)

    db.add(
        CaseTaskEntry(
            id=entry_id,
            task_id=task.id,
            user_id=UUID(str(current_user["user_id"])),
            kind="file",
            file_name=name,
            content_type=file.content_type,
            file_path=str(path),
            size_bytes=len(content),
        )
    )
    task.updated_at = datetime.now(timezone.utc)
    _tell_the_others(db, task, current_user, "A file was added to a shared task")
    db.commit()
    return {"ok": True, "id": entry_id}


@router.get("/{task_id}/files/{entry_id}")
def download_file(
    task_id: UUID,
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    task, _case = _task_or_404(db, task_id, current_user)
    entry = (
        db.query(CaseTaskEntry)
        .filter(CaseTaskEntry.id == entry_id, CaseTaskEntry.task_id == task.id, CaseTaskEntry.kind == "file")
        .first()
    )
    if not entry or not entry.file_path or not Path(entry.file_path).is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(
        entry.file_path,
        filename=entry.file_name,
        media_type=entry.content_type or "application/octet-stream",
    )


@router.delete("/{task_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    task_id: UUID,
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("tasks.view")),
):
    task, _case = _task_or_404(db, task_id, current_user)
    entry = (
        db.query(CaseTaskEntry)
        .filter(CaseTaskEntry.id == entry_id, CaseTaskEntry.task_id == task.id)
        .first()
    )
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    mine = entry.user_id is not None and str(entry.user_id) == str(current_user["user_id"])
    if not (mine or _can(db, current_user, "tasks.manage")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only remove your own entries.")
    if entry.file_path:
        Path(entry.file_path).unlink(missing_ok=True)
    db.delete(entry)
    db.commit()
