"""认证会话数据类 - 读写一体设计。

认证前：填写 url/username/password/expires_in
认证后：token/expires_at 自动填充
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field


def _aware_utc(dt: datetime) -> datetime:
    """对带 tz 的 datetime 原样返回；对 naive datetime 补 UTC 后返回，使比较时不会出现 TypeError。

    背景：Pydantic v2 反序列化 ISO datetime 字符串时默认得到 naive datetime。
    AuthSession.expires_at 一旦写入就是 UTC，round-trip 后必须仍是同一个时间点，
    否则 `aware now() > naive expires_at` 会抛 TypeError。

    业务约束：本框架内所有写入 expires_at 的路径都使用 timezone.utc，
    所以"naive → UTC"是无损解释。
    """
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AuthSession(BaseModel):
    """认证会话（读写一体）。

    认证前：填写 url/username/password/expires_in
    认证后：token/expires_at 自动填充

    注意：tag（唯一标识）通过 users 字典的 key 决定，不再存储在对象中。

    属性：
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
    # 修复 #10：refresh_token 与 access_token 分开存储
    # OAuth2 标准中两者不同；用 access_token 当 refresh_token 发会被多数服务商拒
    refresh_token: str | None = Field(
        default=None,
        description="刷新令牌（独立于 access_token），由认证/刷新接口返回",
    )

    # ── 计算属性 ────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        """是否已认证（有有效 token 且未过期）。"""
        if not self.token:
            return False
        if self.expires_at and datetime.now(timezone.utc) > _aware_utc(self.expires_at):
            return False
        return True

    @property
    def should_refresh(self) -> bool:
        """是否应该刷新（提前 5 分钟或 token 即将过期）。"""
        if not self.expires_at:
            return False
        threshold = datetime.now(timezone.utc) + timedelta(minutes=5)
        return threshold > _aware_utc(self.expires_at)

    @property
    def auth_header(self) -> str | None:
        """生成 Authorization 头值。

        修复 #66：拒绝 token_type 和 token 中的 ASCII 控制字符，
        防止 HTTP header 注入（CWE-93）。
        """
        if not self.token:
            return None
        # 拒绝 ASCII 控制字符 (0x00-0x1F, 0x7F) —— 这些在 HTTP header 中非法
        # 排除：SP (0x20) 和 HT (0x09) 是合法 header 字符
        def _has_control(s: str) -> bool:
            return any(ord(c) < 0x20 and c != "\t" or ord(c) == 0x7F for c in s)
        if _has_control(self.token_type) or _has_control(self.token):
            # 错误信息不直接打印原值（避免日志注入）
            # 用 repr 形式安全显示
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

    def apply_token(self, token: str, expires_in: int | None = None) -> AuthSession:
        """写入 token 并按 expires_in 语义更新 lifetime：>0 重置 expires_in/expires_at；==0 清空两者；None 保持 expires_in 但重新锚定 expires_at。

        语义（修复 #4）:
          - expires_in > 0:   显式设置新 lifetime（expires_in=N, expires_at = now + N）
          - expires_in == 0:  显式清空 lifetime（expires_at = None）
          - expires_in is None: 保持 self.expires_in 不变, 但 re-anchor
                                expires_at = now + self.expires_in（如 self.expires_in > 0）

        设计取舍:
          - None 表示"调用方不指定",不重置已配置的 lifetime
          - re-anchor 让"重置 token 值但不重新认证"也能刷新过期时刻
            （refresh 路径常用）
          - 0 是显式"清空"信号,比让 expires_at 保持不变更明确
        """
        # 修复 #R1：早失败——写入 token 时验证不含控制字符
        # 避免延迟到 auth_header 访问时才发现，且防止认证流程后段被恶意
        # 服务端响应注入
        if any(ord(c) < 0x20 and c != "\t" or ord(c) == 0x7F for c in token):
            raise ValueError(
                f"apply_token: token contains control character "
                f"(token_len={len(token)})"
            )
        self.token = token
        if expires_in is None:
            # 保持 self.expires_in，重新锚定 expires_at 到 now+self.expires_in
            # （这是修复 Case 3 行为：原代码用 truthy 检查,0/falsy 会被吞掉）
            if self.expires_in and self.expires_in > 0:
                self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)
            # else: 保持 expires_at 不变（None 或 pre-existing）
            return self
        if expires_in > 0:
            self.expires_in = expires_in
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        else:
            # expires_in == 0: 显式清空 lifetime
            self.expires_in = 0
            self.expires_at = None
        return self

    def clear_token(self) -> AuthSession:
        """清空 token、expires_at 和 expires_in 三个字段，使 session 回到未认证且无 lifetime 配置的初始状态。"""
        self.token = None
        self.expires_at = None
        self.expires_in = None  # 修复 #4：也清空 expires_in,与新构造的 session 状态一致
        return self

    def is_same_credential(self, other: AuthSession) -> bool:
        """按 url/username/password 三个字段逐项相等比较，判断两个 AuthSession 是否指向同一份凭证。"""
        return (
            self.url == other.url
            and self.username == other.username
            and self.password == other.password
        )

    def clear_password(self) -> AuthSession:
        """把 password 字段置空以缩短敏感凭据在内存中的驻留时间，url/username/token 保持不变。

        调用场景:
          - 认证成功后立即调用，密码已不再需要
          - 进程即将退出前清理敏感数据

        注意:
          - PreToken 模式下 password 兼作 token，清空后 token 仍可用
            （apply_token 已将 password 复制到 token）
          - URL/username 不清空（认证配置需要保留）
          - 失败时 is_authenticated/should_refresh 的依赖可能受影响
        """
        self.password = ""
        return self

    @classmethod
    def from_dict(cls, data: dict) -> AuthSession:
        """用 cls(**data) 语法从字段字典直接构造并返回 AuthSession 实例。"""
        return cls(**data)
