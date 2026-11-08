"""Run dispatcher (V3.2 Scenario Composer — ``gimbal run launch`` 执行链).

Per-row fan-out of a Scenario's selected DataSets:

1. :func:`run_prepare.compose_scenario` — 场景 definition + 一行数据集 → 数据驱动的
   gimbal scenario dict(行键注入 ``config.vars``,按基线类型还原)。
2. Plate ``/convert`` — 校验 + 剥平台视图字段(orchestration 绝不外发)。
3. 执行凭证注入 convert 产物(明文不流经 plate)— Task 3 起由
   ``materialize_run_copy`` 纯函数接管(services/users 物化,注入清单 =
   模板扫描 ∪ serviceBindings 绑定)。
4. 落盘 case 文件(``DATA_DIR/runs/cases/<runId>/``)。
5. ``gimbal_launcher.launch`` 子进程执行 ``gimbal run launch <case>``,
   stdout JSON RunResult 驱动行级计数。

Mirrors the in-flight task pattern in ``app/routers/executions.py``
(tracked ``set[asyncio.Task]`` + ``_shutting_down`` flag + ``drain_*``
helper) so the app lifespan can shut down cleanly.

The former Case layer was dissolved — ``RunRequest`` IS the recipe
(dataSetIds / serviceBindings / …, pure values) applied directly
to the scenario by :func:`run_prepare.compose_scenario` (the 配置器/transformer).

Returns ``RunResponse(runId)`` to the caller immediately, and the
``Execution`` row (re-used from Spec-2) holds the aggregate counters
so the existing ``/executions`` UI shows the run without any frontend
changes.
"""
from __future__ import annotations

import asyncio
import copy
import enum
import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy import text as sa_text
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.timeutil import utcnow as _utcnow
from ..models import Execution, ExecutionSnapshot, User
from ..models.execution import (
    STATUS_CANCELED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
    ExecutionJob,
    STATUS_RUNNING,
)
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import RunRequest, RunResponse, ServiceBinding
from . import gimbal_launcher, plate_client
from .auth_ref_scan import scan_auth_aliases
from .endpoint_declarations import declared_paths_of
from .run_injection import (
    as_step_index,
    compose_injection_scenario,
    entry_issues,
    injectable_universe,
)
from .run_materialize import materialize_run_copy
from . import service_aliases
# N1(2026-11-01):装载准备(凭证清单/解析、compose、内置 users、数据集
# 查找、prepare_exec 统一入口)迁往 run_prepare —— 本模块只做派发与
# 执行编排;ResolvedAuth/AuthResolveError 亦由 run_prepare 定义。
from .run_prepare import (
    AuthResolveError,
    compose_scenario,
    find_dataset_by_id,
    prepare_exec,
    resolve_exec_auths,
)


# ─── shutdown 状态 + 队列 worker 桥（C11）───────────────────────
# 进程内注册表（_in_flight/_cancel_requested/_tasks_by_execution/全局
# launch 信号量）已退役：执行任务进 execution_jobs 表，worker 循环
# （services/execution_queue.py）认领驱动；取消走 DB 位。
_shutting_down: bool = False


def is_shutting_down() -> bool:
    return _shutting_down


async def wait_dispatchers_quiescent(timeout_s: float = 10.0) -> bool:
    """等待在途执行任务自然收尾(不取消、不置停机位)—— 测试 teardown
    与 DROP SCHEMA 竞态的解:M6 起行终态落库把后台尾巴略微拉长,
    PG teardown 若不等它,DELETE/INSERT 与 DROP SCHEMA 互锁死锁。

    C11:在途 = 本进程 worker 正在执行的任务（execution_queue._busy）。"""
    from . import execution_queue as _eq
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while _eq._busy and loop.time() < deadline:
        await asyncio.sleep(0.05)
    return not _eq._busy


async def drain_in_flight_dispatches() -> int:
    """优雅停止 worker（当前任务回队）。lifespan 调用。"""
    global _shutting_down
    _shutting_down = True
    from . import execution_queue as _eq
    return await _eq.stop_workers()


def reset_shutdown_state() -> None:
    """Clear the shutdown flag (lifespan startup).

    ``_shutting_down`` 只在 drain 时置位;不复位的话,同一进程复用模块
    (测试直接调 drain 后再来一次 app lifespan)时 dispatch 会静默跳过
    入队,Execution 永远停在 queued。
    """
    global _shutting_down
    _shutting_down = False


# ─── 取消（C11：DB 位）+ 调试会话注册表（C6）────────────────────
# 取消语义保持协作式：request_cancel 写 execution_jobs.cancel_requested
# 位；worker 的 _fanout 取消轮询器在行边界消费（在飞子进程/请求自然
# 跑完——Windows 下 task.cancel 会泄漏 gimbal 子进程，不做）；未跑行
# 记 canceled、不进计数器；canceled 单允许 passed+failed < total_runs。
# 语义判据：job 状态 queued/running 且租约新鲜 = 活单。
async def request_cancel(db, execution_id: int) -> bool:
    """标记取消请求（DB 位）；返回是否存在可取消的活任务。"""
    from . import execution_queue as _eq
    return await _eq.request_cancel(db, execution_id)


def reset_cancel_state() -> None:
    """测试隔离：清空调试会话注册表与取消快速通道（DB 位随 fresh 库自清）。"""
    debug_sessions.clear()
    from . import execution_queue as _eq0
    _eq0._cancel_hint.clear()


# C6（P3-04）：execution_id → 调试执行上下文（ServerSession 由本模块
# 持有；命令/输出端点经此代理——前端不接触执行器 token）。
debug_sessions: dict[int, dict] = {}


# ─── row-level live registry (spec v3 §4 审计三定位)────────────────
# 行级可观测(Task 7):活跃执行的行状态驻内存,GET /executions/{id}/rows
# 实时读取;执行终态化(fanout task 结束)后 pop,读侧自动回落到
# JSONL 回放 —— 活跃读内存、历史读文件,两段式无缝切换。
@dataclass
class RowState:
    """一行(dataset row × repeat)的实时状态(纯值对象,单 loop 内读写)。"""

    seq: int
    dataset_id: str | None
    row_index: int
    rep: int
    status: str
    case_dir: str = ""                 # case stem(非全路径,不泄漏服务端布局)
    started_at: str | None = None
    finished_at: str | None = None
    # 交叉定位(spec v3 §4):注入条目 id + 数据集行两字段首次同时有值;
    # 纯基线行/纯数据集的另一侧为 None。
    injection_id: str | None = None
    # P2-01/P2-04:单元级台账面(从执行器事件投影;旧引擎/无事件路径
    # unit_id=""、attempts=1 —— 与 0008 存量行兼容)
    unit_id: str = ""
    branch: str = "main"
    attempts: int = 1
    # B6(R11 轻量版):server 链执行本行的槽位号;launch 链 None
    server_slot: int | None = None


# 行终态集合:JSONL 里 per-row 最后一行 status 的取值("dispatched" 为
# 中间态,"queued" 只存在于 registry)。回放器据此区分时间戳归属
# (final → finishedAt,否则 → startedAt);新增失败分支时同步维护。
_FINAL_STATUSES = frozenset({
    "passed", "failed", "canceled",
    "gimbal_rejected", "plate_unavailable", "plate_rejected",
    "launch_timeout", "launch_error", "dispatcher_error",
})

_row_states: dict[int, list[RowState]] = {}   # 活跃执行;finalize 后 pop


def execution_rows(execution_id: int) -> list[dict]:
    """行级状态读侧(内存段):活跃执行读内存 registry。

    历史执行走 :func:`execution_rows_page`(M6 起 DB 行是持久层,
    JSONL 回放只兜 M6 之前的存量单)。"""
    live = _row_states.get(execution_id)
    if live is not None:
        return [asdict(r) for r in live]
    return []


async def execution_rows_page(
    db: Any, execution_id: int, *, page: int = 1, page_size: int = 200,
) -> tuple[list[dict], int]:
    """历史执行行级分页(M6,债 5):DB 行 LIMIT/OFFSET + total。

    活跃执行(内存 registry 在场)整段返回后 Python 切片 —— 活跃行的
    权威在内存,分页只是展示层。M6 之前的存量单 DB 无行 → JSONL 回放
    (只读归档)兜底。
    """
    live = _row_states.get(execution_id)
    if live is not None:
        items = [asdict(r) for r in live]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    from sqlalchemy import func as sa_func, select as sa_select

    from ..models.execution import ExecutionRow

    total = (await db.execute(
        sa_select(sa_func.count()).select_from(ExecutionRow)
        .where(ExecutionRow.execution_id == execution_id)
    )).scalar_one()
    if total:
        rows = (await db.execute(
            sa_select(ExecutionRow)
            .where(ExecutionRow.execution_id == execution_id)
            .order_by(ExecutionRow.seq)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()
        return [
            {
                "seq": r.seq, "datasetId": r.dataset_id,
                "injectionId": r.injection_id, "rowIndex": r.row_index,
                "rep": r.rep, "status": r.status, "caseDir": r.case_dir or "",
                "startedAt": _dt_to_iso(r.started_at),
                "finishedAt": _dt_to_iso(r.finished_at),
                "serverSlot": r.server_slot,
                # B4:报告按 unit 归组 graph 链步骤(行 API 响应模型不含此键)
                "unitId": r.unit_id or "",
            }
            for r in rows
        ], int(total)
    # 存量单(M6 前无 DB 行):JSONL 只读归档回放,整段回再切片
    legacy = _replay_rows(execution_id)
    start = (page - 1) * page_size
    return legacy[start : start + page_size], len(legacy)


def _iso_to_dt(ts: str | None):
    """RowState 的 ISO 串(可带 Z / +00:00Z 杂交尾)→ aware datetime。"""
    if not ts:
        return None
    from datetime import datetime

    raw = ts[:-1] if ts.endswith("Z") else ts
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        from datetime import timezone

        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _dt_to_iso(dt) -> str | None:
    """DB datetime → naive-UTC ISO 串(与 registry/JSONL 口径一致)。"""
    from ..core.timeutil import iso_naive_utc

    return iso_naive_utc(dt)


class _EventIngester:
    """P2-02/C2:执行器事件/日志流式入库缓冲(launcher 回调 → execution_events)。

    回调在 launch 的读协程内同步触发 —— 只入内存缓冲;达到阈值经
    ``asyncio.create_task`` 异步批量落库(新会话,不与行持久化抢会话)。
    ``finalize`` 冲刷余量(gather 收口时调用);落库 best-effort,失败
    只记日志不阻断执行。
    """

    _FLUSH_EVERY = 200
    _FLUSH_INTERVAL_SEC = 0.5
    # 结构化日志设计 AD2:logs 缓冲上限 —— DB 长时间不可用时回填重试会让
    # 缓冲无界增长,超限丢最旧(诊断面可丢;events 不设上限,台账不可丢)。
    _LOGS_BUF_CAP = 50_000

    def __init__(self, db_factory: Any, execution_id: int) -> None:
        self._db_factory = db_factory
        self._execution_id = execution_id
        self._events: list[dict] = []
        self._logs: list[dict] = []
        self._pending: "set[asyncio.Task] | None" = None
        self._ticker: "asyncio.Task | None" = None
        self._stopped = False
        # 结构化日志设计 AD2/AD5:_flush 全路径 single-flight 锁 ——
        # 阈值 task 与 ticker 直调曾可并发开两个事务,PG 按 INSERT 时刻
        # 分 id、按提交时刻可见,先分 id 后提交的批次会落在已推进的
        # id cursor 之下(SSE 日志流 tail 漏行的 id 版)。锁内串行 =
        # 「执行内 id 按提交序单调」成为机制保证(tail 游标的地基)。
        # single-flight(AD2/AD5):阈值 task / ticker / finalize / 回填重试
        # 四条路径共用此锁 —— 换缓冲+落库+提交全程串行,执行内 id 按提交
        # 序单调;并发入口在锁上排队,各自换出排队期间积累的新缓冲。
        self._flush_lock = asyncio.Lock()
        # S9 自监控五计数(累计快照,随 flush jsonb_set 写 config_json.
        # ingest_stats;对账公式:文件行数 ≈ logs_ingested + dropped_
        # unparsable + below_level,崩失败量差是诚实边界):
        #   logs_ingested / logs_dropped_overflow / flush_errors 在本类累计;
        #   logs_dropped_unparsable / logs_below_level 在泵里计数(行不进
        # 缓冲)—— 同一 dict 传给池/launcher,start 时透传到 stderr 泵。
        self.pump_counters = {"logs_dropped_unparsable": 0,
                              "logs_below_level": 0}
        self.logs_ingested = 0
        self.flush_errors = 0
        # 超限丢最旧计数(S9 批 5 接入 ingest_stats 快照;先行内存累计)
        self.logs_dropped_overflow = 0
        # 上次已落库快照(None = 尚未写过;ticker 以「计数脏」触发冲刷)
        self._stats_written: "dict | None" = None
        # C12 修正：execution 级单调 seq 分配器——引擎 seq 是进程内
        # 计数，多 case（每 case 一个进程/run）会从 1 重来，直接落库
        # 会撞 (execution_id, seq) 唯一约束被静默丢弃（多行执行丢事件）。
        # 此处重映射为执行域单调递增（逐 case 内保序）。
        self._next_seq = 1
        # 日志占位 seq 分配器(负数轴递减):每批分配不重叠区间,
        # 避免多批撞 (execution_id, seq) 唯一约束被静默丢弃
        self._log_seq = 0

    def start(self) -> None:
        """启动周期冲刷(短执行也能在运行中被读到;大流量由阈值提前冲)。"""
        async def _tick() -> None:
            while not self._stopped:
                await asyncio.sleep(self._FLUSH_INTERVAL_SEC)
                # S9:泵侧计数脏即写 —— below_level/unparsable 在泵里计数、
                # 这些行不进缓冲,尾部只剩丢弃行时也得有 flush 把计数带出去
                if (self._events or self._logs
                        or self._stats_snapshot() != self._stats_written):
                    await self._flush()
        if self._ticker is None:
            self._ticker = asyncio.create_task(_tick())

    async def seed_from_db(self) -> None:
        """P3.5-2：恢复重跑时 seq 续接 —— 从已有事件 max(seq) / 日志
        min(seq)（负数轴最深处）起步。job 因租约过期/重启回队重跑时，
        不续接会从 1 重分配、撞 (execution_id, seq) 唯一约束被
        on_conflict_do_nothing 静默丢弃（重跑段事件整批丢失）。
        首次运行空表 → 起点不变（一次聚合查询的开销）。
        """
        from sqlalchemy import func as _func, select as _select

        from ..models.execution import ExecutionEvent as _EE
        async with self._db_factory() as session:
            row = (await session.execute(
                _select(_func.max(_EE.seq), _func.min(_EE.seq))
                .where(_EE.execution_id == self._execution_id))).one()
        if row[0] is not None:
            self._next_seq = int(row[0]) + 1
        if row[1] is not None and int(row[1]) < self._log_seq:
            self._log_seq = int(row[1])

    def on_event(self, d: dict) -> None:
        d = dict(d)
        d["seq"] = self._next_seq
        self._next_seq += 1
        self._events.append(d)
        self._maybe_flush()

    def on_log(self, d: dict) -> None:
        self.logs_ingested += 1
        self._logs.append(d)
        # AD2:超限丢最旧(保最新;丢弃计数供 S9 对账)
        if len(self._logs) > self._LOGS_BUF_CAP:
            drop = len(self._logs) - self._LOGS_BUF_CAP
            del self._logs[:drop]
            self.logs_dropped_overflow += drop
        self._maybe_flush()

    def _stats_snapshot(self) -> dict:
        """S9 五计数当前快照(泵侧两项从共享 dict 现读)。"""
        return {
            "logs_ingested": self.logs_ingested,
            "logs_dropped_unparsable": self.pump_counters["logs_dropped_unparsable"],
            "logs_below_level": self.pump_counters["logs_below_level"],
            "flush_errors": self.flush_errors,
            "logs_dropped_overflow": self.logs_dropped_overflow,
        }

    def _maybe_flush(self) -> None:
        if len(self._events) + len(self._logs) < self._FLUSH_EVERY:
            return
        if self._pending is None:
            try:
                self._pending = set()
            except RuntimeError:
                return   # 无运行循环(同步上下文兜底):留给 finalize
        if any(not t.done() for t in self._pending):
            return   # 在飞冲刷未收口,余量并入下一轮(锁兜底;此检查免排队)
        t = asyncio.create_task(self._flush())
        self._pending.add(t)
        t.add_done_callback(self._pending.discard)

    async def _flush(self) -> None:
        # single-flight(AD2/AD5):阈值 task / ticker / finalize / 回填重试
        # 四条路径共用此锁 —— 换缓冲+落库+提交全程串行,执行内 id 按提交
        # 序单调;并发入口在锁上排队,各自换出排队期间积累的新缓冲。
        async with self._flush_lock:
            events, self._events = self._events, []
            logs, self._logs = self._logs, []
            log_seq_base = self._log_seq - len(logs)
            self._log_seq = log_seq_base
            try:
                from . import execution_store
                async with self._db_factory() as session:
                    await execution_store.insert_events(
                        session, self._execution_id, events)
                    await execution_store.insert_logs(
                        session, self._execution_id, logs,
                        seq_base=log_seq_base)
                    # S9:快照随本批 flush 同事务落库(jsonb_set 键级原子
                    # 更新 —— config_json 有 counterDrift 等多写入者,整读
                    # 整写会互相覆盖;设值快照幂等,禁止 SQL +N 形态)。
                    # 快照与已入库行严格一致,对账不存在「行入了计数没加」
                    # 的窗口。空缓冲也写(finalize 终值唯一写入点在此)。
                    snap = self._stats_snapshot()
                    await session.execute(sa_text(
                        "UPDATE executions SET config_json = jsonb_set("
                        "COALESCE(config_json, '{}'::jsonb), '{ingest_stats}',"
                        " CAST(:stats AS jsonb)) WHERE id = :eid"),
                        {"stats": json.dumps(snap),
                         "eid": self._execution_id})
                    await session.commit()
                    self._stats_written = snap
            except BaseException as e:  # noqa: BLE001
                # 失败/取消都要回填缓冲(下次冲刷重试),不丢这批事件/日志。
                # P3.5-3 对账实测:finalize 取消 ticker 时批次可能正在 DB
                # 往返中,CancelledError 不是 Exception 子类,旧 except
                # Exception 会放行 → 整批静默丢失(批已换出,final flush
                # 拿到空缓冲)。回填后由 finalize 的收尾 flush 重试。
                self._events = events + self._events
                self._logs = logs + self._logs
                self._log_seq += len(logs)
                if isinstance(e, Exception):
                    # S9:flush_failed 双写 —— 事件面(下次冲刷入库,DB 恢复
                    # 后可见)+ 后端自身日志(DB 不可用时唯一幸存面)。取消
                    # 不算 flush 失败(进程收口语义,批次已回填重试)。连续
                    # 失败只留一条待刷事件(避免持续失败下 events 无界膨胀;
                    # 每次失败都计数、都打日志,信息不丢)。
                    self.flush_errors += 1
                    if not (self._events
                            and self._events[-1].get("event_type")
                            == "ingest.flush_failed"):
                        self._events.append({
                            "event_type": "ingest.flush_failed",
                            "seq": self._next_seq,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "error": repr(e)[:500],
                        })
                        self._next_seq += 1
                    logger.error(
                        "run_dispatcher: event flush {}/{} failed "
                        "(re-buffered): {}",
                        self._execution_id, len(events) + len(logs), e,
                    )
                else:
                    raise      # CancelledError 照常传播(取消语义不变)

    async def finalize(self) -> None:
        """gather 收口后冲刷余量并等待在飞冲刷完成。"""
        self._stopped = True
        if self._ticker is not None:
            self._ticker.cancel()
            try:
                await self._ticker
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._ticker = None
        if self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)
        await self._flush()


async def _persist_row_terminal(db_factory: Any, execution_id: int,
                                state: "RowState") -> None:
    """行终态即落库(M6 转正):崩溃窗口不丢已终态行。

    best-effort —— 失败只记日志:活跃读侧的权威仍在内存 registry,
    DB 是持久层跟进(§2.2);计数器审计面另由 JSONL 生命周期行承担。
    """
    from sqlalchemy.exc import IntegrityError

    from ..models.execution import ExecutionRow

    try:
        async with db_factory() as session:
            session.add(ExecutionRow(
                execution_id=execution_id, seq=state.seq,
                unit_id=state.unit_id, branch=state.branch,
                attempts=state.attempts,
                dataset_id=state.dataset_id, injection_id=state.injection_id,
                row_index=state.row_index, rep=state.rep,
                status=state.status, case_dir=state.case_dir or "",
                started_at=_iso_to_dt(state.started_at),
                finished_at=_iso_to_dt(state.finished_at),
                server_slot=state.server_slot,
            ))
            try:
                await session.commit()
            except IntegrityError:
                # 同 (execution, seq) 已有终态行(P3.5-2:job 重跑时行级
                # 断点之外的兜底 —— 中断行重跑完成即撞唯一约束)
                await session.rollback()
                from sqlalchemy import update

                await session.execute(
                    update(ExecutionRow)
                    .where(ExecutionRow.execution_id == execution_id,
                           ExecutionRow.seq == state.seq)
                    .values(status=state.status, case_dir=state.case_dir or "",
                            unit_id=state.unit_id, branch=state.branch,
                            attempts=state.attempts,
                            started_at=_iso_to_dt(state.started_at),
                            finished_at=_iso_to_dt(state.finished_at),
                            server_slot=state.server_slot)
                )
                await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: persist row terminal {}/{} failed: {}",
            execution_id, state.seq, e,
        )


