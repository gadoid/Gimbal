"""Run dispatcher (V3.2 Scenario Composer — ``gimbal run launch`` 执行链).

Per-row fan-out of a Scenario's selected DataSets:

1. :func:`run_prepare.compose_scenario` — 场景 definition + 一行数据集 → 数据驱动的
   gimbal scenario dict(行键注入 ``config.vars``,按基线类型还原)。
2. Plate ``/convert`` — 校验 + 剥平台视图字段(orchestration 绝不外发)。
3. 执行凭证注入 convert 产物(明文不流经 plate)— Task 3 起由
   ``materialize_run_copy`` 纯函数接管(services/users 物化,注入清单 =
   模板扫描 ∪ serviceBindings 绑定)。
4. 落盘 case 文件(``DATA_DIR/runs/cases/<runId>/``)。
5. 执行器 server 实例执行(``gimbal_server_session``:POST /runs + SSE;
   legacy 链退场,ADR-0003 #23)。

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
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy import text as sa_text
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.exc import IntegrityError
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
from ..schemas.scenario_composer import (RunRequest, RunResponse, ServiceBinding,
                                        scrub_retired_bindings)
from . import gimbal_launcher, plate_client
from .run_params import RAW_SCHEME_ID
from .auth_ref_scan import scan_auth_aliases
from .endpoint_declarations import declared_paths_of
from .run_injection import (
    as_step_index,
    compose_injection_scenario,
    entry_issues,
    injectable_universe,
)
from .run_materialize import materialize_run_copy
from . import run_prepare, service_aliases
# 装载准备(凭证清单/解析、compose、内置 users、数据集
# 查找、prepare_exec 统一入口)迁往 run_prepare —— 本模块只做派发与
# 执行编排;ResolvedAuth/AuthResolveError 亦由 run_prepare 定义。
from .run_prepare import (
    AuthResolveError,
    compose_scenario,
    find_dataset_by_id,
    prepare_exec,
    resolve_exec_auths,
)

if TYPE_CHECKING:
    # 仅注解用(_fanout_pool_scaffold 返回类型):运行期在函数体内局部
    # 导入(避开模块加载期的环);注解经 __future__ annotations 延迟
    # 求值,不在此处求值。CI 的 pyflakes 未定义名守卫在此报
    # F821(引号前向引用指向一个模块级不存在的名字)。
    from .gimbal_server_session import ServerSessionPool


# ─── shutdown 状态 + 队列 worker 桥（C11）───────────────────────
# 进程内注册表（_in_flight/_cancel_requested/_tasks_by_execution/全局
# 执行任务进 execution_jobs 表，worker 循环
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


# execution_id → 调试执行上下文（ServerSession 由本模块
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
    # 单元级台账面(从执行器事件投影;无事件路径
    # unit_id=""、attempts=1 —— 与 0008 存量行兼容)
    unit_id: str = ""
    branch: str = "main"
    attempts: int = 1
    # B6(R11 轻量版):server 链执行本行的槽位号;launch 链 None
    server_slot: int | None = None
    # B3:行级失败原因(引擎 runError 或派发层异常 error;终态回写块
    # 投影,随 _persist_row_terminal 落库;passed/canceled 为 None)
    run_error: str | None = None


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

    历史执行走 :func:`execution_rows_page`(DB 行是持久层,
    JSONL 回放只兜存量单)。"""
    live = _row_states.get(execution_id)
    if live is not None:
        return [asdict(r) for r in live]
    return []


async def execution_rows_page(
    db: Any, execution_id: int, *, page: int = 1, page_size: int = 200,
) -> tuple[list[dict], int]:
    """历史执行行级分页:DB 行 LIMIT/OFFSET + total。

    活跃执行(内存 registry 在场)整段返回后 Python 切片 —— 活跃行的
    权威在内存,分页只是展示层;JSONL 归档回放仅兜存量单
    (全量执行均有 DB 行)。
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
    if not total:
        return [], 0
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
            # B3:行级失败原因(响应模型键 runError;报告同键消费)
            "runError": r.run_error,
            # B4:报告按 unit 归组 graph 链步骤(行 API 响应模型不含此键)
            "unitId": r.unit_id or "",
        }
        for r in rows
    ], int(total)


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
    """DB datetime → UTC ISO 串(Z 后缀;时区对齐:API 时间
    一律带明确时区标记,前端 new Date 按本地渲染 —— naive 无 offset
    会被浏览器当本地时区解析,+8 主机显示慢 8h)。"""
    from ..core.timeutil import iso_utc_z

    return iso_utc_z(dt)


class _EventIngester:
    """执行器事件/日志流式入库缓冲(launcher 回调 → execution_events)。

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
        # 阈值 task 与 ticker 直调可并发开两个事务,PG 按 INSERT 时刻
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
                if not isinstance(e, asyncio.CancelledError):
                    logger.warning(
                        "run_dispatcher: 事件批冲刷失败已回填待重试"
                        "(execution={}): {}", self._execution_id, e)
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


_ROW_UPSERT_COLS = ("unit_id", "branch", "attempts", "dataset_id",
                    "injection_id", "row_index", "rep", "status",
                    "case_dir", "started_at", "finished_at", "server_slot",
                    "run_error")


async def _upsert_execution_rows(db: Any, rows: list[dict]) -> None:
    """ExecutionRow 同键 (execution_id, seq) upsert **单源**。

    三处手写 insert→IntegrityError→update 拷贝曾互有列漂移,收编
    互有列漂移(恢复分支漏 unit_id/branch/attempts 等、graph 批漏
    branch/case_dir/started_at —— 撞约束后窄列回填,字段错位残留旧
    值)。on_conflict 全列覆盖(_ROW_UPSERT_COLS),形状结构上不可能
    漂移;同批同键去重(PG ON CONFLICT 不允许一语句两次命中同行),
    语义 = 同键后到覆盖(与 execution_store._upsert_steps 同构)。
    调用方 row dict 须含 _ROW_UPSERT_COLS 全部键(未知的填 None,
    不静默沿用库内旧值)。"""
    from ..models.execution import ExecutionRow
    from .execution_store import _dialect_insert

    if not rows:
        return
    insert_ = _dialect_insert(db)
    dedup: dict[tuple, dict] = {}
    for r in rows:
        dedup[(r["execution_id"], r["seq"])] = r
    stmt = insert_(ExecutionRow).values(list(dedup.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=["execution_id", "seq"],
        set_={c: getattr(stmt.excluded, c) for c in _ROW_UPSERT_COLS},
    )
    await db.execute(stmt)


async def _persist_row_terminal(db_factory: Any, execution_id: int,
                                state: "RowState") -> None:
    """行终态即落库:崩溃窗口不丢已终态行。

    best-effort —— 失败只记日志:活跃读侧的权威仍在内存 registry,
    DB 是持久层跟进(§2.2);计数器审计面另由 JSONL 生命周期行承担。
    """
    try:
        async with db_factory() as session:
            await _upsert_execution_rows(session, [{
                "execution_id": execution_id, "seq": state.seq,
                "unit_id": state.unit_id, "branch": state.branch,
                "attempts": state.attempts,
                "dataset_id": state.dataset_id,
                "injection_id": state.injection_id,
                "row_index": state.row_index, "rep": state.rep,
                "status": state.status,
                "case_dir": state.case_dir or "",
                "started_at": _iso_to_dt(state.started_at),
                "finished_at": _iso_to_dt(state.finished_at),
                "server_slot": state.server_slot,
                "run_error": state.run_error,
            }])
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: persist row terminal {}/{} failed: {}",
            execution_id, state.seq, e,
        )


# ─── startup reconcile (P3) ────────────────────────────────────────
async def reconcile_stale_executions(
    db_factory: Any, *, periodic: bool = False,
) -> int:
    """reconcile 僵尸执行(C11 起 jobs 感知;N2 起走唯一终态迁移;
    支持周期模式与 canceled 口径(webhook 设计 v3)。

    * executions stuck queued/running **且无 job 行**(迁移期残留/
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
    ③started_at 从 created_at 回填;④failed 终态发完成通知(启动
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
            # job 已取消 → 执行记 canceled;取消不是失败,
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
    """周期对账入口(background_tasks 注册,webhook 设计 v3)。

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
        # /run/precheck 与告警可见）。
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
    """R × E 的单元口径计数(nRuns 乘法下沉执行器,不展开进
    total_runs;P7 闸同口径)。"""
    return sum(len(d["rows"]) for d in fanout_datasets) * len(injections)


# ─── main entry point ─────────────────────────────────────────────
async def _check_env_consistency(
    db: AsyncSession, scenario_payload: dict, env_id: int | None,
) -> list[str]:
    """环境告警（Release v4.4 §6.3）：本次环境声明的版本线 ≠ 场景钉定
    的版本线 → 告警。返回告警文本列表（调用方写 config_json 的
    environmentWarnings 键）。

    authz M2a S6:环境由环境链唯一给出(S2),不再经绑定 authAlias →
    别名 ``environment_id`` 反推 ——「混合环境」告警随之退役(一次执行
    只有一个环境)。
    """
    from ..models.environment import Environment
    from .env_chain import instance_lines

    if env_id is None:
        return []
    env = await db.get(Environment, env_id)
    if env is None:
        return []
    warnings: list[str] = []
    definition = definition_from_payload(scenario_payload)
    meta_plate = (definition.get("meta") or {}).get("plate") or {}
    # 重构 §1.2:版本线迁 system_env_instances(env.lines JSON 列退役)
    for system, line in (await instance_lines(db, env_id)).items():
        declared = meta_plate.get(system)
        if ref_category(declared) == PIN:  # b2-3:线一致告警仅对钉定
            declared_line = declared.split("#")[0]
            if declared_line != line:
                warnings.append(
                    f"环境不一致:环境「{env.name}」声明 {system}@{line},"
                    f"场景声明 {system}@{declared_line}——执行将使用场景"
                    "的版本线,建议适配或调整环境")
    return warnings


