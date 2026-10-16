import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.services.audit_service import create_audit_log
from app.services.branch_service import create_main_branch
from app.services.login_security import (
    clear_expired_lock,
    is_locked,
    minutes_left,
    record_failure,
    record_success,
)
from app.database import get_db
from app.models.user import User
from app.models.business import Business
from app.schemas.auth import (
    ChangePasswordRequest,
    RegisterRequest,
    LoginRequest,
    TokenResponse,
)
from app.security import (
    burn_password_check,
    hash_password,
    verify_password,
    create_access_token,
)
from app.dependencies.auth import get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def generate_slug(name: str) -> str:
    """
    Convert a business name into a URL-safe slug.

    Example:
        "Limpopo Funeral Care" -> "limpopo-funeral-care"
    """

    slug = name.strip().lower()

    slug = re.sub(r"[^a-z0-9]+", "-", slug)

    slug = slug.strip("-")

    if not slug:
        slug = "funeral-business"

    return slug


def get_unique_business_slug(
    db: Session,
    business_name: str,
) -> str:
    """
    Generate a unique business slug.

    If the requested slug already exists, append -2, -3, etc.
    """

    base_slug = generate_slug(business_name)

    slug = base_slug
    counter = 2

    while (
        db.query(Business)
        .filter(Business.slug == slug)
        .first()
        is not None
    ):
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Public business-owner registration.

    Creates:
        1. A new Business
        2. The first User for that business

    The first user automatically becomes main_admin.
    """

    # ---------------------------------------------------------
    # CHECK EMAIL
    # ---------------------------------------------------------

    existing_user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # ---------------------------------------------------------
    # CREATE BUSINESS
    # ---------------------------------------------------------

    business_slug = get_unique_business_slug(
        db,
        data.business_name,
    )

    business = Business(
        name=data.business_name.strip(),
        slug=business_slug,
        phone=data.business_phone,
        email=data.business_email,
        address=data.business_address,
        is_active=True,
    )

    db.add(business)

    # Flush gives us the generated business UUID
    # before the transaction is committed.
    db.flush()

    # Every business starts with its main branch.
    main_branch = create_main_branch(db, business.id)

    # ---------------------------------------------------------
    # CREATE MAIN ADMIN
    # ---------------------------------------------------------

    user = User(
        business_id=business.id,
        full_name=data.full_name.strip(),
        email=data.email,
        password_hash=hash_password(data.password),
        role="main_admin",
        is_active=True,
        branch_id=main_branch.id,
    )

    db.add(user)

    # ---------------------------------------------------------
    # COMMIT BOTH RECORDS
    # ---------------------------------------------------------

    try:
        db.flush()

        create_audit_log(
            db,
            business_id=business.id,
            user_id=user.id,
            action="business.registered",
            entity_type="business",
            entity_id=business.id,
            details={"role": "main_admin"},
            notes="Business account was registered.",
        )

        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create business account. Please check that the business information and email are unique.",
        )

    db.refresh(business)
    db.refresh(user)

    # ---------------------------------------------------------
    # CREATE LOGIN TOKEN
    # ---------------------------------------------------------

    access_token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
        auth_type="business_user",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    if not user:
        burn_password_check(data.password)
        raise invalid

    clear_expired_lock(user)

    if is_locked(user):
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed sign-in attempts. Try again in "
                f"{minutes_left(user)} minute(s), or ask an "
                "administrator to unlock the account."
            ),
            headers={
                "Retry-After": str(minutes_left(user) * 60),
            },
        )

    if not verify_password(
        data.password,
        user.password_hash,
    ):
        locked_now = record_failure(db, user)
        db.commit()

        if locked_now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many failed sign-in attempts. The account is "
                    f"locked for {settings.login_lockout_minutes} "
                    "minutes."
                ),
                headers={
                    "Retry-After": str(
                        settings.login_lockout_minutes * 60
                    ),
                },
            )

        raise invalid

    # Only someone who knows the password learns the account is off.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    record_success(db, user)
    db.commit()

    access_token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
        auth_type="business_user",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/change-password",
    response_model=TokenResponse,
)
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
        )

    if is_locked(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
        )

    if not verify_password(data.current_password, user.password_hash):
        record_failure(
            db,
            user,
            action="auth.password_change_failed",
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your current password is not correct",
        )

    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a password you have not used before",
        )

    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_login_count = 0

    create_audit_log(
        db,
        business_id=user.business_id,
        user_id=user.id,
        action="auth.password_changed",
        entity_type="user",
        entity_id=user.id,
    )

    db.commit()

    # Every earlier session has ended, so hand back a fresh one.
    return {
        "access_token": create_access_token(
            user_id=str(user.id),
            business_id=str(user.business_id),
            role=user.role,
            auth_type="business_user",
        ),
        "token_type": "bearer",
    }


@router.get(
    "/me",
)
def get_me(
    current_user: dict = Depends(get_current_user),
):
    return current_user