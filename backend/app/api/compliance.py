from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.compliance import ComplianceItem
from app.services import compliance as svc
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/compliance", tags=["Compliance"])


class ItemCreate(BaseModel):
    kind: str
    title: str = Field(min_length=2, max_length=200)
    reference: str | None = Field(default=None, max_length=100)
    issued_on: date | None = None
    expires_on: date
    notes: str | None = Field(default=None, max_length=2000)
    branch_id: UUID | None = None


class ItemUpdate(BaseModel):
    kind: str | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    reference: str | None = Field(default=None, max_length=100)
    issued_on: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _check(kind, issued_on, expires_on):
    if kind is not None and kind not in svc.KINDS:
        raise HTTPException(422, "Choose a valid type.")
    if issued_on and expires_on and expires_on < issued_on:
        raise HTTPException(422, "It cannot expire before it was issued.")


def _get(db, user, item_id) -> ComplianceItem:
    item = (
        db.query(ComplianceItem)
        .filter(
            ComplianceItem.id == item_id,
            ComplianceItem.business_id == user["business_id"],
        )
        .first()
    )
    if item is None:
        raise HTTPException(404, "Not found.")
    return item


@router.get("/kinds")
def kinds(user: dict = Depends(require_permission("compliance.view"))):
    return [{"key": k, "label": svc.KIND_LABELS[k]} for k in svc.KINDS]


@router.get("")
def list_items(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("compliance.view")),
):
    today = date.today()
    query = db.query(ComplianceItem).filter(
        ComplianceItem.business_id == user["business_id"]
    )
    if not include_archived:
        query = query.filter(ComplianceItem.status == "active")
    items = query.order_by(
        ComplianceItem.status, ComplianceItem.expires_on
    ).all()
    out = [svc.serialize(i, today) for i in items]
    live = [i for i in out if i["status"] == "active"]
    return {
        "expired": sum(1 for i in live if i["state"] == "expired"),
        "urgent": sum(1 for i in live if i["state"] == "urgent"),
        "soon": sum(1 for i in live if i["state"] == "soon"),
        "items": out,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("compliance.manage")),
):
    _check(payload.kind, payload.issued_on, payload.expires_on)
    if payload.kind not in svc.KINDS:
        raise HTTPException(422, "Choose a valid type.")

    item = ComplianceItem(
        business_id=user["business_id"],
        created_by=user["user_id"],
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="compliance.created",
        entity_type="compliance_item",
        entity_id=item.id,
        details={"kind": item.kind, "expires_on": str(item.expires_on)},
        notes="A licence or certificate was recorded.",
    )
    db.commit()
    return svc.serialize(item, date.today())


@router.patch("/{item_id}")
def update_item(
    item_id: UUID,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("compliance.manage")),
):
    item = _get(db, user, item_id)
    changes = payload.model_dump(exclude_unset=True)
    _check(
        changes.get("kind"),
        changes.get("issued_on", item.issued_on),
        changes.get("expires_on", item.expires_on),
    )
    if "expires_on" in changes and changes["expires_on"] is None:
        raise HTTPException(422, "An expiry date is required.")

    for field, value in changes.items():
        setattr(item, field, value)
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="compliance.updated",
        entity_type="compliance_item",
        entity_id=item.id,
        details={"fields": sorted(changes)},
        notes="A licence or certificate was updated.",
    )
    db.commit()
    return svc.serialize(item, date.today())


@router.post("/{item_id}/archive")
def archive_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("compliance.manage")),
):
    """Retire an old certificate once its renewal has been recorded."""
    item = _get(db, user, item_id)
    item.status = "archived"
    create_audit_log(
        db,
        business_id=user["business_id"],
        user_id=user["user_id"],
        action="compliance.archived",
        entity_type="compliance_item",
        entity_id=item.id,
        notes="A licence or certificate was archived.",
    )
    db.commit()
    return svc.serialize(item, date.today())