_COMBO_REPLAY_UNSET = object()


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
    token: "object | None" = None,
    trace: "dict | None" = None,
    exec_replay: dict | None = None,
    env_replay: dict | None = None,
    combo_replay: object = _COMBO_REPLAY_UNSET,
) -> RunResponse:
    """库中场景的派发入口 = 取场景 → :func:`dispatch_target`(P3 §六)。

    对外签名不变(runs 路由 / Suite 成员三处调用零改动);
    临时调用由路由层自行构造 :class:`RunTarget` 直接走第二段。
    ``exec_replay``(④ 分层):重跑传入的执行配置**终值**快照
    (slotMap/carryOverrides/execConfigId)—— 不回查配置行(§7:
    配置后改不影响历史执行)。
    ``env_replay``(§8.2 快照兼容):重跑传入首发环境快照
    (``{environmentId, environmentSource}``)—— 直用不重解析;
    缺键旧行传 None = 按新链正常解析。
    ``combo_replay``:重跑传入的首发组合溯源快照(未绑定 = 空
    ``ComboBase``);只恢复台账,绑定终值由请求中的 ``serviceBindings``
    快照承载。缺省哨兵才表示非重跑、需要解析当前方案。

    ``preloaded_scenario``: the runs router already loads the scenario
    row for the ownership check — pass it here to avoid querying
    the same row twice (and keep a single source for the
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
        token=token, trace=trace,
        exec_replay=exec_replay, env_replay=env_replay,
        combo_replay=combo_replay)


async def dispatch_target(
    db: AsyncSession,
    user_id: int,
    req: RunRequest,
    target: RunTarget,
    *,
    run_id: str | None = None,
    token: "object | None" = None,
    trace: "dict | None" = None,
    exec_replay: dict | None = None,
    env_replay: dict | None = None,
    combo_replay: object = _COMBO_REPLAY_UNSET,
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

    执行链恒 server;台账
    ``chain`` 键照记 ``"server"``,存量行的 ``legacy`` 值仅历史可读。

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
    steps = steps_from_payload(scenario_payload)
    _reject_unsupported_run_options(req)   # 未接面显式拒绝
    _validate_step_to(req, steps)

    # 执行配置分层②(§5)与 ④ 重跑快照 → _resolve_dispatch_exec_cfg
    _req_exec_id, _exec_cfg = await _resolve_dispatch_exec_cfg(
        db, user_id, req, target=target, token=token, exec_replay=exec_replay)

    # authz M2a S6:绑定校验先行(§8.2 标签解析要吃有效身份集合)
    _bindings = await _validated_bindings(db, req)

    # 账户组合垫底(v4 §3.2):只取本次所选方案的组合;raw 与重跑快照
    # 均不回查当前组合。重跑必须完全吃 config_json 终值,否则当前组合
    # 新增服务会漂移进重跑、悬空组合会阻断历史快照。
    from . import account_combo as _ac
    from . import scheme_store
    from .run_params import RAW_SCHEME_ID

    _combo = _ac.ComboBase(None, "", 0)
    if combo_replay is _COMBO_REPLAY_UNSET:
        if req.scheme_id != RAW_SCHEME_ID:
            scheme = None
            if req.scheme_id:
                try:
                    scheme = await scheme_store.get_row(
                        db, target.scenario_id, req.scheme_id)
                except KeyError:
                    raise Conflict(
                        "scheme_not_owned",
                        f"执行方案不存在或不属于该场景: {req.scheme_id}")
            else:
                scheme = await scheme_store.resolve_for_run(
                    db, target.scenario_id, None)
            if scheme is not None:
                _combo = await _ac.scheme_combo(db, scheme.payload)
                _bindings = _ac.pad_bindings(_bindings, _combo)
    else:
        _combo = combo_replay or _ac.ComboBase(None, "", 0)

    # §8.2 标签解析链(三路分流)+ §6.3 环境告警 → _resolve_execution_env
    env_choice, env_warnings, _project_id = await _resolve_execution_env(
        db, req, target=target, scenario_payload=scenario_payload,
        steps=steps, bindings=_bindings, exec_cfg=_exec_cfg,
        exec_replay=exec_replay, env_replay=env_replay)

    # fanout 计算(compute_run_fanout 单源;params 合成单虚行)→
    # _resolve_dispatch_fanout
    (fanout_datasets, injections, selected_entries,
     skipped_while_degraded, _params_mode) = await _resolve_dispatch_fanout(
        db, target, req, scenario_payload)
    # raw 保留字(决策 3):carry 关闭 + 不取任何方案配方。skip_carry
    # 必须随任务下发 —— worker 不回查请求上下文(配方快照语义)。
    _skip_carry = (getattr(req, "scheme_id", None) == RAW_SCHEME_ID)

    # authz W6 执行人 ≠ 属主的脱敏上下文 + S4/S8 坐标 → _load_scenario_context
    _scen, _scen_owner_id, _scen_project_id = await _load_scenario_context(
        db, target, user_id)
    # 分层②决策 9 carry 覆盖链(④ 重跑直用快照终值)→ _resolve_carry_policy
    _exec_carry = await _resolve_carry_policy(
        db, exec_cfg=_exec_cfg, exec_replay=exec_replay,
        scen_project_id=_scen_project_id)
    # S8 凭证池裁决(个人池 / 项目池;graph 全单元同项目)→ _resolve_cred_project
    cred_project_id = await _resolve_cred_project(
        db, req, user_id, _scen_project_id)
    if _scen_owner_id is not None and user_id != _scen_owner_id:
        scenario_payload, fanout_datasets = _strip_cross_owner_payload(
            scenario_payload, fanout_datasets)

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
    # 注入清单(唯一实现)与 graph 全图缺槽 fail-fast → _resolve_auth_aliases
    auth_aliases = await _resolve_auth_aliases(
        db, user_id, scenario_payload, _bindings,
        graph=getattr(req, "graph", None), cred_project_id=cred_project_id)
    # S5 取用覆盖 + 决策 1 圈定(重跑照查快照)→ _resolve_slot_and_circled
    _slot_map, _circled = await _resolve_slot_and_circled(
        db, steps=steps, bindings=_bindings, exec_cfg=_exec_cfg,
        exec_replay=exec_replay)
    # M3 §8.5 预检硬门(三路径统一漏斗)→ _dispatch_precheck_gate
    await _dispatch_precheck_gate(
        db, req=req, target=target, project_id=_project_id,
        scenario_payload=scenario_payload, user_id=user_id,
        bindings=_bindings, auth_aliases=auth_aliases,
        slot_map=_slot_map, cred_project_id=cred_project_id,
        env=env_choice, circled=_circled, combo=_combo)

    # M2b Q3 行级 @slot 账号列 fail-fast(含令牌范围核对)→ _resolve_row_bindings
    row_bindings_cfg = await _resolve_row_bindings(
        db, user_id, fanout_datasets, req,
        circled=_circled, token=token, cred_project_id=cred_project_id)

    # 执行链恒 server(EXEC_CHAIN 键不存在;legacy 链退场见 ADR-0003 #23)。
    chain = "server"
    _validate_debug_request(req, total_runs=total_runs)

    # clientRef 幂等预查 + 建执行行(含 0056 唯一索引竞态兜底)→
    # _persist_dispatch_execution
    execution = await _persist_dispatch_execution(
        db, user_id=user_id, req=req, target=target,
        scenario_payload=scenario_payload, run_id=run_id,
        total_runs=total_runs, scen_project_id=_scen_project_id,
        token=token, trace=trace,
        config_json=_dispatch_config_json(
            run_id=run_id, req=req, target=target,
            scenario_payload=scenario_payload,
            auth_aliases=auth_aliases, cred_project_id=cred_project_id,
            row_bindings_cfg=row_bindings_cfg, bindings=_bindings,
            slot_map=_slot_map, exec_carry=_exec_carry, circled=_circled,
            req_exec_id=_req_exec_id, env_choice=env_choice,
            env_warnings=env_warnings,
            skipped_while_degraded=skipped_while_degraded,
            params_mode=_params_mode, skip_carry=_skip_carry,
            chain=chain, trace=trace, combo=_combo))

    # 执行配方入队,worker 认领驱动(spawn 进程内 fanout 不是执行路径)。
    # 配方是 dispatch 校验后的完整快照（worker 不回查请求上下文）；
    # chain（C13 台账）恒记 "server"（B6③ 后单链;键保留 = 存量行
    # legacy 值与新行同形可读,worker 不再消费该键）。配方装配 →
    # _dispatch_job_payload。
    from . import execution_queue as _eq
    payload = _dispatch_job_payload(
        req=req, chain=chain, execution_id=execution.id, run_id=run_id,
        user_id=user_id, scenario_payload=scenario_payload,
        fanout_datasets=fanout_datasets, selected_entries=selected_entries,
        scen_owner_id=_scen_owner_id, scen_project_id=_scen_project_id,
        cred_project_id=cred_project_id, auth_aliases=auth_aliases,
        bindings=_bindings, slot_map=_slot_map, exec_carry=_exec_carry,
        skip_carry=_skip_carry, env_choice=env_choice)
    await _eq.enqueue(db, execution.id, kind=payload["kind"], payload=payload)
    # 惰性 ensure:lifespan 未跑（测试 ASGITransport 直连）也能驱动队列
    _eq.ensure_workers()
    # RS3 plate_pins 不在此回填：job 经 DB 队列异步驱动，dispatch 返回时
    # fanout 尚未解析生效修订 —— 由 _fanout 解析出后自行落库。

    return RunResponse(
        runId=run_id, executionId=execution.id,
        identityMode=(token.kind if token is not None else "personal"))


# ─── C1 切片2:dispatch_target 取用/门禁辅助(抽缝不改语义)─────────

def _reject_unsupported_run_options(req: RunRequest) -> None:
    """RunOptions 未接面显式拒绝:step_from 需要被跳过上游的输出
    由外部提供(同 GraphControlSpec 不开放 fromNode 的理由);subscribe
    平台无消费面。生成物形状收下了这两个键,但派发链静默丢弃它们
    会制造"看似生效"的假象 —— 409 说清楚,不兼容不吞。
    """
    if req.run_options is None:
        return
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


def _validate_step_to(req: RunRequest, steps: list) -> None:
    """step_to 校验(同 V1 executions:与场景 steps 数比对,越界 409)。"""
    if req.step_to is None:
        return
    if not steps:
        raise NotFound("no_steps", "scenario has no steps; step_to cannot be set")
    if req.step_to >= len(steps):
        raise Conflict(
            "step_to_out_of_range",
            f"step_to={req.step_to} out of range (0..{len(steps) - 1})",
        )


def _validate_debug_request(req: RunRequest, *, total_runs: int) -> None:
    """调试前置(引擎既有约束的收口):单 case 且无乘法、非 graph。"""
    if getattr(req, "debug", None) is None:
        return
    if getattr(req, "graph", None) is not None:
        raise Conflict("debug_not_supported", "graph 执行不支持调试")
    if total_runs != 1:
        raise Conflict(
            "debug_single_case",
            "调试执行仅支持单 case（数据集行 × 注入族须为 1）")
    if int(req.n_runs or 1) != 1:
        raise Conflict("debug_single_run", "调试执行要求 nRuns=1")


async def _resolve_dispatch_exec_cfg(
    db: AsyncSession, user_id: int, req: RunRequest, *, target: RunTarget,
    token: object | None, exec_replay: dict | None,
) -> tuple:
    """执行配置分层②(设计方案 §5):JWT 手动场景执行吃执行配置(显式
    选定或默认行);令牌(同指纹不变量)/编排 graph(单元自治)/临时
    调用不吃 —— 显式携带而不可用即拒,不静默忽略(似生效未生效)。
    ④ 分层:``exec_replay``(重跑)传入终值快照 —— 不回查配置行、
    不走解析(§7:配置后改不影响历史执行)。返回 (req_exec_id, exec_cfg)。
    """
    _req_exec_id = getattr(req, "exec_config_id", None)
    if (exec_replay or None) is not None:
        return exec_replay.get("execConfigId") or None, None
    _exec_eligible = (token is None
                      and getattr(req, "graph", None) is None
                      and target.kind == "scenario")
    if _req_exec_id is not None and not _exec_eligible:
        raise Conflict(
            "exec_config_unsupported",
            "执行配置只对个人(JWT)手动场景执行开放"
            "(令牌/编排/临时调用不吃)")
    if not _exec_eligible:
        return _req_exec_id, None
    from .exec_config import ExecConfigNotFound, load_choice
    try:
        _exec_cfg = await load_choice(db, user_id, _req_exec_id)
    except ExecConfigNotFound as e:
        raise NotFound("exec_config_not_found", str(e)) from None
    return _req_exec_id, _exec_cfg


async def _validated_bindings(db: AsyncSession, req: RunRequest) -> dict:
    """authz M2a S6:绑定 = 服务键 → 别名;选的别名须存在且同基础服务
    (先行 —— §8.2 标签解析要吃有效身份集合,绑定校验必须在前)。
    """
    _bindings = {k: b.model_dump(by_alias=True)
                 for k, b in (req.service_bindings or {}).items()}
    from .service_aliases import (BindingAliasInvalid,
                                  validate_binding_aliases)
    try:
        await validate_binding_aliases(db, _bindings)
    except BindingAliasInvalid as e:
        raise Conflict(e.code, e.message,
                       extra={"service": e.service, "alias": e.alias}) from None
    return _bindings


async def _resolve_execution_env(
    db: AsyncSession, req: RunRequest, *, target: RunTarget,
    scenario_payload: dict, steps: list, bindings: dict, exec_cfg,
    exec_replay: dict | None, env_replay: dict | None,
):
    """§8.2 标签解析链:**有效调用身份标签 >
    项目默认 > 平台默认**。显式注入(RunRequest/graph 的
    environmentId)与方案/执行配置/偏好链位全部退役;多身份标签
    不一致 → env_mixed 硬拦截(无逃生口)。三路分流:
    * rerun(``env_replay``)按首发快照回放,不重解析(重解析会让
      旧通道经 RunRequest.environmentId 传键,字段退役后被 pydantic
      静默丢弃,「按快照回放」实际从未生效);
    * graph 单元自治:顶层不解析(快照记空),逐单元在
      materialize_graph 内按各自身份集合解析(顶层
      无条件解析,宿主标签恒非空,被 graph_dispatch 当重放快照钉
      整图,逐单元解析不可达);
    * scenario/adhoc 现解析:有效身份 = 绑定 + 执行配置换用(slot_map)
      后的取用集合;adhoc 无项目归属,身份自 payload 定义扫描
      (call.user = 条目名,与 prepare_adhoc 校验链同口径 —— 派发侧
      填身份名,否则执行标签恒为平台默认,校验过的
      地址/版本线与实际执行可能不是同一套)。

    返回 (env_choice, env_warnings, project_id);project_id 供下游
    carry/凭证/硬门坐标用(rerun 回放同样需要)。§6.3 环境告警(本次
    标签的版本线 vs 场景钉定)一并生成 —— 告警失败不阻塞执行,降级可见。
    """
    from .env_chain import EnvChoice, EnvMixed, NO_ENV, resolve_execution_tag
    # 身份/项目坐标先集(rerun 回放也需要 project_id 供硬门地址/分区判定)
    _tag_names: list[str] = []
    _project_id: int | None = None
    if target.kind == "adhoc":
        from . import service_aliases as _sa
        _tag_names = list(await _sa.exec_auth_aliases_of_definition(
            db, definition_from_payload(scenario_payload), bindings))
    elif target.kind == "scenario":
        from sqlalchemy import select as _sel
        _project_id = (await db.execute(_sel(ComposerScenario.project_id).where(
            ComposerScenario.scenario_id == target.scenario_id))).scalar()
        from . import service_aliases as _sa
        _tag_names = list(await _sa.exec_auth_aliases_of_definition(
            db, definition_from_payload(scenario_payload), bindings))
        if exec_cfg is not None and exec_cfg.explicit and exec_cfg.bindings:
            from .service_aliases import slot_lookup_overrides as _slo
            _sm = await _slo(db, steps, bindings, exec_cfg.bindings)
            _tag_names = list(dict.fromkeys(
                _sm.get(a, a) for a in _tag_names if _sm.get(a, a)))
    if env_replay is not None:
        env_choice = EnvChoice.from_snapshot(env_replay) or NO_ENV
    elif getattr(req, "graph", None) is not None:
        env_choice = NO_ENV
    else:
        try:
            env_choice = await resolve_execution_tag(
                db, identity_names=_tag_names, project_id=_project_id)
        except EnvMixed as e:
            raise Conflict("env_mixed", str(e),
                           extra={"identities": e.entries}) from None
    try:
        env_warnings = await _check_env_consistency(
            db, scenario_payload, env_choice.env_id)
    except Exception as e:  # noqa: BLE001 — 告警失败不阻塞执行,但降级可见
        env_warnings = []
        logger.warning(
            "run_dispatcher: env consistency 告警生成失败(告警面置空): {}",
            e)
    return env_choice, env_warnings, _project_id


async def _resolve_dispatch_fanout(
    db: AsyncSession, target: RunTarget, req: RunRequest,
    scenario_payload: dict,
):
    """fanout 计算(权限域二期 P1 抽出为 compute_run_fanout:suite 总量
    预检与本处共用同一份实现,算法不得漂移)。
    入站参数(设计 决策 5):params 已在路由入口五道闸校验,
    此处合成为**单虚行**走数据集行既有通路,跳过 compute_run_fanout
    —— 互斥族已拒 params+dataSets/injection 组合;方案配方带入的
    数据集行不消费(评审 ①「砍掉比缝合便宜」)。datasetId=None 与
    基线空覆盖行同拍(compute_run_fanout 的 L780 口径)。
    返回 (fanout_datasets, injections, selected_entries,
    skipped_while_degraded, params_mode)。
    """
    _params_mode = bool(getattr(req, "params", None))
    if _params_mode:
        from .run_params import virtual_row
        return ([{"datasetId": None,
                  "rows": [(0, virtual_row(req.params))]}],
                [None], [], [], _params_mode)
    (fanout_datasets, injections, selected_entries,
     skipped_while_degraded) = await compute_run_fanout(
        db, target.scenario_id, scenario_payload, req)
    return (fanout_datasets, injections, selected_entries,
            skipped_while_degraded, _params_mode)


async def _load_scenario_context(db: AsyncSession, target: RunTarget,
                                 user_id: int):
    """authz W6 的执行上下文:载入场景行取属主/项目坐标。
    临时调用(adhoc):payload 由调用者即席提供,执行人即作者 —— 显式
    记为本人(built_in_users fail-closed,None 会把作者自己的也当空)。
    返回 (scen, scen_owner_id, scen_project_id);S4:carry 作用域第二层
    (项目层;adhoc/私有区 = None → 个人层)。
    """
    _scen = (await get_row(db, target.scenario_id)
             if getattr(target, "kind", "scenario") == "scenario"
             and target.scenario_id else None)
    _scen_owner_id = _scen.owner_id if _scen is not None else user_id
    _scen_project_id = _scen.project_id if _scen is not None else None
    return _scen, _scen_owner_id, _scen_project_id


async def _resolve_carry_policy(db: AsyncSession, *, exec_cfg,
                                exec_replay: dict | None,
                                scen_project_id: int | None):
    """分层②决策 9:项目区个人 carry 覆盖「默认不吃、显式吃」(裁决
    单源 exec_config.carry_overrides_for,预览同款);⑧ 项目区链的
    项目默认配置覆盖层压在显式个人之下(§5:显式个人 > 项目配置 >
    项目层 > 公共层);④ 重跑直用快照终值(区规则在首发已裁,
    不二次裁决)。
    """
    if (exec_replay or None) is not None:
        return exec_replay.get("carryOverrides") or None
    from .exec_config import (carry_overrides_for,
                              merge_carry_overrides,
                              project_carry_overrides)
    _exec_carry = carry_overrides_for(exec_cfg, scen_project_id)
    _proj_ov = await project_carry_overrides(db, scen_project_id)
    return merge_carry_overrides(_proj_ov, _exec_carry)


async def _resolve_cred_project(db: AsyncSession, req: RunRequest,
                                user_id: int,
                                scen_project_id: int | None) -> int | None:
    """S8 凭证来源:缺省 / 'personal' = 执行人个人池;'project' = 场景所属
    普通项目的项目凭证池(执行人须是项目成员)。编排(graph):全部单元
    须同属一个普通项目 —— 凭证池只有一个,不跨项目混取。
    """
    if getattr(req, "credential_source", None) != "project":
        return None
    from .zone import can_use_project_credentials
    _graph = getattr(req, "graph", None)
    _cred_pid = scen_project_id
    if _graph is not None:
        _unit_ids = list(dict.fromkeys(
            u.scenario_id for u in
            [*_graph.before, *_graph.units, *_graph.after]))
        _unit_pids = set((await db.execute(
            select(ComposerScenario.project_id).where(
                ComposerScenario.scenario_id.in_(_unit_ids))
        )).scalars().all())
        if len(_unit_pids) != 1 or None in _unit_pids:
            raise Conflict(
                "credential_source_invalid",
                "项目凭证要求编排的全部单元同属一个普通项目")
        _cred_pid = next(iter(_unit_pids))
    if not await can_use_project_credentials(db, user_id, _cred_pid):
        raise Conflict(
            "credential_source_invalid",
            "项目凭证只能用于你所在普通项目的场景")
    return _cred_pid


def _strip_cross_owner_payload(scenario_payload: dict, fanout_datasets: list):
    """authz W6:执行人 ≠ 场景属主(引用执行 / suite 聚合跑他人成员)——
    原件不剥(发布不改原件),执行形态在此脱敏:数据集敏感列剥、
    payload 去 config.users(快照/任务参数不落作者明文;内置凭证主
    规则在 prepare_exec 本就当空,两者同口径)。返回脱敏后的
    (scenario_payload, fanout_datasets)。
    """
    from .scenario_store import (
        strip_builtin_credentials, strip_sensitive_columns)
    payload = strip_builtin_credentials(copy.deepcopy(scenario_payload))
    datasets = [
        {**fd, "rows": [(i, (strip_sensitive_columns([r])[0]
                             if r else r))
                        for i, r in fd["rows"]]}
        for fd in fanout_datasets]
    return payload, datasets


async def _resolve_auth_aliases(db: AsyncSession, user_id: int,
                                scenario_payload: dict, bindings: dict, *,
                                graph, cred_project_id: int | None) -> list:
    """注入清单 —— 唯一实现(service_aliases.exec_auth_aliases:模板扫描
    (steps + config.setup/teardown,webhook v4 §3.2)∪ 生效别名声明
    条目(S6:绑定选别名即换用))。存档口径(§4.1 拍板):
    config_json.serviceBindings 只记原始绑定,别名默认只体现于
    injectedAuths 清单与实际注入的 users。

    编排缺槽按**全图**凭证清单判(与物化同源),不是锚点场景的
    清单 —— 否则单元缺槽要到执行期才步骤级报错。TOK-02
    个人池与项目凭证池同闸 —— 个人池缺身份
    静默漏到引擎层匿名调用 —— 双池统一 fail-fast。
    """
    auth_aliases = await service_aliases.exec_auth_aliases_of_definition(
        db, definition_from_payload(scenario_payload), bindings)
    if graph is None:
        return auth_aliases
    from . import graph_dispatch as _gd
    try:
        _g_missing, _g_ambig = await _gd.missing_auth_aliases(
            db, graph.model_dump(by_alias=True), user_id,
            cred_project_id=cred_project_id)
    except _gd.GraphDispatchError as e:
        raise Conflict("graph_invalid", str(e)) from None
    if _g_ambig:
        # 歧义独立报(不误标「未登记」)
        raise Conflict(
            "auth_aliases_ambiguous",
            "以下身份条目命中多个候选账户(同引用多行且无同标签唯一"
            "命中),请调整条目环境标签或清理同名账户:"
            + "、".join(_g_ambig),
            extra={"aliases": _g_ambig,
                   "credentialSource": ("project" if cred_project_id
                                        is not None else "personal")})
    if _g_missing:
        if cred_project_id is not None:
            raise Conflict(
                "auth_aliases_missing",
                "以下身份条目项目凭证未登记,请项目管理员在项目配置页"
                "登记,或改用个人凭证:" + "、".join(_g_missing),
                extra={"aliases": _g_missing,
                       "credentialSource": "project"})
        raise Conflict(
            "auth_aliases_missing",
            "以下身份条目在你的个人凭证池未登记,请先在「凭证管理」"
            "登记后再发起编排:" + "、".join(_g_missing),
            extra={"aliases": _g_missing,
                   "credentialSource": "personal"})
    return []      # 已按全图核对;锚点清单不再重复判


async def _resolve_slot_and_circled(db: AsyncSession, *, steps: list,
                                    bindings: dict, exec_cfg,
                                    exec_replay: dict | None):
    """S5 失败即中止:注入清单在执行人池解不到账户 → 整单拒发(否则
    告警继续、执行期步骤级报错;预检口径与执行对齐)。取用裁决与
    注入/预览同一份(pick_bindings)。分层②:显式选定配置的绑定把
    取用条目换掉(注入标签不变;仅显式选定参与,默认行不自动换用)。
    决策 1 圈定即承诺(阶段 1):生效配置行(显式选定 > 本人默认;令牌/
    graph/adhoc 不吃配置,天然不圈)非空圈定集 = 白名单生效;重跑按
    首发快照照查(§7 配置后改不影响历史执行)。比对在 precheck_hard_gate
    同一道门;行级 @slot 绑定在 _resolve_row_bindings 同一码拦截。
    返回 (slot_map, circled)。
    """
    _slot_map: dict[str, str] = {}
    if (exec_replay or None) is not None:
        _slot_map = dict(exec_replay.get("slotMap") or {})
    elif exec_cfg is not None and exec_cfg.explicit and exec_cfg.bindings:
        from .service_aliases import slot_lookup_overrides
        _slot_map = await slot_lookup_overrides(db, steps, bindings,
                                                exec_cfg.bindings)
    if (exec_replay or None) is not None:
        _circled: frozenset[str] = frozenset(
            exec_replay.get("circledAliases") or [])
    else:
        _circled = exec_cfg.circled if exec_cfg is not None else frozenset()
    return _slot_map, _circled


async def _dispatch_precheck_gate(
    db: AsyncSession, *, req: RunRequest, target: RunTarget,
    project_id: int | None, scenario_payload: dict, user_id: int,
    bindings: dict, auth_aliases: list, slot_map: dict,
    cred_project_id: int | None, env, circled,
    combo: "object | None" = None,
) -> None:
    """M3 §8.5 预检硬门:三路径统一 —— UI/JWT、access
    token 都经本漏斗;判定与 /run/precheck 共用一套分类(run_precheck
    私有函数,「不开第二份」)。webhook 定时路径在 integration_runner
    装载前接同一门。graph(逐单元物化)与 adhoc(check_addresses
    专属链)不走此门。旧 auth_aliases_missing 缺失检查由门的
    identity_missing/account_missing 细分承接(码更准,文案承接)。
    """
    if target.kind != "scenario" or getattr(req, "graph", None) is not None:
        return
    from ..routers.run_precheck import PrecheckGateError, precheck_hard_gate
    try:
        await precheck_hard_gate(
            db, project_id=project_id,
            definition=definition_from_payload(scenario_payload),
            user_id=user_id, bindings=bindings,
            auth_aliases=auth_aliases,
            slot_map=slot_map or None,
            cred_project_id=cred_project_id, env=env,
            circled=circled or None, combo=combo)
    except PrecheckGateError as e:
        raise Conflict(e.code, e.message, extra=e.detail) from None


async def _resolve_row_bindings(db: AsyncSession, user_id: int,
                                fanout_datasets: list, req: RunRequest, *,
                                circled, token: object | None,
                                cred_project_id: int | None) -> dict:
    """M2b Q3 数据集按账号驱动:行账号列 ``@slot.<槽>`` = 本次凭证池里的
    绑定名。派发前扫全部选中行 fail-fast(缺失 / 环境不符整单拒发);
    令牌调用另核对覆盖绑定 id ⊆ 令牌范围。返回 row_bindings_cfg
    ({datasetId:rowIndex: {槽: 绑定 id}});无行引用时恒空。
    """
    _row_refs = [
        (fd.get("datasetId"), i, slot, alias)
        for fd in fanout_datasets for i, r in fd["rows"]
        for slot, alias in run_prepare.row_binding_refs(r).items()]
    if not _row_refs:
        return {}
    if getattr(req, "graph", None) is not None:
        raise Conflict(
            "dataset_binding_unsupported",
            "suite 编排暂不支持数据集账号列(@slot.<槽>)")
    _hit, _miss, _amb = await run_prepare.lookup_row_bindings(
        db, user_id, {(s, a) for _d, _i, s, a in _row_refs},
        cred_project_id=cred_project_id)
    _src = "project" if cred_project_id is not None else "personal"
    for code, bad, msg in (
            ("dataset_binding_missing", set(_miss),
             ("以下数据集行的账号在项目凭证中未登记:"
              if cred_project_id is not None else
              "以下数据集行的账号在你名下没有同名绑定:")),
            ("dataset_binding_ambiguous", set(_amb),
             "以下数据集行的账号绑定存在多候选(同系统多标签且无"
             "唯一命中),请为其补充同标签账户或改绑:")):
        if bad:
            rows_out = [
                {"datasetId": d, "rowIndex": i, "slot": s, "alias": a}
                for d, i, s, a in _row_refs if (s, a) in bad][:20]
            raise Conflict(code, msg + "、".join(
                f"{r['slot']}={r['alias']}(行 {r['rowIndex']})"
                for r in rows_out),
                extra={"rows": rows_out, "credentialSource": _src})
    # 决策 1 圈定即承诺(阶段 1):行级 @slot 的取用名一并计入比对
    # (与 precheck_hard_gate 的定义级差集同码互补;行引用只在派发
    # 段可见,故在此拦)。未圈定(空集)= 跳过。
    if circled:
        _rows_out_c = sorted({a for _d, _i, _s, a in _row_refs
                               if a not in circled})
        if _rows_out_c:
            raise Conflict(
                "identity_not_circled",
                "以下数据集行账号绑定不在本次生效执行配置的圈定集内,"
                "请到执行配置页「纳入」后重跑:" + "、".join(_rows_out_c),
                extra={"aliases": _rows_out_c})
    if token is not None:
        from . import access_token as _at
        _scope_aliases, _scope_auths = await _at.load_scope(db, token.id)
        # PickedIdentity 无 .id(slots),
        # 绑定标识 = account_id —— 与十行下方的留档路径同款
        _out = sorted({a for (s, a), b in _hit.items()
                       if b.account_id not in _scope_auths})
        if _out:
            raise Conflict(
                _at.ERR_RESOURCE_NOT_ALLOWED,
                "数据集行的账号绑定不在令牌授权范围:" + "、".join(_out),
                extra={"aliases": _out})
    row_bindings_cfg: dict[str, dict[str, int]] = {}
    for d, i, s, a in _row_refs:
        # PickedIdentity 的绑定标识是 account_id(P1 缺陷修复:旧读
        # .id → 行级绑定留档路径自 P1 起必 AttributeError)
        row_bindings_cfg.setdefault(f"{d}:{i}", {})[s] = (
            _hit[(s, a)].account_id)
    return row_bindings_cfg


async def _dup_client_ref_id(db: AsyncSession, client_ref: str, *,
                             token_id: int | None, user_id: int) -> int | None:
    """clientRef 幂等查重(设计 决策 8):外部投递天然
    at-least-once,重复 clientRef = 重复业务订单。身份维度与 0056 部分
    唯一索引同拍:令牌 = (token_id, client_ref);JWT = (owner_id,
    client_ref) ∧ token_id IS NULL。预查与 IntegrityError 兜底回查共用。
    """
    _idem_cond = Execution.client_ref == client_ref
    if token_id is not None:
        _idem_cond &= Execution.token_id == token_id
    else:
        _idem_cond &= (Execution.token_id.is_(None)
                       & (Execution.owner_id == user_id))
    return (await db.execute(
        select(Execution.id).where(_idem_cond)
        .order_by(Execution.id).limit(1))).scalar_one_or_none()


def _dup_client_ref_conflict(dup_id: int) -> Conflict:
    """重复提交即首次投递已受理;409 回显原 executionId(重跑走 rerun)。
    返回异常实例由调用方 raise(兜底路径可带 ``from None`` 消噪)。
    """
    return Conflict(
        "duplicate_client_ref",
        f"clientRef 已被执行 #{dup_id} 使用;重复提交即首次投递"
        "已受理,请用原 executionId 查询结果(重跑走 rerun)",
        extra={"executionId": dup_id})


async def _persist_dispatch_execution(
    db: AsyncSession, *, user_id: int, req: RunRequest, target: RunTarget,
    scenario_payload: dict, run_id: str, total_runs: int,
    scen_project_id: int | None, token: object | None,
    trace: dict | None, config_json: dict,
) -> Execution:
    """建执行行(整单落库的单写点)+ clientRef 幂等(设计
    决策 8):预查 → 插入;并发竞态由 0056 部分唯一索引兜底(撞
    IntegrityError 回查映射同 409)。回查也落空 = 违规来自别的约束
    (与本索引无关)→ 原样上抛,不编造 duplicate_client_ref。
    列级语义见各字段旁注。
    """
    if req.client_ref:
        _dup_id = await _dup_client_ref_id(
            db, req.client_ref,
            token_id=(token.id if token is not None else None),
            user_id=user_id)
        if _dup_id is not None:
            raise _dup_client_ref_conflict(_dup_id)
    try:
        return await _create_execution(
        db,
        # (Case 层解散后执行的挂载点就是场景;临时调用为占位 id)。
        scenario_id=target.scenario_id,
        owner_id=user_id,
        # S8 审计「项目 + 发起人」:执行所属项目 = 场景项目快照
        # (S1.1 项目执行对成员可见的数据源)
        project_id=scen_project_id,
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
            (definition_from_payload(scenario_payload).get("meta") or {})
            .get("name") or ""
        ).strip(),
        # 执行时场景快照:与传给 _fanout 的 scenario_payload 同拍同源
        # (同一读取),保证"快照即所执行";深拷贝隔离后续 fanout 内的
        # setdefault 写穿,不污染快照。
        scenario_snapshot=copy.deepcopy(scenario_payload),
        # RS3：plate_pins 随 fanout 后回填（生效修订在 fanout 内解析）
        plate_pins=None,
        config_json=config_json,
    )
    except IntegrityError:
        if not req.client_ref:
            raise
        await db.rollback()
        _dup_id = await _dup_client_ref_id(
            db, req.client_ref,
            token_id=(token.id if token is not None else None),
            user_id=user_id)
        if _dup_id is None:
            raise
        raise _dup_client_ref_conflict(_dup_id) from None


def _dispatch_config_json(
    *, run_id: str, req: RunRequest, target: RunTarget,
    scenario_payload: dict, auth_aliases: list,
    cred_project_id: int | None, row_bindings_cfg: dict, bindings: dict,
    slot_map: dict, exec_carry, circled, req_exec_id, env_choice,
    env_warnings, skipped_while_degraded, params_mode: bool,
    skip_carry: bool, chain: str, trace: dict | None,
    combo: "object | None" = None,
) -> dict:
    """config_json 台账配方(纯装配):dispatch 校验后的终值快照逐键
    落档 —— 重跑(rerun)按此回放,worker 不回查请求上下文。
    """
    return {
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
        # S8 凭证来源(重跑按此回放;项目凭证另记所用项目)
        **({"credentialSource": "project",
            "credentialProjectId": cred_project_id}
           if cred_project_id is not None else {}),
        # M2b Q3:行级账号覆盖({datasetId:rowIndex: {槽: 绑定 id}})
        **({"rowBindings": row_bindings_cfg} if row_bindings_cfg else {}),
        # 服务键 → {alias}(S6;重跑按此回放)—— 账户组合垫底后的
        # **合并终值**(§6.4):重跑按既有原则吃快照终值,不随组合后续
        # 修改漂移
        "serviceBindings": bindings,
        # 执行指令快照:RunOptions 生成物 dump(snake_case 内层,
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
        # 账户组合溯源快照(§6.4):id+名称+修订号——serviceBindings 已是
        # 合并终值,组合后续修改不漂移重跑;此块只做「当次用了哪版组合」
        # 的台账定位
        **({"accountComboId": combo.combo_id,
            "accountComboName": combo.name,
            "accountComboRevision": combo.revision}
           if combo is not None and combo.bound else {}),
        # 分层④:执行配置终值快照 —— 重跑回放的依据(空 dict =
        # 当时无覆盖,与旧行缺键=回落默认链解析可区分);execConfigId
        # 为链路溯源(回放不回查该行)
        "execSlotMap": slot_map,
        "execCarryOverrides": exec_carry,
        # 决策 1 圈定即承诺(阶段 1):圈定集终值快照 —— 重跑照查
        # (单一规则不豁免);旧行缺键 = 当时未圈,回放空集 = 跳过。
        "execCircledAliases": sorted(circled),
        **({"execConfigId": req_exec_id}
           if req_exec_id is not None else {}),
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
        # ── 入站执行参数快照(设计 §5)──────────────────────
        # rerun 回放 params/schemeId("raw" 原样);clientRef 不回放
        # (与 batchId 同口径:重跑是新的一次独立发起)。carryPolicy
        # "off" 仅 raw(决策 3);paramsStrict = 场景契约快照。
        **({"inboundParams": req.params} if params_mode else {}),
        **({"carryPolicy": "off"} if skip_carry else {}),
        **({"paramsStrict": bool((scenario_payload or {}).get("paramsStrict"))}
           if params_mode else {}),
    }


def _dispatch_job_payload(
    *, req: RunRequest, chain: str, execution_id: int, run_id: str,
    user_id: int, scenario_payload: dict, fanout_datasets: list,
    selected_entries: list, scen_owner_id, scen_project_id,
    cred_project_id: int | None, auth_aliases: list, bindings: dict,
    slot_map: dict, exec_carry, skip_carry: bool, env_choice,
) -> dict:
    """C11 worker 任务配方(纯装配):dispatch 校验后的完整快照,
    graph 与 cases 两种形态;worker 认领后不回查请求上下文。
    """
    if getattr(req, "graph", None) is not None:
        return {
            "kind": "graph",
            "chain": chain,
            "args": {
                "execution_id": execution_id, "run_id": run_id,
                "owner_id": user_id,
                "graph_spec": req.graph.model_dump(by_alias=True),
                # S2.1:显式位才整图生效;否则逐单元解析(见 graph_dispatch)
                "env_snapshot": env_choice.snapshot(),
                "n_runs": req.n_runs, "halt_at": req.step_to,
                "scenario_payload": dict(scenario_payload),
                # S8 收口:项目凭证池(None = 发起人个人池)
                "cred_project_id": cred_project_id,
            },
        }
    debug_spec = getattr(req, "debug", None)
    return {
        "kind": "cases",
        "chain": chain,
        "debug": (debug_spec.model_dump(mode="json")
                  if debug_spec is not None else None),
        "args": {
            "execution_id": execution_id, "run_id": run_id,
            "scenario_payload": dict(scenario_payload),
            "datasets": fanout_datasets,
            "injections": selected_entries,
            "owner_id": user_id,
            # authz W6:场景属主随任务下发,内置凭证主规则在
            # _fanout → prepare_exec 判(executor ≠ 属主 ⇒ 当空);
            # adhoc(临时调用)= 执行人本人(即席 payload,属主显式
            # 记为本人;built_in_users fail-closed,None 一律当空)
            "scenario_owner_id": scen_owner_id,
            # S2.1:环境随配方下发(地址 ③ 层并入部署表)
            "env_snapshot": env_choice.snapshot(),
            # S4:carry 作用域第二层(项目层;None = 私有区 → 个人层)
            "scenario_project_id": scen_project_id,
            # S8:项目凭证池(None = 执行人个人池)
            "cred_project_id": cred_project_id,
            "auth_aliases": auth_aliases,
            "halt_at": req.step_to,
            "n_runs": req.n_runs,
            "parallel": req.parallel,
            "service_bindings": bindings,
            # 分层②:条目取用覆盖(声明条目 → 池取用条目)与 carry
            # 覆盖随任务配方下发(纯值;worker 不回查配置行 —— 快照
            # 语义与方案引用同款,配置后改不影响已派发执行)
            "slot_map": slot_map,
            "exec_carry_overrides": exec_carry,
            # 入站参数(设计 决策 3):raw 保留字 →
            # prepare_exec 跳过 carry 上下文构建。升级前入队的旧
            # 配方缺键 = False(缺省不跳),回放语义不受影响。
            "skip_carry": skip_carry,
        },
    }


# ─── C11：worker 任务体入口（payload → fanout）──────────────────

async def run_job_from_payload(job: dict) -> None:
    """execution_queue worker 的任务体：解包配方 → _fanout/_fanout_graph。

    payload 是 dispatch_run 校验后的完整快照（JSON 往返安全形态）；
    ServiceBinding 在此重建为模型（_fanout 消费面不变）。
    """
    p = job["payload"]
    args = dict(p["args"])
    if p["kind"] == "graph":
        # B6③:单链后配方不再携带链选择;升级前入队的存量配方(chain=legacy)
        # 由 worker 消费时一律按 server 链执行(键忽略,仅台账可读)。
        await _fanout_graph(db_factory=_session_factory, **args)
        return
    # S6:升级前入队的配方可能带 url/authAlias —— 剥离退役字段再重建
    args["service_bindings"] = {
        k: ServiceBinding(**v) for k, v in
        scrub_retired_bindings(args.get("service_bindings")).items()
    }
    await _fanout(
        db_factory=_session_factory,
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

    failed 兜底也发完成通知 —— 任务体崩溃是调用方无从得知的静默失败,
    零通知会漏报。
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
    env_snapshot: dict | None = None,
    cred_project_id: int | None = None,
) -> None:
    """graph 编排执行链 —— 物化 SuiteGraph → 单 spawn →
    事件投影台账(与单场景链同读面;乘法/并发/横切面在执行器)。
    C12/C13：chain=server 时 spawn 走执行器 server 实例。

    取消(graph 单元级取消方案 §6「可」项):取消轮询器置位后 ——
    ① 物化完成、下发执行器之前命中 → 不下发,canceled 零计数收口;
    ② 在飞 → 按链下发单元级取消:server 链向执行器 ``cancel(scope="unit")``
    (runId 返回前每 0.5s 重试);legacy 链写 ``--cancel-file`` 信号文件
    (执行器 drain)。两链同语义:在飞单元跑完、未启动主体记 cancelled、
    after 照常;收口时至少一个主体单元 cancelled → 执行记 canceled,否则
    按真实结果收口并在 config 写 ``cancelIgnored`` 留痕。
    能力门禁:spawn 期探测并落 ``job payload["unit_cancel"]`` —— server 链
    读 healthz cancel_scopes(旧执行器空能力,不下发,读侧 409);legacy 链
    读本地 gimbal FEATURES(GIMBAL_BIN 外部安装保守 False)。取消落在执行器
    启动窗口时总是先创建下发任务,session 就绪后按能力位决定发或停(§3.1)
    —— 停发并留痕 cancelIgnored=executor_no_unit_cancel。
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
    # 预检与收口 → _graph_prior_event_count / _graph_recover_failed
    _prior = await _graph_prior_event_count(db_factory, execution_id)
    if _prior:
        logger.warning(
            "run_dispatcher: graph execution {} recovered with {} prior "
            "events → failed (at-most-once, no graph replay)",
            execution_id, _prior)
        await _graph_recover_failed(db_factory, execution_id, _prior)
        await ingester.finalize()
        return

    # 取消轮询器只在真正要下发的路径上启动:上面的恢复分支在 try/finally
    # 之前返回,teardown 不会执行 —— 若在此之前启动,轮询任务会一直查库
    # 到进程退出(恢复后执行已 failed,取消位永远不会置上)。
    # 单元级取消装置(能力位/下发重试/teardown)→ _GraphCancelCtl
    cancel = _GraphCancelCtl(db_factory, execution_id)
    cancel.start()

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
                env=EnvChoice.from_snapshot(env_snapshot),
                # S8 收口:项目凭证池(None = 发起人个人池)
                cred_project_id=cred_project_id)
        graph = graph_bundle["graph"]
        graph_sem = graph_bundle
        if cancel.cancel_local["set"] or execution_id in _eq._cancel_hint:
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
        # 台账三件套(pins/baseline/m2_hash,判定失败不阻断)→
        # _persist_graph_semantics
        await _persist_graph_semantics(db_factory, execution_id, graph_sem)

        # 逐单元事件投影 → _graph_event_projection
        on_event = _graph_event_projection(unit_events, proj, ingester)
        result = await graph_dispatch.execute_graph(
            db_factory, execution_id, run_dir, graph,
            on_event=on_event, on_log=ingester.on_log,
            log_counters=ingester.pump_counters,
            m2_info=graph_sem.get("m2_info"),
            on_session=cancel.on_session)
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
        cancel.teardown()

    # ② 取消收口判定(方案 §2,取消位命中且主体单元有 cancelled →
    # canceled;否则按真实结果收口并留痕 cancelIgnored)→ _graph_cancel_verdict
    final_status, cancel_ignored = _graph_cancel_verdict(
        graph_spec, unit_events,
        cancel_set=cancel.cancel_local["set"], result=result,
        capable=cancel.capable)
    if final_status is not None:
        status = final_status

    # 台账(重构方案第 3 处)行装配与落库 + 计数(计数按单元累加;
    # blocked/cancelled 入 skipped)→ _graph_result_rows / _persist_graph_rows
    finished_ts = _utcnow().isoformat() + "Z"
    _row_states[execution_id] = []   # 无行级 registry;读侧回落 DB
    attempts_total = proj["attempts"] or int(
        getattr(result, "attempts", 0) or 0) or 1
    ordered_units, rows_to_write = _graph_result_rows(
        execution_id, status, graph_spec, unit_events, attempts_total)
    await _persist_graph_rows(db_factory, execution_id, rows_to_write,
                              ordered_units, finished_ts)
    cfg_patch: dict = {}
    if proj.get("gates"):
        # 判定门结论(第 4 处):经事件通道落 config_json,21 页实测值来源
        cfg_patch["gatesEvaluated"] = proj["gates"]
    if cancel_ignored:
        cfg_patch["cancelIgnored"] = cancel_ignored
    if cfg_patch:
        try:
            async with db_factory() as session:
                await _config_json_merge(session, execution_id, cfg_patch)
                await session.commit()
        except Exception as e:  # noqa: BLE001 — 结论留档 best-effort,降级可见
            logger.warning(
                "run_dispatcher: cancel 结论留档失败(config_json 未含"
                " cancelIgnored): {}", e)
    await _finalize_execution(db_factory, execution_id, status=final_status)


