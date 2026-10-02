from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


PRESENCE_STATUSES = (
    "online",
    "away",
    "offline",
    "checked_in",
)


class StaffPresenceUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in PRESENCE_STATUSES:
            raise ValueError(
                "Presence status must be one of: "
                "online, away, offline, checked_in"
            )

        return value


class StaffPresenceResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    business_id: UUID
    user_id: UUID
    user_name: str
    role: str
    status: str
    last_seen_at: datetime | None
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    created_at: datetime
    updated_at: datetime
