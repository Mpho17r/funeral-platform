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
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_main_admin
from app.models.business import Business
from app.schemas.business import (
    BusinessCreate,
    BusinessResponse,
)
from app.services.business_storage import (
    get_business_branding_file,
    save_business_branding_file,
)


router = APIRouter(
    prefix="/businesses",
    tags=["Businesses"],
)


# ============================================================
# CONSTANTS
# ============================================================

REINSTATEMENT_POLICIES = {
    "automatic",
    "manual",
    "not_allowed",
}


# ============================================================
# REQUEST SCHEMAS
# ============================================================

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
        if (
            self.lapse_after_days
            < self.grace_period_days
        ):
            raise ValueError(
                "Lapse period must be greater than or equal to the grace period."
            )

        if (
            self.reinstatement_policy
            not in REINSTATEMENT_POLICIES
        ):
            raise ValueError(
                "Reinstatement policy must be one of: "
                "automatic, manual, not_allowed."
            )

        return self


# ============================================================
# HELPERS
# ============================================================

def get_business_or_404(
    business_id: UUID,
    db: Session,
) -> Business:

    business = (
        db.query(Business)
        .filter(Business.id == business_id)
        .first()
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


# ============================================================
# CREATE BUSINESS
# ============================================================

@router.post(
    "",
    response_model=BusinessResponse,
    status_code=201,
)
def create_business(
    business_data: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):

    existing_business = (
        db.query(Business)
        .filter(
            Business.slug == business_data.slug
        )
        .first()
    )

    if existing_business:
        raise HTTPException(
            status_code=409,
            detail="Business slug already exists",
        )

    business = Business(
        **business_data.model_dump(),
    )

    db.add(business)
    db.commit()
    db.refresh(business)

    return business


# ============================================================
# GET BUSINESS
# ============================================================

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


# ============================================================
# GET BUSINESS LOGO
# ============================================================

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
        business_id=business_id,
        file_type="logo",
    )

    if file_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business logo not found",
        )

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".webp": "image/webp",
    }

    return FileResponse(
        path=file_path,
        media_type=media_types[
            file_path.suffix
        ],
    )


# ============================================================
# GET BUSINESS WATERMARK
# ============================================================

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
        business_id=business_id,
        file_type="watermark",
    )

    if file_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business watermark not found",
        )

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".webp": "image/webp",
    }

    return FileResponse(
        path=file_path,
        media_type=media_types[
            file_path.suffix
        ],
    )


# ============================================================
# UPDATE BRANDING SETTINGS
# ============================================================

@router.patch(
    "/{business_id}/branding",
    response_model=BusinessResponse,
)
def update_business_branding(
    business_id: UUID,
    branding_data: BusinessBrandingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):

    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    # BRAND ASSETS
    business.logo_url = branding_data.logo_url
    business.watermark_url = (
        branding_data.watermark_url
    )

    # BRAND COLOURS
    business.primary_color = (
        branding_data.primary_color
    )

    business.secondary_color = (
        branding_data.secondary_color
    )

    # WATERMARK
    business.watermark_opacity = (
        branding_data.watermark_opacity
    )

    # APPLICATION APPEARANCE
    business.theme_preference = (
        branding_data.theme_preference
    )

    db.commit()
    db.refresh(business)

    return business


# ============================================================
# UPDATE MEMBERSHIP COVER POLICY
# ============================================================

@router.patch(
    "/{business_id}/cover-policy",
    response_model=BusinessResponse,
)
def update_business_cover_policy(
    business_id: UUID,
    policy_data: BusinessCoverPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):

    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

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

    db.commit()
    db.refresh(business)

    return business


# ============================================================
# UPLOAD BUSINESS LOGO
# ============================================================

@router.post(
    "/{business_id}/branding/logo",
    response_model=BusinessResponse,
)
def upload_business_logo(
    business_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):

    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPEG, PNG, and WebP "
                "images are allowed."
            ),
        )

    contents = file.file.read()

    max_size = 5 * 1024 * 1024

    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File size must not exceed 5 MB.",
        )

    logo_url = save_business_branding_file(
        business_id=business.id,
        file=file,
        contents=contents,
        file_type="logo",
    )

    business.logo_url = logo_url

    db.commit()
    db.refresh(business)

    return business


# ============================================================
# UPLOAD BUSINESS WATERMARK
# ============================================================

@router.post(
    "/{business_id}/branding/watermark",
    response_model=BusinessResponse,
)
def upload_business_watermark(
    business_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_main_admin),
):

    verify_business_access(
        business_id,
        current_user,
    )

    business = get_business_or_404(
        business_id,
        db,
    )

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPEG, PNG, and WebP "
                "images are allowed."
            ),
        )

    contents = file.file.read()

    max_size = 5 * 1024 * 1024

    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File size must not exceed 5 MB.",
        )

    watermark_url = save_business_branding_file(
        business_id=business.id,
        file=file,
        contents=contents,
        file_type="watermark",
    )

    business.watermark_url = watermark_url

    db.commit()
    db.refresh(business)

    return business