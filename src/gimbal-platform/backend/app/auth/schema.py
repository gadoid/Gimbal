"""auth/schema.py —— AuthSession Pydantic 模型(运行时认证对象)。

物理迁移自 gimbal/schema/auth.py,与 gimbal 侧字段/方法签名完全一致。
注意区别:
 -本类为 Pydantic 模型,platform 进程内存对象
 - app.models.auth_session.AuthSession 是 SQLAlchemy ORM 模型(数据库行)
 二者字段对齐(字段名 / 类型 / 默认值),但 ORM 那份额外有 id / owner_id。

M2(B-5/W20):凭证六字段(url/username/password/expires_in/token_type/
refresh_token)不再本类平铺 —— 持有生成物 ``UserCredential``
(app/schemas/_m2.py,M2 §9.2「M2 只定义凭证;运行态与方法留在各自
运行时类」)。本类保留运行态(token/expires_at)与全部行为方法;
平铺 kwargs 构造与属性读写经兼容层委托到 credential,历史构造点与
消费面无感。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas._m2 import UserCredential


# 平铺凭证键(兼容层的折叠/委托范围;模块级常量 —— pydantic 会把
# 下划线类属性私有化,类内不可直接迭代)
_CRED_FIELDS = ("url", "username", "password",
                "expires_in", "token_type", "refresh_token")


def _aware_utc(dt: datetime) -> datetime:
    """对带 tz 的 datetime 原样返回;对 naive datetime 补 UTC 后返回。

    背景:Pydantic v2 反序列化 ISO datetime 字符串时默认得到 naive datetime。
    AuthSession.expires_at 一旦写入就是 UTC,round-trip 后必须仍是同一个时间点,
    否则 ``aware now() > naive expires_at`` 会抛 TypeError。
    """
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AuthSession(BaseModel):
    """认证会话(读写一体)。"""

    model_config = ConfigDict(extra="forbid")

    # ── 凭证(M2 生成物;值的唯一权威)──────────────────────────
    credential: UserCredential = Field(default_factory=UserCredential)

    # ── 运行态(认证后填充;不进 M2)────────────────────────────
    token: str | None = Field(default=None, description="访问令牌,认证后填充")
    expires_at: datetime | None = Field(default=None, description="过期时间,认证后自动计算")

    # ── 平铺凭证键兼容层(构造/读写委托;不另立状态)──────────────
    @model_validator(mode="before")
    @classmethod
    def _fold_flat_credential(cls, data: Any) -> Any:
        """平铺凭证 kwargs → credential(历史构造形态;显式 credential
        子键胜出,平铺键只补缺)。"""
        if not isinstance(data, dict):
            return data
        flat = {k: data[k] for k in _CRED_FIELDS if k in data}
        if not flat:
            return data
        explicit = data.get("credential")
        merged = {**flat, **(explicit if isinstance(explicit, dict) else {})}
        for k in flat:
            data.pop(k)
        data["credential"] = merged
        return data

    @property
    def url(self) -> str:
        return self.credential.url

    @url.setter
    def url(self, value: str) -> None:
        self.credential.url = value

    @property
    def username(self) -> str:
        return self.credential.username

    @username.setter
    def username(self, value: str) -> None:
        self.credential.username = value

    @property
    def password(self) -> str:
        return self.credential.password

    @password.setter
    def password(self, value: str) -> None:
        self.credential.password = value

    @property
    def expires_in(self) -> int | None:
        return self.credential.expires_in

    @expires_in.setter
    def expires_in(self, value: int | None) -> None:
        self.credential.expires_in = value

    @property
    def token_type(self) -> str:
        return self.credential.token_type

    @token_type.setter
    def token_type(self, value: str) -> None:
        self.credential.token_type = value

    @property
    def refresh_token(self) -> str:
        return self.credential.refresh_token

    @refresh_token.setter
    def refresh_token(self, value: str) -> None:
        self.credential.refresh_token = value

    # ── 计算属性 ──

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

    # ── 方法 ──

    def apply_token(self, token: str | None, expires_in: int | None = None) -> "AuthSession":
        """写入 token 并按 expires_in 语义更新 lifetime。

        语义:
          - token 为 None / 空字符串: 早返回, 不写入 token, 不更新 expires_at
            (用于 Authenticator 调用 apply_token(token=None) 表示"未拿到 token" 的场景,
             不应该被当成控制字符校验失败导致 500)
          - expires_in > 0:   显式设置新 lifetime(expires_in=N, expires_at = now + N)
          - expires_in == 0:  显式清空 lifetime(expires_at = None)
          - expires_in is None: 保持 self.expires_in 不变,但 re-anchor
                                expires_at = now + self.expires_in(如 self.expires_in > 0)
        """
        # 早返回: token 为 None 或空字符串 → 当作"未拿到 token",不报错也不写入
        if not token:
            return self
        # ASCII 控制字符安全检查 (CWE-93): 拒绝 token 中的 0x00-0x1F / 0x7F (排除 SP / HT)
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
            if self.credential.expires_in and self.credential.expires_in > 0:
                self.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=self.credential.expires_in
                )
            return self
        if expires_in > 0:
            self.credential.expires_in = expires_in
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        else:
            self.credential.expires_in = 0
            self.expires_at = None
        return self

    def clear_token(self) -> "AuthSession":
        """清空 token、expires_at 和 expires_in 三个字段。"""
        self.token = None
        self.expires_at = None
        self.credential.expires_in = None
        return self

    def is_same_credential(self, other: "AuthSession") -> bool:
        """按 url/username/password 三个字段逐项相等比较。"""
        return (
            self.credential.url == other.credential.url
            and self.credential.username == other.credential.username
            and self.credential.password == other.credential.password
        )

    def clear_password(self) -> "AuthSession":
        """把 password 字段置空以缩短敏感凭据在内存中的驻留时间。"""
        self.credential.password = ""
        return self

    @classmethod
    def from_dict(cls, data: dict) -> "AuthSession":
        """用 cls(**data) 语法从字段字典直接构造。"""
        return cls(**data)


__all__ = ["AuthSession"]
