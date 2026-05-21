"""认证会话数据类 - 读写一体设计。

认证前：填写 tag/url/username/password/expires_in
认证后：token/expires_at 自动填充
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pydantic import BaseModel, Field


class AuthSession(BaseModel):
    """认证会话（读写一体）。

    认证前：填写 tag/url/username/password/expires_in
    认证后：token/expires_at 自动填充

    属性：
        tag: 唯一标识，如 'admin', 'service_a'
        url: 认证接口地址
        username: 用户名
        password: 密码
        expires_in: Token 有效期（秒），认证前配置
        token: 访问令牌，认证后填充
        token_type: Token 类型，默认 Bearer
        expires_at: 过期时间，认证后自动计算

    计算属性：
        is_authenticated: 是否已认证（有有效 token）
        should_refresh: 是否应该刷新（提前 5 分钟）
        auth_header: Authorization 头值
        remaining_seconds: 距离过期的剩余秒数

    方法：
        apply_token(token, expires_in): 填充 token，自动计算 expires_at
        clear_token(): 清除 token 信息
    """
    # ── 标识 ────────────────────────────────────────────────
    tag: str = Field(..., description="唯一标识，如 'admin', 'service_a'")

    # ── 认证地址和凭证 ──────────────────────────────────────
    url: str = Field(default="", description="认证接口地址")
    username: str = Field(default="", description="用户名")
    password: str = Field(default="", description="密码")

    # ── Token 配置 ─────────────────────────────────────────
    expires_in: int | None = Field(
        default=None,
        description="Token 有效期（秒），认证前配置。如 7200 表示 2 小时"
    )
    token: str | None = Field(default=None, description="访问令牌，认证后填充")
    token_type: str = Field(default="Bearer", description="Token 类型")
    expires_at: datetime | None = Field(default=None, description="过期时间，认证后自动计算")

    # ── 计算属性 ────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """是否已认证（有有效 token 且未过期）。"""
        if not self.token:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    @property
    def should_refresh(self) -> bool:
        """是否应该刷新（提前 5 分钟或 token 即将过期）。"""
        if not self.expires_at:
            return False
        threshold = datetime.utcnow() + timedelta(minutes=5)
        return threshold > self.expires_at

    @property
    def auth_header(self) -> str | None:
        """生成 Authorization 头值。"""
        if not self.token:
            return None
        return f"{self.token_type} {self.token}"

    @property
    def remaining_seconds(self) -> int | None:
        """距离过期的剩余秒数。"""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))

    # ── 方法 ────────────────────────────────────────────────

    def apply_token(self, token: str, expires_in: int | None = None) -> AuthSession:
        """填充 token，自动计算 expires_at。

        Args:
            token: 访问令牌
            expires_in: 可选，重新设置有效期（秒）

        Returns:
            self，方便链式调用
        """
        self.token = token
        if expires_in is not None:
            self.expires_in = expires_in
        if self.expires_in:
            self.expires_at = datetime.utcnow() + timedelta(seconds=self.expires_in)
        return self

    def clear_token(self) -> AuthSession:
        """清除 token 信息。"""
        self.token = None
        self.expires_at = None
        return self

    def is_same_credential(self, other: AuthSession) -> bool:
        """判断是否具有相同的凭证配置（tag/url/username/password）。"""
        return (
            self.tag == other.tag
            and self.url == other.url
            and self.username == other.username
            and self.password == other.password
        )

    @classmethod
    def from_dict(cls, data: dict, tag: str | None = None) -> AuthSession:
        """从字典创建 AuthSession。

        Args:
            data: 配置字典
            tag: 可选，指定 tag（优先使用 data 中的 tag）

        Returns:
            AuthSession 实例
        """
        # 合并 tag
        if tag:
            data = {**data, "tag": tag}
        return cls(**data)
