from pydantic import BaseModel, field_validator


class CaseLifecycleTransition(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        value = value.strip().lower()

        if not value:
            raise ValueError("Case status is required")

        return value


class CaseLifecycleResponse(BaseModel):
    id: str
    status: str
