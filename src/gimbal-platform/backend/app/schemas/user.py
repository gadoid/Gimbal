"""User-management Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

from typing import Literal

from typing import Literal

from pydantic import BaseModel, Field

# 字段约束与 RegisterIn 同源(auth.py 是唯一权威)。
from .auth import DisplayNameField, PasswordField, UsernameField
from .page import PageOut


Role = Literal["member", "operator", "admin"]


class UserCreateIn(BaseModel):
    """Payload for POST /users(admin 开号,M2.5 收紧:任何登录用户都能
    自行开号的 spec-1 遗留已闭合 —— 用户管理页是唯一开号入口)。"""

    username: str = UsernameField
    password: str = PasswordField
    display_name: str = DisplayNameField
    role: Role = "member"


class UserDeleteIn(BaseModel):
    """DELETE /users/{id} 处置入参(P2-2 三选一,默认转公共库)。

    * ``publicize``:私有场景转公共库(署名保留原作者字符串快照);
    * ``transfer``:场景转让给 ``transfer_to`` 指定成员(数据集/方案
      随场景走;个人别名一并转共享);
    * ``purge``:场景一并删除(前端明示二次确认)。
    """

    disposal: Literal["publicize", "transfer", "purge"] = "publicize"
    transfer_to: int | None = None


class UserPatchIn(BaseModel):
    """Payload for PATCH /users/{user_id}.  All fields optional.

    ``role``(M2.5)取代 is_admin 成为人事权威字段;末位 admin 保护
    按角色判定(不可降级最后一个 admin)。"""

    display_name: str | None = Field(default=None, max_length=128)
    role: Role | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


# UserOut 曾是 UserPublic 的逐字段拷贝("独立演化"从未发生,只留下
# 双份漂移风险)— 收敛为同一 schema 的别名。
from .auth import UserPublic  # noqa: E402

UserOut = UserPublic

class UserListOut(PageOut[UserOut]):
    """M4 Page 信封(§6.3):用户列表分页(接口收紧已随 M2.5 落地)。"""