def _replay_rows(execution_id: int) -> list[dict]:
    """按天 JSONL 回放:同 (executionId, seq) 后行覆盖前行(final 覆盖 dispatched)。"""
    rows: dict[int, dict] = {}
    for path in sorted((settings.DATA_DIR / "runs").glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("executionId") != execution_id:
                    continue
                seq = rec.get("seq")
                if seq is None:
                    continue
                cur = rows.setdefault(seq, {"seq": seq,
                                            "datasetId": rec.get("datasetId"),
                                            # 旧 JSONL 无注入族 → 缺键 None,不炸
                                            "injectionId": rec.get("injectionId"),
                                            "rowIndex": rec.get("rowIndex", 0),
                                            "rep": rec.get("rep", 0),
                                            "status": rec.get("status", ""),
                                            "caseDir": "",
                                            "startedAt": None, "finishedAt": None})
                cur["status"] = rec.get("status", cur["status"])
                if rec.get("casePath"):
                    # casePath 指向 case.json 文件;caseDir 取其父目录名
                    # (= case stem,与 live registry 的 case_dir 同口径)。
                    cur["caseDir"] = Path(rec["casePath"]).parent.name
                ts = rec.get("ts")
                if rec.get("status") in _FINAL_STATUSES:
                    cur["finishedAt"] = ts
                else:
                    cur["startedAt"] = ts or cur["startedAt"]
    return [rows[k] for k in sorted(rows)]


# ─── startup reconcile (P3) ────────────────────────────────────────
async def reconcile_stale_executions(
    db_factory: Any, *, periodic: bool = False,
) -> int:
    """reconcile 僵尸执行(C11 起 jobs 感知;N2 起走唯一终态迁移;
    P0-3.2/3.3 起支持周期模式与 canceled 口径,webhook 设计 v3)。

    * executions stuck queued/running **且无 job 行**（0009 前遗留/
      建行后入队前崩溃）→ failed + ``config_json.reconciled``（原口径）;
    * job ``failed``/``canceled`` 终态而 execution 仍 queued/running
      （worker 收口前崩溃）→ job failed → failed 收口;job canceled →
      **canceled 收口**(D7:不做零计数兜底、不通知 —— 取消不是失败,
      回调上线后 status=canceled);
    * job ``queued``/``running``：留给 worker（queued 待认领;running
      由 sweep_stale 按租约回收——回队重跑或 attempts 耗尽失败）。

    两种模式:启动期(``periodic=False``,全量扫描,理由文案保持原文)
    与周期(``periodic=True``,经 :func:`periodic_reconcile_once` 注册
    background_tasks,每 ``EXEC_RECONCILE_INTERVAL_S`` 秒一拍;只收
    ``created_at`` 早于 ``EXEC_RECONCILE_GRACE_S`` 宽限期的单 —— 避免与
    正在收尾的执行抢终态)。周期理由文案带 ``periodic reconcile:`` 前缀,
    ``config_json.reconciled.reason`` 可区分两期。

    N2 变化:①收口改经 :func:`transition_execution`(原子守卫,重启
    竞态下已终态的不覆写);②整单未分发(passed=failed=0)按 failed=total
    计(与 if_stuck 同款 2-3 口径,消除"状态 failed 而计数 0"的矛盾);
    ③started_at 从 created_at 回填;④failed 终态发完成通知(N2-2:启动
    对账不再静默)。返回**实际发生迁移**的行数。
    """
    from sqlalchemy import select as _select
    async with db_factory() as session:
        q = _select(Execution.id, Execution.created_at,
                    ExecutionJob.status).outerjoin(
            ExecutionJob, ExecutionJob.execution_id == Execution.id).where(
                Execution.status.in_((STATUS_QUEUED, STATUS_RUNNING)))
        if periodic:
            grace = timedelta(seconds=settings.EXEC_RECONCILE_GRACE_S)
            q = q.where(Execution.created_at < _utcnow() - grace)
        rows = (await session.execute(q)).all()
    prefix = "periodic reconcile: " if periodic else ""
    count = 0
    for ex_id, created_at, job_status in rows:
        if job_status in ("queued", "running"):
            continue   # worker 域:待认领或由租约回收
        if job_status == "canceled":
            # D7(P0-3.3):job 已取消 → 执行记 canceled;取消不是失败,
            # 不做零计数兜底、不发通知(canceled 站内通知本就不发),
            # 回调面(P2)按 MOVED 正常发 status=canceled。
            moved = await transition_with_retry(
                db_factory, ex_id, STATUS_CANCELED, notify=False,
                reconciled_reason=(
                    f"{prefix}job canceled without execution finalize"))
        else:
            moved = await transition_with_retry(
                db_factory, ex_id, STATUS_FAILED, count_fallback=True,
                reconciled_reason=(
                    f"{prefix}backend restarted mid-dispatch"
                    if job_status is None
                    else f"{prefix}job {job_status} without execution finalize"),
                backfill_started_at=created_at)
        count += 1 if moved is TransitionResult.MOVED else 0
    if count:
        logger.warning(
            "run_dispatcher: reconciled {} stale execution(s) ({})",
            count, "periodic" if periodic else "after restart",
        )
    return count


async def periodic_reconcile_once() -> int:
    """周期对账入口(background_tasks 注册,P0-3.2/设计 v3 P0-5)。

    卡住的执行最迟「宽限 10 分钟 + 周期 5 分钟」内被收口 —— 回调上线
    后这是「收不到回调」兜底的书面承诺(集成指南按 executionId 轮询)。"""
    return await reconcile_stale_executions(_session_factory, periodic=True)


async def startup_recovery() -> tuple[int, int]:
    """启动恢复（C11）：租约孤儿回收 → reconcile 僵尸执行 → 清扫 case 目录。

    「平台重启后排队中的任务继续执行」由 job 留存 + worker 认领兑现;
    「已在运行的任务按对账结果收口」= 孤儿按 attempts 回队重跑或失败。
    """
    from . import execution_queue as _eq
    async with _session_factory() as session:
        swept_jobs = await _eq.sweep_stale(session)
        await session.commit()
    stale = await reconcile_stale_executions(_session_factory)
    swept = sweep_stale_case_dirs()
    return stale, swept + swept_jobs


# ─── fanout 计算(dispatch 与 suite 预检共用)────────────────────
async def compute_run_fanout(
    db: AsyncSession, scenario_id: str, payload: dict | None,
    req: RunRequest,
) -> tuple[list[dict], list, list, list]:
    """数据集选择合并 + 注入条目过滤 + 交叉矩阵 → (fanout_datasets,
    injections, selected_entries, skipped_while_degraded)。

    权限域二期 P1 自 dispatch_run 抽出:**suite 总量预检与 dispatch
    共用这同一份实现**(《Suite成员层、引用分享与浏览镜头-设计方案》
    §6.6)—— 两处算法漂移会出现「预检通过、单成员 409」的边缘。
    selected_entries = 选中注入条目(dispatch 的配方留档);
    skipped_while_degraded = 降级期跳过的条目 id(判定降级留档);
    预检只消费 fanout/injections 计数,后两者忽略。不建行、不改库;
    校验失败照常抛 NotFound/Conflict。

    P3(临时调用 §六):入参由 ORM 行改为 ``(scenario_id, payload)`` ——
    本函数只用这两个值(数据集归属校验 + 注入条目过滤),临时构造的
    payload 与库行同形即可共用;调用方传 ``scen.scenario_id, scen.payload``。
    """
    # 行级选择合并(spec v3 §4):dataSetSelection 权威键 — 仅当其缺省
    # (空)时旧 dataSetIds 才生效(兼容读,映射整库);两键同发则旧键
    # 整键忽略。同库多段合并取超集、段序无关:行集 ∪ 行集;任一段整库
    # (行集空)则整库(整库 ⊇ 任意行集);段内行号去重。
    sel_by_ds: dict[str, list[int] | None] = {}
    for sel in req.data_set_selection:
        ds_id = sel.dataset_id
        row_idxes = sorted(set(sel.row_indexes))
        if ds_id not in sel_by_ds:
            sel_by_ds[ds_id] = row_idxes or None
        elif not row_idxes:
            # 重复的整库段无论先后都提升为整库(超集语义)。
            sel_by_ds[ds_id] = None
        elif sel_by_ds[ds_id] is not None:
            sel_by_ds[ds_id] = sorted(set(sel_by_ds[ds_id]) | set(row_idxes))
        # else:已整库(None)遇行集段 — 整库 ⊇ 行集,保持整库。
    if not sel_by_ds:
        for ds_id in req.data_set_ids:
            sel_by_ds[ds_id] = None

    selected_datasets: list[ComposerDataSet] = []
    for ds_id in sel_by_ds:
        ds = await find_dataset_by_id(db, ds_id)
        if ds is None or ds.scenario_id != scenario_id:
            raise NotFound(
                "data_set_not_found", f"data set not found: {ds_id}"
            )
        selected_datasets.append(ds)

    # 断言注入条目(spec v3 §8):被选中且悬空检测通过的条目 → 注入族
    # (与数据集行交叉派生 case,spec v3 §4);死/旧条目 skip + 告警,
    # 绝不炸。判定本体 = filter_injection_entries(执行设计 §1.6:
    # /run/precheck 与 dispatch 共用这**一份**实现,失效口径不开第二份)。
    raw_payload = payload or {}
    selected_entries, dangling_ids, skipped_while_degraded = (
        await filter_injection_entries(raw_payload, req.injection_entry_ids or [])
    )
    if dangling_ids:
        # Release v4.4 §6.3：正式执行悬空注入条目 → 失败（非静默跳过）。
        # 预览判定 = 版本模型 §6（A-2/W5）：任一受管系统 working（含未钉
        # 修订）即预览；调试执行保持宽容（探索性质，悬空面在
        # /run/precheck 与告警可见）。旧口径 is_preview=bool(req.debug) 废。
        from .run_semantics import working_preview
        if working_preview(raw_payload) or req.debug:
            logger.warning(
                "run_dispatcher: dangling injection entries (preview, allowed): {}",
                dangling_ids,
            )
        else:
            raise Conflict(
                "dangling_injection_entries",
                f"正式执行存在悬空注入条目（{len(dangling_ids)} 条）："
                f"{dangling_ids[:5]}... 请先在编排页修正或移除这些条目",
                extra={"entries": dangling_ids},
            )

    # 行级过滤(spec v3 §4):rowIndexes 选中行;越界 409。行集为空的
    # 数据集 = 隐式空覆盖行(D12 基线语义);rowIndexes 校验对真实行数。
    # rows 携带 (原始行号, 行字典) 对 — 审计/stem 记编辑器行号,
    # 稀疏选择不重排(整库选择即 0..N-1 原样)。
    fanout_datasets: list[dict] = []
    for ds in selected_datasets:
        rows_raw = list(ds.rows or [])
        sel = sel_by_ds.get(ds.dataset_id)
        if sel is None:
            fanout_datasets.append({
                "datasetId": ds.dataset_id,
                "rows": [(i, r) for i, r in enumerate(rows_raw)] or [(0, {})],
            })
        else:
            for ri in sel:
                if ri < 0 or ri >= len(rows_raw):
                    raise Conflict(
                        "row_index_out_of_range",
                        f"rowIndex={ri} out of range for data set "
                        f"{ds.dataset_id} (0..{len(rows_raw) - 1})",
                    )
            fanout_datasets.append({
                "datasetId": ds.dataset_id,
                "rows": [(ri, rows_raw[ri]) for ri in sel],
            })
    # 交叉矩阵(spec v3 §4):R(行集合,空={[基线]})× E(选中条目集合,
    # 空={[无注入]})— 每 case = 一行 × 一条目,单一偏离可直接归因;
    # 替代 v2 的 N+M 并集与 `not fanout and not entries` 特判。
    injections = list(selected_entries) or [None]
    if not fanout_datasets:
        fanout_datasets = [{"datasetId": None, "rows": [(0, {})]}]
    return fanout_datasets, injections, selected_entries, skipped_while_degraded


def fanout_total(fanout_datasets: list[dict], injections: list) -> int:
    """R × E 的单元口径计数(P2-05:nRuns 乘法下沉执行器,不展开进
    total_runs;P7 闸同口径)。"""
    return sum(len(d["rows"]) for d in fanout_datasets) * len(injections)


# ─── main entry point ─────────────────────────────────────────────
async def _check_env_consistency(
    db: AsyncSession, scenario_payload: dict,
    service_bindings: dict[str, ServiceBinding],
) -> list[str]:
    """环境告警（Release v4.4 §6.3 / V5-B）：混合环境 + 版本线不一致。

    混合环境：服务别名指向多个环境 → 告警（哪条版本线生效不明确）。
    版本线不一致：环境声明的版本线 ≠ 场景 meta.plate 的版本线 → 告警。
    返回告警文本列表（调用方写 config_json 的 environmentWarnings 键）。
    """
    from ..models.environment import Environment
    from ..models.service_alias import ServiceAlias

    if not service_bindings:
        return []

    # 1. 别名 → 环境（经 service_aliases.environment_id）
    alias_names = sorted({
        b.auth_alias for b in service_bindings.values() if b.auth_alias})
    if not alias_names:
        return []
    aliases = (await db.execute(
        select(ServiceAlias).where(
            ServiceAlias.alias_name.in_(alias_names))
    )).scalars().all()
    env_ids = sorted({a.environment_id for a in aliases if a.environment_id})
    if not env_ids:
        return []
    envs = (await db.execute(
        select(Environment).where(Environment.id.in_(env_ids))
    )).scalars().all()
    if not envs:
        return []

    warnings: list[str] = []

    # 2. 混合环境告警
    if len(envs) > 1:
        warnings.append(
            f"混合环境:服务绑定指向 {len(envs)} 个环境"
            f"（{'、'.join(e.name for e in envs)}）——版本线生效优先级不明确")

    # 3. 版本线不一致告警（每个环境 vs 场景 meta.plate）
    definition = definition_from_payload(scenario_payload)
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    for env in envs:
        for system, line in (env.lines or {}).items():
            declared = meta_plate.get(system)
            if ref_category(declared) == PIN:  # b2-3:线一致告警仅对钉定
                declared_line = declared.split("#")[0]
                if declared_line != line:
                    warnings.append(
                        f"环境不一致:环境「{env.name}」声明 {system}@{line},"
                        f"场景声明 {system}@{declared_line}——执行将使用场景"
                        "的版本线,建议适配或调整环境")
    return warnings


@dataclass(frozen=True)
class RunTarget:
    """派发目标(P3 临时调用 §六:``dispatch_run`` 拆两段的第一段产物)。

    * ``scenario_id``:执行行的挂载 id —— 库场景即其 ``scenario_id``;
      临时调用为占位 ``adhoc-<run_id>``(models.execution 非场景形态的
      ``<形态前缀>-<id>`` 约定,与 ``suite-<id>`` 同款);
    * ``payload``:与库行 payload 同形的容器(``{definition, ...}``,
      ``definition_from_payload`` 解包);快照、扇出、注入清单都读它;
    * ``kind``:进 ``Execution.kind``(scenario | adhoc)。

    不带 owner_id:执行者(凭证池归属)始终是调用者 ``user_id``,派发链
    从不读场景属主 —— 加了反而会悄悄改掉 admin 代跑的语义。
    """
    scenario_id: str
    payload: dict
    kind: str = "scenario"


async def dispatch_run(
    db: AsyncSession,
    user_id: int,
    req: RunRequest,
    *,
    preloaded_scenario: ComposerScenario | None = None,
    chain_override: str | None = None,
    token: "object | None" = None,
    trace: "dict | None" = None,
) -> RunResponse:
    """库中场景的派发入口 = 取场景 → :func:`dispatch_target`(P3 §六)。

    对外签名不变(runs 路由 / 重跑 / Suite 成员三处调用零改动);
    临时调用由路由层自行构造 :class:`RunTarget` 直接走第二段。

    ``preloaded_scenario``: the runs router already loads the scenario
    row for the ownership check — pass it here to avoid querying the
    same row twice (and keep a single source for the
    scenario_not_found 404).
    """
    # P3:优雅关闭窗口内不再"建行但不 spawn"(那会制造一条 201 返回、
    # 永远停在 queued 的僵尸单)。直接拒单,客户端重启后重试。
    if is_shutting_down():
        raise Conflict(
            "shutting_down",
            "platform is shutting down; retry after the backend restarts",
        )

    # 1. Load the scenario (PK is the string scenario_id, not the int id)
    scen = (
        preloaded_scenario
        if preloaded_scenario is not None
        else (await get_row(db, req.scenario_id)
              if req.scenario_id else None)
    )
    if scen is None:
        raise NotFound("scenario_not_found", f"scenario not found: {req.scenario_id}")
    return await dispatch_target(
        db, user_id, req,
        RunTarget(scenario_id=scen.scenario_id,
                  payload=scen.payload or {}, kind="scenario"),
        chain_override=chain_override, token=token, trace=trace)


async def dispatch_target(
    db: AsyncSession,
    user_id: int,
    req: RunRequest,
    target: RunTarget,
    *,
    run_id: str | None = None,
    chain_override: str | None = None,
    token: "object | None" = None,
    trace: "dict | None" = None,
) -> RunResponse:
    """Validate + 入队 + return runId（C11：执行配方进 execution_jobs，
    worker 认领驱动；本函数不再 spawn 进程内 fanout）。

    第二段(P3 §六):只认 ``target``(scenario_id / payload / kind),库场景
    与临时调用共用 —— 校验、扇出、建执行行、快照、入队全在这里,逐字段
    与拆分前一致(tests/test_adhoc_run 对拍钉住)。``run_id`` 可由调用方
    预生成(临时调用的占位 id 要先用到它),缺省在此分配。

    Caller (the runs router) wraps any exception in HTTPException.  This
    function NEVER raises for "Plate is down" — it records the failure
    and returns the runId so the user can still see the run in
    ``/executions`` (per the agreed run-failure semantics).

    ``chain_override``（C13 对账用，非公开 API 面）：强制本次执行的链
    （legacy|server），覆盖 settings.EXEC_CHAIN；随配方与 config_json
    落档，回滚 = 开关关闭即回旧链。

    令牌调用面(webhook v4 §3.1):``token`` 来自 ``principal_or_user``
    分流(JWT 调用恒 None → 不写投递行、不回调);``client_ref``/
    ``callback_path`` 在 ``req`` 上。
    """
    if is_shutting_down():
        raise Conflict(
            "shutting_down",
            "platform is shutting down; retry after the backend restarts",
        )
    scenario_payload = target.payload or {}

    # 2. Validate datasets.
    # (旧 env 校验块已随 D2 执行环境退役 — 旧客户端多发的 env 键由
    # pydantic extra=ignore 静默忽略。)

    # RunOptions 未接面显式拒绝(W19):step_from 需要被跳过上游的输出
    # 由外部提供(同 GraphControlSpec 不开放 fromNode 的理由);subscribe
    # 平台无消费面。生成物形状收下了这两个键,但派发链静默丢弃它们
    # 会制造"看似生效"的假象 —— 409 说清楚,不兼容不吞。
    if req.run_options is not None:
        if req.run_options.step_from is not None:
            raise Conflict(
                "run_options_step_from_unsupported",
                "step_from 尚未接入平台派发链(被跳过步骤的输出平台无从"
                "提供);请移除该键",
            )
        if req.run_options.subscribe:
            raise Conflict(
                "run_options_subscribe_unsupported",
                "subscribe 尚未接入平台派发链;请移除该键",
            )

    # step_to 校验(同 V1 executions:与场景 steps 数比对,越界 409)
    steps = steps_from_payload(scenario_payload)
    if req.step_to is not None:
        if not steps:
            raise NotFound("no_steps", "scenario has no steps; step_to cannot be set")
        if req.step_to >= len(steps):
            raise Conflict(
                "step_to_out_of_range",
                f"step_to={req.step_to} out of range (0..{len(steps) - 1})",
            )

    # S2.1 环境链:本次显式(RunRequest 顶层 > 图级)> 方案 > 项目默认 >
    # 个人偏好 > 默认环境。方案字段由客户端摊平;请求没带环境但带了
    # schemeId 时回查方案兜底。解析结果进 config_json(重跑按快照回放)
    # 与任务配方(worker 不回查请求上下文)。
    from .env_chain import EnvironmentNotFound, resolve_for_scenario
    _explicit_env = req.environment_id
    if _explicit_env is None and getattr(req, "graph", None) is not None:
        _explicit_env = req.graph.environment_id
    _scheme_env = None
    if _explicit_env is None and req.scheme_id and target.kind == "scenario":
        from . import scheme_store as _sst
        try:
            _sch = await _sst.get_row(db, target.scenario_id, req.scheme_id)
            _scheme_env = (_sch.payload or {}).get("environmentId")
        except Exception:  # noqa: BLE001 — 悬空方案不阻塞(溯源字段)
            _scheme_env = None
    try:
        env_choice = await resolve_for_scenario(
            db, target.scenario_id if target.kind == "scenario" else None,
            user_id=user_id, explicit=_explicit_env, scheme_env=_scheme_env)
    except EnvironmentNotFound as e:
        raise NotFound("environment_not_found", str(e)) from None

    # V5-B 环境告警（§6.3）:混合环境 + 版本线不一致 → 写 config_json
    try:
        env_warnings = await _check_env_consistency(
            db, scenario_payload, req.service_bindings or {})
    except Exception:  # noqa: BLE001 — 告警失败不阻塞执行
        env_warnings = []

    # fanout 计算(权限域二期 P1 抽出为 compute_run_fanout:suite 总量
    # 预检与本处共用同一份实现,算法不得漂移)。
    (fanout_datasets, injections, selected_entries,
     skipped_while_degraded) = await compute_run_fanout(
        db, target.scenario_id, scenario_payload, req)

    # authz W6:执行人 ≠ 场景属主(引用执行 / suite 聚合跑他人成员)——
    # 原件不剥(发布不改原件),执行形态在此脱敏:数据集敏感列剥、
    # payload 去 config.users(快照/任务参数不落作者明文;内置凭证主
    # 规则在 prepare_exec 本就当空,两者同口径)。adhoc 无存储属主不判。
    # 临时调用(adhoc):payload 由调用者即席提供,执行人即作者 —— 显式
    # 记为本人(built_in_users fail-closed,None 会把作者自己的也当空)
    _scen_owner_id = (
        (_sr.owner_id if (_sr := await get_row(
            db, target.scenario_id)) is not None else None)
        if getattr(target, "kind", "scenario") == "scenario"
        and target.scenario_id else user_id)
    if _scen_owner_id is not None and user_id != _scen_owner_id:
        from .scenario_store import (
            strip_builtin_credentials, strip_sensitive_columns)
        scenario_payload = strip_builtin_credentials(
            copy.deepcopy(scenario_payload))
        fanout_datasets = [
            {**fd, "rows": [(i, (strip_sensitive_columns([r])[0]
                                 if r else r))
                            for i, r in fd["rows"]]}
            for fd in fanout_datasets]

    # 3. Allocate runId + Execution row
    # total_runs 必须按实际行数算(与 _fanout 的迭代口径一致)— 旧的
    # row_count 列在 raw-SQL 迁移路径下不回填,NULL/过期会让计数器
    # 超过 total_runs 出现 failed > total 的怪状态。
    run_id = run_id or _new_run_id()
    total_runs = fanout_total(fanout_datasets, injections)
    if total_runs > settings.MAX_RUNS_PER_EXECUTION:
        raise Conflict(
            "too_many_runs",
            f"total runs {total_runs} exceed platform cap "
            f"{settings.MAX_RUNS_PER_EXECUTION} (rows x injections)",
        )
    # 注入清单 = 模板扫描 ∪ 绑定(spec §5)。扫描源是存储的 definition
    # steps + config.setup/teardown 条目(webhook v4 §3.2 —— setup 引用
    # 的凭证此前在 runs 链不注入;与 run_prepare/integration_runner 同
    # 口径);绑定的 authAlias 并入(即使 steps 未引用该 alias)。去重保序。
    # 注入清单 —— 两链唯一实现(service_aliases.exec_auth_aliases:
    # 模板扫描 ∪ 绑定 authAlias ∪ 别名表凭证默认,显式绑定优先)。
    # 存档口径(§4.1 拍板):config_json.serviceBindings 只记场景原始
    # 绑定,别名默认只体现于 injectedAuths 清单与实际注入的 users。
    auth_aliases = await service_aliases.exec_auth_aliases_of_definition(
        db,
        definition_from_payload(scenario_payload),
        {k: {"authAlias": b.auth_alias}
         for k, b in (req.service_bindings or {}).items()},
    )

    from . import execution_queue as _eq
    chain = chain_override or str(
        getattr(settings, "EXEC_CHAIN", "legacy") or "legacy")
    debug_spec = getattr(req, "debug", None)
    if debug_spec is not None:
        # 调试前置（引擎既有约束的收口）：单 case 且无乘法、非 graph
        if getattr(req, "graph", None) is not None:
            raise Conflict("debug_not_supported", "graph 执行不支持调试")
        if total_runs != 1:
            raise Conflict(
                "debug_single_case",
                "调试执行仅支持单 case（数据集行 × 注入族须为 1）")
        if int(req.n_runs or 1) != 1:
            raise Conflict("debug_single_run", "调试执行要求 nRuns=1")
        chain = "server"

    execution = await _create_execution(
        db,
        # (Case 层解散后执行的挂载点就是场景;临时调用为占位 id)。
        scenario_id=target.scenario_id,
        owner_id=user_id,
        total_runs=total_runs,
        # P3:执行形态(scenario | adhoc)—— 非场景形态登记在
        # models.execution.NON_SCENARIO_KINDS,列表/重跑按它判定。
        kind=target.kind,
        # 批次键(执行设计 §1.2):前端队列逐条发起时共用,执行记录归并用;
        # 单条发起为 None。列 + config_json 双落:列驱动筛选,config 驱动
        # 重跑配方的原样保真。
        batch_id=req.batch_id,
        # 入站调用台账(webhook v4 §7.1):JWT 调用恒 None。
        token_id=token.id if token is not None else None,
        client_ref=req.client_ref,
        callback_path_override=req.callback_path,
        # 台账快照列(M2):通知/列表展示用 name,场景删了执行仍可读。
        # 直读唯一权威 payload.definition.meta.name,不走 _meta_from_row
        # 的整 meta 严格校验 —— 畸形行不拦发起,空值由通知侧兜底链接住。
        scenario_name=str(
            (definition_from_payload(scenario_payload).get("meta") or {}
            ).get("name") or ""
        ).strip(),
        # 执行时场景快照:与传给 _fanout 的 scenario_payload 同拍同源
        # (同一读取),保证"快照即所执行";深拷贝隔离后续 fanout 内的
        # setdefault 写穿,不污染快照。
        scenario_snapshot=copy.deepcopy(scenario_payload),
        # RS3：plate_pins 随 fanout 后回填（生效修订在 fanout 内解析）
        plate_pins=None,
        config_json={
            "runId": run_id,
            "scenarioId": target.scenario_id,
            "dataSetIds": req.data_set_ids,
            "dataSetSelection": [
                s.model_dump(by_alias=True) for s in req.data_set_selection
            ],
            # 执行环境键已随 D2 退役(不再写入);历史行旧键由前端
            # RECIPE_LABELS 标签保留可读。
            # 实际注入清单(扫描 ∪ 绑定)— 读侧据此展示认证列。缺 alias
            # 只告警继续(清单如实记录原始请求,与"解不到≠没要求"对齐)。
            "injectedAuths": auth_aliases,
            # service → {authAlias?, url?}(驼峰 dump,None 键不落)。
            "serviceBindings": {
                k: b.model_dump(by_alias=True, exclude_none=True)
                for k, b in req.service_bindings.items()
            },
            # 执行指令快照(W19):RunOptions 生成物 dump(snake_case 内层,
            # 与 RunScheme.options 同形)。旧平铺键 stepTo/nRuns/parallel
            # 不再写;读侧(rerun/列表投影)带旧行回退映射。
            "runOptions": (req.run_options.model_dump(mode="json",
                                                       exclude_none=True)
                           if req.run_options is not None else None),
            # 原始请求的注入条目 id(悬空过滤**前**):rerun 按配方重建的
            # 唯一来源(执行设计 §3.4)—— 只记录请求,不记录判定结果。
            "injectionEntryIds": req.injection_entry_ids,
            # 方案溯源快照(spec §5,阶段③):纯记录,无分发语义
            "schemeId": req.scheme_id,
            # S2.1 环境选择快照(environmentId/environmentSource;无环境
            # 时键缺席)—— 重跑按此回放
            **env_choice.snapshot(),
            "schemeName": req.scheme_name,
            # 批次键(执行设计 §1.2):与列同值;rerun 按 config_json 重建
            # 配方时不带旧批(重跑是新的一次独立发起)。
            "batchId": req.batch_id,
            "reportDefinitionId": getattr(req, "report_definition_id", None),
            # C13:执行链留档（legacy|server;调试恒 server）
            "chain": chain,
            # §7.1 追溯块(令牌与 JWT 都写 resolvedServices/builtinAuths;
            # 令牌另带 token 快照与 outOfScope)
            **({"resolvedServices": trace["resolvedServices"]}
               if trace and trace.get("resolvedServices") is not None else {}),
            **({"builtinAuths": trace["builtinAuths"]}
               if trace and trace.get("builtinAuths") else {}),
            **({"token": trace["token"]}
               if trace and trace.get("token") else {}),
            **({"outOfScope": trace["outOfScope"]}
               if trace and trace.get("outOfScope") else {}),
            **({"environmentWarnings": env_warnings} if env_warnings else {}),
            # spec §1.1 Y:判定降级是可审计事实,不留静默窗口。
            # entriesSkippedWhileDegraded = 降级期间被跳过的条目 id(因由不限);
            # 键缺席 = 本次执行没有「降级 + 跳过」同时发生,不是「零跳过」。
            **({"judgeDegraded": True, "entriesSkippedWhileDegraded": skipped_while_degraded}
               if skipped_while_degraded else {}),
        },
    )

    # C11（P3-01）：不再 spawn 进程内 fanout —— 执行配方入队，worker 认领驱动。
    # 配方是 dispatch 校验后的完整快照（worker 不回查请求上下文）；
    # chain（C13）记录执行链：settings.EXEC_CHAIN（legacy|server）或
    # dispatch 的 chain_override（对账脚本用）；debug（C6）强制 server 链。
    from . import execution_queue as _eq
    if getattr(req, "graph", None) is not None:
        payload = {
            "kind": "graph",
            "chain": chain,
            "args": {
                "execution_id": execution.id, "run_id": run_id,
                "owner_id": user_id,
                "graph_spec": req.graph.model_dump(by_alias=True),
                # S2.1:显式位才整图生效;否则逐单元解析(见 graph_dispatch)
                "env_snapshot": env_choice.snapshot(),
                "n_runs": req.n_runs, "halt_at": req.step_to,
                "scenario_payload": dict(scenario_payload),
            },
        }
    else:
        payload = {
            "kind": "cases",
            "chain": chain,
            "debug": (debug_spec.model_dump(mode="json")
                      if debug_spec is not None else None),
            "args": {
                "execution_id": execution.id, "run_id": run_id,
                "scenario_payload": dict(scenario_payload),
                "datasets": fanout_datasets,
                "injections": selected_entries,
                "owner_id": user_id,
                # authz W6:场景属主随任务下发,内置凭证主规则在
                # _fanout → prepare_exec 判(executor ≠ 属主 ⇒ 当空);
                # adhoc(临时调用)= 执行人本人(上方 _scen_owner_id;
                # built_in_users fail-closed,None 一律当空)
                "scenario_owner_id": _scen_owner_id,
                # S2.1:环境随配方下发(地址 ③ 层并入部署表)
                "env_snapshot": env_choice.snapshot(),
                "auth_aliases": auth_aliases,
                "halt_at": req.step_to,
                "n_runs": req.n_runs,
                "parallel": req.parallel,
                "service_bindings": {
                    k: b.model_dump(by_alias=True)
                    for k, b in (req.service_bindings or {}).items()
                },
            },
        }
    await _eq.enqueue(db, execution.id, kind=payload["kind"], payload=payload)
    # 惰性 ensure:lifespan 未跑（测试 ASGITransport 直连）也能驱动队列
    _eq.ensure_workers()
    # RS3 plate_pins 不在此回填：job 经 DB 队列异步驱动，dispatch 返回时
    # fanout 尚未解析生效修订 —— 由 _fanout 解析出后自行落库。

    return RunResponse(
        runId=run_id, executionId=execution.id,
        identityMode=(token.kind if token is not None else "personal"))


# ─── C11：worker 任务体入口（payload → fanout）──────────────────

async def run_job_from_payload(job: dict) -> None:
    """execution_queue worker 的任务体：解包配方 → _fanout/_fanout_graph。

    payload 是 dispatch_run 校验后的完整快照（JSON 往返安全形态）；
    ServiceBinding 在此重建为模型（_fanout 消费面不变）。
    """
    p = job["payload"]
    args = dict(p["args"])
    if p["kind"] == "graph":
        # B-1(2026-10-13):graph 分支此前丢掉 chain 选择 —— cases 分支
        # 透传 p["chain"] 而 graph 恒走缺省 legacy,EXEC_CHAIN=server /
        # chain_override 对 suite 执行完全不生效。
        await _fanout_graph(db_factory=_session_factory,
                            chain=p.get("chain") or "legacy", **args)
        return
    bindings = args.get("service_bindings") or {}
    args["service_bindings"] = {
        k: ServiceBinding(**v) for k, v in bindings.items()
    }
    await _fanout(
        db_factory=_session_factory,
        chain=p.get("chain") or "legacy",
        debug=p.get("debug"),
        **args,
    )


async def finalize_canceled_before_start(job: dict) -> None:
    """取消先于启动：执行直接 canceled 收口（无行、零计数）。

    N2:改经唯一终态迁移(原子守卫);取消类不回填 started_at
    (从未启动),不发通知(用户自发的取消)。
    """
    execution_id = job["payload"]["args"]["execution_id"]
    await transition_with_retry(_session_factory, execution_id,
                                STATUS_CANCELED)
    _row_states.pop(execution_id, None)
    logger.info("run_dispatcher: execution {} canceled before start", execution_id)


async def finalize_execution_if_stuck(execution_id: int, error: str) -> None:
    """任务体异常的兜底终态化(N2:走唯一迁移;幂等 = 终态不再改)。

    N2-2 拍板:failed 兜底也发完成通知 —— 任务体崩溃是调用方无从得知
    的静默失败,此前零通知。
    """
    await transition_with_retry(
        _session_factory, execution_id, STATUS_FAILED,
        dispatcher_error=error, count_fallback=True)


# ─── background fan-out ──────────────────────────────────────────
def _start_cancel_poller(db_factory: Any, execution_id: int, *,
                         on_set: Any = None) -> tuple[dict, "asyncio.Task"]:
    """C11 取消轮询器(cases / graph 两链共用):DB 位 → 局部标志(0.5s 节拍)。

    返回 ``(cancel_local, task)``;``cancel_local["set"]`` 由消费点同步读,
    ``cancel_local["done"]`` 由调用方收尾置位。``on_set`` 在首次置位时
    调一次(graph 链据此向执行器下发 scope=unit 取消)。
    """
    from . import execution_queue as _eq

    cancel_local = {"set": False, "done": False}

    async def _poll_cancel() -> None:
        while not cancel_local["done"]:
            try:
                async with db_factory() as s:
                    if await _eq.is_cancel_requested(s, execution_id):
                        cancel_local["set"] = True
                        if on_set is not None:
                            try:
                                on_set()
                            except Exception:  # noqa: BLE001
                                logger.exception(
                                    "run_dispatcher: cancel on_set 回调异常 {}",
                                    execution_id)
                        return
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(0.5)

    return cancel_local, asyncio.create_task(_poll_cancel())


def _legacy_unit_cancel_capable() -> bool:
    """legacy 链(单子进程)是否具备单元级取消(--cancel-file 通道)。

    legacy 链没有 HTTP 面,无法运行期探测:GIMBAL_BIN 未设置(默认同解释器
    ``-m gimbal``,引擎与本进程同安装)时读本地 gimbal 包的 FEATURES 声明;
    GIMBAL_BIN 指向外部安装 → 无法探测,保守 False(旧引擎不认 --cancel-file
    参数会启动失败,宁可 409 也不下发)。
    """
    if settings.GIMBAL_BIN:
        return False
    try:
        from gimbal.version import FEATURES
    except Exception:  # noqa: BLE001 — 本地无 gimbal 包(异常部署)按无能力
        return False
    return "cancel-file" in FEATURES


async def _record_unit_cancel(db_factory: Any, execution_id: int,
                              capable: bool) -> None:
    """把「本执行是否具备单元级取消」写进 job payload(台账性质,写失败
    只告警不阻断 —— 失败时能力位缺失,读侧按各自缺省口径处理)。"""
    from sqlalchemy import select as _sel

    from ..models.execution import ExecutionJob
    try:
        async with db_factory() as session:
            job = (await session.execute(
                _sel(ExecutionJob).where(
                    ExecutionJob.execution_id == execution_id))
            ).scalar_one_or_none()
            if job is None:
                return
            payload = dict(job.payload or {})
            payload["unit_cancel"] = bool(capable)
            job.payload = payload
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: record unit_cancel flag failed for {}",
            execution_id)


