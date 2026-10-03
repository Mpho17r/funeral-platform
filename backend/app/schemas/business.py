from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# CREATE BUSINESS
# ============================================================

class BusinessCreate(BaseModel):
    name: str
    slug: str

    # BRANDING
    logo_url: str | None = None

    primary_color: str = "#000000"

    secondary_color: str = "#64748b"

    watermark_url: str | None = None

    watermark_opacity: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
    )

    theme_preference: str = "system"

    # CONTACT
    phone: str | None = None

    email: str | None = None

    address: str | None = None


# ============================================================
# BUSINESS RESPONSE
# ============================================================

class BusinessResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    name: str

    slug: str

    # ========================================================
    # BRANDING
    # ========================================================

    logo_url: str | None

    primary_color: str

    secondary_color: str

    watermark_url: str | None

    watermark_opacity: float

    theme_preference: str

    # ========================================================
    # CONTACT
    # ========================================================

    phone: str | None

    email: str | None

    address: str | None

    # ========================================================
    # MEMBERSHIP COVER POLICY
    # ========================================================

    grace_period_days: int

    cover_during_arrears: bool

    lapse_after_days: int

    reinstatement_policy: str

        # ========================================================
    # STAFF ATTENDANCE POLICY
    # ========================================================

    tea_break_minutes: int = 15
    lunch_break_minutes: int = 60
    idle_timeout_minutes: int = 15

    break_expiry_behavior: str = "notify_and_keep_active"
    break_warning_enabled: bool = True
    break_warning_minutes: int = 2
    break_expiry_notification_enabled: bool = True

    # ========================================================
    # STATUS
    # ========================================================

    is_active: bool
