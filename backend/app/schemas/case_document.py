from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CaseDocumentCreate(BaseModel):
    document_type: str
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: str | None = None
    file_size: int | None = None
    description: str | None = None


class CaseDocumentUpdate(BaseModel):
    document_type: str | None = None
    description: str | None = None


class CaseDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    case_id: UUID
    document_type: str
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: str | None
    file_size: int | None
    description: str | None
    uploaded_by: UUID | None
    created_at: datetime
    updated_at: datetime
