"""Forgot password and email verification (the emailed-link flows)."""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.security import hash_password
from app.services import account_tokens as tokens
from app.services import message_delivery
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/auth", tags=["Account security"])

# The same words whether or not the address belongs to an account, so the
# form cannot be used to find out who has one.
SAME_ANSWER = (
    "If an account uses that email address, we have sent a link to reset "
    "the password. It works for a short time."
)
BAD_LINK = "This link is not valid any more. Ask for a new one."


class ForgotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class VerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)


def _by_email(db: Session, email: str) -> User | None:
    return (
        db.query(User)
        .filter(func.lower(User.email) == email.strip().lower())
        .first()
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    data: ForgotIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = _by_email(db, data.email)

    if (
        user is not None
        and user.is_active
        and tokens.sent_in_last_hour(db, user.id, tokens.RESET)
        < tokens.MAX_RESET_EMAILS_PER_HOUR
    ):
        raw = tokens.issue(db, user, tokens.RESET)
        db.commit()
        # Sent after the reply, so how long this took does not show
        # whether the account exists.
        tokens.send_later(background_tasks, tokens.reset_email(user, raw))

    return {"message": SAME_ANSWER}


@router.post("/reset-password")
def reset_password(
    data: ResetIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    token = tokens.find_valid(db, data.token, tokens.RESET)
    user = db.get(User, token.user_id) if token is not None else None

    if token is None or user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BAD_LINK)

    now = datetime.now(timezone.utc)

    user.password_hash = hash_password(data.new_password)
    # Every earlier session ends, and a lock from too many wrong tries lifts.
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    # Receiving the email proves the address is theirs.
    if user.email_verified_at is None:
        user.email_verified_at = now
    token.used_at = now

    create_audit_log(
        db,
        business_id=user.business_id,
        user_id=user.id,
        action="auth.password_reset_by_email",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()

    tokens.send_later(background_tasks, tokens.changed_notice(user))

    return {"message": "Your password has been changed. You can sign in now."}


@router.post("/verify-email")
def verify_email(data: VerifyIn, db: Session = Depends(get_db)):
    token = tokens.find_valid(db, data.token, tokens.VERIFY)
    user = db.get(User, token.user_id) if token is not None else None

    if (
        token is None
        or user is None
        or not user.is_active
        or token.email != user.email
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BAD_LINK)

    now = datetime.now(timezone.utc)
    if user.email_verified_at is None:
        user.email_verified_at = now
    token.used_at = now

    create_audit_log(
        db,
        business_id=user.business_id,
        user_id=user.id,
        action="auth.email_verified",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()

    return {"message": "Your email address is confirmed."}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    data: ForgotIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Send a verification link without requiring an authenticated session.

    The same response is returned for unknown, inactive, and already-verified
    addresses to avoid account enumeration.
    """
    user = _by_email(db, data.email)
    if (
        user is not None
        and user.is_active
        and user.email_verified_at is None
        and message_delivery.email_configured()
        and tokens.sent_in_last_hour(db, user.id, tokens.VERIFY)
        < tokens.MAX_VERIFY_EMAILS_PER_HOUR
    ):
        raw = tokens.issue(db, user, tokens.VERIFY)
        db.commit()
        tokens.send_later(background_tasks, tokens.verify_email(user, raw))

    return {
        "message": (
            "If the account exists and still needs verification, "
            "a confirmation link has been sent."
        )
    }
