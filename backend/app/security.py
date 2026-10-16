from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


# Checked when the email is unknown, so an unknown email takes as long to
# answer as a wrong password and cannot be told apart by timing.
_DUMMY_HASH = password_hash.hash("not-a-real-password")


def burn_password_check(password: str) -> None:
    password_hash.verify(password, _DUMMY_HASH)


def create_access_token(
    user_id: str,
    business_id: str,
    role: str,
    auth_type: str = "business_user",
) -> str:

    issued_at = datetime.now(timezone.utc)

    expires_at = issued_at + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        "sub": user_id,
        "auth_type": auth_type,
        "business_id": business_id,
        "role": role,
        "iat": int(issued_at.timestamp()),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )