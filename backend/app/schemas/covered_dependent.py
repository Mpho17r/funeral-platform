from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


COVERED_DEPENDENT_STATUSES = (
    "active",
    "removed",
    "deceased",
)

COVERED_DEPENDENT_RELATIONSHIPS = (
    "spouse",
    "partner",
    "child",
    "parent",
    "sibling",
    "grandparent",
    "grandchild",
    "other",
)


class CoveredDependentCreate(BaseModel):
    membership_id: UUID

    first_name: str = Field(
        min_length=1,
        max_length=100,
    )

    last_name: str = Field(
        min_length=1,
        max_length=100,
    )

    relationship: str = Field(
        min_length=1,
        max_length=50,
    )

    id_number: str | None = Field(
        default=None,
        max_length=50,
    )

    date_of_birth: date | None = None

    phone: str | None = Field(
        default=None,
        max_length=30,
    )

    status: str = "active"

    cover_start_date: date

    cover_end_date: date | None = None

    @field_validator("first_name", "last_name", "relationship")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in COVERED_DEPENDENT_STATUSES:
            raise ValueError(
                "Covered dependent status must be one of: "
                "active, removed, deceased"
            )

        return value

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, value: str) -> str:
        value = value.lower().strip()

        if value not in COVERED_DEPENDENT_RELATIONSHIPS:
            raise ValueError(
                "Relationship must be one of: "
                "spouse, partner, child, parent, sibling, "
                "grandparent, grandchild, other"
            )

        return value


class CoveredDependentUpdate(BaseModel):
    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    relationship: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    id_number: str | None = Field(
        default=None,
        max_length=50,
    )

    date_of_birth: date | None = None

    phone: str | None = Field(
        default=None,
        max_length=30,
    )

    status: str | None = None

    cover_start_date: date | None = None

    cover_end_date: date | None = None

    @field_validator("first_name", "last_name", "relationship")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty")

        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in COVERED_DEPENDENT_STATUSES:
            raise ValueError(
                "Covered dependent status must be one of: "
                "active, removed, deceased"
            )

        return value

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.lower().strip()

        if value not in COVERED_DEPENDENT_RELATIONSHIPS:
            raise ValueError(
                "Relationship must be one of: "
                "spouse, partner, child, parent, sibling, "
                "grandparent, grandchild, other"
            )

        return value


class CoveredDependentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    membership_id: UUID

    first_name: str
    last_name: str
    relationship: str

    id_number: str | None
    date_of_birth: date | None
    phone: str | None

    status: str

    cover_start_date: date
    cover_end_date: date | None

    created_at: datetime
    updated_at: datetime