async def _fanout_graph(
    *,
    db_factory: Any,
    execution_id: int,
    run_id: str,
    owner_id: int,
    graph_spec: dict,
    n_runs: int = 1,
    halt_at: int | None = None,
    scenario_payload: dict | None = None,
    chain: str = "legacy",
    env_snapshot: dict | None = None,
) -> None:
    """C5(P3-05):graph 编排执行链 —— 物化 SuiteGraph → 单 spawn →
    事件投影台账(与单场景链同读面;乘法/并发/横切面在执行器)。
    C12/C13：chain=server 时 spawn 走执行器 server 实例。

    取消(graph 单元级取消方案 2026-11-02 P2 + §6「可」项/legacy 通道
    2026-11-03):取消轮询器置位后 ——
    ① 物化完成、下发执行器之前命中 → 不下发,canceled 零计数收口;
    ② 在飞 → 按链下发单元级取消:server 链向执行器 ``cancel(scope="unit")``
    (runId 返回前每 0.5s 重试);legacy 链写 ``--cancel-file`` 信号文件
    (执行器 drain)。两链同语义:在飞单元跑完、未启动主体记 cancelled、
    after 照常;收口时至少一个主体单元 cancelled → 执行记 canceled,否则
    按真实结果收口并在 config 写 ``cancelIgnored`` 留痕。
    能力门禁:spawn 期探测并落 ``job payload["unit_cancel"]`` —— server 链
    读 healthz cancel_scopes(旧执行器空能力,不下发,读侧 409);legacy 链
    读本地 gimbal FEATURES(GIMBAL_BIN 外部安装保守 False)。取消落在执行器
    启动窗口时总是先创建下发任务,session 就绪后按能力位决定发或停(评审
    2026-11-03 §3.1)—— 旧执行器停发并留痕 cancelIgnored=executor_no_unit_cancel。
    """
    from . import execution_queue as _eq
    from . import graph_dispatch
    from .graph_dispatch import GraphDispatchError

    ingester = _EventIngester(db_factory, execution_id)
    await ingester.seed_from_db()   # P3.5-2：恢复重跑事件 seq 续接
    ingester.start()

    run_dir = _run_dir(run_id)
    log_path = _jsonl_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # P3 收尾(graph 恢复策略 = at-most-once):graph 执行整图一个 run,
    # 恢复重跑必然整图重放,对被测系统重复全部副作用不可接受 → 已开跑
    # (存在事件)的恢复直接 failed 收口、不重跑。cases 链是行级断点
    # (P3.5-2),只有中断行重跑 —— 恢复语义对照见路线图 P3.5。
    from sqlalchemy import func as _f, select as _sel

    from ..models.execution import ExecutionEvent as _EV
    try:
        async with db_factory() as session:
            _prior = (await session.execute(
                _sel(_f.count()).select_from(_EV)
                .where(_EV.execution_id == execution_id))).scalar()
    except Exception:  # noqa: BLE001 — 查询失败按无进度处理(可重跑)
        _prior = 0
    if _prior:
        logger.warning(
            "run_dispatcher: graph execution {} recovered with {} prior "
            "events → failed (at-most-once, no graph replay)",
            execution_id, _prior)
        from ..models.execution import ExecutionRow

        finished_ts = _utcnow().isoformat() + "Z"
        _row_states[execution_id] = []
        try:
            from sqlalchemy.exc import IntegrityError as _IE

            async with db_factory() as session:
                session.add(ExecutionRow(
                    execution_id=execution_id, seq=0,
                    unit_id="graph", branch="graph", attempts=1,
                    status="failed", case_dir="case-graph",
                    started_at=None, finished_at=_iso_to_dt(finished_ts)))
                try:
                    await session.commit()
                except _IE:
                    await session.rollback()
                    from sqlalchemy import update as _u

                    await session.execute(
                        _u(ExecutionRow)
                        .where(ExecutionRow.execution_id == execution_id,
                               ExecutionRow.seq == 0)
                        .values(status="failed",
                                finished_at=_iso_to_dt(finished_ts)))
                    await session.commit()
        except Exception:  # noqa: BLE001
            pass
        # N2:恢复收口改经唯一终态迁移(原子守卫 + failed 通知 ——
        # 此前静默,N2-2 拍板补发);P0-3.2:改带重试版
        await transition_with_retry(
            db_factory, execution_id, STATUS_FAILED,
            dispatcher_error=(
                f"graph recovery: at-most-once 收口"
                f"({_prior} prior events, 不整图重放)"))
        await ingester.finalize()
        return

    # 取消轮询器只在真正要下发的路径上启动:上面的恢复分支在 try/finally
    # 之前返回,_teardown 不会执行 —— 若在此之前启动,轮询任务会一直查库到
    # 进程退出(恢复后执行已 failed,取消位永远不会置上)。
    session_holder: dict = {}
    deliver: dict = {"task": None, "accepted": False}
    # 单元级取消能力:server 链 session 就绪时按 healthz 能力位填 ok 并落
    # job payload(旧执行器 False → 不下发,读侧按能力位 409);legacy 链
    # spawn 前按本地 FEATURES 判定,ok 时才有信号文件可写。
    unit_cancel: dict = {"ok": chain != "server" and _legacy_unit_cancel_capable(),
                         "recorded": chain != "server"}
    cancel_file: "Path | None" = (
        run_dir / "case-graph" / "cancel-unit"
        if chain != "server" and unit_cancel["ok"] else None)

    async def _deliver_unit_cancel() -> None:
        # 执行器受理前每 0.5s 重试:POST /runs 可能尚未返回 runId(cancel()
        # 返回 False);执行已结束(done)则停。能力检查在 session 就绪后做
        # (取消可能先于 session 到达):旧执行器(cancel_scopes 无 unit)
        # 停止下发 —— 读了也会被当 step 处理(带 A0 缺陷),按真实结果
        # 收口并留痕 cancelIgnored=executor_no_unit_cancel。
        while not cancel_local["done"]:
            ss = session_holder.get("ss")
            if ss is not None:
                if not unit_cancel["ok"]:
                    logger.info(
                        "run_dispatcher: graph execution {} executor lacks "
                        "unit cancel scope; cancel not delivered", execution_id)
                    return
                try:
                    if await ss.cancel(scope="unit"):
                        deliver["accepted"] = True
                        logger.info(
                            "run_dispatcher: graph execution {} unit-level cancel "
                            "accepted by executor", execution_id)
                        return
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(0.5)

    def _on_cancel_set() -> None:
        if chain == "server":
            # 总是创建下发任务(评审 2026-11-03 §3.1):取消可能落在执行器
            # 启动窗口(ss.start 轮询 healthz 期间,on_session 未回调、能力位
            # 未落定),此时若按能力位拦截,轮询器命中一次即 return,能力位
            # 后来转 True 也无人再触发下发 —— 取消被接受却静默跑完。
            # 旧执行器的拦截挪进 _deliver_unit_cancel(session 就绪后判)。
            if deliver["task"] is None:
                deliver["task"] = asyncio.create_task(_deliver_unit_cancel())
        elif cancel_file is not None:
            try:
                cancel_file.parent.mkdir(parents=True, exist_ok=True)
                cancel_file.write_text("", encoding="utf-8")
                logger.info(
                    "run_dispatcher: graph execution {} unit-level cancel "
                    "signal file written ({})", execution_id, cancel_file)
            except OSError:
                logger.warning(
                    "run_dispatcher: write cancel file failed for {} ({})",
                    execution_id, cancel_file)

    def _on_session(ss: Any) -> None:
        session_holder["ss"] = ss
        capable = "unit" in (getattr(ss, "cancel_scopes", ()) or ())
        unit_cancel["ok"] = capable
        if not unit_cancel["recorded"]:
            unit_cancel["recorded"] = True
            asyncio.create_task(
                _record_unit_cancel(db_factory, execution_id, capable))

    cancel_local, cancel_poller = _start_cancel_poller(
        db_factory, execution_id, on_set=_on_cancel_set)

    def _teardown() -> None:
        # 进程内快速通道也算命中(写位与轮询之间的窗口),再出清
        if execution_id in _eq._cancel_hint:
            cancel_local["set"] = True
        cancel_local["done"] = True
        cancel_poller.cancel()
        if deliver["task"] is not None:
            deliver["task"].cancel()
        _eq._cancel_hint.discard(execution_id)

    # 逐单元事件投影(重构方案第 3 处):unit → {started_at, finished_at,
    # status};blocked/cancelled 单元不发事件,从 run.finished.details 按
    # unit id 补齐。总状态不再取「最后一个 scenario.end」—— 后置通过
    # 会覆盖主体失败、判定门失败只改 exit_code 会被吞。
    unit_events: dict[str, dict] = {}
    proj = {"attempts": 0, "gates": None}
    status = "failed"
    result = None
    graph_sem: dict = {}
    try:
        async with db_factory() as session:
            from .env_chain import EnvChoice
            graph_bundle = await graph_dispatch.materialize_graph(
                session, owner_id, graph_spec, full=True,
                env=EnvChoice.from_snapshot(env_snapshot))
        graph = graph_bundle["graph"]
        graph_sem = graph_bundle
        if cancel_local["set"] or execution_id in _eq._cancel_hint:
            # ① 物化窗口取消:执行仍 queued、取消位已写 —— 不下发执行器,
            # 走「启动前取消」口径(canceled、零计数;finally 收尾 ingester/轮询)
            logger.info("run_dispatcher: graph execution {} canceled after "
                        "materialize, before dispatch", execution_id)
            # 与 finalize_canceled_before_start 同形:不回填 started_at(从未
            # 启动),不发通知;_finalize_execution 会无条件回填 now,不用它
            await transition_with_retry(db_factory, execution_id, STATUS_CANCELED)
            _row_states.pop(execution_id, None)
            return
        await _mark_running(db_factory, execution_id)
        # B-1(2026-10-13):suite 执行接入版本模型 —— 台账三件套与单场景
        # dispatcher 同点写(pins 来自成员声明合并[R25 已统一到交集生效
        # 修订],baseline 判定输入同口径;m2_hash 取 /convert 附带身份,
        # 随台账一次写)。台账性质:判定/写库失败不阻断执行。
        # b2-3/b2-4/b2.5:追溯台账(PIN ∪ INTEGRATION)+ integration 标识
        # 补取,均抽为 run_semantics 可测函数(补取只进台账,不动执行副本)
        from . import run_semantics as _rs_g
        _g_pins = await _rs_g.graph_pins_with_identity(
            {k: v for k, v in (graph_sem.get("meta_plate") or {}).items()
             if v and ref_category(v) in (PIN, INTEGRATION)},
            plate_client.resolve)
        _g_baseline = None
        try:
            from . import run_semantics
            async with db_factory() as _g_sem_s:
                _g_baseline = await run_semantics.assess_baseline(
                    _g_sem_s,
                    meta_plate=graph_sem.get("meta_plate") or {},
                    endpoints_used=graph_sem.get("endpoints_used") or {},
                    unanchored_services=(
                        graph_sem.get("unanchored_services") or []))
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning(
                "run_dispatcher: graph 入库标准判定失败 (execution={})",
                execution_id)
        _g_m2 = (graph_sem.get("m2_info") or {}).get("hash")
        if _g_pins or _g_baseline is not None or _g_m2:
            try:
                from sqlalchemy import update as sa_update
                _g_values: dict = {}
                if _g_pins:
                    _g_values["plate_pins"] = _g_pins
                if _g_m2:
                    _g_values["m2_hash"] = str(_g_m2)
                if _g_baseline is not None:
                    _g_values["baseline_eligible"] = _g_baseline[0]
                    _g_values["baseline_block"] = _g_baseline[1]
                    _g_values["baseline_evidence"] = _g_baseline[2] or None
                async with db_factory() as _g_pin_sess:
                    await _g_pin_sess.execute(
                        sa_update(Execution)
                        .where(Execution.id == execution_id)
                        .values(**_g_values))
                    await _g_pin_sess.commit()
            except Exception:  # noqa: BLE001
                logger.warning(
                    "graph plate_pins 回填失败 (execution={})", execution_id)

        def _on_event(d: dict) -> None:
            et = d.get("event_type")
            if et == "scenario.start":
                u = d.get("unit")
                if u:
                    unit_events.setdefault(u, {}).setdefault(
                        "started_at", d.get("timestamp"))
            elif et == "scenario.end":
                u = d.get("unit")
                if u:
                    e = unit_events.setdefault(u, {})
                    e["finished_at"] = d.get("timestamp")
                    e["status"] = d.get("status")
            elif et == "gates.evaluated":
                # 第 4 处:执行器结构化判定门结论 → 落执行记录
                proj["gates"] = {"gates": d.get("gates") or [],
                                 "passed": bool(d.get("passed"))}
            elif et == "run.finished":
                proj["attempts"] = int(d.get("attempts") or 0)
                details = d.get("details")
                if isinstance(details, list):
                    for row in details:
                        if not isinstance(row, dict):
                            continue
                        uid = row.get("unit") or row.get("unit_id")
                        st = row.get("status")
                        if (uid and st in ("blocked", "canceled",
                                           "cancelled", "halted")
                                and uid not in unit_events):
                            unit_events[uid] = {"status": st}
            ingester.on_event(d)

        if chain != "server":
            # legacy 链能力位在 spawn 前落库(server 链在 on_session):
            # cancel 端点读 job payload 判定,晚于首次取消会白拒一次。
            await _record_unit_cancel(db_factory, execution_id, unit_cancel["ok"])
        result = await graph_dispatch.execute_graph(
            db_factory, execution_id, run_dir, graph,
            on_event=_on_event, on_log=ingester.on_log,
            log_counters=ingester.pump_counters, chain=chain,
            m2_info=graph_sem.get("m2_info"),
            on_session=_on_session, cancel_file=cancel_file)
        if result.launch_status == "ok":
            # 总状态由 run.finished 的 exit_code 推导(重构方案第 3 处):
            # 判定门不通过只改退出码,按 scenario.end 取总状态会吞掉
            status = "passed" if result.exit_code == 0 else (
                "gimbal_rejected" if result.exit_code == 2 else "failed")
        else:
            status = ("launch_timeout"
                      if result.launch_status == "timeout" else "launch_error")
    except GraphDispatchError as e:
        logger.error("run_dispatcher: graph materialize failed {}: {}",
                     execution_id, e)
        status = "plate_rejected"
    except Exception as e:  # noqa: BLE001
        logger.exception("run_dispatcher: graph fanout crashed {}", execution_id)
        status = "dispatcher_error"
    finally:
        await ingester.finalize()
        _teardown()

    # ② 取消收口判定(方案 §2):取消位命中且至少一个**主体**单元被执行器记
    # cancelled → 执行 canceled;命中但主体已全部启动/结束(没有单元可停)
    # → 按真实结果收口,config.cancelIgnored 留痕供详情页解释。
    main_refs = [u.get("ref") for u in graph_spec.get("units", []) if u.get("ref")]

    def _is_main(uid: str) -> bool:
        return any(uid == r or uid.startswith(r + "#") for r in main_refs)

    main_cancelled = any(
        ev.get("status") in ("cancelled", "canceled") and _is_main(uid)
        for uid, ev in unit_events.items())
    final_status: str | None = None
    cancel_ignored: str | None = None
    if cancel_local["set"] and result is not None:
        if main_cancelled:
            status = "canceled"
            final_status = STATUS_CANCELED
        elif chain == "server" and not unit_cancel["ok"]:
            # 旧执行器(cancel_scopes 无 unit):取消被读侧接受(启动窗口
            # 能力位未落定)但未下发 —— 与「所有单元已启动」区分留痕,
            # 读侧 cancel_note 给对应解释。
            cancel_ignored = "executor_no_unit_cancel"
        else:
            cancel_ignored = "all units already started"

    # 台账(重构方案第 3 处):seq=0 图行(与 at-most-once 恢复路径同形)
    # + seq=1..n 逐单元行(按物化单元清单顺序;×重复变体按 unit 标签
    # `ref#k` 追加在基座 ref 之后)。无事件且无 details 的单元按
    # blocked 记(被 control.only 裁剪 / 未跑)。
    finished_ts = _utcnow().isoformat() + "Z"
    _row_states[execution_id] = []   # 无行级 registry;读侧回落 DB
    from ..models.execution import ExecutionRow
    ordered_units: list[tuple[str, dict]] = []
    for u in [*graph_spec.get("before", []),
              *graph_spec.get("units", []),
              *graph_spec.get("after", [])]:
        ref = u.get("ref")
        if not ref:
            continue
        evs = sorted(
            ((k, v) for k, v in unit_events.items()
             if k == ref or k.startswith(ref + "#")),
            key=lambda kv: kv[0])
        if not evs:
            evs = [(ref, {"status": "blocked"})]
        ordered_units.extend(evs)
    attempts_total = proj["attempts"] or int(
        getattr(result, "attempts", 0) or 0) or 1
    rows_to_write: list[dict] = [
        {"seq": 0, "unit_id": "graph", "status": status,
         "attempts": attempts_total}]
    for idx, (uid, ev) in enumerate(ordered_units, start=1):
        rows_to_write.append({
            "seq": idx, "unit_id": uid,
            "status": ev.get("status") or "blocked",
            "attempts": 1,
            "started_at": _iso_to_dt(ev["started_at"])
            if ev.get("started_at") else None,
            "finished_at": _iso_to_dt(ev["finished_at"])
            if ev.get("finished_at") else None,
        })
    try:
        from sqlalchemy.exc import IntegrityError

        async with db_factory() as session:
            for r in rows_to_write:
                session.add(ExecutionRow(
                    execution_id=execution_id, seq=r["seq"],
                    unit_id=r["unit_id"], branch="graph",
                    attempts=r["attempts"], status=r["status"],
                    case_dir="case-graph",
                    started_at=r.get("started_at"),
                    finished_at=r.get("finished_at")
                    or _iso_to_dt(finished_ts)))
            try:
                await session.commit()
            except IntegrityError:
                # P3.5-2:job 重跑 graph 执行 —— 行 upsert(恢复时 graph
                # 整图重放,事件 seq 已由 ingester 续接)
                await session.rollback()
                from sqlalchemy import update as _upd

                for r in rows_to_write:
                    await session.execute(
                        _upd(ExecutionRow)
                        .where(ExecutionRow.execution_id == execution_id,
                               ExecutionRow.seq == r["seq"])
                        .values(status=r["status"], unit_id=r["unit_id"],
                                attempts=r["attempts"],
                                finished_at=r.get("finished_at")
                                or _iso_to_dt(finished_ts)))
                await session.commit()
    except Exception:  # noqa: BLE001
        pass
    # 计数与终态(计数按单元累加;blocked/cancelled 入 skipped)
    n_pass = sum(1 for _, ev in ordered_units if ev.get("status") == "passed")
    n_fail = sum(1 for _, ev in ordered_units
                 if ev.get("status") in ("failed", "error", "halted"))
    await _bump_counters(db_factory, execution_id,
                         passed=n_pass,
                         failed=n_fail,
                         skipped=max(len(ordered_units) - n_pass - n_fail, 0))
    cfg_patch: dict = {}
    if proj.get("gates"):
        # 判定门结论(第 4 处):经事件通道落 config_json,21 页实测值来源
        cfg_patch["gatesEvaluated"] = proj["gates"]
    if cancel_ignored:
        cfg_patch["cancelIgnored"] = cancel_ignored
    if cfg_patch:
        try:
            async with db_factory() as session:
                ex = await session.get(Execution, execution_id)
                if ex is not None:
                    cfgj = dict(ex.config_json or {})
                    cfgj.update(cfg_patch)
                    ex.config_json = cfgj
                    await session.commit()
        except Exception:  # noqa: BLE001 — 结论留档 best-effort
            pass
    await _finalize_execution(db_factory, execution_id, status=final_status)


