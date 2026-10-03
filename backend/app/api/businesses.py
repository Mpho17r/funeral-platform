from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_main_admin, require_permission
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessResponse
from app.services.audit_service import create_audit_log
from app.services.business_storage import (
    get_business_branding_file,
    save_business_branding_file,
)


router = APIRouter(
    prefix="/businesses",
    tags=["Businesses"],
)


REINSTATEMENT_POLICIES = {
    "automatic",
    "manual",
    "not_allowed",
}


class BusinessBrandingUpdate(BaseModel):
    logo_url: str | None = None
    primary_color: str
    secondary_color: str
    watermark_url: str | None = None
    watermark_opacity: float = Field(
        ge=0.0,
        le=1.0,
    )
    theme_preference: str


class BusinessCoverPolicyUpdate(BaseModel):
    grace_period_days: int = Field(
        ge=0,
    )
    cover_during_arrears: bool
    lapse_after_days: int = Field(
        ge=1,
    )
    reinstatement_policy: str

    @model_validator(mode="after")
    def validate_policy(self):
        if self.lapse_after_days < self.grace_period_days:
            raise ValueError(
                "Lapse period must be greater than or equal to the grace period."
            )

        if self.reinstatement_policy not in REINSTATEMENT_POLICIES:
            raise ValueError(
                "Reinstatement policy must be one of: "
                "automatic, manual, not_allowed."
            )

        return self


def get_business_or_404(
    business_id: UUID,
    db: Session,
) -> Business:
    business = db.get(
        Business,
        business_id,
    )

    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    return business


def verify_business_access(
    business_id: UUID,
    current_user: dict,
):
    if current_user["business_id"] != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this business",
        )


@router.post(
    "",
    response_model=BusinessResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_business(
    business_data: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):
    business = Business(
        name=business_data.name,
        slug=business_data.slug,
        logo_url=business_data.logo_url,
        primary_color=business_data.primary_color,
        secondary_color=business_data.secondary_color,
        watermark_url=business_data.watermark_url,
        watermark_opacity=business_data.watermark_opacity,
        theme_preference=business_data.theme_preference,
        phone=business_data.phone,
        email=business_data.email,
        address=business_data.address,
    )

    db.add(business)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        constraint_name = getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )

        if constraint_name == "ix_businesses_slug":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A business with this slug already exists.",
            ) from exc

        raise

    db.refresh(business)

    return business


@router.get(
    "/{business_id}",
    response_model=BusinessResponse,
)
def get_business(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    verify_business_access(
        business_id,
        current_user,
    )

    return get_business_or_404(
        business_id,
        db,
    )


@router.patch(
    "/{business_id}/branding",
    response_model=BusinessResponse,
)
def update_business_branding(
    business_id: UUID,
    branding_data: BusinessBrandingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branding.manage")),
):
    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    business.logo_url = branding_data.logo_url
    business.primary_color = branding_data.primary_color
    business.secondary_color = branding_data.secondary_color
    business.watermark_url = branding_data.watermark_url
    business.watermark_opacity = branding_data.watermark_opacity
    business.theme_preference = branding_data.theme_preference

    db.commit()
    db.refresh(business)

    return business


@router.patch(
    "/{business_id}/cover-policy",
    response_model=BusinessResponse,
)
def update_business_cover_policy(
    business_id: UUID,
    policy_data: BusinessCoverPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("settings.manage")),
):
    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    previous_policy = {
        "grace_period_days": business.grace_period_days,
        "cover_during_arrears": business.cover_during_arrears,
        "lapse_after_days": business.lapse_after_days,
        "reinstatement_policy": business.reinstatement_policy,
    }

    business.grace_period_days = (
        policy_data.grace_period_days
    )
    business.cover_during_arrears = (
        policy_data.cover_during_arrears
    )
    business.lapse_after_days = (
        policy_data.lapse_after_days
    )
    business.reinstatement_policy = (
        policy_data.reinstatement_policy
    )

    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="business.cover_policy_updated",
        entity_type="business",
        entity_id=business.id,
        details={
            "previous": previous_policy,
            "new": {
                "grace_period_days": (
                    business.grace_period_days
                ),
                "cover_during_arrears": (
                    business.cover_during_arrears
                ),
                "lapse_after_days": (
                    business.lapse_after_days
                ),
                "reinstatement_policy": (
                    business.reinstatement_policy
                ),
            },
        },
        notes=(
            "Membership cover policy updated by "
            "Main Admin."
        ),
    )

    db.commit()
    db.refresh(business)

    return business


BREAK_EXPIRY_BEHAVIORS = {
    "auto_return",
    "keep_active",
    "notify_and_keep_active",
}


