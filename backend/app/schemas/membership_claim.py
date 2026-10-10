from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# BENEFICIARIES
# ============================================================

class BeneficiaryCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    relationship: str = Field(..., min_length=1, max_length=50)
    id_number: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    share_percent: Decimal = Field(..., gt=0, le=100, decimal_places=2)
    notes: str | None = None


class BeneficiaryUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    relationship: str | None = Field(default=None, min_length=1, max_length=50)
    id_number: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    share_percent: Decimal | None = Field(
        default=None, gt=0, le=100, decimal_places=2
    )
    notes: str | None = None


class BeneficiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    membership_id: UUID
    first_name: str
    last_name: str
    relationship: str
    id_number: str | None
    phone: str | None
    email: str | None
    share_percent: Decimal
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BeneficiarySummaryResponse(BaseModel):
    membership_id: UUID
    active_beneficiaries: int
    allocated_percent: Decimal
    remaining_percent: Decimal
    is_fully_allocated: bool


# ============================================================
# CLAIMS
# ============================================================

class ClaimCreate(BaseModel):
    case_id: UUID
    claimed_amount: Decimal = Field(..., gt=0, decimal_places=2)
    notes: str | None = None


class ClaimUpdate(BaseModel):
    claimed_amount: Decimal | None = Field(
        default=None, gt=0, decimal_places=2
    )
    notes: str | None = None


class ClaimApprove(BaseModel):
    approved_amount: Decimal = Field(..., ge=0, decimal_places=2)
    # Required when approving despite failed coverage or above the
    # plan's monetary limits. Needs the claims.override permission.
    override_reason: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("override_reason")
    @classmethod
    def blank_override_is_none(cls, value):
        if value is not None and not value.strip():
            return None
        return value


class ClaimReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class ClaimPay(BaseModel):
    payment_reference: str = Field(..., min_length=1, max_length=100)


class ClaimCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    claim_number: str
    membership_id: UUID
    case_id: UUID
    covered_dependent_id: UUID | None
    status: str
    claimed_amount: Decimal
    approved_amount: Decimal | None
    submission_coverage: dict | None
    decision_coverage: dict | None
    override_used: bool
    decision_reason: str | None
    decided_by: UUID | None
    decided_at: datetime | None
    paid_at: datetime | None
    paid_by: UUID | None
    payment_reference: str | None
    payout_allocations: list | None
    notes: str | None
    submitted_by: UUID | None
    created_at: datetime
    updated_at: datetime