async def _fanout(
    *,
    db_factory: Any,
    execution_id: int,
    run_id: str,
    scenario_payload: dict,
    datasets: list[dict],
    injections: list[dict | None] | tuple = (),
    owner_id: int,
    auth_aliases: list[str],
    halt_at: int | None = None,
    n_runs: int = 1,
    parallel: int = 1,
    service_bindings: dict[str, ServiceBinding] | None = None,
    chain: str = "legacy",
    debug: "dict | None" = None,
    scenario_owner_id: int | None = None,
    env_snapshot: dict | None = None,
) -> None:
    """Per-row × per-repeat compose + convert + 执行器调用（双链）。

    ``env_snapshot``(S2.1):dispatch 落档的环境选择(与 config_json 同
    一份快照;旧配方缺键 = 无环境 = 旧 ③ 行为)。

    ``halt_at``(V1 step_to 移植):0-based 含端点,透传 CLI
    ``--step-to`` —— RuntimeControl 在该步后停(剩余步显示 skipped)。

    C12/C13 双链:``chain``（legacy|server）——legacy 落盘 case 后
    ``gimbal run launch`` 子进程（stdout jsonl）；server 为本次执行
    持有一个执行器 server 实例（POST /runs + SSE 消费），取消走
    cancel 端点，结束 terminate 进程树。``debug``（C6）强制 server 链
    且单 case；会话注册进 ``debug_sessions`` 供平台调试台代理。

    C11 取消：DB 位（execution_jobs.cancel_requested）→ 本函数的取消
    轮询器写入局部标志 → 行边界消费（未跑行记 canceled 不进计数器）。

    spec v3 §8:``injections`` 为选中的断言注入条目(dispatch 已过滤死/
    旧条目)— 与数据集行交叉(spec v3 §4:行 × 条目 × repeat 笛卡尔),
    每 case 先行值合入 vars,再在 definition 层经
    ``compose_injection_scenario`` patch(Assign 直补 + asserts patch,
    不触碰 config.vars)后走 plate convert,``materialize_run_copy``
    其后照旧。
    """
    from . import execution_queue as _eq

    # C11 取消轮询器:DB 位 → 局部标志(0.5s 节拍;行边界同步读)
    cancel_local, cancel_poller = _start_cancel_poller(db_factory, execution_id)

    async def _teardown() -> None:
        """fanout 收尾：停取消轮询、回收 server 实例、注销调试会话。"""
        cancel_local["done"] = True
        cancel_poller.cancel()
        if server_pool is not None:
            try:
                await server_pool.close()
            except Exception:  # noqa: BLE001
                pass
        debug_sessions.pop(execution_id, None)
        _eq._cancel_hint.discard(execution_id)
        _row_states.pop(execution_id, None)

    # C12/P3.5-1:server 链/调试 —— 并发槽位实例池(引擎 /runs 单 run
    # 设计,并发第二个 POST 直接 409;多行 × parallel>1 须每槽位一实例。
    # 单行/调试退化为单实例语义)
    server_pool = None
    if chain == "server" or debug is not None:
        from .gimbal_server_session import ServerSessionPool
        _total_rows = (sum(len(ds["rows"]) for ds in datasets)
                       * len(list(injections) or [None]))
        # P3 收尾:全局上限钳制 —— parallel 可到 MAX_RUNS_PER_EXECUTION,
        # 不钳制会一次冷启动上百个引擎进程(行排队等空闲槽位)
        _slots = (1 if debug is not None
                  else max(1, min(int(parallel or 1), _total_rows or 1,
                                  settings.EXEC_MAX_SERVER_INSTANCES)))
        server_pool = ServerSessionPool(size=_slots)
    # P2-02/C2:执行器事件/日志流式入库(launcher on_event/on_log →
    # 缓冲 → 批量 execution_events;读侧 SSE/日志分析页共用)
    ingester = _EventIngester(db_factory, execution_id)
    await ingester.seed_from_db()   # P3.5-2：恢复重跑事件 seq 续接
    ingester.start()
    log_path = _jsonl_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # 每个 run 一个 case 目录:case 文件 + 引擎原生报告,并发 fan-out
    # 互不互踩;与 JSONL 同域构成执行审计面(什么数据真的打给了引擎)。
    run_dir = _run_dir(run_id)
    if server_pool is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        # C12:执行级 server 池槽位 0(reports 落 run_dir,引擎 reporter 相对
        # server 进程 cwd 写;调试实例在 debug_sessions 注册供代理)。
        # P3.5-1:槽位 1..N-1 在行执行按需冷启动(锁外并行)
        try:
            await server_pool.start(
                engine_log_path=run_dir / "server-engine.log", cwd=run_dir,
                on_log=ingester.on_log,   # AD2:stderr 泵 → 本执行 ingester
                log_counters=ingester.pump_counters)  # S9:泵侧丢弃计数
        except Exception as e:  # noqa: BLE001
            await _teardown()
            # 池启动失败但 ingester 已 start(含启动期可能入缓冲的行):
            # finalize 收口,否则 ticker 任务泄漏(0.5s 周期冲刷永不停止)。
            await ingester.finalize()
            raise
        if debug is not None:
            debug_sessions[execution_id] = {"session": server_pool.first}

    # 执行用认证:owner 级解密一次,逐行注入 run 副本的 Config.users。
    # 解密失败 = fail-fast(V1 严格语义):整单 execution 记为
    # failed,所有行计入 failed 计数,不带着空/坏凭证打环境。
    try:
        # 注入清单为空(无 ${auth.*} 扫描引用、无绑定 authAlias)时
        # 直接跳过解析。
        exec_auths = (
            await resolve_exec_auths(db_factory, owner_id, auth_aliases)
            if auth_aliases
            else []
        )
    except AuthResolveError as e:
        logger.error(
            "run_dispatcher: auth resolve failed for execution {}: {}",
            execution_id, e,
        )
        total_rows = (sum(len(ds["rows"]) for ds in datasets)
                      * len(injections or [None]))
        # §7 顺序不变量在异常路径同样成立:先排空泵(关池)再冲刷 ingester,
        # 最后才写终态 —— server 启动期已入缓冲的日志行不丢、ticker 不泄漏。
        if server_pool is not None:
            try:
                await server_pool.close()
            except Exception:  # noqa: BLE001
                pass
        await ingester.finalize()
        await _fail_whole_execution(
            db_factory, log_path, execution_id=execution_id, run_id=run_id,
            total_rows=total_rows, error=str(e),
        )
        await _teardown()
        return

    # 认证解析通过、即将分发行 → queued 置 running(UI 可见"在跑")。
    await _mark_running(db_factory, execution_id)

    sem = asyncio.Semaphore(max(1, parallel))

    # P6:整单固定一次 compose 时间戳 — deepcopy 隔离存储 payload(防写穿
    # ORM 行),同一行 n_runs 次重复的 convert 输入完全一致, memo 键才能命中。
    scenario_payload = copy.deepcopy(scenario_payload)

    # N1(2026-11-01):装载准备归一 —— 别名 base_url 预解析(F4 方案 B,
    # 查表失败降级空表)、RS3 生效修订解析(plate_client.resolve +
    # merge_resolve_effective;plate_rejected/plate_unavailable 异常
    # 拓扑不变)、内置 users 基座、carry 预解析(M4:field_states 增量在
    # payload.ui.fieldStates)统一走 run_prepare.prepare_exec。认证已在
    # 上方先行 fail-fast 解析(with_auth=False 跳过重复解密);deepcopy
    # 先行 —— 修订回写落在副本上,不写穿存储 payload。
    _ui_fs = ((scenario_payload or {}).get("ui") or {}).get("fieldStates") or {}
    from .env_chain import EnvChoice
    prep = await prepare_exec(
        db_factory, scenario_payload, owner_id=owner_id,
        ui_field_states=_ui_fs, resolve_mode="single", with_auth=False,
        scenario_owner_id=scenario_owner_id,
        environment=EnvChoice.from_snapshot(env_snapshot))

    # A-3/W7(版本模型 4.3):入库标准台账 —— 与 pins 同点写,判定/写库
    # 失败均不阻断执行(台账性质;留默认值 = 未判定)。
    baseline: tuple[bool, str | None, dict] | None = None
    try:
        from . import run_semantics
        async with db_factory() as _sem_s:
            baseline = await run_semantics.assess_baseline(
                _sem_s, meta_plate=prep.meta_plate,
                endpoints_used=prep.endpoints_used,
                unanchored_services=prep.unanchored_services)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning(
            'run_dispatcher: 入库标准判定失败 (execution={})', execution_id)
        baseline = None
    # RS3：生效修订表落库（dispatch 侧无引用可回填 —— job 经 DB
    # 队列异步驱动，在解析处就地写入；台账性质，失败不阻断执行）。
    if prep.plate_pins or baseline is not None:
        try:
            from sqlalchemy import update as sa_update
            async with db_factory() as _pin_sess:
                _values: dict = {}
                if prep.plate_pins:
                    _values['plate_pins'] = prep.plate_pins
                if baseline is not None:
                    _values['baseline_eligible'] = baseline[0]
                    _values['baseline_block'] = baseline[1]
                    _values['baseline_evidence'] = baseline[2] or None
                await _pin_sess.execute(
                    sa_update(Execution)
                    .where(Execution.id == execution_id)
                    .values(**_values))
                await _pin_sess.commit()
        except Exception:  # noqa: BLE001
            logger.warning(
                'plate_pins 回填失败 (execution={})', execution_id)

    # P6:fan-out 级 convert memo + plate 连续不可用熔断计数。
    convert_cache: dict[str, dict] = {}
    plate_state = {"consecutive_unavailable": 0}

    def _breaker_open() -> bool:
        return (
            plate_state["consecutive_unavailable"]
            >= settings.PLATE_BREAKER_THRESHOLD
        )

    # 内置认证(definition.config.users)是 users 合并的保留基座 —— plate
    # /convert 的产物可能剥掉平台视图字段,凭证合并不依赖 converted
    # 自带 users,而是以场景定义为源(与 V1 在原始 yaml 上渲染同语义)。
    # (N1:基座取值移入 run_prepare,此处消费 prep 产物)
    built_in_users = prep.built_in_users
    # serviceBindings 原样传给 materialize_run_copy(url 物化只对 steps
    # 实际引用的 service 键生效,见 run_materialize._apply_services)。
    service_bindings = service_bindings or {}

    # carry 预解析(spec §4.1):dispatch 阶段一次,run 内快照一致 —
    # 绑定/契约编辑的生效边界是下次执行。构建在 run_prepare 内完成
    # (plate 故障在 build 内部降级空面;DB 故障降级为无 carry)——
    # carry 是增强不是前置条件,任何故障都不阻塞执行。
    carry_ctx = prep.carry_ctx

    async def _row(ds: dict | None, row_idx: int, row: dict | None, rep: int,
                   seq: int, injection: dict | None = None) -> None:
        """One (dataset row × injection entry) cross entry —
        compose + convert + launch(乘法经 --n-runs 下沉执行器)。
        ``row_idx`` 是编辑器原始行号
        (``rows`` 携带 (原始行号, 行字典) 对,稀疏选择不重排)。"""
        state = row_states[seq]
        _prev = done_rows.get(seq)
        if _prev is not None:
            # P3.5-2 恢复跳过:沿用首次尝试的终态(registry 读侧一致),
            # 不重跑、不重计数
            state.status = _prev
            return
        # P2-04:本行事件投影器(所有路径可安全读;无事件路径恒空)
        proj = {"unit": None, "status": None, "attempts": 0}
        result = None   # launch 产物(plate 异常路径无 launch → None)
        injection_id = (injection or {}).get("id")
        ds_id = ds["datasetId"] if ds is not None else None
        # 日志定位标签:数据集行用 datasetId,注入族用条目 id,基线行 baseline。
        row_src = ds_id or injection_id or "baseline"
        async with sem:
            # P4 协作式取消:行边界在信号量准入处(全部行 task 在 fanout
            # 启动时就已创建并排队,准入前检查永远看不到晚到的取消请求)。
            # 已准入的行视为在飞、自然跑完;排队中的行在准入时刻检查,
            # 未启动的直接记 canceled,不进计数器。
            if cancel_local["set"] or execution_id in _eq._cancel_hint:
                # (hint = 路由同进程写入的取消快速通道;轮询器 0.5s 节拍
                # 之内也能即刻收敛)M6:行终态(canceled 含)即落库;行级
                # JSONL 停写(运行级生命周期行保留为运维审计面)。
                state.status = "canceled"
                state.finished_at = _utcnow().isoformat() + "Z"
                await _persist_row_terminal(db_factory, execution_id, state)
                return
            # 交叉组合序(spec v3 §3):行值合入(vars)→ 条目 Assign 直补
            # + asserts patch — 偏离最后生效。基线/无行维度 = 空行字典。
            row_dict = dict(row or {})
            composed = compose_scenario(scenario_payload, row_dict)
            if injection is not None:
                composed = compose_injection_scenario(composed, injection)
            # 每个 case 独立子目录:case.json(数据驱动用例快照)+ 引擎
            # 原生报告目录;stem 带 dataset/row/rep 定位,便于事后审计。
            # stem 三定位(spec v3 §4 审计):数据集(或 baseline)+ 行号
            # + 条目 id(无注入省略)+ rep,如 case-003-ds-x-r1-inj-inj-2-n0。
            stem = (
                f"case-{seq:03d}-{ds['datasetId'] or 'baseline'}-r{row_idx}"
                + (f"-inj-{injection_id}" if injection_id else "")
                + f"-n{rep}"
            )
            case_dir = run_dir / stem
            ts = _utcnow().isoformat() + "Z"
            log_line = {
                "ts": ts,
                "runId": run_id,
                "executionId": execution_id,
                "seq": seq,
                "scenarioId": composed.get("scenarioId"),
                "datasetId": ds_id,
                "injectionId": injection_id,
                "rowIndex": row_idx,
                "rep": rep,
                "status": "dispatched",
                "casePath": str((case_dir / "case.json")),
                "reportDir": str((case_dir / "reports")),
            }
            state.status = "dispatched"
            state.started_at = ts

            try:
                if _breaker_open():
                    # 熔断开路:不再调用 plate,行快速失败(落到下方
                    # 公共尾部:记日志行 + failed 计数)。
                    log_line["status"] = "plate_unavailable"
                    log_line["error"] = (
                        "plate circuit open: "
                        f"{plate_state['consecutive_unavailable']} "
                        "consecutive unavailable"
                    )
                else:
                    cache_key = _convert_cache_key(composed)
                    if cache_key in convert_cache:
                        # 防御性深拷贝:materialize_run_copy 虽是纯函数,
                        # 任何未来的原地注入仍不得污染缓存共享引用。
                        convert_data = copy.deepcopy(convert_cache[cache_key])
                    else:
                        convert_data = await plate_client.convert(composed)
                        # 入缓存的是物化前原始快照(注入只进 run 副本)。
                        convert_cache[cache_key] = copy.deepcopy(convert_data)
                    plate_state["consecutive_unavailable"] = 0
                    # Convert succeeded — hand the gimbal-shaped product to the
                    # engine. 明文 users 只进 run 副本(convert 那份不带,防明文
                    # 流进 plate 校验/日志);注入形状同 V1 executor 生产路径。
                    # convert_data = {consumer, converted};converted 是
                    # GimbalScenarioExporter 的产物(已剥平台视图扩展字段)。
                    converted = convert_data.get("converted") or {}
                    # M2 §5.1:/convert 响应附带的构建身份 → 转交执行器（代际门）
                    m2_info = convert_data.get("m2") or None
                    # W21/挂账二.1:M2 构建身份派发回填 —— 身份落
                    # executions.m2_hash(整执行同源,首行一次;台账性质,
                    # 失败不阻断执行)。
                    if (m2_info and m2_info.get("hash")
                            and not plate_state.get("m2_hash_written")):
                        plate_state["m2_hash_written"] = True
                        try:
                            from sqlalchemy import update as sa_update
                            async with db_factory() as _m2_sess:
                                await _m2_sess.execute(
                                    sa_update(Execution)
                                    .where(Execution.id == execution_id)
                                    .values(m2_hash=str(m2_info["hash"])))
                                await _m2_sess.commit()
                        except Exception:  # noqa: BLE001
                            logger.warning(
                                "m2_hash 回填失败 (execution={})", execution_id)
                    # 物化 run 副本(纯函数,深拷贝 — 绝不原地改 converted):
                    # users 合并(内置基座 + 注入覆盖,固定 merge 语义)与
                    # services 物化(绑定 url > authored;env.baseUrl 补缺层
                    # 已随 D2 执行环境退役)。
                    composed_exec = materialize_run_copy(
                        converted,
                        service_bindings={
                            k: b.model_dump(by_alias=True)
                            for k, b in service_bindings.items()
                        },
                        resolved_auths=exec_auths,
                        built_in_users=built_in_users,
                        carry_context=carry_ctx,
                        alias_base_urls=prep.alias_base_urls,
                    )
                    # 落盘数据驱动用例快照后交给 CLI 子进程执行。
                    case_path = _write_case_file(case_dir, composed_exec)
                    # P7 全局并发闸:进程级 launch 在飞上限(跨 execution
                    # 合并生效;行级 sem 只管单 execution 的 parallel)。
                    if True:
                        # (C11:P7 全局 launch 闸退役——并发由 worker 数与
                        # 行级 sem 界定)P2-04 事件投影:本行的 scenario.end/run.finished
                        # 单独摘出(状态/attempts/unit 由此投影;无事件路径
                        # —— PlateMock/旧引擎 —— 回退 launch 结果推导)。
                        def _row_on_event(d: dict, _p=proj, _seq=seq) -> None:
                            et = d.get("event_type")
                            # B3:步骤结果按行归属(同场景多行的 unit 标签相同,
                            # 只能靠行号区分);insert_events 取走、不进 payload
                            if et == "step.end":
                                d = {**d, "row_seq": _seq}
                            if et == "scenario.end":
                                _p["status"] = d.get("status")
                                _p["unit"] = d.get("unit") or _p["unit"]
                            elif et == "run.finished":
                                # attempts 缺省(旧引擎)=0 → 行级回退 1
                                _p["attempts"] = int(d.get("attempts") or 0)
                                _p["unit"] = d.get("unit") or _p["unit"]
                            ingester.on_event(d)

                        if server_pool is not None:
                            # C12:server 链(调试恒走此链) —— SSE 事件同
                            # 一回调面;超时由 run_case 内部 cancel 收口。
                            # P3.5-1:实例经槽位池借还,parallel>1 的多行
                            # 各占一个实例,不再撞引擎单 run 409
                            result = await server_pool.run_case(
                                case_path, halt_at=halt_at, n_runs=n_runs,
                                debug=debug, on_event=_row_on_event,
                                m2_info=m2_info)
                            # B6:记下槽位——case-artifact 的引擎日志按它路由到
                            # server-engine[-N].log(多 worker 时不再 404)
                            state.server_slot = getattr(result, "server_slot", None)
                        else:
                            result = await gimbal_launcher.launch(
                                case_path,
                                step_to=halt_at,
                                report_dir=case_dir / "reports",
                                cwd=case_dir,
                                engine_log_path=case_dir / "engine.log",
                                on_event=_row_on_event,
                                on_log=ingester.on_log,
                                log_counters=ingester.pump_counters,
                                n_runs=n_runs,
                            )
                    log_line["runResult"] = result.run_result
                    if result.launch_status != "ok":
                        # 子进程层故障(超时 kill / spawn 失败):记失败但
                        # 不中断后续行(fan-out 永不因单行崩溃)。
                        log_line["status"] = (
                            "launch_timeout"
                            if result.launch_status == "timeout"
                            else "launch_error"
                        )
                        log_line["runError"] = result.error
                        logger.warning(
                            "run_dispatcher: launch {} for row {}/{}#{}: {}",
                            result.launch_status, row_src, row_idx, rep,
                            result.error,
                        )
                    elif proj["status"] is not None:
                        # P2-04:scenario.end 事件投影(执行器权威);
                        # passed 之外一律 failed(与 exit 判定同口径)
                        log_line["status"] = (
                            "passed" if proj["status"] == "passed" else "failed"
                        )
                        logger.info(
                            "run_dispatcher: row {}/{} projected by events: "
                            "unit={} status={} attempts={}",
                            row_src, row_idx, proj["unit"], proj["status"],
                            proj["attempts"],
                        )
                    elif result.exit_code == 0:
                        log_line["status"] = "passed"
                        logger.info(
                            "run_dispatcher: row {}/{}#{} executed: exit=0 passed={} failed={}",
                            row_src, row_idx, rep,
                            result.passed, result.failed,
                        )
                    elif result.exit_code == 2:
                        # 引擎 Scenario 校验拒绝(与 HTTP 422 同源)。
                        log_line["status"] = "gimbal_rejected"
                        log_line["runError"] = result.error
                        logger.warning(
                            "run_dispatcher: gimbal rejected row {}/{}#{}: {}",
                            row_src, row_idx, rep, result.error,
                        )
                    else:
                        # exit 1 = 测试失败(正常业务结果);>=3 = 引擎侧错误。
                        log_line["status"] = "failed"
                        log_line["runError"] = result.error
                        logger.info(
                            "run_dispatcher: row {}/{}#{} executed: exit={} passed={} failed={}",
                            row_src, row_idx, rep, result.exit_code,
                            result.passed, result.failed,
                        )
            except plate_client.PlateUnavailableError as e:
                plate_state["consecutive_unavailable"] += 1
                log_line["status"] = "plate_unavailable"
                log_line["error"] = str(e)
                logger.warning("run_dispatcher: plate unavailable for row {}/{}#{}: {}", row_src, row_idx, rep, e)
            except plate_client.PlateRejectedError as e:
                log_line["status"] = "plate_rejected"
                log_line["error"] = e.message
                log_line["errors"] = list(e.errors or [])
                logger.warning("run_dispatcher: plate rejected row {}/{}#{}: {}", row_src, row_idx, rep, e.message)
            except Exception as e:  # noqa: BLE001  defensive — never let a row kill the fan-out
                log_line["status"] = "dispatcher_error"
                log_line["error"] = repr(e)
                logger.exception("run_dispatcher: unexpected error row {}/{}#{}", row_src, row_idx, rep)

            # P1:引擎结果全量证据落盘(仅真实拿到 LaunchResult 的路径;
            # plate 异常分支不设 runResult,短路跳过)。
            if "runResult" in log_line:
                _write_result_evidence(case_dir, result, log_line["status"])

            # T7-Q1:final 行 ts 刷新为完成时刻 — log_line 的 ts 构造于
            # 派发时刻,沿用会让 JSONL 回放的 finishedAt == startedAt
            # (行时长恒为 0)。同一时刻写 registry,两读路口径一致。
            finished_ts = _utcnow().isoformat() + "Z"
            log_line["ts"] = finished_ts

            # 行终态落 registry(spec §9.1):完成时刻 + case stem(供
            # 工件端点)。M6:终态即落 DB(崩溃窗口不丢),行级 JSONL 停写。
            state.status = log_line["status"]
            state.finished_at = finished_ts
            state.case_dir = case_dir.name
            # P2-04/P2-05:单元列投影(unit 取事件标签;attempts 取
            # run.finished 单列,缺省回退 launch 解析值,再缺省 1)
            state.unit_id = proj["unit"] or "u"
            state.attempts = (
                proj["attempts"]
                or int(getattr(result, "attempts", 0) or 0)
                or 1
            )
            await _persist_row_terminal(db_factory, execution_id, state)

            # Atomic per-row counter bump.  Deltas (not absolute
            # write-backs) so concurrent rows and concurrent UI
            # deletions (MAX(0, col-1) SQL) compose correctly.
            passed = 1 if log_line["status"] == "passed" else 0
            # S5:引擎 run.finished 的 skipped 计数随行累加(plate 异常/
            # 校验拒绝分支无引擎结果,恒 0)
            row_skipped = (
                int(getattr(result, "skipped", 0) or 0)
                if "runResult" in log_line else 0
            )
            await _bump_counters(
                db_factory, execution_id, passed=passed, failed=1 - passed,
                skipped=row_skipped,
            )

            # P2-4(webhook 设计 v3 §5.5/D10):单 case 执行(行数为 1)
            # 在行完成处把提取产物脱敏后写进 ``config_json.outputs``
            # (唯一例外键,见 models.execution 注释)—— 终态迁移组装
            # 回调 payload 时读取;发生在 finalize/终态之前,顺序保证
            # 回调拿得到。多行执行不写、回调 outputs=null。best-effort:
            # 写失败只丢回调里的 outputs,不影响行/终态。
            if len(entries) == 1 and "runResult" in log_line:
                _outputs: dict = {}
                for _d in (getattr(result, "details", None) or []):
                    if (isinstance(_d, dict)
                            and isinstance(_d.get("outputs"), dict)):
                        _outputs.update(_d["outputs"])
                if _outputs:
                    await _store_single_case_outputs(
                        db_factory, execution_id, _outputs)

    # (dataset row × injection entry × repeat) 交叉笛卡尔积(spec v3 §4):
    # injections 已含 None 占位(未选条目时 = [None],恰一次无注入组合)。
    # rows 携带 (原始行号, 行字典) 对 — row_idx 即编辑器行号,稀疏选择
    # 不重排。seq 为 case 文件名里的全局序号(与 entries 顺序一致,
    # 单测可断言)。
    injections = list(injections) or [None]
    # P2-05:乘法下沉 —— n_runs 不再展开为行(repeat 维退役),单行一次
    # spawn 传 --n-runs/--retry 给执行器;entries = 行 × 注入族。
    entries = [
        (ds, row_idx, row, inj, 0)
        for ds in datasets
        for row_idx, row in ds["rows"]
        for inj in injections
    ]
    # P3.5-2:行级断点 —— 恢复场景(job 租约过期/重启回队重跑)先读已
    # 终态行,已完成的 seq 不再执行:不重复打被测系统、不重复计数
    # (行落库先于计数 bump → DB 存在的行必已计数,跳过即无重复)。
    # DB 只落终态行(_persist_row_terminal),存在即终态;首次运行空集。
    done_rows: dict[int, str] = {}
    try:
        from sqlalchemy import select as _sel_row

        from ..models.execution import ExecutionRow as _ER
        async with db_factory() as session:
            _existing = (await session.execute(
                _sel_row(_ER.seq, _ER.status)
                .where(_ER.execution_id == execution_id))).all()
        done_rows = {int(s): st for s, st in _existing
                     if st in _FINAL_STATUSES}
    except Exception:  # noqa: BLE001 — 查询失败按无断点处理(全量重跑)
        done_rows = {}
    # spec §9.1:组完全部行任务后初始化行状态 registry(全部 queued;
    # _row 内逐行推进,执行终态化时整体 pop → 读侧回落 JSONL 回放)。
    row_states = _row_states[execution_id] = [
        RowState(
            seq=seq,
            dataset_id=ds["datasetId"] if ds is not None else None,
            row_index=row_idx,
            rep=rep,
            status="queued",
            injection_id=(inj or {}).get("id"),
        )
        for seq, (ds, row_idx, _, inj, rep) in enumerate(entries)
    ]
    try:
        try:
            await asyncio.gather(
                *(_row(ds, i, row, r, seq, inj)
                  for seq, (ds, i, row, inj, r) in enumerate(entries))
            )
        except BaseException:
            # gather 异常兜底(2026-10-13 复审):_row 全路径吞 Exception,
            # 走到这里的是防御面之外的问题(取消/意外)。不变量在异常
            # 路径同样成立 —— 关池排空泵 → finalize 冲刷已入缓冲的事件/
            # 日志,再放行异常(终态由 worker 的 finalize_execution_if_stuck
            # 兜,取消路径由租约回收重跑)。此前只走 _teardown:缓冲静默
            # 丢失、ticker 任务泄漏。best-effort,收尾失败不吞原始异常。
            try:
                if server_pool is not None:
                    try:
                        await server_pool.close()
                    except Exception:  # noqa: BLE001
                        pass
                await ingester.finalize()
            except Exception:  # noqa: BLE001
                logger.warning(
                    "run_dispatcher: fanout exception-path finalize failed "
                    "for {}", execution_id)
            raise
        # 尾部日志阻断修复(2026-10-13):server 链进程不随 run 结束退出,
        # stderr 泵在 run_case 返回后仍会读到滞留管道的行(最后一步
        # WARNING / uvicorn 收尾)。finalize 之后的 on_log 只进**已停止**
        # ingester 的缓冲,永远不落库,却已计入 logs_ingested —— S9 对账
        # 失真、S6 摘要漏最尾证据。先关池(close = terminate 进程树并等
        # 泵读到 EOF,幂等 —— _teardown 再关无害),泵排空后再 finalize。
        # launch 链无此问题:进程退出即管道 EOF,泵在 launch 返回前读完。
        if server_pool is not None:
            try:
                await server_pool.close()
            except Exception:  # noqa: BLE001
                pass
        # P2-02:冲刷事件/日志余量(先于终态落库 —— SSE/日志页在 done 后仍可读全量)
        await ingester.finalize()

        # Terminal status + timestamps only (counters already maintained
        # incrementally above).
        if cancel_local["set"] or execution_id in _eq._cancel_hint:
            # C11 协作式取消:未跑行已在行边界记 canceled,在飞子进程/
            # server run 已自然跑完(或经 cancel 端点收口);canceled 允许
            # passed+failed < total_runs(finalize 跳过校账)。
            await _finalize_execution(db_factory, execution_id,
                                      status=STATUS_CANCELED)
        else:
            await _finalize_execution(db_factory, execution_id)
    finally:
        await _teardown()