class BusinessAttendancePolicyUpdate(BaseModel):
    tea_break_minutes: int = Field(
        ge=0,
        le=480,
    )
    lunch_break_minutes: int = Field(
        ge=0,
        le=480,
    )
    idle_timeout_minutes: int = Field(
        ge=1,
        le=480,
    )
    break_expiry_behavior: str = "notify_and_keep_active"
    break_warning_enabled: bool = True
    break_warning_minutes: int = Field(
        default=2,
        ge=0,
        le=120,
    )
    break_expiry_notification_enabled: bool = True

    @model_validator(mode="after")
    def validate_break_expiry_behavior(self):
        if self.break_expiry_behavior not in BREAK_EXPIRY_BEHAVIORS:
            raise ValueError(
                "break_expiry_behavior must be one of: "
                "auto_return, keep_active, "
                "notify_and_keep_active"
            )

        if self.break_warning_enabled:
            if (
                self.break_warning_minutes >= self.tea_break_minutes
                and self.tea_break_minutes > 0
            ):
                raise ValueError(
                    "break_warning_minutes must be less than "
                    "tea_break_minutes"
                )

            if (
                self.break_warning_minutes >= self.lunch_break_minutes
                and self.lunch_break_minutes > 0
            ):
                raise ValueError(
                    "break_warning_minutes must be less than "
                    "lunch_break_minutes"
                )

        return self


@router.patch(
    "/{business_id}/attendance-policy",
    response_model=BusinessResponse,
)
def update_business_attendance_policy(
    business_id: UUID,
    policy: BusinessAttendancePolicyUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    require_permission("settings.manage")(
        current_user,
        db,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    if current_user["business_id"] != business.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this business",
        )

    previous_policy = {
        "tea_break_minutes": business.tea_break_minutes,
        "lunch_break_minutes": business.lunch_break_minutes,
        "idle_timeout_minutes": business.idle_timeout_minutes,
        "break_expiry_behavior": business.break_expiry_behavior,
        "break_warning_enabled": business.break_warning_enabled,
        "break_warning_minutes": business.break_warning_minutes,
        "break_expiry_notification_enabled": (
            business.break_expiry_notification_enabled
        ),
    }

    business.tea_break_minutes = policy.tea_break_minutes
    business.lunch_break_minutes = policy.lunch_break_minutes
    business.idle_timeout_minutes = policy.idle_timeout_minutes
    business.break_expiry_behavior = policy.break_expiry_behavior
    business.break_warning_enabled = policy.break_warning_enabled
    business.break_warning_minutes = policy.break_warning_minutes
    business.break_expiry_notification_enabled = (
        policy.break_expiry_notification_enabled
    )

    create_audit_log(
        db,
        business_id=business.id,
        user_id=current_user["user_id"],
        action="business.attendance_policy_updated",
        entity_type="business",
        entity_id=business.id,
        details={
            "previous": previous_policy,
            "new": {
                "tea_break_minutes": business.tea_break_minutes,
                "lunch_break_minutes": business.lunch_break_minutes,
                "idle_timeout_minutes": business.idle_timeout_minutes,
                "break_expiry_behavior": (
                    business.break_expiry_behavior
                ),
                "break_warning_enabled": (
                    business.break_warning_enabled
                ),
                "break_warning_minutes": (
                    business.break_warning_minutes
                ),
                "break_expiry_notification_enabled": (
                    business.break_expiry_notification_enabled
                ),
            },
        },
        notes="Staff attendance policy updated.",
    )

    db.commit()
    db.refresh(business)

    return business


@router.post(
    "/{business_id}/branding/logo",
    response_model=BusinessResponse,
)
async def upload_business_logo(
    business_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branding.manage")),
):
    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    try:
        contents = await file.read()
        logo_url = save_business_branding_file(
            business_id=business_id,
            file=file,
            contents=contents,
            file_type="logo",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    business.logo_url = logo_url

    db.commit()
    db.refresh(business)

    return business


@router.post(
    "/{business_id}/branding/watermark",
    response_model=BusinessResponse,
)
async def upload_business_watermark(
    business_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branding.manage")),
):
    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    try:
        contents = await file.read()
        watermark_url = save_business_branding_file(
            business_id=business_id,
            file=file,
            contents=contents,
            file_type="watermark",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    business.watermark_url = watermark_url

    db.commit()
    db.refresh(business)

    return business


@router.get(
    "/{business_id}/branding/logo",
)
def get_business_logo(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    verify_business_access(
        business_id,
        current_user,
    )

    get_business_or_404(
        business_id,
        db,
    )

    file_path = get_business_branding_file(
        business_id,
        "logo",
    )

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business logo not found",
        )

    return FileResponse(
        file_path,
    )


@router.get(
    "/{business_id}/branding/watermark",
)
def get_business_watermark(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    verify_business_access(
        business_id,
        current_user,
    )

    get_business_or_404(
        business_id,
        db,
    )

    file_path = get_business_branding_file(
        business_id,
        "watermark",
    )

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business watermark not found",
        )

    return FileResponse(
        file_path,
    )
    