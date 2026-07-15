"""Auth-related Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterIn(BaseModel):
    """Payload for POST /auth/register."""

    username: str = Field(pattern=r"^[A-Za-z0-9_]+$", min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=128)

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
    created_at: str

    @field_validator("created_at", mode="before")
    @classmethod
    def _coerce_datetime(cls, v: Any) -> Any:
        """Accept either a datetime object (from ORM) or an ISO string (from dict)."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class TokenOut(BaseModel):
    """Auth response shape — access + refresh + bearer marker + user."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class MeOut(BaseModel):
    """Response shape for GET /auth/me."""

    user: UserPublic