async def _mark_running(db_factory: Any, execution_id: int) -> None:
    """queued → running + started_at(原子条件 update,只动 queued 行)。

    fanout 在认证解析通过、行分发开始前调用 —— UI 由此区分"排队中"
    与"在跑"(此前 queued 直接到终态,长时间执行无法观测进度感)。
    条件更新天然幂等:终态/已 running 的行不被覆写;行被并发删除时
    where 不命中,静默跳过即可(fanout 稍后自然 no-op 收尾)。
    """
    try:
        async with db_factory() as session:
            await session.execute(
                sqlalchemy_update(Execution)
                .where(
                    Execution.id == execution_id,
                    Execution.status == STATUS_QUEUED,
                )
                .values(
                    status=STATUS_RUNNING,
                    started_at=func.coalesce(Execution.started_at, _utcnow()),
                )
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001
        # 观测性标记,失败不阻断 fanout(终态写入才是权威)。
        logger.warning(
            "run_dispatcher: mark running failed for execution {}: {}",
            execution_id, e,
        )


async def _fail_whole_execution(
    db_factory: Any,
    log_path: Path,
    *,
    execution_id: int,
    run_id: str,
    total_rows: int,
    error: str,
) -> None:
    """Auth fail-fast path: log once, count every row as failed, finalize.

    解密失败 = fail-fast(V1 严格语义):整单 execution 记为 failed,
    所有行计入 failed 计数,不带着空/坏凭证打环境。
    """
    await _append_log(log_path, {
        "ts": _utcnow().isoformat() + "Z",
        "runId": run_id,
        "executionId": execution_id,
        "status": "auth_resolve_failed",
        "error": error,
    })
    # 认证快速失败标记(执行设计 §3.2「认证快速失败」信号的唯一依据):
    # 写进 config_json,列表读侧不用扫 JSONL 就能标出"未分发行的单"。
    try:
        async with db_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is not None:
                cfg = dict(ex.config_json or {})
                cfg["authFailFast"] = {"error": str(error)[:512]}
                ex.config_json = cfg
                await session.commit()
    except Exception as e:  # noqa: BLE001 — 标记失败不影响 fail-fast 收尾
        logger.warning(
            "run_dispatcher: authFailFast marker failed for execution {}: {}",
            execution_id, e,
        )
    await _bump_counters(db_factory, execution_id, passed=0, failed=total_rows)
    await _finalize_execution(db_factory, execution_id)


async def _append_log(path: Path, payload: dict) -> None:
    """Best-effort JSONL append(to_thread 异步写,不阻塞事件循环)。

    写失败只告警,绝不打断 fan-out(P9:原同步写在逐行大单下会
    阻塞 loop)。
    """
    try:
        await asyncio.to_thread(_append_jsonl, path, payload)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: failed to write JSONL log line for {}: {}",
            payload.get("runId"), e,
        )


