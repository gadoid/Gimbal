"""Auth-related Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

# 账号字段约束的唯一权威(register 与 admin-create 共用;此前两处
# 逐字节复制,收紧密码策略时极易只改一处)。
UsernameField = Field(pattern=r"^[A-Za-z0-9_]+$", min_length=3, max_length=32)
PasswordField = Field(min_length=8, max_length=128)
DisplayNameField = Field(default="", max_length=128)


class RegisterIn(BaseModel):
    """Payload for POST /auth/register."""

    username: str = UsernameField
    password: str = PasswordField
    display_name: str = DisplayNameField

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("password must contain at least one letter and one digit")
        return v


class LoginIn(BaseModel):
    """Payload for POST /auth/login."""

    username: str
    password: str


class RefreshIn(BaseModel):
    """Payload for POST /auth/refresh."""

    refresh_token: str


class UserPublic(BaseModel):
    """Public-facing user view. ``created_at`` is serialized to ISO 8601 string."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    @field_serializer("created_at")
    def _iso(self, v: datetime | None) -> str | None:
        """Serialize as ISO 8601 string for the JSON wire format."""
        return v.isoformat() if v is not None else None


class TokenOut(BaseModel):
    """Auth response shape — access + refresh + bearer marker + user."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class MeOut(BaseModel):
    """Response shape for GET /auth/me."""

    user: UserPublic