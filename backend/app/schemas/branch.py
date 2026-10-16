import re

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")


def _clean_code(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip().upper()

    if not CODE_PATTERN.match(cleaned):
        raise ValueError(
            "Code must be 2 to 10 letters or numbers, "
            "with no spaces"
        )

    return cleaned


class BranchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None

    @field_validator("code")
    @classmethod
    def normalise_code(cls, value):
        return _clean_code(value)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        stripped = value.strip()

        if not stripped:
            raise ValueError("Name cannot be blank")

        return stripped


class BranchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = None
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None

    @field_validator("code")
    @classmethod
    def normalise_code(cls, value):
        return _clean_code(value)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        if value is None:
            return None

        stripped = value.strip()

        if not stripped:
            raise ValueError("Name cannot be blank")

        return stripped


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    code: str
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_main: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BranchSummaryResponse(BaseModel):
    branch_id: UUID
    active_staff: int
    active_resources: int
    members: int
    live_cases: int
    total_cases: int


class BranchTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
