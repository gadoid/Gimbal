"""Execution model(V3)+ 执行快照/行级明细拆表(M2)。

Execution 是用户触发的场景执行:run_dispatcher 逐行 fan-out 调
gimbal_launcher 子进程(``gimbal run launch``),只更新本表计数器;
每-run 明细自 M2 起入 ``execution_rows``(吸收 JSONL,M6 转正为读写面)。

M2(PG迁移方案 §2.2):
* **拆表**:scenario_snapshot 大 JSON 移入 ``execution_snapshots``
  (1:1,整删语义 CASCADE)—— 列表查询天然不碰快照;rerun 不依赖快照
  (用 config_json 重建配方 + 现查场景),快照唯一消费方是
  ``GET /executions/{id}/scenario-snapshot`` 端点。
* **台账三件套**:owner_id FK SET NULL + owner_name 快照(执行记录是
  审计级数据,必须比用户活得久,列表对孤儿行显示「已注销」)+
  scenario_name 快照(场景删了执行仍可读)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar

# Execution.status values (V3 dispatcher lifecycle)
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELED = "canceled"


class Execution(Base):
    __tablename__ = "executions"
    # (owner_id, id) 复合(0005 升级原单列 owner 索引):列表/汇总/streak
    # 均为 owner 过滤 + id 倒序,前缀吃过滤、后缀吃倒序扫
    __table_args__ = (
        Index("ix_executions_owner_id", "owner_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(128), index=True)
    # 台账快照:场景删除后仍可读(空串 = 场景已删且名字不可考)
    scenario_name: Mapped[str] = mapped_column(String(255), default="")
    # 台账语义:人走执行留(SET NULL + 姓名快照;权限方案 §4.3)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    owner_name: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default=STATUS_QUEUED)
    # queued / running(认证解析通过、行分发开始)/ done / failed / canceled
    # 批次键(执行设计 §1.2/§6):前端队列一次挑 N 条逐条发起时共用一个
    # batch_id,执行记录据此归并展示。平台一次只发一条的语义不变 —— 批
    # 只是归并键,没有批级执行策略(串行/并行/失败即停)。单条发起(运行
    # 对话框/重跑)为 NULL,记录页按无批单条渲染。历史行 NULL = 批功能
    # 上线前,合法状态不迁移。
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    # V3 dispatcher recipe: {runId, scenarioId, dataSetIds,
    # injectedAuths, serviceBindings, stepTo, nRuns, parallel}
    # (D2 起执行环境键已退役;存量历史行仍含旧键,读侧按键驱动渲染)
    config_json: Mapped[dict] = mapped_column(JsonVar, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExecutionSnapshot(Base):
    """执行时场景快照(M2 拆表):dispatch 同拍复制的 payload 容器。

    场景后改不影响历史单"当时跑了什么"的导出;敏感度与
    composer_scenarios.payload 同级(读侧同按 owner 收紧),随执行整删。
    """

    __tablename__ = "execution_snapshots"

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), primary_key=True
    )
    snapshot: Mapped[dict] = mapped_column(JsonVar, default=dict)


class ExecutionRow(Base):
    """行级明细台账(M2 建表;JSONL 吸收,M6 转正为读写面)。

    字段对齐 run_dispatcher._replay_rows 折叠后的真实行形状 —— JSONL
    是事件流(同 (execution_id, seq) 后行覆盖前行),落库写入点 =
    **每行终态即 upsert**(崩溃窗口不丢已终态行);活跃执行读侧仍走
    内存 _row_states,DB 行作持久层跟进(§2.2)。
    """

    __tablename__ = "execution_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 注入族行的条目 id;数据集行缺省 None
    injection_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    rep: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24))
    # 软引用:工件按 CASE_RETENTION_DAYS 周期清扫,行长期保留 ——
    # 前端对已清扫工件显示「已过期清扫」而非死链(M1)。
    case_dir: Mapped[str] = mapped_column(String(255), default="")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 事件流折叠的终态键:同 (execution_id, seq) 后行覆盖前行
    __table_args__ = (
        # 事件流折叠的终态键:同 (execution_id, seq) 后行覆盖前行;
        # upsert 冲突面,M6 写路径依赖
        Index("uq_execution_row_seq", "execution_id", "seq", unique=True),
    )
