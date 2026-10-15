from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: UUID
    created_at: datetime
    user_id: UUID | None
    user_name: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    notes: str | None
    details: dict | None


class AuditLogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditLogItem]


class AuditLogFilters(BaseModel):
    actions: list[str]
    entity_types: list[str]
