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

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime

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
    # 执行形态(重构方案迁移 0014):scenario = 单场景/聚合批次成员;
    # suite_graph = 编排执行(scenario_id 写占位 suite-<id>,不计入
    # 任何成员场景的历史)。与队列层 execution_jobs.kind(cases/graph/
    # debug)同名不同层、值域互斥。存量行 scenario = 既有全部。
    kind: Mapped[str] = mapped_column(String(32), default="scenario")
    # 编排执行的归属 Suite(聚合成员执行同样落 suite_id 供 21 页归并)。
    # 有意不加 FK:执行台账归执行人,历史不随 Suite 删除消失(21 页
    # 对已删 Suite 降级为纯文本名)。
    suite_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    # S5(P0):run.finished 携带的 skipped 计数落库(此前只留在 result.json
    # 工件,台账列缺失)。存量行 0 = 无跳过口径,不回填。
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    # V3 dispatcher recipe: {runId, scenarioId, dataSetIds,
    # injectedAuths, serviceBindings, stepTo, nRuns, parallel}
    # (D2 起执行环境键已退役;存量历史行仍含旧键,读侧按键驱动渲染)
    config_json: Mapped[dict] = mapped_column(JsonVar, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
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
    """单元级明细台账（M2 行级建表；P2-01/C8 单元化）。

    P2-01 前 = 行级（dataset/injection × row_index × rep）；P2-01 起
    ``unit_id``（别名+展开序号，与执行器事件标签一致）、``branch``
    （分支维度）、``attempts``（乘法执行次数）成为主键面，dataset/
    injection/row_index 保留为单元属性。写入点 = 每单元终态即 upsert
    （P2-04 起由执行器事件投影，平台不再自行写行状态）。存量行
    unit_id=''（行级时代写入，读侧兼容）。
    """

    __tablename__ = "execution_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    # P2-01:单元标识(与执行器 unit 标签一致);存量行 '' = 行级时代
    unit_id: Mapped[str] = mapped_column(String(255), default="")
    # P2-01:分支维度(graph 括号/主体;单场景恒 main)
    branch: Mapped[str] = mapped_column(String(16), default="main")
    # P2-01:乘法执行次数(n_runs run 数 + 各 run 内重试数)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
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
        UtcDateTime, nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    # 事件流折叠的终态键:同 (execution_id, seq) 后行覆盖前行
    __table_args__ = (
        # 事件流折叠的终态键:同 (execution_id, seq) 后行覆盖前行;
        # upsert 冲突面,M6 写路径依赖
        Index("uq_execution_row_seq", "execution_id", "seq", unique=True),
    )


class ExecutionEvent(Base):
    """执行事件/日志统一落库面（P2-02/C2）。

    执行器 jsonl 事件流（kind='event'）与结构化日志（kind='log'）共用
    一张表：标签列（category/module/service/protocol/unit/attempt/step）
    建索引支撑日志分析页（P2-07）组合筛选；``payload`` 存原始内容
    （事件 model_dump / 日志行 JSON）。``call.exchange`` 的证据体拆
    ``ExecutionEventEvidence``，主表 message 只留摘要。
    """

    __tablename__ = "execution_events"

    # Integer(非 BigInteger):SQLite 仅对 INTEGER 主键生成 rowid 自增
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(UtcDateTime)
    kind: Mapped[str] = mapped_column(String(8))          # event | log
    level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 调用边界端点标识（P3 收尾信封完整：view_hints.endpoint_id 或
    # service/method/path 推导），0010 迁移补列
    endpoint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt: Mapped[str | None] = mapped_column(String(16), nullable=True)
    step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JsonVar, default=dict)

    __table_args__ = (
        Index("uq_execution_event_seq", "execution_id", "seq", unique=True),
        Index("ix_execution_events_labels", "execution_id", "category", "unit"),
        Index("ix_execution_events_type", "execution_id", "event_type"),
        Index("ix_execution_events_ts", "ts"),
    )


class ExecutionEventEvidence(Base):
    """``call.exchange`` 证据体（P2-02/C2：大字段单独存，主表留摘要与引用）。"""

    __tablename__ = "execution_event_evidence"

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence: Mapped[dict] = mapped_column(JsonVar, default=dict)


class ExecutionJob(Base):
    """C11（P3-01）：执行任务持久化队列。

    POST /api/runs 只入队（Execution 行 + 本表一行）；worker 经
    ``FOR UPDATE SKIP LOCKED`` 认领（PG；SQLite 测试链退化为普通子查询
    ——单连接测试无并发抢占面）。取消是 DB 位（``cancel_requested``），
    worker 在行边界查询；进程内注册表（_in_flight/_cancel_requested/
    信号量）随之退役。

    - attempts：认领次数。认领即 +1；超上限的僵尸回收直接失败收口
      （执行链不可假设幂等——重复下单面）。
    - heartbeat_at：运行中 worker 周期续租；超过租约未续视为孤儿。
    - payload：执行配方（dispatch_run 已完成校验/物化参数的快照，
      worker 不再回查请求上下文）。
    """

    __tablename__ = "execution_jobs"

    # Integer(PK):SQLite 仅对 INTEGER 主键生成 rowid 自增（同 execution_rows）
    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                    autoincrement=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), unique=True)
    # queued / running / done / failed / canceled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # cases / graph / debug（debug = cases + debug 段，强制 server 链）
    kind: Mapped[str] = mapped_column(String(16), default="cases")
    payload: Mapped[dict] = mapped_column(JsonVar, default=dict)
    claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped["datetime | None"] = mapped_column(
        UtcDateTime, nullable=True)
    heartbeat_at: Mapped["datetime | None"] = mapped_column(
        UtcDateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_execution_jobs_status_id", "status", "id"),
    )
