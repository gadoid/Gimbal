"""InboundCredential / InboundGrant — 入站身份两类令牌(webhook 设计 v3 §4.1)。

外部系统(含 Agent)以自己的身份调用 Gimbal:执行已有场景、注册定时
任务、执行完成后接收回调。身份挂在**外部系统别名**(``service_aliases``,
``kind=external``)上 —— 同一别名承载出站(执行时打它)与入站(它打
我们)两个方向(D2)。

两类令牌(库中只存 sha256,明文只在生成时返回一次):

* **入站凭证 ``gic_…``**(``Authorization: Bearer gic_…``):证明调用方
  是某个已登记且 ``inbound_enabled`` 的别名。别名属主或 admin 在别名
  页面生成;长期有效,可吊销、可轮换(轮换 = 吊销旧 + 生成新,无原子
  双令牌窗口)。
* **grant ``ggt_…``**(``X-Gimbal-Grant: ggt_…``):证明某用户授权该
  别名**代其执行**(个人模式,凭证取该用户池子)。用户本人在别名页面
  签发;默认 90 天(配置 GRANT_DEFAULT_TTL_DAYS),上限 365 天。

无 grant 的入站请求 = 平台模式:owner 记 ``__platform__`` 系统用户,
只放行 query_safe 只读接口(D6)。用户停用/删除时其名下 grant 全部
撤销/级联删除,不随资源转让 —— grant 只认签发人,认别名。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, ForeignKey, Index, String, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class InboundCredential(Base):
    """入站凭证(一个别名可多张:轮换期新旧并存、按用途多张)。"""

    __tablename__ = "inbound_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    # 随别名整删(ON DELETE CASCADE):别名没了,凭证无意义
    alias_name: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("service_aliases.alias_name",
                   onupdate="CASCADE", ondelete="CASCADE"))
    # sha256 hex(明文 gic_… 只在生成响应里出现一次)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    # 吊销即失效(软删,保留行供审计);轮换 = 吊销旧 + 生成新
    revoked_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)


class InboundGrant(Base):
    """grant:某用户授权某别名代其执行(个人模式凭证/权限的锚)。

    只撤销不硬删(用户删除时随 FK 级联删除);执行/注册入口每次用前
    重新校验(命中 + 未过期 + 未撤销 + 属于该别名),失效即按口径暂停
    (集成任务 ``paused_reason=grant_revoked``)或拒绝。
    """

    __tablename__ = "inbound_grants"
    __table_args__ = (
        # 运行前重校验按别名查活跃 grant(P1-5 消费面)
        Index("ix_inbound_grants_alias", "alias_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    alias_name: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("service_aliases.alias_name",
                   onupdate="CASCADE", ondelete="CASCADE"))
    # 签发人 = 执行 owner(personal 模式凭证池取此人)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
