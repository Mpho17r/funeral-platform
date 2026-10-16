"""Sign-in protection: lockout after repeated wrong passwords.

* Wrong passwords are counted per account. After
  ``login_max_failed_attempts`` in a row the account is locked for
  ``login_lockout_minutes``.
* A correct password resets the count. A lock that has run out clears
  itself the next time someone tries to sign in.
* While an account is locked the password is not checked at all, so
  guessing cannot continue during the lock.
* Everything is recorded in the audit trail without the password or
  the email address.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.services.audit_service import create_audit_log


def now() -> datetime:
    return datetime.now(timezone.utc)


def is_locked(user: User, at: datetime | None = None) -> bool:
    at = at or now()

    return user.locked_until is not None and user.locked_until > at


def minutes_left(user: User, at: datetime | None = None) -> int:
    """Whole minutes until the lock ends, never less than one."""

    at = at or now()

    if user.locked_until is None:
        return 0

    seconds = (user.locked_until - at).total_seconds()

    return max(1, int((seconds + 59) // 60))


def clear_expired_lock(user: User, at: datetime | None = None) -> None:
    at = at or now()

    if user.locked_until is not None and user.locked_until <= at:
        user.locked_until = None
        user.failed_login_count = 0


def record_failure(
    db: Session,
    user: User,
    *,
    action: str = "auth.login_failed",
) -> bool:
    """Count a wrong password. Returns True when this one locked the
    account. The caller commits."""

    user.failed_login_count = (user.failed_login_count or 0) + 1

    create_audit_log(
        db,
        business_id=user.business_id,
        user_id=user.id,
        action=action,
        entity_type="user",
        entity_id=user.id,
        details={"failed_attempts": user.failed_login_count},
    )

    if user.failed_login_count < settings.login_max_failed_attempts:
        return False

    user.locked_until = now() + timedelta(
        minutes=settings.login_lockout_minutes
    )

    create_audit_log(
        db,
        business_id=user.business_id,
        user_id=user.id,
        action="auth.account_locked",
        entity_type="user",
        entity_id=user.id,
        details={
            "failed_attempts": user.failed_login_count,
            "locked_minutes": settings.login_lockout_minutes,
        },
    )

    return True


def record_success(db: Session, user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now()

    create_audit_log(
        db,
        business_id=user.business_id,
        user_id=user.id,
        action="auth.login_succeeded",
        entity_type="user",
        entity_id=user.id,
    )
