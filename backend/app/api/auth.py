import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.business import Business
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
)
from app.security import (
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
    )

    db.add(user)

    # ---------------------------------------------------------
    # COMMIT BOTH RECORDS
    # ---------------------------------------------------------

    try:
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

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    if not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

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


@router.get(
    "/me",
)
def get_me(
    current_user: dict = Depends(get_current_user),
):
    return current_user