"""User-management Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


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
    created_at: datetime

    @field_serializer("created_at")
    def _iso(self, v: datetime | None) -> str | None:
        """Serialize as ISO 8601 string for the JSON wire format."""
        return v.isoformat() if v is not None else None