"""Services as work: someone is responsible and keeps the status up to date.

The person a service is given to (one or several) can update its status
without needing the permission to manage services; managers can do
everything. Everyone involved is told when it is given to them or changes.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_service import CaseService, CaseServiceAssignee
from app.models.funeral_case import FuneralCase
from app.models.user import User
from app.services.audit_service import create_audit_log
from app.services.notifications import notify
from app.services.permission_service import has_permission
from app.services.service_billing import sync_service_into_drafts

router = APIRouter(prefix="/service-work", tags=["Service work"])

STATUSES = ("pending", "confirmed", "in_progress", "completed", "cancelled")
SA = timezone(timedelta(hours=2))


def _can(db: Session, user: dict, permission: str) -> bool:
    return has_permission(
        db, user_id=user["user_id"], role=user["role"], permission_key=permission
    )


def _mine(service: CaseService, user: dict) -> bool:
    return str(user["user_id"]) in {str(i) for i in service.assignee_ids}


def _service(db: Session, user: dict, service_id: UUID) -> CaseService:
    service = (
        db.query(CaseService)
        .filter(
            CaseService.id == service_id,
            CaseService.business_id == user["business_id"],
        )
        .first()
    )
    if service is None:
        raise HTTPException(404, "Service not found")
    return service


def _names(db: Session, ids) -> dict:
    ids = {UUID(str(i)) for i in ids}
    if not ids:
        return {}
    return {
        str(u.id): u.full_name
        for u in db.query(User).filter(User.id.in_(list(ids))).all()
    }


def _row(service: CaseService, case: FuneralCase, names: dict, user: dict, can_manage: bool):
    return {
        "id": str(service.id),
        "case_id": str(case.id),
        "case_number": case.case_number,
        "deceased_full_name": case.deceased_full_name,
        "service_name": service.service_name,
        "service_type": service.service_type,
        "status": service.status,
        "scheduled_date": service.scheduled_date,
        "due_at": service.due_at,
        "completed_at": service.completed_at,
        "assignees": [
            {"id": str(i), "name": names.get(str(i), "Former colleague")}
            for i in service.assignee_ids
        ],
        "is_mine": _mine(service, user),
        "can_update": can_manage or _mine(service, user),
    }


@router.get("/people")
def people(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("services.manage")),
):
    rows = (
        db.query(User)
        .filter(User.business_id == user["business_id"], User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )
    return [{"id": str(u.id), "name": u.full_name, "role": u.role} for u in rows]


@router.get("/board")
def board(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    state: str = Query("open", pattern="^(open|done|archived)$"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("services.view")),
):
    """Services given to me, or (for managers) every service."""

    can_manage = _can(db, user, "services.manage")
    query = (
        db.query(CaseService, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CaseService.case_id)
        .filter(
            CaseService.business_id == user["business_id"],
            FuneralCase.business_id == user["business_id"],
        )
    )
    if scope == "all":
        if not can_manage:
            raise HTTPException(403, "Only people who manage services can see them all.")
    else:
        mine = db.query(CaseServiceAssignee.service_id).filter(
            CaseServiceAssignee.user_id == user["user_id"]
        )
        query = query.filter(CaseService.id.in_(mine))

    if state == "archived":
        query = query.filter(CaseService.archived_at.is_not(None))
    else:
        query = query.filter(CaseService.archived_at.is_(None))
        if state == "open":
            query = query.filter(CaseService.status.notin_(("completed", "cancelled")))
        else:
            query = query.filter(CaseService.status.in_(("completed", "cancelled")))

    rows = (
        query.order_by(
            CaseService.due_at.is_(None),
            CaseService.due_at.asc(),
            CaseService.scheduled_date.is_(None),
            CaseService.scheduled_date.asc(),
            CaseService.created_at.desc(),
        )
        .limit(500)
        .all()
    )
    names = _names(db, {i for s, _ in rows for i in s.assignee_ids})
    return {
        "scope": scope,
        "can_see_all": can_manage,
        "services": [_row(s, c, names, user, can_manage) for s, c in rows],
    }


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("services.view")),
):
    """What to tell someone when they open the platform."""

    mine = db.query(CaseServiceAssignee.service_id).filter(
        CaseServiceAssignee.user_id == user["user_id"]
    )
    rows = (
        db.query(CaseService)
        .filter(
            CaseService.business_id == user["business_id"],
            CaseService.id.in_(mine),
            CaseService.archived_at.is_(None),
            CaseService.status.notin_(("completed", "cancelled")),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    return {
        "open": len(rows),
        "not_started": sum(1 for s in rows if s.status in ("pending", "confirmed")),
        "overdue": sum(1 for s in rows if s.due_at is not None and s.due_at < now),
    }


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


@router.post("/{service_id}/status")
def set_status(
    service_id: UUID,
    data: StatusIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("services.view")),
):
    if data.status not in STATUSES:
        raise HTTPException(422, "Status must be one of: " + ", ".join(STATUSES))
    service = _service(db, user, service_id)
    can_manage = _can(db, user, "services.manage")
    if not (can_manage or _mine(service, user)):
        raise HTTPException(403, "This service is not given to you.")
    if data.status == "cancelled" and not can_manage:
        raise HTTPException(403, "Only people who manage services can cancel one.")
    if service.archived_at is not None:
        raise HTTPException(409, "Restore this service from the archive first.")
    if service.status == data.status:
        return {"id": str(service.id), "status": service.status}

    before = service.status
    service.status = data.status
    service.completed_at = (
        datetime.now(timezone.utc) if data.status == "completed" else None
    )

    if service.inventory_item_id is not None and (
        data.status == "cancelled" or before == "cancelled"
    ):
        from app.api.services import _sync_stock

        case = db.get(FuneralCase, service.case_id)
        _sync_stock(
            db, service,
            0 if data.status == "cancelled" else (service.quantity or 1),
            user, case.case_number if case else None,
        )
    db.flush()
    sync_service_into_drafts(db, service)

    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="case.service_status_changed",
        entity_type="case_service",
        entity_id=service.id,
        details={"case_id": str(service.case_id), "from": before, "to": data.status},
        notes="Service status was changed.",
    )

    who = db.query(User.full_name).filter(User.id == user["user_id"]).scalar()
    notify(
        db,
        business_id=user["business_id"],
        user_ids=service.assignee_ids,
        kind="service_update",
        title=f"{who or 'Someone'} set a service to {data.status.replace('_', ' ')}",
        body=service.service_name,
        link="/tasks",
        actor_id=user["user_id"],
    )
    db.commit()
    return {"id": str(service.id), "status": service.status}


class AssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_ids: list[UUID] = Field(default_factory=list, max_length=20)
    due_at: datetime | None = None


@router.post("/{service_id}/assign")
def assign(
    service_id: UUID,
    data: AssignIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("services.manage")),
):
    service = _service(db, user, service_id)
    wanted = list(dict.fromkeys(data.assignee_ids))
    valid = {
        u.id
        for u in db.query(User).filter(
            User.business_id == user["business_id"],
            User.is_active.is_(True),
            User.id.in_(wanted),
        )
    }
    if len(valid) != len(wanted):
        raise HTTPException(422, "Choose people from your own team.")

    before = set(service.assignee_ids)
    service.assignee_rows = [
        r for r in service.assignee_rows if r.user_id in valid
    ]
    have = {r.user_id for r in service.assignee_rows}
    for uid in wanted:
        if uid not in have:
            service.assignee_rows.append(CaseServiceAssignee(user_id=uid))
    service.due_at = data.due_at

    added = [u for u in wanted if u not in before]
    case = db.get(FuneralCase, service.case_id)
    if added:
        notify(
            db,
            business_id=user["business_id"],
            user_ids=added,
            kind="service_assigned",
            title=(
                "A service was shared with you" if len(wanted) > 1
                else "A service was given to you"
            ),
            body=f"{service.service_name}"
            + (f" — {case.deceased_full_name}" if case else ""),
            link="/tasks",
            actor_id=user["user_id"],
        )
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="case.service_assigned",
        entity_type="case_service",
        entity_id=service.id,
        details={"assignees": [str(u) for u in wanted]},
        notes="Service responsibility was changed.",
    )
    db.commit()
    return {"id": str(service.id), "assignee_ids": [str(u) for u in service.assignee_ids]}
