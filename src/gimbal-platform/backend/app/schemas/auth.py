"""Auth-related Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

import re
from datetime import datetime

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

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


class ChangePasswordIn(BaseModel):
    """Payload for POST /auth/change-password(P2-1 个人设置)。

    旧密码必须核验;新密码复用注册强度(PasswordField 同源)。
    """

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = PasswordField


class RefreshIn(BaseModel):
    """Payload for POST /auth/refresh."""

    refresh_token: str


class UserPublic(BaseModel):
    """Public-facing user view. ``created_at`` is serialized to ISO 8601 string."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    # M6-3:物理列已删 —— API 字面保留(前端旧缓存 fallback),由 role 派生
    is_admin: bool = False
    # 三级角色(M2.5,/auth/me 经 MeOut 包裹 UserPublic 自动下发)
    role: Literal["member", "operator", "admin"] = "member"
    is_active: bool
    created_at: datetime
    # 通知 unread-count 的 roleVersion 比对源(§1.3 第六轮)
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _derive_is_admin(cls, data):
        if isinstance(data, dict):
            if "is_admin" not in data and "role" in data:
                return {**data, "is_admin": data["role"] == "admin"}
            return data
        role = getattr(data, "role", None)
        if role is not None and getattr(data, "is_admin", None) is None:
            from types import SimpleNamespace

            merged = dict(getattr(data, "__dict__", {}))
            merged["is_admin"] = role == "admin"
            return SimpleNamespace(**merged)
        return data

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