"""§14.2 场景资产包恢复:幂等台账(v2.10 M2 最小闭环,AC-45/46)。

「目标项目 × 导出包标识 × 源场景标识」是幂等键(§14.2:数据库唯一
约束防止并发重复创建);``request_digest`` 按规范化输入计算 —— 同键
同摘要是**同一请求的重放**,返回已提交的目标映射;同键不同摘要返回
409 供处置。行同时是恢复报告的持久化载体(区分已恢复绑定 / 显式解绑
待修复 / 未导入方案,§14.2 导入报告)。

恢复入口调用只 flush 的写入函数,整场景(目标场景 + 方案 + 引用 +
默认标记 + 修复状态 + 审计)在一个数据库事务提交(AC-46);本表
随该事务落行 —— 台账缺失即恢复未发生,无半成品。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey, Index, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class ScenarioAssetImport(Base):
    __tablename__ = "scenario_asset_imports"
    __table_args__ = (
        # §14.2 幂等键(并发权威:唯一约束,同键并发一方胜出)
        UniqueConstraint("project_id", "package_id", "source_scenario_id",
                         name="uq_scenario_import_key"),
        Index("ix_scenario_imports_project", "project_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False)
    # 导出包标识(bundle.packageId;服务端生成的 UUID 或调用方给定)
    package_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_scenario_id: Mapped[str] = mapped_column(
        String(128), nullable=False)
    # 规范化恢复请求摘要(sha256 hex;§14.2 同键同摘要 = 重放)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # 恢复产出的目标映射(重放返回口径)
    restored_scenario_id: Mapped[str] = mapped_column(
        String(128), nullable=False)
    restored_scheme_ids: Mapped[list] = mapped_column(JsonVar, default=list)
    default_scheme_id: Mapped[str | None] = mapped_column(String(128))
    # §14.2 导入报告(计数区分,不把待修复计为可执行)
    report: Mapped[dict] = mapped_column(JsonVar, default=dict)
    # 包内待修复依赖的源标识(审计;不保存秘密)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