def _write_result_evidence(
    case_dir: Path, result: gimbal_launcher.LaunchResult, status: str
) -> None:
    """P1 证据落盘:per-case result.json(步骤级 details 完整保留)。

    JSONL 保持 counts-only(运维索引);完整证据(含 details[] / 兜底
    stdout 原文)落在本文件,与 case.json 同目录构成审计面。
    Best-effort:写失败只告警,绝不打断行执行。
    """
    payload: dict[str, Any] = {
        "launchStatus": result.launch_status,
        "exitCode": result.exit_code,
        "status": status,
        "total": result.total,
        "passed": result.passed,
        "failed": result.failed,
        "skipped": result.skipped,
        "details": result.details,
        "error": result.error,
    }
    if not result.details and result.stdout:
        # 引擎未给出可解析 JSON 报告(如 exit 2 走 typer err)时保留原文。
        payload["stdout"] = result.stdout
    try:
        (case_dir / "result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: failed to write result.json for {}: {}",
            case_dir, e,
        )


async def _store_single_case_outputs(
    db_factory: Any, execution_id: int, outputs: dict,
) -> None:
    """单 case 执行的 outputs 落 ``config_json.outputs``(P2-4/D10)。

    落库前过 :func:`integration_runner.scrub_outputs`(E1 同键表 ——
    收在存储点保证所有调用方统一脱敏)。独立会话写(行计数/终态是
    另一批会话);best-effort —— 失败只记 warning(回调 outputs 缺席,
    行/终态不受影响)。终态迁移在 finalize 之后,顺序上本写恒先于
    回调组装。"""
    from .integration_runner import scrub_outputs
    outputs = scrub_outputs(outputs)
    try:
        async with db_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is None:
                return
            cfg = dict(ex.config_json or {})
            cfg["outputs"] = outputs
            ex.config_json = cfg
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: single-case outputs for {} failed: {}",
            execution_id, e)