# ── graph 编排执行体辅助 ──────────────────────────────────────────

async def _graph_prior_event_count(db_factory: Any, execution_id: int) -> int:
    """graph 恢复预检:执行已有事件数(存在即「已开跑」)。查询失败按
    无进度处理(可重跑)。
    """
    from sqlalchemy import func as _f, select as _sel

    from ..models.execution import ExecutionEvent as _EV
    try:
        async with db_factory() as session:
            return (await session.execute(
                _sel(_f.count()).select_from(_EV)
                .where(_EV.execution_id == execution_id))).scalar()
    except Exception:  # noqa: BLE001 — 查询失败按无进度处理(可重跑)
        return 0


async def _graph_recover_failed(db_factory: Any, execution_id: int,
                                prior: int) -> None:
    """恢复重跑收口(整图 at-most-once):seq=0 图行留档 + N2 唯一终态迁移
    (原子守卫 + failed 通知兜底;P0-3.2 带重试版)。
    行留档失败仅告警(行台账缺失,终态不受影响)。
    """
    finished_ts = _utcnow().isoformat() + "Z"
    _row_states[execution_id] = []
    try:
        async with db_factory() as session:
            await _upsert_execution_rows(session, [{
                "execution_id": execution_id, "seq": 0,
                "unit_id": "graph", "branch": "graph", "attempts": 1,
                "dataset_id": None, "injection_id": None,
                "row_index": 0, "rep": 0,
                "status": "failed", "case_dir": "case-graph",
                "started_at": None, "finished_at": _iso_to_dt(finished_ts),
                "server_slot": None,
                "run_error": (
                    "recovered with prior events "
                    "(at-most-once, no graph replay)"),
            }])
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: 恢复路径 graph 行留档失败(行台账缺失,"
            "终态不受影响): {}", e)
    await transition_with_retry(
        db_factory, execution_id, STATUS_FAILED,
        dispatcher_error=(
            f"graph recovery: at-most-once 收口"
            f"({prior} prior events, 不整图重放)"))


