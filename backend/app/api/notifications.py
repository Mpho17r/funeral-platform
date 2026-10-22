from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _mine(db: Session, user: dict):
    return db.query(Notification).filter(
        Notification.user_id == UUID(str(user["user_id"])),
        Notification.business_id == UUID(str(user["business_id"])),
    )


def _out(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "created_at": n.created_at.isoformat(),
        "read": n.read_at is not None,
    }


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = _mine(db, user)
    unread = query.filter(Notification.read_at.is_(None)).count()
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    rows = (
        query.order_by(Notification.created_at.desc()).limit(limit).all()
    )
    return {"unread": unread, "items": [_out(n) for n in rows]}


@router.post("/read-all")
def read_all(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _mine(db, user).filter(Notification.read_at.is_(None)).update(
        {"read_at": datetime.now(timezone.utc)}, synchronize_session=False
    )
    db.commit()
    return {"unread": 0}


@router.post("/{notification_id}/read")
def read_one(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    note = _mine(db, user).filter(Notification.id == notification_id).first()
    if note is None:
        raise HTTPException(404, "Notification not found")
    if note.read_at is None:
        note.read_at = datetime.now(timezone.utc)
        db.commit()
    return _out(note)