async def _bump_counters(
    db_factory: Any, execution_id: int, *, passed: int, failed: int,
    skipped: int = 0,
) -> None:
    """Atomic Execution counter bump(P8:失败重试一次,双败 JSONL 记账)。

    Deltas(not absolute write-backs)so concurrent rows and concurrent
    UI deletions compose correctly. skipped = 引擎 run.finished 携带的
    跳过计数(S5 落库;无引擎结果的行恒 0)。
    """
    for attempt in (1, 2):
        try:
            async with db_factory() as session:
                await session.execute(
                    sqlalchemy_update(Execution)
                    .where(Execution.id == execution_id)
                    .values(
                        passed=Execution.passed + passed,
                        failed=Execution.failed + failed,
                        skipped=Execution.skipped + skipped,
                    )
                )
                await session.commit()
            return
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                logger.error(
                    "run_dispatcher: counter bump failed twice for execution {}: {}",
                    execution_id, e,
                )
                await _append_log(_jsonl_path(), {
                    "ts": _utcnow().isoformat() + "Z",
                    "executionId": execution_id,
                    "status": "counter_bump_failed",
                    "error": repr(e),
                    "deltas": {"passed": passed, "failed": failed},
                })


class TransitionResult(enum.Enum):
    """终态迁移三态返回(P0-3.2,webhook 设计 v3)。

    此前 bool 把「已终态」(幂等跳过,正常)与「写库失败」(异常,静默
    等下次启动对账)混为同一个 False —— 回调上线后写失败的执行既无
    终态也无回调,调用方无从分辨。三态拆开:只有 ``FAILED`` 需要调用方
    重试(:func:`transition_with_retry`),``MOVED`` 是回调/计数的唯一
    依据,``ALREADY_TERMINAL`` 幂等跳过。"""

    MOVED = "moved"
    ALREADY_TERMINAL = "already_terminal"
    FAILED = "failed"


async def transition_execution(
    db_factory: Any, execution_id: int, final_status: "str | None" = None, *,
    dispatcher_error: "str | None" = None,
    count_fallback: bool = False,
    reconciled_reason: "str | None" = None,
    backfill_started_at: Any = None,
    notify: bool = True,
) -> "TransitionResult":
    """执行域**唯一**终态迁移(N2 归一;P0-3.2 起三态返回)。

    原子条件更新 ``WHERE status IN (queued, running)`` —— 已终态的执行
    不覆写、不重复通知;返回 :class:`TransitionResult`(MOVED=真实迁移,
    供调用方计数/记日志/写回调;ALREADY_TERMINAL=已终态或行不存在;
    FAILED=写库失败,见 :func:`transition_with_retry`)。
    六个历史写入点(正常收口/取消先于启动/任务体异常兜底/启动对账/
    graph 恢复收口/cancel 端点无活任务)全部改经本函数。

    收尾动作全部收敛在此,且只在真实迁移时发生:
      * ``final_status=None`` → 严格规则 ``failed > 0 → failed``(SQL 内
        原子推导,与收口前计数一致);
      * ``count_fallback``:整单未分分发(passed=failed=0)按 failed=total
        计(2-3 口径修正,取消先于启动不适用);
      * ``backfill_started_at``:started_at 为空时回填(正常收口=now;
        启动对账=created_at;取消类不回填 —— 从未启动);
      * ``dispatcher_error`` / ``reconciled_reason``:config_json 标记;
      * counterDrift 校账(仅非 canceled);
      * 完成通知(独立会话 + 自吞异常):done/failed 且有 owner 才发 ——
        N2-2 拍板:stuck 兜底/启动对账/graph 恢复收口三个异常路径也发
        (此前静默),canceled 不发(用户自发的取消)。
    """
    try:
        async with db_factory() as session:
            result = await session.execute(
                sqlalchemy_update(Execution)
                .where(Execution.id == execution_id,
                       Execution.status.in_((STATUS_QUEUED, STATUS_RUNNING)))
                .values(
                    status=(final_status if final_status is not None else case(
                        (Execution.failed > 0, STATUS_FAILED),
                        else_=STATUS_DONE)),
                    finished_at=_utcnow()))
            if result.rowcount != 1:
                return TransitionResult.ALREADY_TERMINAL   # 已终态/行不存在
            ex = await session.get(Execution, execution_id)
            if ex is None:
                return TransitionResult.ALREADY_TERMINAL
            if ex.started_at is None and backfill_started_at is not None:
                ex.started_at = backfill_started_at
            if count_fallback and not ex.failed and not ex.passed:
                ex.failed = max(int(ex.total_runs or 0), 1)
            cfg = dict(ex.config_json or {})
            if dispatcher_error is not None:
                cfg["dispatcherError"] = str(dispatcher_error)[:512]
            if reconciled_reason is not None:
                cfg["reconciled"] = {
                    "at": _utcnow().isoformat() + "Z",
                    "reason": reconciled_reason,
                }
            if (ex.status != STATUS_CANCELED
                    and ex.passed + ex.failed != ex.total_runs):
                logger.error(
                    "run_dispatcher: counter drift execution {}: "
                    "total={} passed+failed={}",
                    execution_id, ex.total_runs, ex.passed + ex.failed,
                )
                cfg["counterDrift"] = True
            ex.config_json = cfg
            # P2-2(webhook v4 §6):outbox 同事务写行 —— 令牌发起
            # (有 token_id)且令牌配了回调地址时写 execution.finished
            # 投递行;三条 canceled 路径也经本函数真实迁移,满足条件即
            # 发 status=canceled(D11)。写行异常自然传播 → 终态与投递
            # 行都不落库(「有终态无回调」不出现)。
            if ex.token_id:
                from .webhook_outbox import enqueue_execution_finished
                await enqueue_execution_finished(session, ex)
            await session.commit()
            if ex.token_id:
                from .webhook_outbox import wake
                wake()
            # 通知口径:done/failed 且有 owner(N2-2:三个异常收口路径
            # 也发;canceled 不发)。ex.status 为迁移后真值(含派生)。
            if notify and ex.status != STATUS_CANCELED and ex.owner_id:
                await _notify_finished(ex, ex.status)
            return TransitionResult.MOVED
    except Exception as e:  # noqa: BLE001 — 迁移失败不炸调用方(重试见 transition_with_retry)
        logger.warning(
            "run_dispatcher: transition_execution {} -> {} failed: {}",
            execution_id, final_status, e)
        return TransitionResult.FAILED


async def transition_with_retry(
    db_factory: Any, execution_id: int, final_status: "str | None" = None,
    *, retry_delay: float = 1.0, **kw: Any,
) -> "TransitionResult":
    """带一次重试的终态迁移(P0-3.2/设计 v3 P0-4)。

    只有 ``FAILED`` 重试(1 秒后一次),仍失败记 error 日志后返回;
    ``ALREADY_TERMINAL`` 幂等跳过、``MOVED`` 直接返回。供六个调用点
    共用,不各自散写重试。"""
    res = await transition_execution(db_factory, execution_id, final_status, **kw)
    if res is TransitionResult.FAILED:
        await asyncio.sleep(retry_delay)
        res = await transition_execution(db_factory, execution_id, final_status, **kw)
        if res is TransitionResult.FAILED:
            logger.error(
                "run_dispatcher: transition {} -> {} 写库失败(重试后仍失败,"
                "等待周期对账兜底)", execution_id, final_status)
    return res


async def _finalize_execution(
    db_factory: Any, execution_id: int, *, status: str | None = None
) -> None:
    """终态收尾(N2 后为薄壳):状态推导 + 唯一迁移函数。

    ``status`` 显式覆盖用于取消终态(canceled);缺省由
    :func:`transition_execution` 按 ``failed > 0 → failed`` 原子推导。
    计数器由上方增量维护;校账(counterDrift)、started_at 回填、通知
    全部在迁移函数内,只在真实迁移时发生(重复收口 = 无效迁移,
    不再覆写、不重复通知 —— 修复此前无守卫直接覆写的漂移面)。
    """
    try:
        await transition_with_retry(
            db_factory, execution_id, status,
            backfill_started_at=_utcnow())
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: failed to update execution {}: {}", execution_id, e)
    # spec §9.1:执行终态化 → 活跃行状态出清(读侧此后走 JSONL 回放)。
    # DB 写失败也出清 —— fanout 已收尾,残留的"活跃"行状态会永久盖住
    # 回放路径。
    _row_states.pop(execution_id, None)


# ── S6/S11:失败通知根因摘要(两行式)+ 出口打码 ────────────────────
# 出口打码(窄防护):通知摘要是日志内容**唯一对外出口**,入 body 前做
# 轻量正则打码 —— 只打「键名=值 / Bearer 串」的取值形态;引擎侧红线
# (凭证不入 message,S11A 抽查测试)是主防线,这里是双保险。
# 单遍 alternation(Bearer 分支优先;pair 值排除 ``Bearer`` 字面 —— 否则
# ``Authorization: "Bearer x"`` 会被 pair 分支吞掉 ``Bearer`` 当值、真值裸奔)
_MASK_RE = re.compile(
    r"(\bbearer\s+)[^\s'\"]{3,}"
    r"|(\b(?:password|passwd|secret|token|authorization|api[_-]?key)\b"
    r"\s*[=:]\s*['\"]?)(?!bearer\b)[^\s'\"]{3,}",
    re.IGNORECASE,
)


def _mask_secrets(text: str) -> str:
    return _MASK_RE.sub(lambda m: (m.group(1) or m.group(2)) + "***", text)


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


async def _failure_digest(db: AsyncSession, execution_id: int) -> "str | None":
    """失败执行的两行式根因摘要(D6 定稿)。

    锚点 = ``step.failed`` 事件(每失败 unit 最新一条,最多 3 组);
    组内两行(混合时间轴 (ts,id) 上锚点之前,同 unit —— 并行多行时
    不串行噪声;unit 为 NULL 的边界外日志视为全局行,对任一 unit 可见):
      1. 最近 WARNING/ERROR 日志行;
      2. 其前同 unit、同 step(锚事件 step)最近一行 —— #304 实证根因
         细节常是 INFO(``expression=`` 在 INFO 里,WARNING 只有泛化句)。
    回退:无 WARNING/ERROR → 锚前最后两条日志行;无日志 → 该组无产出。
    全部组无产出 → None(通知回落现状文案)。消息过 ``_mask_secrets``。

    竞态前置不变量:调用方顺序必须是 ``ingester.finalize()`` →
    ``_finalize_execution`` → 本函数(§7 四步收口)—— 失败行日志刚进
    缓冲即终态的场景,摘要靠 finalize 先冲刷余量才取得到(防回归用例
    钉住该顺序)。
    """
    from sqlalchemy import and_, or_, select as _select

    from ..models.execution import ExecutionEvent as EE

    failed_rows = (await db.execute(
        _select(EE).where(
            EE.execution_id == execution_id,
            EE.kind == "event", EE.event_type == "step.failed")
        .order_by(EE.ts.desc(), EE.id.desc()).limit(50))).scalars().all()
    anchors: dict[str, EE] = {}   # 倒序首见 = 该 unit 最新
    for r in failed_rows:
        anchors.setdefault(r.unit or "", r)
    groups: list[str] = []
    for unit, anchor in list(anchors.items())[:3]:
        def _before(ts, id_):
            return or_(EE.ts < ts, and_(EE.ts == ts, EE.id < id_))

        def _in_unit():
            # 同 unit + 全局行(unit NULL,边界外日志)
            return or_(EE.unit == anchor.unit,
                       EE.unit.is_(None)) if anchor.unit else True

        l1 = l2 = None
        warn = (await db.execute(
            _select(EE).where(
                EE.execution_id == execution_id, EE.kind == "log",
                EE.level.in_(("WARNING", "ERROR", "CRITICAL")),
                _in_unit(), _before(anchor.ts, anchor.id))
            .order_by(EE.ts.desc(), EE.id.desc()).limit(1))).scalars().first()
        if warn is not None:
            l1 = warn
            l2 = (await db.execute(
                _select(EE).where(
                    EE.execution_id == execution_id, EE.kind == "log",
                    _in_unit(), EE.step == anchor.step,
                    _before(warn.ts, warn.id))
                .order_by(EE.ts.desc(), EE.id.desc()).limit(1))).scalars().first()
        else:
            # 回退:锚前最后两条日志行
            last2 = (await db.execute(
                _select(EE).where(
                    EE.execution_id == execution_id, EE.kind == "log",
                    _in_unit(), _before(anchor.ts, anchor.id))
                .order_by(EE.ts.desc(), EE.id.desc()).limit(2))).scalars().all()
            if last2:
                l1 = last2[0]
                l2 = last2[1] if len(last2) > 1 else None
        if l1 is None or not (l1.message or "").strip():
            continue
        text = f"{unit or '?'}: " + _clip(_mask_secrets(l1.message), 120)
        if l2 is not None and (l2.message or "").strip():
            text += "\n↳ " + _clip(_mask_secrets(l2.message), 80)
        groups.append(text)
    return "\n".join(groups) if groups else None


