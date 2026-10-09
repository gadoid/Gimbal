"""IntegrationTask — 外部系统集成「功能」的模板/实例两层单表。

《GIMBAL-外部系统集成架构设计》§4(决策 1/3/8):
- **模板行**(``template_id IS NULL``)保存定义:引用哪个用例、执行
  身份、触发周期、结果策略、卡片模板;**实例行**(``template_id``
  指向模板)保存某个执行人的运行状态。公共任务共享的是定义,
  不是某个人的执行。
- **实例不保存定义副本**:模板修改后实例下次执行即生效,避免分叉。
- **不写执行记录**(决策 3):本表即集成的全部状态,行台账/事件/
  案卷都不落 —— 需要排查时执行器引擎日志可按需开启。
- 评审 E6(2026-10-09):``target_type`` 一等列,scenario 先行,
  suite(Suite 层重构已收官)随后接入,免二次迁移;P1 执行链只
  消费 scenario。
- 评审 E7:模板删除走软删(``removed_at``),被订阅的公共模板硬删
  会让所有人卡片同时失效;卡片据 removed_at/可见性走「已移除」态。
- 平台模式的实例 ``holder_id`` = 平台系统用户(users.is_system,
  迁移 0015 种子);个人模式(P2)= 每个订阅者一个实例。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class IntegrationTask(Base):
    __tablename__ = "integration_tasks"
    __table_args__ = (
        # 实例定位:一个模板下每个持有人至多一个实例。普通唯一索引即可
        # —— 模板行 template_id/holder_id 均为 NULL,PG/SQLite 的唯一
        # 索引都不把 NULL 视为相等,模板行互不冲突。
        Index("uq_integration_instance", "template_id", "holder_id",
              unique=True),
        Index("ix_integration_due", "state", "enabled", "next_run_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # ── 模板层(template_id IS NULL)────────────────────────────
    name: Mapped[str] = mapped_column(String(128))
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    # P1 只有 platform;personal 随 P2(订阅生成实例/缺凭证态)开放
    identity_mode: Mapped[str] = mapped_column(String(16), default="platform")
    # 评审 E6:scenario 先行,suite 随后(target_type + 两个可空引用)
    target_type: Mapped[str] = mapped_column(String(16), default="scenario")
    scenario_id: Mapped[str] = mapped_column(String(128), nullable=True)
    suite_id: Mapped[int] = mapped_column(Integer, nullable=True)
    scheme_id: Mapped[str] = mapped_column(String(128), nullable=True)
    # 主要对接系统名(限流分组;P1 可空 = 不分组)
    target_system: Mapped[str] = mapped_column(String(64), default="")
    trigger_cron: Mapped[str] = mapped_column(String(64), default="*/5 * * * *")
    result_policy: Mapped[str] = mapped_column(String(16), default="latest")
    # 卡片模板(P1 固定 status;后续 kv/counter/list)
    card_template: Mapped[str] = mapped_column(String(16), default="status")
    # E1(评审):token 等敏感值禁止进 outputs/state_vars —— 由 runner
    # 侧脱敏保证;此处仅存映射定义本身
    output_mapping: Mapped[dict] = mapped_column(JsonVar, default=dict)
    state_mapping: Mapped[dict] = mapped_column(JsonVar, default=dict)
    updated_by: Mapped[int] = mapped_column(Integer, nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    # ── 实例层(template_id NOT NULL)───────────────────────────
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("integration_tasks.id"), nullable=True)
    holder_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # idle / running / paused
    state: Mapped[str] = mapped_column(String(16), default="idle")
    # auth_failed / missing_credential / manual
    paused_reason: Mapped[str] = mapped_column(String(32), default="")
    running_since: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    # passed / failed / timeout
    last_status: Mapped[str] = mapped_column(String(16), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_outputs: Mapped[dict] = mapped_column(JsonVar, default=dict)
    state_vars: Mapped[dict] = mapped_column(JsonVar, default=dict)
    last_manual_run_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    fail_streak: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
