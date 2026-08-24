"""Execution model(V3)。

Execution 是用户触发的场景执行:run_dispatcher 逐行 fan-out 调
gimbal_launcher 子进程(``gimbal run launch``),只更新本表计数器;
每-run 明细的 exec_runs 表(V1 子进程时代)已随存量数据清理退役。

DB 列 ``scenario_id`` 由 Spec-2 时代的 ``case_id`` 迁移改名而来
(Case 层已解散,场景即挂载点;迁移见 core/db.py)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base

# Execution.status values (V3 dispatcher lifecycle)
STATUS_QUEUED = "queued"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELED = "canceled"


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(128), index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default=STATUS_QUEUED)
    # queued / done / failed / canceled
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # V3 dispatcher recipe: {runId, scenarioId, dataSetIds, envId,
    # exec_auth_alias, stepTo, injectCredentials, nRuns, parallel,
    # prefix, mergePolicy}
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
