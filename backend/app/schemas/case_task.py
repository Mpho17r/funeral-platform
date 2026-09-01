from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


TASK_STATUSES = (
    "pending",
    "in_progress",
    "completed",
)


class CaseTaskCreate(BaseModel):

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    description: str | None = None

    status: str = Field(
        default="pending",
        max_length=50,
    )

    due_date: date | None = None

    assigned_to: UUID | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Task title cannot be empty")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in TASK_STATUSES:
            raise ValueError(
                "Task status must be one of: "
                "pending, in_progress, completed"
            )

        return value


class CaseTaskUpdate(BaseModel):

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    description: str | None = None

    status: str | None = Field(
        default=None,
        max_length=50,
    )

    due_date: date | None = None

    assigned_to: UUID | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Task title cannot be empty")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.lower().strip()

        if value not in TASK_STATUSES:
            raise ValueError(
                "Task status must be one of: "
                "pending, in_progress, completed"
            )

        return value


class CaseTaskResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    business_id: UUID
    case_id: UUID

    title: str
    description: str | None

    status: str

    due_date: date | None

    assigned_to: UUID | None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
