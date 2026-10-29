from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_main_admin, require_manager_or_admin
from app.models.business import Business
from app.models.kai import KaiAutopilotItem
from app.models.user import User
from app.services import autopilot as service
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/autopilot", tags=["KAI Autopilot"])

# Managers and the main admin: whoever hands out the work.
manage = require_manager_or_admin


def _settings(business: Business, can_change: bool) -> dict:
    return {
        "mode": business.autopilot_mode,
        "create_tasks": business.autopilot_create_tasks,
        "assign": business.autopilot_assign,
        "escalate": business.autopilot_escalate,
        "max_open": business.autopilot_max_open,
        "can_change": can_change,
    }


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(pattern="^(off|suggest|auto)$")
    create_tasks: bool = True
    assign: bool = True
    escalate: bool = True
    max_open: int = Field(default=8, ge=1, le=50)


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    business = db.get(Business, user["business_id"])
    return _settings(business, user["role"] == "main_admin")


@router.put("/settings")
def put_settings(
    data: SettingsIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_main_admin),
):
    business = db.get(Business, user["business_id"])
    before = _settings(business, True)
    business.autopilot_mode = data.mode
    business.autopilot_create_tasks = data.create_tasks
    business.autopilot_assign = data.assign
    business.autopilot_escalate = data.escalate
    business.autopilot_max_open = data.max_open
    create_audit_log(
        db,
        business_id=business.id,
        user_id=user["user_id"],
        action="business.autopilot_settings_updated",
        entity_type="business",
        entity_id=business.id,
        details={"before": before, "after": data.model_dump()},
        notes="KAI Autopilot settings were changed.",
    )
    db.commit()
    return _settings(business, True)


def _out(item: KaiAutopilotItem) -> dict:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "status": item.status,
        "summary": item.summary,
        "reason": item.reason,
        "case_id": str(item.case_id) if item.case_id else None,
        "created_at": item.created_at,
        "decided_at": item.decided_at,
        "can_undo": item.status in ("applied", "approved"),
    }


@router.get("/items")
def list_items(
    status: str = Query("pending", pattern="^(pending|done|all)$"),
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    query = db.query(KaiAutopilotItem).filter(
        KaiAutopilotItem.business_id == user["business_id"]
    )
    if status == "pending":
        query = query.filter(KaiAutopilotItem.status == "pending")
    elif status == "done":
        query = query.filter(
            KaiAutopilotItem.status.in_(("applied", "approved", "dismissed", "undone"))
        )
    rows = query.order_by(KaiAutopilotItem.created_at.desc()).limit(limit).all()
    return [_out(r) for r in rows]


def _item(db: Session, user: dict, item_id: UUID) -> KaiAutopilotItem:
    item = (
        db.query(KaiAutopilotItem)
        .filter(
            KaiAutopilotItem.id == item_id,
            KaiAutopilotItem.business_id == user["business_id"],
        )
        .first()
    )
    if item is None:
        raise HTTPException(404, "Not found")
    return item


def _decide(db: Session, user: dict, item_id: UUID, action):
    item = _item(db, user, item_id)
    try:
        with db.begin_nested():
            action(db, item, user["user_id"]) if action is not service.undo else action(db, item)
    except service.AutopilotError as error:
        raise HTTPException(error.status_code, error.detail)
    db.commit()
    return _out(item)


@router.post("/items/{item_id}/approve")
def approve(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    return _decide(db, user, item_id, service.approve)


@router.post("/items/{item_id}/dismiss")
def dismiss(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    return _decide(db, user, item_id, service.dismiss)


@router.post("/items/{item_id}/undo")
def undo(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    return _decide(db, user, item_id, service.undo)


@router.post("/run")
def run_now(
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    """Do a pass right now instead of waiting for the next one."""

    business = db.get(Business, user["business_id"])
    if business.autopilot_mode == "off":
        raise HTTPException(409, "KAI Autopilot is switched off.")
    return service.run(db, business)


@router.get("/workload")
def get_workload(
    db: Session = Depends(get_db),
    user: dict = Depends(manage),
):
    business = db.get(Business, user["business_id"])
    loads = service.workload(db, business.id)
    present = service.present_today(db, business.id)
    people = (
        db.query(User)
        .filter(User.business_id == business.id, User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )
    return {
        "max_open": business.autopilot_max_open,
        "people": [
            {
                "id": str(p.id),
                "name": p.full_name,
                "role": p.role,
                "open": loads.get(p.id, 0),
                "present": p.id in present,
            }
            for p in people
        ],
    }
