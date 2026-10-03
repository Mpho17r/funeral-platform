from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class StaffAttendanceSessionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    business_id: UUID
    user_id: UUID
    status: str
    checked_in_at: datetime
    checked_out_at: datetime | None
    created_at: datetime
    updated_at: datetime


BREAK_TYPES = (
    "tea",
    "lunch",
)


class StaffBreakSessionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    attendance_session_id: UUID
    business_id: UUID
    user_id: UUID
    break_type: str
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StaffBreakStartRequest(BaseModel):
    break_type: str

    @field_validator("break_type")
    @classmethod
    def validate_break_type(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in BREAK_TYPES:
            raise ValueError(
                "Break type must be one of: tea, lunch"
            )

        return value


class StaffAttendanceMeResponse(BaseModel):
    attendance: StaffAttendanceSessionResponse | None
    current_break: StaffBreakSessionResponse | None
    presence: str
    last_seen_at: datetime | None