class _GraphCancelCtl:
    """graph 单元级取消装置(取消方案 §6「可」项):
    取消轮询器置位后 —— ① 物化完成、下发执行器之前命中 → 不下发,
    canceled 零计数收口(调用方处理);② 在飞 → 向执行器
    ``cancel(scope="unit")``(runId 返回前每 0.5s 重试)。
    能力门禁:session 就绪时按 healthz cancel_scopes 落 job payload
    (旧执行器空能力 → 不下发,读侧按能力位 409)。B6③ 后单链,legacy
    --cancel-file 信号文件通道已随链退役。取消落在执行器启动窗口时总是
    先创建下发任务,session 就绪后按能力位决定发或停(§3.1)—— 旧执行器停发并留痕 cancelIgnored=executor_no_unit_cancel。
    """

    def __init__(self, db_factory: Any, execution_id: int) -> None:
        self._db_factory = db_factory
        self._execution_id = execution_id
        self.session: Any = None
        self.capable = False
        self.accepted = False
        self._recorded = False
        self.task: Any = None
        self.cancel_local: dict = {}
        self.poller: Any = None

    def start(self) -> None:
        """启动取消轮询器(on_set 钩子创建下发任务)。"""
        self.cancel_local, self.poller = _start_cancel_poller(
            self._db_factory, self._execution_id, on_set=self.on_cancel_set)

    async def _deliver(self) -> None:
        # 执行器受理前每 0.5s 重试:POST /runs 可能尚未返回 runId(cancel()
        # 返回 False);执行已结束(done)则停。能力检查在 session 就绪后做
        # (取消可能先于 session 到达):旧执行器(cancel_scopes 无 unit)
        # 停止下发 —— 读了也会被当 step 处理(带 A0 缺陷),按真实结果
        # 收口并留痕 cancelIgnored=executor_no_unit_cancel。
        while not self.cancel_local["done"]:
            ss = self.session
            if ss is not None:
                if not self.capable:
                    logger.info(
                        "run_dispatcher: graph execution {} executor lacks "
                        "unit cancel scope; cancel not delivered",
                        self._execution_id)
                    return
                try:
                    if await ss.cancel(scope="unit"):
                        self.accepted = True
                        logger.info(
                            "run_dispatcher: graph execution {} unit-level "
                            "cancel accepted by executor", self._execution_id)
                        return
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(0.5)

    def on_cancel_set(self) -> None:
        # 总是创建下发任务(§3.1):取消可能落在执行器
        # 启动窗口(ss.start 轮询 healthz 期间,on_session 未回调、能力位
        # 未落定),此时若按能力位拦截,轮询器命中一次即 return,能力位
        # 后来转 True 也无人再触发下发 —— 取消被接受却静默跑完。
        # 旧执行器的拦截挪进 _deliver(session 就绪后判)。
        if self.task is None:
            self.task = asyncio.create_task(self._deliver())

    def on_session(self, ss: Any) -> None:
        # 单元级取消能力:session 就绪时按 healthz 能力位落 job payload
        # (旧执行器 False → 不下发,读侧按能力位 409)
        self.session = ss
        self.capable = "unit" in (getattr(ss, "cancel_scopes", ()) or ())
        if not self._recorded:
            self._recorded = True
            asyncio.create_task(
                _record_unit_cancel(self._db_factory, self._execution_id,
                                    self.capable))

    def teardown(self) -> None:
        # 进程内快速通道也算命中(写位与轮询之间的窗口),再出清
        from . import execution_queue as _eq
        if self._execution_id in _eq._cancel_hint:
            self.cancel_local["set"] = True
        self.cancel_local["done"] = True
        self.poller.cancel()
        if self.task is not None:
            self.task.cancel()
        _eq._cancel_hint.discard(self._execution_id)


