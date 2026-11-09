"""AccessToken / AccessTokenScope — 访问令牌(webhook v4 §4.1)。

v4 三段收敛的左侧身份:**单一令牌 ``gtk_``**,绑定一个用户(个人令牌)
(authz C1:平台令牌随平台模式退役,只承载个人令牌)。调用方不在 Gimbal 登记 ——
令牌下管理授权范围(允许使用的服务别名与凭证),调用、注册、每次定时
运行前由平台计算本次用到的别名与凭证并核对子集关系。

* 明文 = ``gtk_`` + ``secrets.token_urlsafe(32)``(43 字符),库里只存
  sha256 与展示片段 hint;回调签名密钥 Fernet 加密,同样只在生成/轮换
  时返回一次(D10);
* 范围按对象外键存(:class:`AccessTokenScope`):对象删除即收回授权,
  同名重建不继承;别名改名级联;
* 生命周期(§3.4):有效 →(自然到期)已到期 →(续期/重新生成)有效;
  (改密/停用/admin 强制)已失效 →(重新生成)有效;吊销 = 终态只读。
  派生拒绝(属主角色 < member / 属主未启用)不落库,认证时按当前值判。

authz M2b Q2 —— **项目令牌**(``kind='project'``):以「项目用户」权限访问
单个项目的外部调用身份;``user_id`` 恒 NULL(个人面 ``user_id == uid`` 的
查询天然排除项目令牌,签发人被删也不会 CASCADE 掉项目令牌),
``project_id`` 指向项目(无 FK,项目删除路由显式吊销);``holder_id`` =
负责人(指定的一位项目管理员;问责 / 通知 / 执行记录属主;失格 = 认证时
派生拒绝);``holder_pending_id`` = 换绑待新负责人确认。执行恒用项目凭证。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class AccessToken(Base):
    __tablename__ = "access_tokens"
    __table_args__ = (
        # 认证按 hash 命中(唯一约束);列表按属主 + 吊销态过滤
        Index("ix_access_tokens_user", "user_id", "revoked_at"),
        # M2b Q2:个人令牌 = 属主非空 ∧ 无项目;项目令牌 = 属主空 ∧ 有项目
        CheckConstraint(
            "(kind = 'personal' AND user_id IS NOT NULL"
            " AND project_id IS NULL)"
            " OR (kind = 'project' AND user_id IS NULL"
            " AND project_id IS NOT NULL)",
            name="ck_token_kind_shape"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    # 令牌属主(随用户整删 CASCADE;C1 后恒本人)—— 项目令牌恒 NULL
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    # M2b Q2 项目令牌:所属项目(无 FK,同 executions.project_id 快照口径)
    project_id: Mapped[int | None] = mapped_column(
        Integer, index=True, nullable=True)
    # 负责人(项目管理员;NULL = 待指派 → 认证派生拒绝)
    holder_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # 换绑待确认的新负责人(确认前令牌按原负责人状态继续可用)
    holder_pending_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="personal")
    name: Mapped[str] = mapped_column(String(64), default="")
    # sha256(完整明文) —— 唯一;明文只在创建/重新生成响应里出现一次
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # 'ab12…9f3c' 展示片段(随机部分前 4 + … + 后 4)
    token_hint: Mapped[str] = mapped_column(String(16), default="")
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    invalidated_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    # password | deactivated | admin(§3.4 invalidate 的三类成因)
    invalidated_reason: Mapped[str | None] = mapped_column(
        String(16), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    # admin 强制失效时的处置说明(D33),随通知下发
    invalidation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    # 回调:URL 在令牌上(§6);主机须在 CALLBACK_HOST_ALLOWLIST 白名单内
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Fernet 密文;投递时解密签 HMAC,取不到即该行失败(必带签名)
    callback_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())

    @property
    def status(self) -> str:
        """派生状态:revoked > invalidated > expired > active(§3.4)。"""
        if self.revoked_at is not None:
            return "revoked"
        if self.invalidated_at is not None:
            return "invalidated"
        from ..core.timeutil import ensure_aware
        if ensure_aware(self.expires_at) <= _utcnow():
            return "expired"
        return "active"

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class AccessTokenScope(Base):
    """令牌授权范围行:一行一个对象(别名或凭证),CHECK 恰好其一。

    凭证 id 在轮换中必须稳定:个人凭证已有原地 PATCH,平台凭证由 D34
    补齐 —— 删除即收回授权(级联消失范围行),同名重建不继承。
    """

    __tablename__ = "access_token_scopes"
    __table_args__ = (
        Index("uq_token_scope_alias", "token_id", "alias_name", unique=True),
        Index("uq_token_scope_auth", "token_id", "auth_id", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    token_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("access_tokens.id", ondelete="CASCADE"), nullable=False)
    alias_name: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("service_aliases.alias_name",
                   onupdate="CASCADE", ondelete="CASCADE"), nullable=True)
    auth_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        nullable=True)
