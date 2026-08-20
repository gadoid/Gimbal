"""User-management Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

from pydantic import BaseModel, Field

# 字段约束与 RegisterIn 同源(auth.py 是唯一权威)。
from .auth import DisplayNameField, PasswordField, UsernameField


class UserCreateIn(BaseModel):
    """Payload for POST /users (admin-initiated user creation).

    Spec-1 simplification: ``is_admin`` is accepted but always coerced to False
    by the router regardless of caller intent (no admin-only enforcement).
    """

    username: str = UsernameField
    password: str = PasswordField
    display_name: str = DisplayNameField
    is_admin: bool = False


class UserPatchIn(BaseModel):
    """Payload for PATCH /users/{user_id}.  All fields optional."""

    display_name: str | None = Field(default=None, max_length=128)
    is_admin: bool | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


# UserOut 曾是 UserPublic 的逐字段拷贝("独立演化"从未发生,只留下
# 双份漂移风险)— 收敛为同一 schema 的别名。
from .auth import UserPublic  # noqa: E402

UserOut = UserPublic