async def _persist_graph_semantics(db_factory: Any, execution_id: int,
                                  graph_sem: dict) -> None:
    """suite 执行接入版本模型 —— 台账三件套与单场景
    dispatcher 同点写(pins 来自成员声明合并[R25 已统一到交集生效修订],
    baseline 判定输入同口径;m2_hash 取 /convert 附带身份,随台账一次写)。
    台账性质:判定/写库失败不阻断执行。
    b2-3/b2-4/b2.5:追溯台账(PIN ∪ INTEGRATION)+ integration 标识
    补取,均抽为 run_semantics 可测函数(补取只进台账,不动执行副本)。
    """
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
    if not (_g_pins or _g_baseline is not None or _g_m2):
        return
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


def _graph_event_projection(
    unit_events: dict, proj: dict, ingester: _EventIngester,
) -> Callable[[dict], None]:
    """逐单元事件投影(重构方案第 3 处):unit → {started_at, finished_at,
    status};blocked/cancelled 单元不发事件,从 run.finished.details 按
    unit id 补齐。总状态不再取「最后一个 scenario.end」—— 后置通过
    会覆盖主体失败、判定门失败只改 exit_code 会被吞。返回 on_event 回调
    (尾端恒转发 ingester 落库)。
    """

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

    return _on_event


