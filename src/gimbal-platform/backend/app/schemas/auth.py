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
    model_config = ConfigDict(populate_by_name=True)

    """Payload for POST /auth/change-password(webhook v4 §3.6)。

    旧密码必须核验;新密码复用注册强度(PasswordField 同源)。两个
    可选动作均默认勾选:

    * ``invalidateTokens`` — 本人全部个人令牌落库失效(原因 password),
      平台令牌不受影响;
    * ``logoutOthers`` — ``users.token_version`` + 1 并返回新 JWT(access
      与 refresh 都带 tv,refresh 比对不等即 401)。
    """

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = PasswordField
    invalidate_tokens: bool = Field(default=True, alias="invalidateTokens")
    logout_others: bool = Field(default=True, alias="logoutOthers")


class RefreshIn(BaseModel):
    """Payload for POST /auth/refresh."""

    refresh_token: str


class UserPublic(BaseModel):
    """Public-facing user view. ``created_at`` is serialized to ISO 8601 string."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    # 三级角色(authz W1 2026-11-07 更名:user | admin | super_admin,
    # 原 member→admin、原 admin→super_admin,权限边界不变;更早的
    # 2026-09-29 更名是原 member→user、operator→member)
    role: Literal["user", "admin", "super_admin"] = "user"
    is_active: bool
    # D32:系统用户标记(用户管理行防御:停用/删除入口对其隐藏)
    is_system: bool = False
    created_at: datetime
    # 通知 unread-count 的 roleVersion 比对源(§1.3 第六轮)
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _snapshot_orm(cls, data):
        """ORM 行先取 ``__dict__`` 快照再校验:commit 后已过期的属性
        (如 ``updated_at``)不在快照里 → 走字段默认,不触发异步会话外的
        懒加载(MissingGreenlet)。原随 is_admin 派生一并承担,派生位停发
        后单独保留。"""
        if isinstance(data, dict) or not hasattr(data, "__dict__"):
            return data
        from types import SimpleNamespace

        return SimpleNamespace(**{
            k: v for k, v in vars(data).items() if not k.startswith("_sa_")})

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
    # authz W2:按表 A 求出的能力列表(_ownership.capabilities_of)。
    # 前端 can() 的唯一依据(W8 迁移后取代 role/isAdmin 判断)。
    capabilities: list[str] = Field(default_factory=list)
    # authz W6:管理员重置密码后的强制改密位(前端路由守卫的跳转
    # 依据,比等 403 更早;改密成功即复位)
    must_change_password: bool = False
    # M2a S1.1:我所在的普通项目(前端项目切换器数据源;公共项目
    # 不落成员行,不在此列)。id/name/kind(normal|public)/role(admin|member)
    projects: list[dict] = Field(default_factory=list)