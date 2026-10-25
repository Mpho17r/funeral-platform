from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.portal import PortalLink
from app.services import portal as svc
from app.services.audit_service import create_audit_log

router = APIRouter(tags=["Portal"])


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["family", "member"]
    case_id: UUID | None = None
    member_id: UUID | None = None
    days_valid: int = Field(default=svc.DEFAULT_DAYS, ge=1, le=svc.MAX_DAYS)


def _link_out(link: PortalLink) -> dict:
    return {
        "id": link.id,
        "kind": link.kind,
        "case_id": link.case_id,
        "member_id": link.member_id,
        "expires_at": link.expires_at,
        "revoked_at": link.revoked_at,
        "last_used_at": link.last_used_at,
        "created_at": link.created_at,
    }


# ---------------------------------------------------------------- staff side


@router.post("/portal-links", status_code=status.HTTP_201_CREATED)
def create_portal_link(
    data: LinkCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("portal.manage")),
):
    """Make a private link. The secret is returned once and never again."""
    business_id = current_user["business_id"]

    if data.kind == "family":
        if data.case_id is None or data.member_id is not None:
            raise HTTPException(422, "A family link needs a case")
        target = (
            db.query(FuneralCase)
            .filter(FuneralCase.id == data.case_id,
                    FuneralCase.business_id == business_id)
            .first()
        )
    else:
        if data.member_id is None or data.case_id is not None:
            raise HTTPException(422, "A member link needs a member")
        target = (
            db.query(Member)
            .filter(Member.id == data.member_id,
                    Member.business_id == business_id)
            .first()
        )
    if target is None:
        raise HTTPException(404, "Not found")

    link, token = svc.create_link(
        db,
        business_id=business_id,
        kind=data.kind,
        case_id=data.case_id,
        member_id=data.member_id,
        created_by=current_user["user_id"],
        days=data.days_valid,
    )
    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="portal.link_created",
        entity_type="portal_link",
        entity_id=link.id,
        details={"kind": data.kind},
        notes="A private portal link was created.",
    )
    db.commit()
    return {**_link_out(link), "token": token, "path": f"/portal/{token}"}


@router.get("/portal-links")
def list_portal_links(
    case_id: UUID | None = None,
    member_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("portal.manage")),
):
    query = db.query(PortalLink).filter(
        PortalLink.business_id == current_user["business_id"]
    )
    if case_id:
        query = query.filter(PortalLink.case_id == case_id)
    if member_id:
        query = query.filter(PortalLink.member_id == member_id)
    return [
        _link_out(l) for l in query.order_by(PortalLink.created_at.desc()).all()
    ]


@router.delete("/portal-links/{link_id}")
def revoke_portal_link(
    link_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("portal.manage")),
):
    link = (
        db.query(PortalLink)
        .filter(PortalLink.id == link_id,
                PortalLink.business_id == current_user["business_id"])
        .first()
    )
    if link is None:
        raise HTTPException(404, "Not found")
    if link.revoked_at is None:
        link.revoked_at = datetime.now(timezone.utc)
        create_audit_log(
            db,
            business_id=link.business_id,
            user_id=current_user["user_id"],
            action="portal.link_revoked",
            entity_type="portal_link",
            entity_id=link.id,
            details={"kind": link.kind},
            notes="A private portal link was revoked.",
        )
        db.commit()
    return _link_out(link)


# ---------------------------------------------------------------- public side
# No sign-in: the secret in the address is the key. Anything wrong with it
# (unknown, expired, revoked) looks the same, so links cannot be probed.


@router.get("/portal/{token}")
def open_portal(token: str, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if svc.too_many_failures(ip):
        raise HTTPException(429, "Too many attempts. Try again later.")

    link = svc.find_link(db, token)
    if link is None:
        svc.record_failure(ip)
        raise HTTPException(404, "This link is not valid any more")

    view = (
        svc.family_view(db, link)
        if link.kind == "family"
        else svc.member_view(db, link)
    )
    db.commit()  # remember last use
    return view
