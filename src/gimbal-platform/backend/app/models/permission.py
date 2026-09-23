"""权限域新表(PG迁移方案 §2.2 / 权限方案 §3.3/§6,M2 = P1a 只建表不上码)。

* ``UserStar`` — 收藏入库,吞掉 DB 外的 data/stars.json(marks_store
  M6 退役);双 FK CASCADE(收藏随场景/用户机械消失,无业务处置语义 —
  §2.1 FK 映射表:Python 删得到但**不该管**)。
* ``Notification`` — 站内通知(权限方案 §3.3 DDL 照抄);批量 upsert
  的并发命中面 = partial unique (user_id, type, batch_id)。
* ``UserPref`` — 用户偏好 KV:一 ``(user_id, key)`` 一行整值 JSON,写即覆盖
  (无行 id、无时间戳 → 只适合"整份读回整份写回"的小形态偏好)。现有键:
  ``notification_types``(铃铛按 type 静音)、``scenario_filter_groups
  .<bucket>``(场景库筛选分组)、以及 ``routers/user_preferences.py`` 白名单
  里的 ``workbench.layout`` / ``follows.pinned`` / ``timeline.colors``。
  新加键请走那张白名单(带形态校验),不要就地再开一只专用端点。
* ``AuditLog`` — 特权操作留痕(权限方案 §6);actor SET NULL + 姓名
  快照(人注销后仍可读)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime

# SQLite 只对 INTEGER PRIMARY KEY 做 rowid 自增;BIGINT 主键在本地/测试
# 方言不自动生成 → sqlite 侧降为 INTEGER,PG 保持 BIGINT。
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class UserStar(Base):
    __tablename__ = "user_stars"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user", "user_id", "id"),
        # 批量 upsert 的并发命中面(权限方案 §3.3 第六轮):50 条批次几乎
        # 同时终态、同时 upsert 同一条通知,没有唯一约束就退化成
        # SELECT-then-UPDATE 的 RMW,MVCC 下产出重复行。
        Index(
            "uq_notification_batch",
            "user_id",
            "type",
            "batch_id",
            unique=True,
            sqlite_where=text("batch_id IS NOT NULL"),
            postgresql_where=text("batch_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    # 站内深链,如 /executions/133?rows=failed
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 批量执行聚合通知的归并键(§3.2 批量合并)
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 资源维度归位(2026-09-23 批次 F1 分发):悬浮标签按
    # (user_id, type, resource_type) 查未读;payload 存发送方/原名等
    # 结构化数据。全可空 —— 仅 resource_handoff 类通知填写,存量行
    # 不回填(消费查询过滤新类型,无脏读面)。
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JsonVar, nullable=True)
    # 公告的过期时刻;查询侧过滤
    expires_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
    # NULL = 未读
    read_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )


class UserPref(Base):
    __tablename__ = "user_prefs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JsonVar, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_created", "created_at"),
        Index("ix_audit_action", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    # SET NULL + 姓名快照:审计记录 outlive 用户(权限方案 §6)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(128), default="")
    # user.role_change / user.delete / announcement.publish / carry.put /
    # adaptation.op.apply / alias.write …(只记特权写,权限方案 §6 清单)
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[dict] = mapped_column(JsonVar, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