async def _notify_finished(ex: Execution, final_status: str) -> None:
    """execution_finished 通知(独立会话;任何失败只记日志)。

    title 带场景 name(铃铛渲染 font-medium 着重),body 前缀
    scenario_id(小字弱化)—— name + id 一起给。name 首选执行快照列;
    存量行快照为空时查活场景行补,场景已删则回落 id。
    """
    from . import notifications as notify_svc
    from ..core import db as db_module
    try:
        async with db_module.SessionLocal() as s2:
            # P2-5(webhook 设计 v3 §5.6/D8):平台模式执行的 owner 是
            # ``__platform__`` 系统用户 —— 站内通知无人消费,跳过
            # (回调才是它的完成通知面)。
            if ex.owner_id:
                owner = await s2.get(User, ex.owner_id)
                if owner is not None and owner.is_system:
                    return
            name = ex.scenario_name
            if not name:
                row = await get_row(s2, ex.scenario_id)
                if row is not None:
                    name = str((definition_from_payload(row.payload)
                                .get("meta") or {}).get("name") or "").strip()
            label = name or ex.scenario_id
            if ex.batch_id:
                await notify_svc.upsert_execution_finished(
                    s2, user_id=ex.owner_id, batch_id=ex.batch_id,
                    run_label=label,
                )
            else:
                body = f"{ex.scenario_id} · {ex.passed} 通过 / {ex.failed} 失败"
                if final_status == STATUS_FAILED:
                    # S6:失败带两行式根因摘要(best-effort —— 摘要失败
                    # 不影响通知本身;无日志执行回落现状文案)
                    try:
                        digest = await _failure_digest(s2, ex.id)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "run_dispatcher: failure digest for {} failed: {}",
                            ex.id, e)
                        digest = None
                    if digest:
                        body = body + "\n" + digest
                await notify_svc.create_notification(
                    s2,
                    user_id=ex.owner_id,
                    type_="execution_finished",
                    title=("执行完成:" if final_status == STATUS_DONE
                           else "执行失败:") + label,
                    body=body,
                    link=f"/executions/{ex.id}"
                         + ("?rows=failed" if final_status == STATUS_FAILED else ""),
                )
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: notify execution {} failed: {}",
                       ex.id, e)


# ─── helpers ──────────────────────────────────────────────────────
def _step_at(steps: list, si: int) -> dict:
    """``steps[si]`` 的 dict 元素;**越界 / 非 dict 元素 ⇒ 空 dict**。

    判定链上「取某步」的**唯一**写法:body 面(判定)、端点面(universe)、
    assert 目标面按同一条规则取步,否则同一下标在两侧得到不同答案、判决静默
    分叉。越界与畸形元素都不抛 —— 判死归 ``entry_issues`` 的 step-oob 分支,
    这里抛 IndexError/AttributeError 只会把整单变 500(守齐,B/Z2)。

    §5 例外:空 dict 是**该投影的缺省形** —— 「无此步」与「空步骤」在三个消费
    面(body 无 / call 无 / strategy 无)上等价,故同落一个值;判死不在这里。"""
    if si < 0 or si >= len(steps) or not isinstance(steps[si], dict):
        return {}
    return steps[si]


def _body_of(payload: dict | None) -> Callable[[int], Any]:
    """steps[si].request.body 投影(entry_issues 的 path-unresolvable
    检测输入,spec v3 §2;jsonpath.exists 在其上判路径可解析性)。

    取**原始** steps(不填 :func:`steps_from_payload` 的过滤版):判定与
    :func:`compose_injection_scenario` 的物化、与前端同用一个索引基数
    (spec §1.1 Z2 —— 过滤版下标会把整个判定错位一位)。取步规则见
    :func:`_step_at`(越界 / 非 dict ⇒ 无 body)。"""
    steps = definition_from_payload(payload).get("steps") or []

    def _body(si: int) -> Any:
        return (_step_at(steps, si).get("request") or {}).get("body")

    return _body


def _assert_targets_of(payload: dict | None) -> Callable[[int], set[str]]:
    """steps[si].strategy 的 assertion target 投影(entry_issues 的
    override-no-match 检测输入;匹配语义与 compose_injection_scenario
    同源:kind=assertion 且 target 相等)。索引基数同上:原始 steps。
    取步规则见 :func:`_step_at`(越界 / 非 dict ⇒ 无 strategy)。"""
    steps = definition_from_payload(payload).get("steps") or []

    def _targets(si: int) -> set[str]:
        return {
            st.get("target")
            for st in (_step_at(steps, si).get("strategy") or [])
            if isinstance(st, dict) and st.get("kind") == "assertion"
        }

    return _targets


# ─── injection-entry gating(dispatch 与 /run/precheck 的唯一实现)───
async def filter_injection_entries(
    raw_payload: dict, selected_ids: list[str]
) -> tuple[list[dict], list[str], list[str]]:
    """注入条目悬空判定 + 过滤(dispatch 与 ``POST /run/precheck`` 共用,
    执行设计 §1.6:失效判定不开第二份实现)。

    spec v3.1 §2.1/§3:判定面 = 契约声明 ∪ body 现存。只为**被选中条目
    实际引用到的步骤**取声明面(懒取,避免无谓的 plate 调用);取不到 →
    None(**降级,不抹平** —— Y:与「端点真无声明」可区分)。索引基数
    (spec §1.1 Z2):声明面/body/asserts 与前端、与 compose_injection_scenario
    一律按 definition.steps 的**原始**下标寻址。

    返回 ``(存活条目, 悬空 id 列表, 降级窗口内跳过的 id 列表)``。
    """
    registry = raw_payload.get("assertion_registry") or {}
    entries = registry.get("entries") or []
    wanted = set(selected_ids)
    selected = [e for e in entries if isinstance(e, dict) and e.get("id") in wanted]

    raw_steps = definition_from_payload(raw_payload).get("steps") or []
    step_count = len(raw_steps)

    needed_steps: set[int] = set()
    for e in selected:
        p = e.get("path")
        si = as_step_index(p.get("stepIndex")) if isinstance(p, dict) else None
        if si is not None:
            needed_steps.add(si)

    def _endpoint_id_of(si: int) -> str | None:
        step = _step_at(raw_steps, si)
        # M3:锚点唯一 = step.endpoint(view_hints 双读已删)
        eid = step.get("endpoint")
        return eid if isinstance(eid, str) and eid else None

    # Release 4.4 核心约束:已锁定场景的判定面按执行副本 meta.plate 写明
    # 的修订取,不跟随 working 树漂移(未声明系统的过渡形态回落 working)
    meta_plate = ((definition_from_payload(raw_payload).get("meta") or {})
                  .get("plate") or {})

    async def _face_of(si: int) -> tuple[int, frozenset[str] | None]:
        eid = _endpoint_id_of(si)
        if eid is None:
            return si, frozenset()            # 无端点 = 真无声明(非得降级)
        ref = meta_plate.get(str(eid).split(".")[0])
        # None = 降级(**不抹平**,Y)
        return si, await declared_paths_of(eid, ref=ref)

    face_by_step: dict[int, frozenset[str] | None] = dict(
        await asyncio.gather(*[_face_of(si) for si in sorted(needed_steps)])
    ) if needed_steps else {}
    for si, face in face_by_step.items():
        if face is None:
            logger.warning(
                "run_dispatcher: step %s 声明面不可得(plate 降级)— 该步判定只认 body 面,"
                "锚在契约声明上的条目可能被误判为悬空并跳过", si,
            )

    # body 面(判定)与端点面(universe)**共用同一份投影** —— 两侧对同一下标
    # 必须给同一答案:各写一份的话,一侧改了规则另一侧不动,判决与 universe
    # 就静默分叉。投影本体见 :func:`_body_of`。
    body_of_step = _body_of(raw_payload)

    universe_by_step: dict[int, set[str]] = {
        si: injectable_universe(body_of_step(si), face)
        for si, face in face_by_step.items()
    }
    # §5 例外:两侧同为该查表的缺省形(`set[str]` 的「只认 $ 根」),等价性一眼可判
    # —— 未预计算该步 ⇒ 与 entry_issues 内部的缺省 universe 同一张表。
    _universe_of = lambda si: universe_by_step.get(si, {"$"})   # noqa: E731

    skipped_while_degraded: list[str] = []
    dangling_ids: list[str] = []
    selected_entries: list[dict] = []
    for e in selected:
        issues = entry_issues(e, step_count, body_of_step,
                             _assert_targets_of(raw_payload), _universe_of)
        if issues:
            p = e.get("path")
            si = as_step_index(p.get("stepIndex")) if isinstance(p, dict) else None
            if si is not None and face_by_step.get(si) is None:
                # Y:判定降级期间跳过的条目要可见。记录口径 = 「跳过发生在该步
                # 声明面不可得的时刻」,跳过的**因由不限**(override-no-match、
                # 真写错的 jsonpath 等与降级无关者一并计入)—— 不声称因果。
                skipped_while_degraded.append(e.get("id"))
            dangling_ids.append(e.get("id"))
            continue
        selected_entries.append(e)
    return selected_entries, dangling_ids, skipped_while_degraded


def _new_run_id() -> str:
    return f"run-{_utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6]}"


def _convert_cache_key(payload: dict) -> str:
    """convert memo 键:合成场景的规范化 JSON 摘要。

    同一行 n_runs 次重复输入完全一致(P6:此前重复打 plate)。
    """
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        .encode("utf-8")
    ).hexdigest()


# (N1 迁移勘误:_jsonl_lock 随 _append_jsonl 原本同居一块,块搬移时
# 失联 —— 与函数一并回插。)
_jsonl_lock = threading.Lock()


def _append_jsonl(path: Path, payload: dict) -> None:
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    with _jsonl_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY
                     | getattr(os, "O_BINARY", 0))
        try:
            os.write(fd, data)
        finally:
            os.close(fd)


# 单行场景/数据集查询收敛到各自 store 的 get_row(全后端唯一实现)。
# (N1 迁移勘误:这组底部导入曾位于已迁走的 _coerce_row_value 与
# _find_dataset_by_id 之间,随块搬移而失联 —— 回插于此。)
from .run_semantics import INTEGRATION, PIN, UNDECLARED, WORKING, invalid_reason, ref_category
from .scenario_store import get_row, steps_from_payload, definition_from_payload
from .scenario_store import _meta_from_row  # noqa: PLC2701 台账快照列(M2)


def _jsonl_path() -> Path:
    return settings.DATA_DIR / "runs" / f"{_utcnow().strftime('%Y-%m-%d')}.jsonl"


def _run_dir(run_id: str) -> Path:
    """一个 run 的 case 文件根目录(与 JSONL 同域的执行审计面)。"""
    return settings.DATA_DIR / "runs" / "cases" / run_id


# 公开别名:executions 路由的 case-artifact 端点按 runId 定位 run 目录
# (跨执行读不可能 —— runId 唯一,目录名即 runId)。
run_dir = _run_dir


def purge_case_dir(run_id: str) -> None:
    """删除整单的 case 案卷目录(P2:case.json 含明文凭证,删除执行
    必须连带清理,否则 UI 删除后凭证仍永久留盘)。Best-effort。"""
    shutil.rmtree(_run_dir(run_id), ignore_errors=True)


def sweep_stale_case_dirs() -> int:
    """启动期保留期清扫:删除 mtime 超过 CASE_RETENTION_DAYS 的 run 目录。

    0 = 禁用。JSONL 按日期分文件、不在此清理(现行设计)。
    """
    days = settings.CASE_RETENTION_DAYS
    if days <= 0:
        return 0
    root = settings.DATA_DIR / "runs" / "cases"
    if not root.exists():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for child in root.iterdir():
        try:
            stale = child.is_dir() and child.stat().st_mtime < cutoff
        except OSError:
            continue
        if stale:
            shutil.rmtree(child, ignore_errors=True)
            if not child.exists():
                removed += 1
    if removed:
        logger.info("run_dispatcher: swept {} stale case dir(s) (> {}d)", removed, days)
    return removed


_JSONL_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")


def sweep_stale_run_journals() -> int:
    """按日 JSONL 运维索引(``runs/YYYY-MM-DD.jsonl``)的保留期清扫。

    按**文件名日期**判龄(不看 mtime:追加写会刷新 mtime)。保留期
    ``RUNS_JSONL_RETENTION_DAYS``(0 = 禁用)。JSONL 是 M6 前存量单的
    行级只读归档(``_replay_rows``)与运维索引,M6 起行级已入库,故默认
    保留期长于 case 案卷。
    """
    days = settings.RUNS_JSONL_RETENTION_DAYS
    if days <= 0:
        return 0
    root = settings.DATA_DIR / "runs"
    if not root.exists():
        return 0
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    removed = 0
    for path in root.glob("*.jsonl"):
        m = _JSONL_NAME_RE.match(path.name)
        if not m:
            continue
        try:
            day = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if day < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
    if removed:
        logger.info("run_dispatcher: swept {} stale run journal(s) (> {}d)",
                    removed, days)
    return removed


async def run_retention_maintenance() -> dict[str, int]:
    """保留期维护(后台周期任务;整体评审 2026-10-15 #2/#3)。

    三项清扫此前要么零调用点(事件面),要么只在启动期跑一次(case
    案卷,含明文凭证)——长期不重启的服务上保留期形同虚设。各项互相
    隔离:一项失败不影响其余,失败计 -1 并记日志。
    """
    from . import execution_store

    out: dict[str, int] = {"case_dirs": 0, "run_journals": 0, "events": 0,
                           "webhook_delivered": 0, "webhook_failed": 0}
    try:
        out["case_dirs"] = await asyncio.to_thread(sweep_stale_case_dirs)
    except Exception as e:  # noqa: BLE001 — 旁路:单项失败不阻断其余
        logger.warning("retention: case dir sweep failed: {}", e)
        out["case_dirs"] = -1
    try:
        out["run_journals"] = await asyncio.to_thread(sweep_stale_run_journals)
    except Exception as e:  # noqa: BLE001 — 旁路
        logger.warning("retention: run journal sweep failed: {}", e)
        out["run_journals"] = -1
    try:
        async with _session_factory() as session:
            out["events"] = await execution_store.purge_expired_events(session)
    except Exception as e:  # noqa: BLE001 — 旁路
        logger.warning("retention: event purge failed: {}", e)
        out["events"] = -1
    # P2-3(webhook 设计 v3 §5.2):投递行保留期 —— delivered 30 天 /
    # failed 180 天,与其余保留期同一维护任务、同一隔离口径。
    try:
        from .webhook_outbox import cleanup_retention
        (out["webhook_delivered"],
         out["webhook_failed"]) = await cleanup_retention(_session_factory)
    except Exception as e:  # noqa: BLE001 — 旁路
        logger.warning("retention: webhook delivery sweep failed: {}", e)
        out["webhook_delivered"] = out["webhook_failed"] = -1
    if any(out.values()):
        logger.info("retention maintenance: {}", out)
    return out


def _write_case_file(case_dir: Path, scenario_dict: dict[str, Any]) -> Path:
    """把注入完成的数据驱动用例落盘为 gimbal 可执行 case.json。

    文件内容 = ``gimbal run launch`` 的唯一输入快照(含明文 users,与
    V1 临时 yaml 同语义);落盘失败(磁盘满等)抛 OSError,由 _row 的
    兜底 except 记 dispatcher_error。
    """
    case_dir.mkdir(parents=True, exist_ok=True)
    case_path = case_dir / "case.json"
    case_path.write_text(
        json.dumps(scenario_dict, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return case_path


async def _create_execution(
    db: AsyncSession,
    *,
    scenario_id: str,
    owner_id: int,
    total_runs: int,
    config_json: dict,
    scenario_snapshot: dict | None = None,
    batch_id: str | None = None,
    scenario_name: str = "",
    kind: str = "scenario",
    suite_id: int | None = None,
    plate_pins: dict | None = None,
    token_id: int | None = None,
    client_ref: str | None = None,
    callback_path_override: str | None = None,
) -> Execution:
    """Insert an Execution row(+ 拆表后的快照行)。

    M2:scenario_snapshot 大 JSON 移入 execution_snapshots(1:1),
    executions 主表只留台账轻列(scenario_name/owner_name 快照)。
    重构方案 0014:kind = scenario(默认)/ suite_graph(编排执行,
    scenario_id 写占位 suite-<id>);suite_id 供 21 页归并,无 FK
    (执行台账归执行人,历史不随 Suite 删除消失)。
    token_id(webhook v4 §7.1):令牌调用台账;JWT 调用恒 None。
    """
    owner_name = (await db.execute(
        select(User.display_name, User.username).where(User.id == owner_id)
    )).first()
    ex = Execution(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        kind=kind,
        suite_id=suite_id,
        owner_id=owner_id,
        owner_name=(owner_name[0] or owner_name[1]) if owner_name else "",
        status=STATUS_QUEUED,
        total_runs=total_runs,
        passed=0,
        failed=0,
        config_json=config_json,
        batch_id=batch_id,
        plate_pins=plate_pins,
        token_id=token_id,
        client_ref=client_ref,
        callback_path_override=callback_path_override,
    )
    db.add(ex)
    await db.flush()  # 拿 execution.id,快照行同事务写入
    if scenario_snapshot:
        db.add(ExecutionSnapshot(
            execution_id=ex.id, snapshot=scenario_snapshot))
    await db.commit()
    await db.refresh(ex)
    return ex


# ─── session factory (for the background task) ───────────────────
def _session_factory() -> AsyncSession:
    """Open a fresh AsyncSession — the background task outlives the
    request-scoped session the router passed in."""
    from ..core.db import SessionLocal
    return SessionLocal()


# 公开别名:启动恢复等模块外调用方不必触私有名。
session_factory = _session_factory

# ─── error sentinels (router translates to HTTPException) ─────────
class NotFound(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Conflict(Exception):
    def __init__(self, code: str, message: str,
                 extra: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra or {}


# 外部系统集成 P1 的私有件公共别名(compose_scenario/built_in_users/
# resolve_exec_auths/find_dataset_by_id)已随 N1 迁至 run_prepare 并
# 公开 —— 外部消费方一律 from .run_prepare import,本模块不再转发。


# 编排执行入口(suites 路由)消费 —— 执行行创建/runId 生成是执行域职责,
# 与装载准备(run_prepare)分属两层。
create_execution = _create_execution
new_run_id = _new_run_id
