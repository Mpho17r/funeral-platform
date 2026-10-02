from datetime import date
from uuid import UUID

from pydantic import BaseModel


class CalendarEventResponse(BaseModel):
    id: str
    event_type: str
    title: str
    date: date
    case_id: UUID
    case_number: str
    deceased_full_name: str
    description: str | None = None
    venue: str | None = None
    assigned_to: UUID | None = None
    assigned_to_name: str | None = None
    status: str | None = None