def _graph_cancel_verdict(graph_spec: dict, unit_events: dict, *,
                           cancel_set: bool, result: Any,
                           capable: bool) -> tuple:
    """② 取消收口判定(方案 §2):取消位命中且至少一个**主体**单元被执行器
    记 cancelled → 执行 canceled;命中但主体已全部启动/结束(没有单元可
    停)→ 按真实结果收口,config.cancelIgnored 留痕供详情页解释。
    返回 (final_status, cancel_ignored) —— final_status 非 None 即取消收口。
    """
    main_refs = [u.get("ref") for u in graph_spec.get("units", [])
                 if u.get("ref")]

    def _is_main(uid: str) -> bool:
        return any(uid == r or uid.startswith(r + "#") for r in main_refs)

    main_cancelled = any(
        ev.get("status") in ("cancelled", "canceled") and _is_main(uid)
        for uid, ev in unit_events.items())
    if not (cancel_set and result is not None):
        return None, None
    if main_cancelled:
        return STATUS_CANCELED, None
    if not capable:
        # 旧执行器(cancel_scopes 无 unit):取消被读侧接受(启动窗口
        # 能力位未落定)但未下发 —— 与「所有单元已启动」区分留痕,
        # 读侧 cancel_note 给对应解释。
        return None, "executor_no_unit_cancel"
    return None, "all units already started"


def _graph_result_rows(execution_id: int, status: str, graph_spec: dict,
                       unit_events: dict, attempts_total: int) -> tuple:
    """台账行装配(重构方案第 3 处):seq=0 图行(与 at-most-once 恢复路径
    同形)+ seq=1..n 逐单元行(按物化单元清单顺序;×重复变体按 unit
    标签 `ref#k` 追加在基座 ref 之后)。无事件且无 details 的单元按
    blocked 记(被 control.only 裁剪 / 未跑)。返回
    (ordered_units, rows_to_write) —— ordered_units 供计数消费。
    """
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
    rows_to_write: list[dict] = [
        {"execution_id": execution_id, "seq": 0,
         "unit_id": "graph", "branch": "graph",
         "attempts": attempts_total,
         "dataset_id": None, "injection_id": None,
         "row_index": 0, "rep": 0,
         "status": status, "case_dir": "case-graph",
         "started_at": None, "finished_at": None,
         "server_slot": None, "run_error": None}]
    for idx, (uid, ev) in enumerate(ordered_units, start=1):
        rows_to_write.append({
            "execution_id": execution_id, "seq": idx, "unit_id": uid,
            "branch": "graph", "attempts": 1,
            "dataset_id": None, "injection_id": None,
            "row_index": 0, "rep": 0,
            "status": ev.get("status") or "blocked",
            "case_dir": "case-graph",
            "started_at": _iso_to_dt(ev["started_at"])
            if ev.get("started_at") else None,
            "finished_at": _iso_to_dt(ev["finished_at"])
            if ev.get("finished_at") else None,
            "server_slot": None,
            "run_error": str(ev["error"])[:2000]
            if ev.get("error") else None,
        })
    return ordered_units, rows_to_write


async def _persist_graph_rows(db_factory: Any, execution_id: int,
                              rows_to_write: list, ordered_units: list,
                              finished_ts: str) -> None:
    """行台账落库 + 计数:upsert 单源(P3.5-2 job 重跑 graph 执行 —— 恢复
    时 graph 整图重放,事件 seq 已由 ingester 续接);计数按单元累加,
    blocked/cancelled 入 skipped。行留档失败仅告警(行台账缺失,计数照常)。
    """
    try:
        async with db_factory() as session:
            await _upsert_execution_rows(session, [
                {**r, "finished_at": r["finished_at"]
                 or _iso_to_dt(finished_ts)}
                for r in rows_to_write])
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: graph 行留档失败(行台账缺失,计数照常): {}",
            e)
    n_pass = sum(1 for _, ev in ordered_units
                 if ev.get("status") == "passed")
    n_fail = sum(1 for _, ev in ordered_units
                 if ev.get("status") in ("failed", "error", "halted"))
    await _bump_counters(db_factory, execution_id,
                         passed=n_pass,
                         failed=n_fail,
                         skipped=max(len(ordered_units) - n_pass - n_fail, 0))


# ── 执行前置共用段 ────────────────────────────────────────────
# _fanout 前置的命名缝:鉴权预检 / 台账写 / 会话池脚手架 / §7 收口序。
# 新执行面特性只接这些缝,不再平铺进 _fanout 主体。


async def _fanout_auth_preflight(
    db_factory, owner_id: int, auth_aliases: list[str], datasets,
    *, cred_project_id: "int | None", slot_map: "dict | None",
) -> tuple:
    """鉴权预检:owner 级解密一次 + 行账号列覆盖绑定(每 (槽, 绑定名)
    只解密一次)。解密失败 = AuthResolveError fail-fast(V1 严格语义,
    调用方整单收口);注入清单为空直接跳过解析。"""
    exec_auths = (
        await resolve_exec_auths(
            db_factory, owner_id, auth_aliases,
            cred_project_id=cred_project_id, slot_map=slot_map)
        if auth_aliases else [])
    row_auths_map = await run_prepare.resolve_row_bindings(
        db_factory, owner_id,
        {(s, a) for ds in datasets for _i, r in ds["rows"]
         for s, a in run_prepare.row_binding_refs(r).items()},
        cred_project_id=cred_project_id)
    return exec_auths, row_auths_map


async def _persist_run_telemetry(db_factory, execution_id: int, prep) -> None:
    """台账写:入库标准判定(A-3/W7)与 RS3 生效修订表 —— 与 pins 同点
    写,判定/写库失败均不阻断执行(台账性质;留默认值 = 未判定)。"""
    from . import run_semantics
    baseline: "tuple[bool, str | None, dict] | None" = None
    try:
        async with db_factory() as _sem_s:
            baseline = await run_semantics.assess_baseline(
                _sem_s, meta_plate=prep.meta_plate,
                endpoints_used=prep.endpoints_used,
                unanchored_services=prep.unanchored_services)
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning(
            'run_dispatcher: 入库标准判定失败 (execution={})', execution_id)
        baseline = None
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


def _fanout_pool_scaffold(datasets, injections, *, parallel: int,
                          debug: dict | None) -> ServerSessionPool:
    """会话池脚手架:槽位上限钳制(P3 收尾 —— parallel 可到
    MAX_RUNS_PER_EXECUTION,不钳制会一次冷启动上百个引擎进程,行排队
    等空闲槽位)+ 池构建。启动(start)由调用方绑定本执行 ingester。"""
    from .gimbal_server_session import ServerSessionPool
    _total_rows = (sum(len(ds["rows"]) for ds in datasets)
                   * len(list(injections) or [None]))
    _slots = (1 if debug is not None
              else max(1, min(int(parallel or 1), _total_rows or 1,
                              settings.EXEC_MAX_SERVER_INSTANCES)))
    return ServerSessionPool(size=_slots)


