from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BusinessCreate(BaseModel):
    name: str
    slug: str
    logo_url: str | None = None
    primary_color: str = "#000000"
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class BusinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    logo_url: str | None
    primary_color: str
    phone: str | None
    email: str | None
    address: str | None
    is_active: bool