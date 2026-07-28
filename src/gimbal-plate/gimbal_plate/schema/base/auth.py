"""gimbal_plate.base.auth —— 认证会话数据类。

迁移自 ``gimbal.schema.auth.AuthSession``,完整保留:
    - 控制字符安全检查(防止 HTTP header 注入,CWE-93)
    - ``apply_token`` / ``clear_token`` / ``clear_password`` / ``is_same_credential`` 方法
    - ``is_authenticated`` / ``should_refresh`` / ``auth_header`` / ``remaining_seconds`` 属性
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field


def _aware_utc(dt: datetime) -> datetime:
    """对带 tz 的 datetime 原样返回;对 naive datetime 补 UTC 后返回。

    背景:Pydantic v2 反序列化 ISO datetime 字符串时默认得到 naive datetime。
    AuthSession.expires_at 一旦写入就是 UTC,round-trip 后必须仍是同一个时间点,
    否则 ``aware now() > naive expires_at`` 会抛 TypeError。

    业务约束:本框架内所有写入 expires_at 的路径都使用 timezone.utc,
    所以 "naive → UTC" 是无损解释。
    """
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AuthSession(BaseModel):
    """认证会话(读写一体)。

    认证前:填写 url/username/password/expires_in
    认证后:token/expires_at 自动填充

    注意:tag(唯一标识)通过 users 字典的 key 决定,不再存储在对象中。
    """

    # ── 认证地址和凭证 ──────────────────────────────────────
    url: str = Field(default="", description="认证接口地址")
    username: str = Field(default="", description="用户名")
    password: str = Field(default="", description="密码")

    # ── Token 配置 ─────────────────────────────────────────
    expires_in: int | None = Field(
        default=None,
        description="Token 有效期(秒),认证前配置。如 7200 表示 2 小时",
    )
    token: str | None = Field(default=None, description="访问令牌,认证后填充")
    token_type: str = Field(default="Bearer", description="Token 类型")
    expires_at: datetime | None = Field(default=None, description="过期时间,认证后自动计算")
    refresh_token: str | None = Field(
        default=None,
        description="刷新令牌(独立于 access_token),由认证/刷新接口返回",
    )

    # ── 计算属性 ────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """是否已认证(有有效 token 且未过期)。"""
        if not self.token:
            return False
        if self.expires_at and datetime.now(timezone.utc) > _aware_utc(self.expires_at):
            return False
        return True

    @property
    def should_refresh(self) -> bool:
        """是否应该刷新(提前 5 分钟或 token 即将过期)。"""
        if not self.expires_at:
            return False
        threshold = datetime.now(timezone.utc) + timedelta(minutes=5)
        return threshold > _aware_utc(self.expires_at)

    @property
    def auth_header(self) -> str | None:
        """生成 Authorization 头值。

        安全约束:拒绝 token_type 和 token 中的 ASCII 控制字符,
        防止 HTTP header 注入(CWE-93)。
        """
        if not self.token:
            return None

        def _has_control(s: str) -> bool:
            return any(
                ord(c) < 0x20 and c != "\t" or ord(c) == 0x7F
                for c in s
            )

        if _has_control(self.token_type) or _has_control(self.token):
            raise ValueError(
                f"auth_header field contains control character (refusing to build). "
                f"token_type_len={len(self.token_type)}, token_len={len(self.token)}"
            )
        return f"{self.token_type} {self.token}"

    @property
    def remaining_seconds(self) -> int | None:
        """距离过期的剩余秒数。"""
        if not self.expires_at:
            return None
        delta = _aware_utc(self.expires_at) - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))

    # ── 方法 ────────────────────────────────────────────────

    def apply_token(self, token: str, expires_in: int | None = None) -> "AuthSession":
        """写入 token 并按 expires_in 语义更新 lifetime。

        语义:
          - expires_in > 0:   显式设置新 lifetime(expires_in=N, expires_at = now + N)
          - expires_in == 0:  显式清空 lifetime(expires_at = None)
          - expires_in is None: 保持 self.expires_in 不变,但 re-anchor
                                expires_at = now + self.expires_in(如 self.expires_in > 0)
        """
        if any(
            ord(c) < 0x20 and c != "\t" or ord(c) == 0x7F
            for c in token
        ):
            raise ValueError(
                f"apply_token: token contains control character "
                f"(token_len={len(token)})"
            )
        self.token = token
        if expires_in is None:
            if self.expires_in and self.expires_in > 0:
                self.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=self.expires_in
                )
            return self
        if expires_in > 0:
            self.expires_in = expires_in
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        else:
            self.expires_in = 0
            self.expires_at = None
        return self

    def clear_token(self) -> "AuthSession":
        """清空 token、expires_at 和 expires_in 三个字段。"""
        self.token = None
        self.expires_at = None
        self.expires_in = None
        return self

    def is_same_credential(self, other: "AuthSession") -> bool:
        """按 url/username/password 三个字段逐项相等比较。"""
        return (
            self.url == other.url
            and self.username == other.username
            and self.password == other.password
        )

    def clear_password(self) -> "AuthSession":
        """把 password 字段置空以缩短敏感凭据在内存中的驻留时间。"""
        self.password = ""
        return self

    @classmethod
    def from_dict(cls, data: dict) -> "AuthSession":
        """用 cls(**data) 语法从字段字典直接构造。"""
        return cls(**data)