async def _drain_and_finalize(server_pool, ingester,
                              execution_id: int) -> None:
    """§7 顺序不变量单点实现:先关池(terminate 进程树、stderr 泵排空到
    EOF),再 finalize 冲刷已入缓冲的事件/日志 —— server 启动期已入缓冲
    的行不丢、ticker 不泄漏。收口失败可见但不阻断调用方。"""
    if server_pool is not None:
        try:
            await server_pool.close()
        except Exception as e:  # noqa: BLE001 — 收口失败可见(可能留引擎进程)
            logger.warning(
                "run_dispatcher: server pool close 失败(可能留引擎进程,"
                "execution={}): {}", execution_id, e)
    await ingester.finalize()


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
    debug: "dict | None" = None,
    scenario_owner_id: int | None = None,
    env_snapshot: dict | None = None,
    scenario_project_id: int | None = None,
    cred_project_id: int | None = None,
    slot_map: dict[str, str] | None = None,
    exec_carry_overrides: dict[str, dict[str, str | None]] | None = None,
    skip_carry: bool = False,
) -> None:
    """Per-row × per-repeat compose + convert + 执行器调用(恒 server 链)。

    ``env_snapshot``(S2.1):dispatch 落档的环境选择(与 config_json 同
    一份快照;旧配方缺键 = 无环境 = 旧 ③ 行为)。

    ``halt_at``(V1 step_to 移植):0-based 含端点,透传执行器
    ``options.step_to`` —— RuntimeControl 在该步后停(剩余步显示
    skipped)。

    C12:执行器 server 实例池(POST /runs + SSE 消费;单 run 设计,
    多行 × parallel>1 每槽位一实例),取消走 cancel 端点,结束
    terminate 进程树。``debug`` 单 case,会话注册进 ``debug_sessions``
    供平台调试台代理。

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
            except Exception as e:  # noqa: BLE001 — 收口失败可见(可能留引擎进程)
                logger.warning(
                    "run_dispatcher: teardown server pool close 失败"
                    "(execution={}): {}", execution_id, e)
        debug_sessions.pop(execution_id, None)
        _eq._cancel_hint.discard(execution_id)
        _row_states.pop(execution_id, None)

    # C12/P3.5-1:并发槽位实例池(C1 切片 1 起经 _fanout_pool_scaffold
    # 构建;单行/调试退化为单实例语义)。
    server_pool = _fanout_pool_scaffold(
        datasets, injections, parallel=parallel, debug=debug)
    # 执行器事件/日志流式入库(launcher on_event/on_log →
    # 缓冲 → 批量 execution_events;读侧 SSE/日志分析页共用)
    ingester = _EventIngester(db_factory, execution_id)
    await ingester.seed_from_db()   # P3.5-2：恢复重跑事件 seq 续接
    ingester.start()
    log_path = _jsonl_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # 每个 run 一个 case 目录:case 文件 + 引擎原生报告,并发 fan-out
    # 互不互踩;与 JSONL 同域构成执行审计面(什么数据真的打给了引擎)。
    run_dir = _run_dir(run_id)
    # (B6③ 后池恒建,旧 ``if server_pool is not None`` 死分支已除)
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
        # C1 切片 1:鉴权预检抽至 _fanout_auth_preflight(注入清单为空
        # 直接跳过解析;M2b Q3 行账号列覆盖绑定每个 (槽, 绑定名) 只解
        # 密一次)。
        exec_auths, row_auths_map = await _fanout_auth_preflight(
            db_factory, owner_id, auth_aliases, datasets,
            cred_project_id=cred_project_id, slot_map=slot_map)
    except AuthResolveError as e:
        logger.error(
            "run_dispatcher: auth resolve failed for execution {}: {}",
            execution_id, e,
        )
        total_rows = (sum(len(ds["rows"]) for ds in datasets)
                      * len(injections or [None]))
        # §7 顺序不变量在异常路径同样成立(C1 切片 1 起单点实现于
        # _drain_and_finalize):排空泵 → 冲刷 → 终态,不丢不漏。
        await _drain_and_finalize(server_pool, ingester, execution_id)
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

    # 装载准备归一 —— 别名 base_url 预解析(F4 方案 B,
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
        environment=EnvChoice.from_snapshot(env_snapshot),
        project_id=scenario_project_id,
        # S6:绑定选别名 → carry 别名键随之切换
        bindings={k: b.model_dump(by_alias=True)
                  for k, b in (service_bindings or {}).items()},
        # 分层②:显式选定配置的条目覆盖与 carry 覆盖(纯值随配方)
        slot_overrides=None, exec_carry_overrides=exec_carry_overrides,
        # 入站参数(设计 决策 3):raw 保留字 → 跳过 carry
        skip_carry=skip_carry)

    # A-3/W7 + RS3 台账写(C1 切片 1 起抽至 _persist_run_telemetry):
    # 入库标准判定与生效修订表,同点写、失败不阻断(台账性质)。
    await _persist_run_telemetry(db_factory, execution_id, prep)

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
        # 本行事件投影器(所有路径可安全读;无事件路径恒空)
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
                # 之内也能即刻收敛)行终态(canceled 含)即落库;行级
                # JSONL 停写(运行级生命周期行保留为运维审计面)。
                state.status = "canceled"
                state.finished_at = _utcnow().isoformat() + "Z"
                await _persist_row_terminal(db_factory, execution_id, state)
                return
            # 交叉组合序(spec v3 §3):行值合入(vars)→ 条目 Assign 直补
            # + asserts patch — 偏离最后生效。基线/无行维度 = 空行字典。
            # M2b Q3:本行凭证组(账号列覆盖执行级取用)
            row_exec_auths = run_prepare.apply_row_bindings(
                exec_auths, row, row_auths_map)
            # 派发头(组合 + case 目录 + 日志行 + state 置 dispatched)→
            # _row_dispatch_head
            composed, case_dir, log_line = _row_dispatch_head(
                scenario_payload=scenario_payload, run_dir=run_dir,
                run_id=run_id, execution_id=execution_id, seq=seq,
                ds=ds, row_idx=row_idx, row=row, rep=rep,
                injection=injection, ds_id=ds_id, injection_id=injection_id,
                state=state)

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
                    # convert memo(P6,fan-out 级)→ _row_convert_cached
                    convert_data = await _row_convert_cached(
                        composed, convert_cache)
                    plate_state["consecutive_unavailable"] = 0
                    # Convert succeeded — hand the gimbal-shaped product to the
                    # engine. 明文 users 不流经 plate(池凭证经 materialize
                    # 在 convert 产物上物化;作者 config.users 由
                    # plate_client.convert 入口统一剥除,TOK-01)——注入
                    # 形状同 V1 executor 生产路径。
                    # convert_data = {consumer, converted};converted 是
                    # GimbalScenarioExporter 的产物(已剥平台视图扩展字段)。
                    converted = convert_data.get("converted") or {}
                    # M2 §5.1:/convert 响应附带的构建身份 → 转交执行器（代际门）
                    m2_info = convert_data.get("m2") or None
                    # m2_hash 派发回填(首行一次)→
                    # _record_m2_hash_once
                    await _record_m2_hash_once(
                        db_factory, execution_id, m2_info, plate_state)
                    # 物化 run 副本(纯函数,深拷贝 — 绝不原地改 converted):
                    # users 合并(内置基座 + 注入覆盖,固定 merge 语义)与
                    # services 物化(authored > ③ 环境部署地址)。
                    composed_exec = materialize_run_copy(
                        converted,
                        resolved_auths=row_exec_auths,
                        built_in_users=built_in_users,
                        carry_context=carry_ctx,
                        alias_base_urls=prep.alias_base_urls,
                    )
                    # 落盘数据驱动用例快照后交给 CLI 子进程执行。
                    case_path = _write_case_file(case_dir, composed_exec)
                    # 行事件投影器 → _row_event_projection。
                    # (C11:P7 全局 launch 闸退役 —— 并发由 worker 数与
                    # 行级 sem 界定)
                    on_event = _row_event_projection(proj, seq, ingester)
                    # C12:server 链(B6③ 后单链;调试同路) —— SSE
                    # 事件同一回调面;超时由 run_case 内部 cancel 收口。
                    # P3.5-1:实例经槽位池借还,parallel>1 的多行
                    # 各占一个实例,不再撞引擎单 run 409
                    result = await server_pool.run_case(
                        case_path, halt_at=halt_at, n_runs=n_runs,
                        debug=debug, on_event=on_event,
                        m2_info=m2_info)
                    # B6:记下 server 槽号——case-artifact 的引擎日志按它路由到
                    # server-engine[-N].log(多 worker 时不再 404)
                    state.server_slot = getattr(result, "server_slot", None)
                    # 行终态推导(runResult 落档 + 事件投影 > exit 判定)→
                    # _row_status_from_result
                    _row_status_from_result(
                        result, proj, log_line,
                        row_src=row_src, row_idx=row_idx, rep=rep)
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

            # 行终态落 registry + DB(spec §9.1)→ _row_settle_terminal
            await _row_settle_terminal(
                db_factory, execution_id, state, log_line, case_dir,
                proj, result)
            # 行级计数 + 单 case outputs(webhook v3 §5.5/D10)→
            # _row_count_and_outputs
            await _row_count_and_outputs(
                db_factory, execution_id,
                log_line=log_line, result=result,
                single_case=(len(entries) == 1))

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
    # P3.5-2 行级断点恢复读(已完成的 seq 不再执行)→ _load_done_rows
    done_rows = await _load_done_rows(db_factory, execution_id)
    # spec §9.1:行状态 registry 初始化(全部 queued)→ _init_row_states
    row_states = _row_states[execution_id] = _init_row_states(entries)
    try:
        try:
            await asyncio.gather(
                *(_row(ds, i, row, r, seq, inj)
                  for seq, (ds, i, row, inj, r) in enumerate(entries))
            )
        except BaseException:
            # gather 异常兜底:_row 全路径吞 Exception,
            # 走到这里的是防御面之外的问题(取消/意外)。不变量在异常
            # 路径同样成立 —— 关池排空泵 → finalize 冲刷已入缓冲的事件/
            # 日志,再放行异常(终态由 worker 的 finalize_execution_if_stuck
            # 兜,取消路径由租约回收重跑)。只走 _teardown 会让缓冲静默
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
        # 尾部日志不阻断:server 链进程不随 run 结束退出,
        # stderr 泵在 run_case 返回后仍会读到滞留管道的行(最后一步
        # WARNING / uvicorn 收尾)。finalize 之后的 on_log 只进**已停止**
        # ingester 的缓冲,永远不落库,却已计入 logs_ingested —— S9 对账
        # 失真、S6 摘要漏最尾证据。先关池(close = terminate 进程树并等
        # 泵读到 EOF,幂等 —— _teardown 再关无害),泵排空后再 finalize。
        # (C1 切片 1 起经 _drain_and_finalize 单点实现。)
        await _drain_and_finalize(server_pool, ingester, execution_id)
        # P2-02:冲刷事件/日志余量(先于终态落库 —— SSE/日志页在 done 后仍可读全量)

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


# ── 行执行体辅助 ─────────────────────────────────────────────────
# _fanout._row 闭包的具名缝:派发头 / convert memo / m2 回填 / 事件投影
# / 终态推导 / registry 收口 / 计数+outputs。行任务体只保留编排序。

def _row_dispatch_head(*, scenario_payload: dict, run_dir: Path,
                       run_id: str, execution_id: int, seq: int,
                       ds: dict | None, row_idx: int, row: dict | None,
                       rep: int, injection: dict | None, ds_id, injection_id,
                       state: RowState) -> tuple:
    """行派发头(交叉组合序,spec v3 §3):行值合入(vars)→ 条目
    Assign 直补 + asserts patch — 偏离最后生效。基线/无行维度 = 空行
    字典。每个 case 独立子目录:case.json(数据驱动用例快照)+ 引擎
    原生报告目录;stem 带 dataset/row/rep 定位,便于事后审计。stem
    三定位(spec v3 §4 审计):数据集(或 baseline)+ 行号 + 条目 id
    (无注入省略)+ rep,如 case-003-ds-x-r1-inj-inj-2-n0。
    返回 (composed, case_dir, log_line);state 记 dispatched/started_at。
    """
    row_dict = run_prepare.strip_row_binding_columns(row)
    composed = compose_scenario(scenario_payload, row_dict)
    if injection is not None:
        composed = compose_injection_scenario(composed, injection)
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
    return composed, case_dir, log_line


async def _row_convert_cached(composed: dict,
                              convert_cache: dict) -> dict:
    """fan-out 级 convert memo(P6,整单一次 compose 时间戳 → 同行
    n_runs 次重复的 convert 输入完全一致,memo 键才能命中):命中取
    防御性深拷贝(materialize_run_copy 虽是纯函数,任何未来的原地注入
    仍不得污染缓存共享引用);未命中调 plate,入缓存的是物化前原始快照
    (注入只进 run 副本)。
    """
    cache_key = _convert_cache_key(composed)
    if cache_key in convert_cache:
        return copy.deepcopy(convert_cache[cache_key])
    convert_data = await plate_client.convert(composed)
    convert_cache[cache_key] = copy.deepcopy(convert_data)
    return convert_data


async def _record_m2_hash_once(db_factory: Any, execution_id: int,
                               m2_info: dict | None,
                               plate_state: dict) -> None:
    """W21/挂账二.1:M2 构建身份派发回填 —— 身份落 executions.m2_hash
    (整执行同源,首行一次;台账性质,失败不阻断执行)。
    """
    if not (m2_info and m2_info.get("hash")
            and not plate_state.get("m2_hash_written")):
        return
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
        logger.warning("m2_hash 回填失败 (execution={})", execution_id)


def _row_event_projection(proj: dict, seq: int,
                          ingester: _EventIngester) -> Callable[[dict], None]:
    """P2-04 行事件投影器:本行的 scenario.end/run.finished 单独摘出
    (状态/attempts/unit 由此投影;无事件路径 —— PlateMock/旧引擎 ——
    回退 launch 结果推导)。B3:步骤结果按行归属(同场景多行的 unit
    标签相同,只能靠行号区分);insert_events 取走、不进 payload。
    """

    def _row_on_event(d: dict) -> None:
        et = d.get("event_type")
        if et == "step.end":
            d = {**d, "row_seq": seq}
        if et == "scenario.end":
            proj["status"] = d.get("status")
            proj["unit"] = d.get("unit") or proj["unit"]
        elif et == "run.finished":
            # attempts 缺省(旧引擎)=0 → 行级回退 1
            proj["attempts"] = int(d.get("attempts") or 0)
            proj["unit"] = d.get("unit") or proj["unit"]
        ingester.on_event(d)

    return _row_on_event


def _row_status_from_result(result: Any, proj: dict, log_line: dict, *,
                            row_src: str, row_idx: int, rep: int) -> None:
    """launch 成功路径的行终态推导(直接写 log_line 的 status/runError
    并落对应日志行):事件投影(scenario.end,执行器权威;passed 之外
    一律 failed,与 exit 判定同口径)> exit 0 / 2(gimbal 校验拒绝,
    与 HTTP 422 同源)/ exit 1 = 测试失败(正常业务结果)、>=3 引擎侧
    错误。launch 非 ok(超时 kill / spawn 失败):记失败但不中断后续行
    (fan-out 永不因单行崩溃)。
    """
    log_line["runResult"] = result.run_result
    if result.launch_status != "ok":
        log_line["status"] = (
            "launch_timeout" if result.launch_status == "timeout"
            else "launch_error")
        log_line["runError"] = result.error
        logger.warning(
            "run_dispatcher: launch {} for row {}/{}#{}: {}",
            result.launch_status, row_src, row_idx, rep, result.error)
        return
    if proj["status"] is not None:
        log_line["status"] = (
            "passed" if proj["status"] == "passed" else "failed")
        logger.info(
            "run_dispatcher: row {}/{} projected by events: "
            "unit={} status={} attempts={}",
            row_src, row_idx, proj["unit"], proj["status"], proj["attempts"])
        return
    if result.exit_code == 0:
        log_line["status"] = "passed"
        logger.info(
            "run_dispatcher: row {}/{}#{} executed: exit=0 passed={} failed={}",
            row_src, row_idx, rep, result.passed, result.failed)
        return
    if result.exit_code == 2:
        log_line["status"] = "gimbal_rejected"
        log_line["runError"] = result.error
        logger.warning(
            "run_dispatcher: gimbal rejected row {}/{}#{}: {}",
            row_src, row_idx, rep, result.error)
        return
    log_line["status"] = "failed"
    log_line["runError"] = result.error
    logger.info(
        "run_dispatcher: row {}/{}#{} executed: exit={} passed={} failed={}",
        row_src, row_idx, rep, result.exit_code, result.passed, result.failed)


async def _row_settle_terminal(db_factory: Any, execution_id: int,
                               state: RowState, log_line: dict,
                               case_dir: Path, proj: dict,
                               result: Any) -> None:
    """行终态落 registry + DB(spec §9.1):T7-Q1 final 行 ts 刷新为
    完成时刻 — log_line 的 ts 构造于派发时刻,沿用会让 JSONL 回放的
    finishedAt == startedAt(行时长恒为 0);同一时刻写 registry,两读路
    口径一致。M6:终态即落 DB(崩溃窗口不丢),行级 JSONL 停写。
    B3:行级失败原因入库 —— 引擎结果错误优先,派发层异常次之
    (plate/熔断/未知异常分支写 "error" 键);passed/canceled 恒无键 →
    None,[:2000] 防超长(引擎 error 形态不可控)。
    P2-04/P2-05:单元列投影(unit 取事件标签;attempts 取 run.finished
    单列,缺省回退 launch 解析值,再缺省 1)。
    """
    finished_ts = _utcnow().isoformat() + "Z"
    log_line["ts"] = finished_ts
    state.status = log_line["status"]
    state.finished_at = finished_ts
    state.case_dir = case_dir.name
    state.run_error = (
        log_line.get("runError") or log_line.get("error")) or None
    if state.run_error is not None:
        state.run_error = str(state.run_error)[:2000]
    state.unit_id = proj["unit"] or "u"
    state.attempts = (
        proj["attempts"] or int(getattr(result, "attempts", 0) or 0) or 1)
    await _persist_row_terminal(db_factory, execution_id, state)


async def _row_count_and_outputs(db_factory: Any, execution_id: int, *,
                                 log_line: dict, result: Any,
                                 single_case: bool) -> None:
    """行级计数 + 单 case outputs:
    计数原子增量(Deltas 而非绝对回写)—— 并发行与并发 UI 删除
    (MAX(0, col-1) SQL)可组合。S5:引擎 run.finished 的 skipped 计数
    随行累加(plate 异常/校验拒绝分支无引擎结果,恒 0)。
    P2-4(webhook 设计 v3 §5.5/D10):单 case 执行(行数为 1)在行完成
    处把提取产物脱敏后写进 ``config_json.outputs``(唯一例外键,见
    models.execution 注释)—— 终态迁移组装回调 payload 时读取;发生在
    finalize/终态之前,顺序保证回调拿得到。多行执行不写、回调
    outputs=null。best-effort:写失败只丢回调里的 outputs,不影响行/终态。
    """
    passed = 1 if log_line["status"] == "passed" else 0
    row_skipped = (
        int(getattr(result, "skipped", 0) or 0)
        if "runResult" in log_line else 0
    )
    await _bump_counters(
        db_factory, execution_id, passed=passed, failed=1 - passed,
        skipped=row_skipped)
    if not (single_case and "runResult" in log_line):
        return
    _outputs: dict = {}
    for _d in (getattr(result, "details", None) or []):
        if (isinstance(_d, dict)
                and isinstance(_d.get("outputs"), dict)):
            _outputs.update(_d["outputs"])
    if _outputs:
        await _store_single_case_outputs(db_factory, execution_id, _outputs)


async def _load_done_rows(db_factory: Any, execution_id: int) -> dict:
    """P3.5-2 行级断点恢复读:已终态行 seq → status。恢复场景(job 租约
    过期/重启回队重跑)先读已终态行,已完成的 seq 不再执行:不重复打
    被测系统、不重复计数(行落库先于计数 bump → DB 存在的行必已计数,
    跳过即无重复)。DB 只落终态行(_persist_row_terminal),存在即终态;
    首次运行空集。查询失败按无断点处理(全量重跑)。
    """
    try:
        from sqlalchemy import select as _sel_row

        from ..models.execution import ExecutionRow as _ER
        async with db_factory() as session:
            _existing = (await session.execute(
                _sel_row(_ER.seq, _ER.status)
                .where(_ER.execution_id == execution_id))).all()
        return {int(s): st for s, st in _existing
                if st in _FINAL_STATUSES}
    except Exception as e:  # noqa: BLE001 — 查询失败按无断点处理(全量重跑)
        logger.warning(
            "run_dispatcher: 断点恢复查询失败,本单全量重跑"
            "(execution={}): {}", execution_id, e)
        return {}


def _init_row_states(entries: list) -> list:
    """spec §9.1:组完全部行任务后初始化行状态 registry(全部 queued;
    行任务内逐行推进,执行终态化时整体 pop → 读侧回落 DB)。
    """
    return [
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


async def _mark_running(db_factory: Any, execution_id: int) -> None:
    """queued → running + started_at(原子条件 update,只动 queued 行)。

    fanout 在认证解析通过、行分发开始前调用 —— UI 由此区分"排队中"
    与"在跑"(queued 直接到终态会让长时间执行无法观测进度)。
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
            await _config_json_merge(
                session, execution_id,
                {"authFailFast": {"error": str(error)[:512]}})
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

    JSONL 保持 counts-only(运维索引);完整证据(含 details[])落在
    本文件,与 case.json 同目录构成审计面。legacy 期的「stdout 原文
    兜底」随 B6③ 退役(server 链无 stdout 面,降级态由 error 字段承载)。
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
            await _config_json_merge(session, execution_id,
                                     {"outputs": outputs})
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "run_dispatcher: single-case outputs for {} failed: {}",
            execution_id, e)


