from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseContactCreate(BaseModel):
    contact_type: str = Field(..., min_length=1, max_length=50)

    first_name: str = Field(..., min_length=1, max_length=100)

    last_name: str = Field(..., min_length=1, max_length=100)

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    email: str | None = Field(
        default=None,
        max_length=255,
    )

    relationship: str | None = Field(
        default=None,
        max_length=100,
    )

    organization: str | None = Field(
        default=None,
        max_length=255,
    )

    address: str | None = None

    notes: str | None = None


class CaseContactUpdate(BaseModel):
    contact_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    email: str | None = Field(
        default=None,
        max_length=255,
    )

    relationship: str | None = Field(
        default=None,
        max_length=100,
    )

    organization: str | None = Field(
        default=None,
        max_length=255,
    )

    address: str | None = None

    notes: str | None = None


class CaseContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID

    contact_type: str

    first_name: str
    last_name: str

    phone: str | None
    email: str | None

    relationship: str | None
    organization: str | None

    address: str | None
    notes: str | None

    created_at: datetime
    updated_at: datetime
