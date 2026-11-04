"""WebhookDelivery — 回调投递行(webhook 设计 v3 P2 §5.2,outbox 模式)。

投递行与终态写入**同一事务**落库(任一失败两者都不落 —— 不会出现
「有终态无回调」或反过来)。写行时把 payload 序列化一次存进 ``body``,
URL 冻结为「别名 base_url + (callback_path_override 或别名 callback_
path)」;签名密钥不落行,投递时从别名现取(Fernet 解密)。

``id`` 即对外 deliveryId / ``X-Gimbal-Delivery`` 头 —— 重试不变,
是调用方的去重键。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        # 投递循环的领取面:pending 且到期的行(FOR UPDATE SKIP LOCKED)
        Index("ix_webhook_delivery_due", "status", "next_retry_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    # 回调目标 = 访问令牌(webhook v4 §6):URL 与 token_name 建行时快照;
    # 令牌删除后投递台账保留(token_id SET NULL),签名密钥不快照、投递
    # 时按令牌现取 —— 令牌行没了即该行失败(token_deleted)。
    token_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("access_tokens.id", ondelete="SET NULL"),
        nullable=True)
    token_name: Mapped[str] = mapped_column(String(64), default="")
    # execution.finished | integration.run_finished | integration.paused
    event_type: Mapped[str] = mapped_column(String(64))
    # 关联执行/集成实例(排查用;目标行删除后投递台账保留,置 NULL)
    execution_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("executions.id", ondelete="SET NULL"),
        nullable=True)
    instance_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("integration_tasks.id", ondelete="SET NULL"),
        nullable=True)
    # 冻结的回调 URL(写行时解析;别名后续改 base_url 不影响已写入的行)
    url: Mapped[str] = mapped_column(String(768))
    # 冻结的请求体字节(json 序列化一次;重试对同一份字节签名)
    body: Mapped[str] = mapped_column(Text)
    # pending / delivered / failed
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
