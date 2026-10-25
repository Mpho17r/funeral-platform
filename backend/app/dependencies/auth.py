from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.database import get_db
from app.models.user import User


security = HTTPBearer()


def _authenticate(credentials, db):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")
        auth_type = payload.get("auth_type")
        business_id = payload.get("business_id")
        role = payload.get("role")

        if auth_type != "business_user":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication layer",
            )

        if not user_id or not business_id or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        user_uuid = UUID(user_id)
        business_uuid = UUID(business_id)

        user = (
            db.query(User)
            .filter(
                User.id == user_uuid,
                User.business_id == business_uuid,
            )
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        from app.models.business import Business
        from app.services.plan_limits import ensure_active

        ensure_active(db.get(Business, user.business_id))

        # A password change or reset ends every earlier session.
        if user.password_changed_at is not None:
            issued_at = payload.get("iat")

            if (
                not isinstance(issued_at, (int, float))
                or issued_at < int(user.password_changed_at.timestamp())
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Your session has ended. Please sign in again.",
                )

        from app.services.branch_scope import scope_for, set_scope

        set_scope(db, scope_for(db, user))

        return {
            "user_id": user.id,
            "auth_type": auth_type,
            "business_id": user.business_id,
            "role": user.role,
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """The signed-in user. Also limits this request's reads to the
    person's own branch unless they may work across all branches."""
    from app.services.branch_scope import set_scope

    try:
        yield _authenticate(credentials, db)
    finally:
        set_scope(db, None)
