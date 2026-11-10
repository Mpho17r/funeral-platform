"""Password reset and email verification: tokens and the emails that carry them.

Safety rules this file keeps:
  * a token is random and only its SHA-256 hash is stored;
  * a token works once and expires; asking for a new one cancels older ones;
  * a verification token is bound to the address it was sent to;
  * the link puts the token after "#", so it is never sent to a server,
    written to an access log, or passed on in a Referer header;
  * how often one account can be emailed is capped, so the form cannot be
    used to flood someone's inbox.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.auth_token import AuthToken
from app.models.user import User
from app.services import message_delivery

log = logging.getLogger("linda.account_tokens")

RESET = "password_reset"
VERIFY = "email_verify"
INVITE = "team_invite"

MAX_RESET_EMAILS_PER_HOUR = 3
MAX_VERIFY_EMAILS_PER_HOUR = 5
MAX_INVITE_EMAILS_PER_HOUR = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def sent_in_last_hour(db: Session, user_id, purpose: str) -> int:
    return (
        db.query(func.count(AuthToken.id))
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.created_at > _now() - timedelta(hours=1),
        )
        .scalar()
        or 0
    )


def issue(db: Session, user: User, purpose: str) -> str:
    """Create a token for this person and return the raw value to email.

    Earlier unused tokens for the same purpose stop working. The caller
    commits.
    """
    now = _now()
    db.query(AuthToken).filter(
        AuthToken.user_id == user.id,
        AuthToken.purpose == purpose,
        AuthToken.used_at.is_(None),
    ).update({AuthToken.used_at: now}, synchronize_session=False)

    raw = secrets.token_urlsafe(32)
    lifetime = (
        timedelta(minutes=settings.reset_token_minutes)
        if purpose == RESET
        else timedelta(hours=settings.verify_token_hours)
    )
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_hash(raw),
            email=user.email if purpose in (VERIFY, INVITE) else None,
            expires_at=now + lifetime,
        )
    )
    return raw


def find_valid(db: Session, raw: str, purpose: str) -> AuthToken | None:
    token = (
        db.query(AuthToken)
        .filter(AuthToken.token_hash == _hash(raw), AuthToken.purpose == purpose)
        .first()
    )
    if token is None or token.used_at is not None or token.expires_at <= _now():
        return None
    return token


def link(page: str, raw: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/{page}#token={raw}"


def deliver(to: str, subject: str, body: str, *, link_text: str | None = None) -> None:
    """Send an email, never raising: this runs after the reply has gone.

    With email not set up, a developer's server prints the link so the flow
    can still be tried. A live system never prints it.
    """
    if not message_delivery.email_configured():
        if settings.is_production:
            log.error("Email is not set up (SMTP_HOST / SMTP_FROM); %r was not sent", subject)
        else:
            log.warning("Email not set up. %s for %s -> %s", subject, to, link_text or "(no link)")
        return
    try:
        message_delivery.send_email(to, subject, body)
    except message_delivery.DeliveryError as exc:
        log.error("Could not send %r: %s", subject, exc)


def reset_email(user: User, raw: str) -> tuple[str, str, str, str]:
    url = link("reset-password", raw)
    body = (
        f"Hello {user.full_name},\n\n"
        "We received a request to reset your LINDA password. Use this link "
        f"within {settings.reset_token_minutes} minutes:\n\n{url}\n\n"
        "If you did not ask for this, ignore this email. Your password has "
        "not changed.\n\nLINDA\n"
    )
    return user.email, "Reset your LINDA password", body, url


def verify_email(user: User, raw: str) -> tuple[str, str, str, str]:
    url = link("verify-email", raw)
    body = (
        f"Hello {user.full_name},\n\n"
        "Please confirm this email address for your LINDA account:\n\n"
        f"{url}\n\nThe link works for {settings.verify_token_hours // 24} days. "
        "If you did not create an account, ignore this email.\n\nLINDA\n"
    )
    return user.email, "Confirm your email address", body, url


def invite_email(user: User, raw: str) -> tuple[str, str, str, str]:
    url = link("accept-invitation", raw)
    body = (
        f"Hello {user.full_name},\n\n"
        "You have been invited to join a business on LINDA. "
        "Your account has been created, but you need to choose your own "
        "password before you can sign in.\n\n"
        f"Create your password using this secure link (valid for "
        f"{settings.verify_token_hours // 24} days):\n\n{url}\n\n"
        "If you were not expecting this invitation, you can ignore this email.\n\nLINDA\n"
    )
    return user.email, "You have been invited to LINDA", body, url


def changed_notice(user: User) -> tuple[str, str, str, str]:
    body = (
        f"Hello {user.full_name},\n\n"
        "The password on your LINDA account was just changed. If this was "
        "you, there is nothing to do. If it was not, reset your password "
        "straight away and tell your administrator.\n\nLINDA\n"
    )
    return user.email, "Your LINDA password was changed", body, ""


def send_later(background_tasks, message: tuple[str, str, str, str]) -> None:
    to, subject, body, url = message
    background_tasks.add_task(deliver, to, subject, body, link_text=url)
