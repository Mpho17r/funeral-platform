from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _clean_title(value):
    if value is None:
        return None

    value = " ".join(value.split())

    return value or None


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "staff"
    job_title: str | None = Field(default=None, max_length=100)

    @field_validator("job_title", mode="after")
    @classmethod
    def tidy_job_title(cls, value):
        return _clean_title(value)

    # Defaults to the creator's branch. Moving a user later uses the
    # transfer endpoint.
    branch_id: UUID | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None

    # Send null or blank to clear it.
    job_title: str | None = Field(default=None, max_length=100)

    @field_validator("job_title", mode="after")
    @classmethod
    def tidy_job_title(cls, value):
        return _clean_title(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    full_name: str
    email: EmailStr
    role: str
    job_title: str | None = None
    is_active: bool
    branch_id: UUID | None = None
    locked_until: datetime | None = None
    last_login_at: datetime | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
