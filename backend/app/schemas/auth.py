from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    business_phone: str | None = Field(default=None, max_length=30)
    business_email: EmailStr | None = None
    business_address: str | None = None
    # "funeral" = the full funeral platform; "general" = any other
    # business that wants jobs, tasks, money and staff managed.
    business_type: Literal["funeral", "general"] = "funeral"

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
