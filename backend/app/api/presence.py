from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.staff_presence import StaffPresence
from app.models.user import User
from app.schemas.staff_presence import (
    StaffPresenceResponse,
    StaffPresenceUpdate,
)


router = APIRouter(
    prefix="/presence",
    tags=["Staff Presence"],
)


def get_or_create_presence(
    db: Session,
    *,
    business_id,
    user_id,
) -> StaffPresence:
    """Return the current presence record for a user."""
    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == business_id,
            StaffPresence.user_id == user_id,
        )
        .first()
    )

    if presence is None:
        presence = StaffPresence(
            business_id=business_id,
            user_id=user_id,
            status="offline",
        )

        db.add(presence)
        db.flush()

    return presence


def serialize_presence(
    presence: StaffPresence,
    user: User,
) -> StaffPresenceResponse:
    return StaffPresenceResponse(
        id=presence.id,
        business_id=presence.business_id,
        user_id=presence.user_id,
        user_name=user.full_name,
        role=user.role,
        status=presence.status,
        last_seen_at=presence.last_seen_at,
        checked_in_at=presence.checked_in_at,
        checked_out_at=presence.checked_out_at,
        created_at=presence.created_at,
        updated_at=presence.updated_at,
    )


@router.get(
    "",
    response_model=list[StaffPresenceResponse],
)
def list_presence(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("presence.view")
    ),
):
    rows = (
        db.query(StaffPresence, User)
        .join(User, User.id == StaffPresence.user_id)
        .filter(
            StaffPresence.business_id
            == current_user["business_id"],
            User.business_id
            == current_user["business_id"],
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )

    return [
        serialize_presence(presence, user)
        for presence, user in rows
    ]


@router.get(
    "/me",
    response_model=StaffPresenceResponse,
)
def get_my_presence(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("presence.view")
    ),
):
    user = (
        db.query(User)
        .filter(
            User.id == current_user["user_id"],
            User.business_id == current_user["business_id"],
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    presence = get_or_create_presence(
        db,
        business_id=current_user["business_id"],
        user_id=current_user["user_id"],
    )

    db.commit()
    db.refresh(presence)

    return serialize_presence(presence, user)


@router.patch(
    "/me",
    response_model=StaffPresenceResponse,
)
def update_my_presence(
    data: StaffPresenceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("presence.manage")
    ),
):
    user = (
        db.query(User)
        .filter(
            User.id == current_user["user_id"],
            User.business_id == current_user["business_id"],
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    presence = get_or_create_presence(
        db,
        business_id=current_user["business_id"],
        user_id=current_user["user_id"],
    )

    now = datetime.now(timezone.utc)

    presence.status = data.status
    presence.last_seen_at = now

    if data.status == "checked_in":
        if presence.checked_in_at is None:
            presence.checked_in_at = now
        presence.checked_out_at = None

    elif data.status == "offline":
        presence.checked_out_at = now

    db.commit()
    db.refresh(presence)

    return serialize_presence(presence, user)
