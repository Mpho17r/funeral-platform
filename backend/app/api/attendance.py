from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.business import Business
from app.dependencies.auth import get_current_user
from app.models.staff_attendance_session import StaffAttendanceSession
from app.models.staff_break_session import StaffBreakSession
from app.models.staff_presence import StaffPresence
from app.schemas.staff_attendance import (
    StaffAttendanceMeResponse,
    StaffAttendanceSessionResponse,
    StaffBreakSessionResponse,
    StaffBreakStartRequest,
)


router = APIRouter(
    prefix="/attendance",
    tags=["Staff Attendance"],
)


def get_active_attendance_session(
    db: Session,
    *,
    business_id,
    user_id,
) -> StaffAttendanceSession | None:
    return (
        db.query(StaffAttendanceSession)
        .filter(
            StaffAttendanceSession.business_id == business_id,
            StaffAttendanceSession.user_id == user_id,
            StaffAttendanceSession.checked_out_at.is_(None),
        )
        .first()
    )


def apply_break_expiry_policy(
    db: Session,
    *,
    business: Business,
    break_session: StaffBreakSession | None,
) -> StaffBreakSession | None:
    if break_session is None:
        return None

    if break_session.ended_at is not None:
        return break_session

    if break_session.break_type == "tea":
        duration_minutes = business.tea_break_minutes
    elif break_session.break_type == "lunch":
        duration_minutes = business.lunch_break_minutes
    else:
        return break_session

    now = datetime.now(timezone.utc)

    expiry_at = (
        break_session.started_at
        + timedelta(minutes=duration_minutes)
    )

    if now < expiry_at:
        return break_session

    if business.break_expiry_behavior == "auto_return":
        break_session.ended_at = expiry_at
        db.flush()

    return break_session


def get_break_state(
    *,
    business: Business,
    break_session: StaffBreakSession | None,
) -> tuple[datetime | None, bool]:
    if break_session is None or break_session.ended_at is not None:
        return None, False

    if break_session.break_type == "tea":
        duration_minutes = business.tea_break_minutes
    elif break_session.break_type == "lunch":
        duration_minutes = business.lunch_break_minutes
    else:
        return None, False

    expiry_at = (
        break_session.started_at
        + timedelta(minutes=duration_minutes)
    )

    if not business.break_warning_enabled:
        return expiry_at, False

    warning_minutes = business.break_warning_minutes

    if warning_minutes <= 0:
        return expiry_at, False

    warning_at = (
        expiry_at
        - timedelta(minutes=warning_minutes)
    )

    now = datetime.now(timezone.utc)

    return expiry_at, warning_at <= now < expiry_at


def refresh_attendance_presence(
    db: Session,
    *,
    business: Business,
    attendance_session: StaffAttendanceSession | None,
    presence: StaffPresence | None,
    current_break: StaffBreakSession | None,
) -> StaffPresence | None:
    if presence is None or attendance_session is None:
        return presence

    if current_break is not None:
        return presence

    if presence.last_seen_at is None:
        return presence

    now = datetime.now(timezone.utc)

    idle_seconds = (
        now - presence.last_seen_at
    ).total_seconds()

    timeout_seconds = (
        business.idle_timeout_minutes * 60
    )

    if idle_seconds >= timeout_seconds:
        presence.status = "away"
    else:
        presence.status = "online"

    db.flush()

    return presence


@router.post(
    "/check-in",
    response_model=StaffAttendanceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def check_in(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    existing_session = get_active_attendance_session(
        db,
        business_id=business_id,
        user_id=user_id,
    )

    if existing_session is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already checked in",
        )

    now = datetime.now(timezone.utc)

    session = StaffAttendanceSession(
        business_id=business_id,
        user_id=user_id,
        status="active",
        checked_in_at=now,
    )

    db.add(session)

    try:
        db.flush()

    except IntegrityError as exc:
        db.rollback()

        if (
            "uq_staff_attendance_sessions_active_user"
            in str(exc.orig)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You are already checked in",
            )

        raise

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
        )
        db.add(presence)

    presence.status = "online"
    presence.last_seen_at = now
    presence.checked_in_at = now
    presence.checked_out_at = None

    db.commit()
    db.refresh(session)

    return session


@router.post(
    "/check-out",
    response_model=StaffAttendanceSessionResponse,
)
def check_out(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    session = get_active_attendance_session(
        db,
        business_id=business_id,
        user_id=user_id,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are not checked in",
        )

    now = datetime.now(timezone.utc)

    active_break = (
        db.query(StaffBreakSession)
        .filter(
            StaffBreakSession.attendance_session_id
            == session.id,
            StaffBreakSession.business_id == business_id,
            StaffBreakSession.user_id == user_id,
            StaffBreakSession.ended_at.is_(None),
        )
        .first()
    )

    if active_break is not None:
        active_break.ended_at = now

    session.checked_out_at = now
    session.status = "completed"

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == business_id,
            StaffPresence.user_id == user_id,
        )
        .first()
    )

    if presence is not None:
        presence.status = "offline"
        presence.last_seen_at = now
        presence.checked_out_at = now

    db.commit()
    db.refresh(session)

    return session


