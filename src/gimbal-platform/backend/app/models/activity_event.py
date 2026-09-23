"""ActivityEvent model — 场景域事件日志(2026-09-23 批次 F3)。

与 ``audit_logs``/``notifications`` 同构的「写路径同步落一条」日志表:
无订阅者、无分发器(方案 §3.2 否决 pub/sub)。三表职责互斥 ——
audit 只记特权写;notifications 是面向接收方的**有状态**提醒(已读流转);
本表是「资源发生过什么」的**无状态**历史,时间线唯一数据源(§3.5)。

写入范围只覆盖 scenario 域(execution/adaptation 状态位已足够,不迁移);
best-effort:独立小事务,失败只记日志不阻断业务(audit.record 口径)。

``actor_id`` 语义:**时间线归属人**,不恒等于动作发起者 ——
``scenario.handoff_received`` 的 actor 是接收方,发送方进 detail
(2026-09-23 评审拍板,防实现时按直觉装反)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime

BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        # /api/activity 按 (actor, 时间倒序) 取近况
        Index("ix_activity_events_actor_created", "actor_id", "created_at"),
        # 反查「该资源发生过什么」(F4 黄标/审计辅助)
        Index("ix_activity_events_resource", "resource_type", "resource_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    # 时间线归属人;SET NULL = 人注销后事件留痕(与 AuditLog.actor 同款)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # scenario.edit / scenario.rename / scenario.save_as /
    # scenario.handoff_received(取值域在服务层常量,DB 不设 CHECK)
    kind: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JsonVar, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
