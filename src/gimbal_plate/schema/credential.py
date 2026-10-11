"""M2 凭证定义（M2 方案 v2.4 §3 M2 / §9.2；步骤 1 定义形态）。

AuthSession 拆分：M2 只定义**凭证**（定义部分）；运行态（token /
expires_at）与九个方法留在执行器（``gimbal/auth/session.py``）与平台
（``auth/schema.py``）各自的运行时类——平台物化只下发凭证字段，
从不下发 token。``refresh_token`` 两侧 AuthSession 都有（auth.py:66）。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserCredential(BaseModel):
    """用户凭证（Config.users 的值类型）。"""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(default="", description="认证接口地址")
    username: str = Field(default="", description="用户名")
    password: str = Field(default="", description="密码")
    expires_in: int | None = Field(
        default=None, description="Token 有效期（秒），认证前配置")
    token_type: str = Field(default="Bearer", description="Token 类型")
    refresh_token: str = Field(
        default="",
        description="刷新令牌（独立于 access token），由认证/刷新接口返回",
    )
