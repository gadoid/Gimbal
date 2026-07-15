"""User-management Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreateIn(BaseModel):
    """Payload for POST /users (admin-initiated user creation).

    Spec-1 simplification: ``is_admin`` is accepted but always coerced to False
    by the router regardless of caller intent (no admin-only enforcement).
    """

    username: str = Field(pattern=r"^[A-Za-z0-9_]+$", min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=128)
    is_admin: bool = False


class UserPatchIn(BaseModel):
    """Payload for PATCH /users/{user_id}.  All fields optional."""

    display_name: str | None = Field(default=None, max_length=128)
    is_admin: bool | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(BaseModel):
    """Public-facing user view (mirrors :class:`app.schemas.auth.UserPublic`).

    Defined independently in spec-1 so that the users router can evolve
    independently of the auth router (e.g. add ``updated_at`` later without
    touching the auth DTO surface).
    """

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