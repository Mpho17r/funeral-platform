from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None


class GroupMemberCreate(BaseModel):
    user_id: UUID
    is_admin: bool = False


class GroupMemberUpdate(BaseModel):
    is_admin: bool


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    user_id: UUID
    is_admin: bool


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