@router.post(
    "/breaks/start",
    response_model=StaffBreakSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_break(
    break_data: StaffBreakStartRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    business = (
        db.query(Business)
        .filter(Business.id == business_id)
        .first()
    )

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    attendance_session = get_active_attendance_session(
        db,
        business_id=business_id,
        user_id=user_id,
    )

    if attendance_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must be checked in to start a break",
        )

    existing_break = (
        db.query(StaffBreakSession)
        .filter(
            StaffBreakSession.business_id == business_id,
            StaffBreakSession.user_id == user_id,
            StaffBreakSession.ended_at.is_(None),
        )
        .first()
    )

    existing_break = apply_break_expiry_policy(
        db,
        business=business,
        break_session=existing_break,
    )

    if existing_break is not None and existing_break.ended_at is not None:
        existing_break = None

    if existing_break is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active break",
        )

    now = datetime.now(timezone.utc)

    break_session = StaffBreakSession(
        attendance_session_id=attendance_session.id,
        business_id=business_id,
        user_id=user_id,
        break_type=break_data.break_type,
        started_at=now,
    )

    db.add(break_session)

    try:
        db.flush()

    except IntegrityError as exc:
        db.rollback()

        if (
            "uq_staff_break_sessions_active_user"
            in str(exc.orig)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an active break",
            )

        raise

    db.commit()
    db.refresh(break_session)

    return break_session


@router.post(
    "/breaks/end",
    response_model=StaffBreakSessionResponse,
)
def end_break(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    attendance_session = get_active_attendance_session(
        db,
        business_id=business_id,
        user_id=user_id,
    )

    if attendance_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are not checked in",
        )

    break_session = (
        db.query(StaffBreakSession)
        .filter(
            StaffBreakSession.business_id == business_id,
            StaffBreakSession.user_id == user_id,
            StaffBreakSession.ended_at.is_(None),
        )
        .first()
    )

    if break_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You do not have an active break",
        )

    now = datetime.now(timezone.utc)

    break_session.ended_at = now

    db.commit()
    db.refresh(break_session)

    return break_session


@router.get(
    "/me",
    response_model=StaffAttendanceMeResponse,
)
def get_my_attendance(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    business = db.get(Business, business_id)

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    attendance_session = get_active_attendance_session(
        db,
        business_id=business_id,
        user_id=user_id,
    )

    current_break = None

    if attendance_session is not None:
        current_break = (
            db.query(StaffBreakSession)
            .filter(
                StaffBreakSession.attendance_session_id
                == attendance_session.id,
                StaffBreakSession.business_id == business_id,
                StaffBreakSession.user_id == user_id,
                StaffBreakSession.ended_at.is_(None),
            )
            .first()
        )

    current_break = apply_break_expiry_policy(
        db,
        business=business,
        break_session=current_break,
    )

    if current_break is not None and current_break.ended_at is not None:
        current_break = None

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.business_id == business_id,
            StaffPresence.user_id == user_id,
        )
        .first()
    )

    presence = refresh_attendance_presence(
        db,
        business=business,
        attendance_session=attendance_session,
        presence=presence,
        current_break=current_break,
    )

    break_expires_at, break_warning_active = get_break_state(
        business=business,
        break_session=current_break,
    )

    db.commit()

    return StaffAttendanceMeResponse(
        attendance=attendance_session,
        current_break=current_break,
        break_warning_active=break_warning_active,
        break_expires_at=break_expires_at,
        presence=presence.status if presence else "offline",
        last_seen_at=presence.last_seen_at if presence else None,
    )


@router.post(
    "/heartbeat",
    response_model=StaffAttendanceMeResponse,
)
def heartbeat(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    business_id = current_user["business_id"]
    user_id = current_user["user_id"]

    business = (
        db.query(Business)
        .filter(Business.id == business_id)
        .first()
    )

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    attendance_session = get_active_attendance_session(
        db,
        business_id=business_id,
        user_id=user_id,
    )

    if attendance_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are not checked in",
        )

    now = datetime.now(timezone.utc)

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
        )
        db.add(presence)

    presence.status = "online"
    presence.last_seen_at = now

    current_break = (
        db.query(StaffBreakSession)
        .filter(
            StaffBreakSession.attendance_session_id
            == attendance_session.id,
            StaffBreakSession.business_id == business_id,
            StaffBreakSession.user_id == user_id,
            StaffBreakSession.ended_at.is_(None),
        )
        .first()
    )

    current_break = apply_break_expiry_policy(
        db,
        business=business,
        break_session=current_break,
    )

    if current_break is not None and current_break.ended_at is not None:
        current_break = None

    break_expires_at, break_warning_active = get_break_state(
        business=business,
        break_session=current_break,
    )

    db.commit()

    return StaffAttendanceMeResponse(
        attendance=attendance_session,
        current_break=current_break,
        break_warning_active=break_warning_active,
        break_expires_at=break_expires_at,
        presence=presence.status,
        last_seen_at=presence.last_seen_at,
    )