async def _config_json_merge(
    session: Any, execution_id: int, patch: dict,
) -> None:
    """config_json 顶层键级原子合并(单语句)。

    :436 禁令同源 —— config_json 有多写入者(ingest_stats 快照 /
    dispatcherError / outputs / authFailFast / counterDrift / 结论
    留档),ORM 整读整写互相覆盖丢更新;``jsonb ||`` 按顶层键原子
    合并,不做读改写。行不存在 = 0 行更新,无害。"""
    await session.execute(sa_text(
        "UPDATE executions SET config_json = "
        "COALESCE(config_json, '{}'::jsonb) || CAST(:patch AS jsonb) "
        "WHERE id = :eid"),
        {"patch": json.dumps(patch), "eid": execution_id})


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

    bool 返回值若混判,会把「已终态」(幂等跳过,正常)与「写库失败」(异常,静默
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
        (静默会漏报),canceled 不发(用户自发的取消)。
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
            cfg_patch: dict = {}
            if dispatcher_error is not None:
                cfg_patch["dispatcherError"] = str(dispatcher_error)[:512]
            if reconciled_reason is not None:
                cfg_patch["reconciled"] = {
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
                cfg_patch["counterDrift"] = True
            # :436 禁令同源 —— config_json 多写入者(stats/ conclusions /
            # outputs / 本函数),整读整写互相覆盖;键级 || 合并单语句原子。
            if cfg_patch:
                await _config_json_merge(session, execution_id, cfg_patch)
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
    不覆写、不重复通知 —— 无守卫直接覆写是漂移面)。
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

    同一行 n_runs 次重复输入完全一致(P6:memo 防重复打 plate)。
    """
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        .encode("utf-8")
    ).hexdigest()


# (_jsonl_lock 与 _append_jsonl 同居一块,搬移时
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
# (这组底部导入服务于已迁走的 _coerce_row_value 与
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
    ``RUNS_JSONL_RETENTION_DAYS``(0 = 禁用)。JSONL 是**现役**调度审计
    索引(执行生命周期逐行追加),M6 起行级台账入库后它保留为运维面,
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
    """保留期维护(后台周期任务)。

    三项清扫要么零调用点(事件面),要么只在启动期跑一次(case
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
    project_id: int | None = None,
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
        project_id=project_id,
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
