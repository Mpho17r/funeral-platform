from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "staff"

    # Defaults to the creator's branch. Moving a user later uses the
    # transfer endpoint.
    branch_id: UUID | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    branch_id: UUID | None = None
    locked_until: datetime | None = None
    last_login_at: datetime | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
