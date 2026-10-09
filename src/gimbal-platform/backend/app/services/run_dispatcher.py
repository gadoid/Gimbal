"""Run dispatcher (V3.2 Scenario Composer — ``gimbal run launch`` 执行链).

Per-row fan-out of a Scenario's selected DataSets:

1. :func:`_compose_scenario` — 场景 definition + 一行数据集 → 数据驱动的
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
to the scenario by :func:`_compose_scenario` (the 配置器/transformer).

Returns ``RunResponse(runId)`` to the caller immediately, and the
``Execution`` row (re-used from Spec-2) holds the aggregate counters
so the existing ``/executions`` UI shows the run without any frontend
changes.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from loguru import logger
from sqlalchemy import func, select
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
from ..models.auth_session import AuthSession as DBAuthSession
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
from .run_materialize import referenced_services, materialize_run_copy
from . import service_aliases

# 物理迁移自 gimbal 后:用平台侧标准 AuthSession 替代自创 ResolvedAuth dataclass。
# 下游 materialize_run_copy(_apply_users)仍消费 username/password/url/token_type/
# expires_in 这几个字段,与标准 AuthSession 完全对齐(后者字段更多但不影响注入
# 逻辑)。保留 ResolvedAuth 作为兼容 shim,免改下游的字段引用。
from app.auth.schema import AuthSession as RuntimeAuthSession  # noqa: E402


@dataclass(frozen=True, slots=True)
class ResolvedAuth:
    """解密后的执行认证(轻量值对象,保留兼容 shim)。

    明文凭证只存在于该对象的生命周期内,不落在 AuthSession ORM 行
    上 — 避免任何意外 commit 把明文写回数据库。

    内部委托给标准 RuntimeAuthSession(物理迁移自 gimbal),字段对齐下游消费者。
    """

    alias: str
    url: str
    username: str
    password: str
    token_type: str
    expires_in: int

    @classmethod
    def from_runtime(cls, runtime: "RuntimeAuthSession", alias: str) -> "ResolvedAuth":
        """从标准 RuntimeAuthSession 构造,供 _resolve_exec_auths 内部使用。"""
        return cls(
            alias=alias,
            url=runtime.url,
            username=runtime.username,
            password=runtime.password,
            token_type=runtime.token_type,
            expires_in=runtime.expires_in or 0,
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

    def __init__(self, db_factory: Any, execution_id: int) -> None:
        self._db_factory = db_factory
        self._execution_id = execution_id
        self._events: list[dict] = []
        self._logs: list[dict] = []
        self._pending: "set[asyncio.Task] | None" = None
        self._ticker: "asyncio.Task | None" = None
        self._stopped = False
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
                if self._events or self._logs:
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
        self._logs.append(d)
        self._maybe_flush()

    def _maybe_flush(self) -> None:
        if len(self._events) + len(self._logs) < self._FLUSH_EVERY:
            return
        if self._pending is None:
            try:
                self._pending = set()
            except RuntimeError:
                return   # 无运行循环(同步上下文兜底):留给 finalize
        if any(not t.done() for t in self._pending):
            return   # 在飞冲刷未收口,余量并入下一轮
        t = asyncio.create_task(self._flush())
        self._pending.add(t)
        t.add_done_callback(self._pending.discard)

    async def _flush(self) -> None:
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
                await session.commit()
        except BaseException as e:  # noqa: BLE001
            # 失败/取消都要回填缓冲(下次冲刷重试),不丢这批事件/日志。
            # P3.5-3 对账实测:finalize 取消 ticker 时批次可能正在 DB
            # 往返中,CancelledError 不是 Exception 子类,旧 except
            # Exception 会放行 → 整批静默丢失(批已换出,final flush
            # 拿到空缓冲)。回填后由 finalize 的收尾 flush 重试。
            self._events = events + self._events
            self._logs = logs + self._logs
            self._log_seq += len(logs)
            if not isinstance(e, Exception):
                raise          # CancelledError 照常传播(取消语义不变)
            logger.warning(
                "run_dispatcher: event flush {}/{} failed (re-buffered): {}",
                self._execution_id, len(events) + len(logs), e,
            )

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
                            finished_at=_iso_to_dt(state.finished_at))
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
async def reconcile_stale_executions(db_factory: Any) -> int:
    """启动期 reconcile（C11 起 jobs 感知）。

    * executions stuck queued/running **且无 job 行**（0009 前遗留/
      建行后入队前崩溃）→ failed + ``config_json.reconciled``（原口径）;
    * job ``failed``/``canceled`` 终态而 execution 仍 queued/running
      （worker 收口前崩溃）→ failed 收口;
    * job ``queued``/``running``：留给 worker（queued 待认领;running
      由 sweep_stale 按租约回收——回队重跑或 attempts 耗尽失败）。

    返回处理行数。
    """
    from sqlalchemy import select as _select
    count = 0
    async with db_factory() as session:
        rows = (
            (
                await session.execute(
                    _select(Execution, ExecutionJob.status).outerjoin(
                        ExecutionJob,
                        ExecutionJob.execution_id == Execution.id).where(
                        Execution.status.in_((STATUS_QUEUED, STATUS_RUNNING)))
                )
            )
            .all()
        )
        for ex, job_status in rows:
            if job_status in ("queued", "running"):
                continue   # worker 域:待认领或由租约回收
            ex.status = STATUS_FAILED
            if ex.started_at is None:
                ex.started_at = ex.created_at or _utcnow()
            ex.finished_at = _utcnow()
            cfg = dict(ex.config_json or {})
            cfg["reconciled"] = {
                "at": _utcnow().isoformat() + "Z",
                "reason": ("backend restarted mid-dispatch"
                           if job_status is None
                           else f"job {job_status} without execution finalize"),
            }
            ex.config_json = cfg
            count += 1
        await session.commit()
    if count:
        logger.warning(
            "run_dispatcher: reconciled {} stale execution(s) after restart",
            count,
        )
    return count


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
    db: AsyncSession, scen: ComposerScenario, req: RunRequest,
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
        ds = await _find_dataset_by_id(db, ds_id)
        if ds is None or ds.scenario_id != scen.scenario_id:
            raise NotFound(
                "data_set_not_found", f"data set not found: {ds_id}"
            )
        selected_datasets.append(ds)

    # 断言注入条目(spec v3 §8):被选中且悬空检测通过的条目 → 注入族
    # (与数据集行交叉派生 case,spec v3 §4);死/旧条目 skip + 告警,
    # 绝不炸。判定本体 = filter_injection_entries(执行设计 §1.6:
    # /run/precheck 与 dispatch 共用这**一份**实现,失效口径不开第二份)。
    raw_payload = scen.payload or {}
    selected_entries, dangling_ids, skipped_while_degraded = (
        await filter_injection_entries(raw_payload, req.injection_entry_ids or [])
    )
    if dangling_ids:
        logger.warning(
            "run_dispatcher: dangling injection entries skipped: {}",
            dangling_ids,
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
async def dispatch_run(
    db: AsyncSession,
    user_id: int,
    req: RunRequest,
    *,
    preloaded_scenario: ComposerScenario | None = None,
    chain_override: str | None = None,
) -> RunResponse:
    """Validate + 入队 + return runId（C11：执行配方进 execution_jobs，
    worker 认领驱动；本函数不再 spawn 进程内 fanout）。

    Caller (the runs router) wraps any exception in HTTPException.  This
    function NEVER raises for "Plate is down" — it records the failure
    and returns the runId so the user can still see the run in
    ``/executions`` (per the agreed run-failure semantics).

    ``chain_override``（C13 对账用，非公开 API 面）：强制本次执行的链
    （legacy|server），覆盖 settings.EXEC_CHAIN；随配方与 config_json
    落档，回滚 = 开关关闭即回旧链。

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
        else await get_row(db, req.scenario_id)
    )
    if scen is None:
        raise NotFound("scenario_not_found", f"scenario not found: {req.scenario_id}")

    # 2. Validate datasets.
    # (旧 env 校验块已随 D2 执行环境退役 — 旧客户端多发的 env 键由
    # pydantic extra=ignore 静默忽略。)

    # step_to 校验(同 V1 executions:与场景 steps 数比对,越界 409)
    steps = steps_from_payload(scen.payload)
    if req.step_to is not None:
        if not steps:
            raise NotFound("no_steps", "scenario has no steps; step_to cannot be set")
        if req.step_to >= len(steps):
            raise Conflict(
                "step_to_out_of_range",
                f"step_to={req.step_to} out of range (0..{len(steps) - 1})",
            )

    # fanout 计算(权限域二期 P1 抽出为 compute_run_fanout:suite 总量
    # 预检与本处共用同一份实现,算法不得漂移)。
    (fanout_datasets, injections, selected_entries,
     skipped_while_degraded) = await compute_run_fanout(db, scen, req)

    # 3. Allocate runId + Execution row
    # total_runs 必须按实际行数算(与 _fanout 的迭代口径一致)— 旧的
    # row_count 列在 raw-SQL 迁移路径下不回填,NULL/过期会让计数器
    # 超过 total_runs 出现 failed > total 的怪状态。
    run_id = _new_run_id()
    total_runs = fanout_total(fanout_datasets, injections)
    if total_runs > settings.MAX_RUNS_PER_EXECUTION:
        raise Conflict(
            "too_many_runs",
            f"total runs {total_runs} exceed platform cap "
            f"{settings.MAX_RUNS_PER_EXECUTION} (rows x injections)",
        )
    # 注入清单 = 模板扫描 ∪ 绑定(spec §5)。扫描源是存储的 definition
    # steps(authored 模板所在处,${auth.*} 引用一网打尽);绑定的
    # authAlias 并入(即使 steps 未引用该 alias)。去重保序。
    scanned = scan_auth_aliases(definition_from_payload(scen.payload).get("steps") or [])
    bound = [b.auth_alias for b in req.service_bindings.values() if b.auth_alias]
    auth_aliases: list[str] = [*scanned, *bound]
    # 别名表凭证默认(服务画像方案 §4.1):raw 服务键精确命中
    # service_aliases.credential_alias → 并入注入清单,按执行者本人
    # 凭证池解析(_resolve_exec_auths 的 owner 过滤)。优先级:场景
    # 显式绑定 > 别名表命中 —— 同键已绑 authAlias 的不吃默认。
    # 存档口径(§4.1 拍板):config_json.serviceBindings 只记场景原始
    # 绑定,别名默认只体现于 injectedAuths 清单与实际注入的 users。
    # 查表失败降级跳过(别名默认是增强,不是前置条件)。
    try:
        alias_creds = await service_aliases.credential_aliases_for(
            db, referenced_services(
                definition_from_payload(scen.payload).get("steps") or []))
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning(
            "run_dispatcher: service alias lookup failed; skipped")
        alias_creds = {}
    bound_keys = {k for k, b in req.service_bindings.items() if b.auth_alias}
    auth_aliases = list(dict.fromkeys([
        *auth_aliases,
        *(cred for raw, cred in alias_creds.items() if raw not in bound_keys),
    ]))

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
        # (Case 层解散后执行的挂载点就是场景)。
        scenario_id=scen.scenario_id,
        owner_id=user_id,
        total_runs=total_runs,
        # 批次键(执行设计 §1.2):前端队列逐条发起时共用,执行记录归并用;
        # 单条发起为 None。列 + config_json 双落:列驱动筛选,config 驱动
        # 重跑配方的原样保真。
        batch_id=req.batch_id,
        # 台账快照列(M2):通知/列表展示用 name,场景删了执行仍可读。
        # 直读唯一权威 payload.definition.meta.name,不走 _meta_from_row
        # 的整 meta 严格校验 —— 畸形行不拦发起,空值由通知侧兜底链接住。
        scenario_name=str(
            (definition_from_payload(scen.payload).get("meta") or {}
            ).get("name") or ""
        ).strip(),
        # 执行时场景快照:与传给 _fanout 的 scenario_payload 同拍同源
        # (同一读取),保证"快照即所执行";深拷贝隔离后续 fanout 内的
        # setdefault 写穿,不污染快照。
        scenario_snapshot=copy.deepcopy(scen.payload or {}),
        config_json={
            "runId": run_id,
            "scenarioId": scen.scenario_id,
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
            "stepTo": req.step_to,
            # 原始请求的注入条目 id(悬空过滤**前**):rerun 按配方重建的
            # 唯一来源(执行设计 §3.4)—— 只记录请求,不记录判定结果。
            "injectionEntryIds": req.injection_entry_ids,
            # 方案溯源快照(spec §5,阶段③):纯记录,无分发语义
            "schemeId": req.scheme_id,
            "schemeName": req.scheme_name,
            # 批次键(执行设计 §1.2):与列同值;rerun 按 config_json 重建
            # 配方时不带旧批(重跑是新的一次独立发起)。
            "batchId": req.batch_id,
            "nRuns": req.n_runs,
            "reportDefinitionId": getattr(req, "report_definition_id", None),
            "parallel": req.parallel,
            # C13:执行链留档（legacy|server;调试恒 server）
            "chain": chain,
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
                "n_runs": req.n_runs, "halt_at": req.step_to,
                "scenario_payload": dict(scen.payload or {}),
            },
        }
    else:
        payload = {
            "kind": "cases",
            "chain": chain,
            "debug": (debug_spec.model_dump(by_alias=True)
                      if debug_spec is not None else None),
            "args": {
                "execution_id": execution.id, "run_id": run_id,
                "scenario_payload": dict(scen.payload or {}),
                "datasets": fanout_datasets,
                "injections": selected_entries,
                "owner_id": user_id,
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
    return RunResponse(runId=run_id, executionId=execution.id)


# ─── C11：worker 任务体入口（payload → fanout）──────────────────

async def run_job_from_payload(job: dict) -> None:
    """execution_queue worker 的任务体：解包配方 → _fanout/_fanout_graph。

    payload 是 dispatch_run 校验后的完整快照（JSON 往返安全形态）；
    ServiceBinding 在此重建为模型（_fanout 消费面不变）。
    """
    p = job["payload"]
    args = dict(p["args"])
    if p["kind"] == "graph":
        await _fanout_graph(db_factory=_session_factory, **args)
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
    """取消先于启动：执行直接 canceled 收口（无行、零计数）。"""
    execution_id = job["payload"]["args"]["execution_id"]
    async with _session_factory() as session:
        ex = await session.get(Execution, execution_id)
        if ex is not None and ex.status in (STATUS_QUEUED, STATUS_RUNNING):
            ex.status = STATUS_CANCELED
            ex.finished_at = _utcnow()
            await session.commit()
    _row_states.pop(execution_id, None)
    logger.info("run_dispatcher: execution {} canceled before start", execution_id)


async def finalize_execution_if_stuck(execution_id: int, error: str) -> None:
    """任务体异常的兜底终态化（幂等：终态不再改）。"""
    try:
        async with _session_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is not None and ex.status in (STATUS_QUEUED, STATUS_RUNNING):
                ex.status = STATUS_FAILED
                ex.finished_at = _utcnow()
                cfg = dict(ex.config_json or {})
                cfg["dispatcherError"] = str(error)[:512]
                ex.config_json = cfg
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "run_dispatcher: finalize_execution_if_stuck failed for {}",
            execution_id)


# ─── background fan-out ──────────────────────────────────────────
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
) -> None:
    """C5(P3-05):graph 编排执行链 —— 物化 SuiteGraph → 单 spawn →
    事件投影台账(与单场景链同读面;乘法/并发/横切面在执行器)。
    C12/C13：chain=server 时 spawn 走执行器 server 实例。"""
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
        try:
            async with db_factory() as session:
                ex = await session.get(Execution, execution_id)
                if ex is not None and ex.status in (STATUS_QUEUED, STATUS_RUNNING):
                    ex.status = STATUS_FAILED
                    ex.finished_at = _utcnow()
                    cfg = dict(ex.config_json or {})
                    cfg["dispatcherError"] = (
                        f"graph recovery: at-most-once 收口"
                        f"({_prior} prior events, 不整图重放)")
                    ex.config_json = cfg
                    await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception(
                "run_dispatcher: graph recovery finalize failed {}", execution_id)
        await ingester.finalize()
        return

    # 逐单元事件投影(重构方案第 3 处):unit → {started_at, finished_at,
    # status};blocked/cancelled 单元不发事件,从 run.finished.details 按
    # unit id 补齐。总状态不再取「最后一个 scenario.end」—— 后置通过
    # 会覆盖主体失败、判定门失败只改 exit_code 会被吞。
    unit_events: dict[str, dict] = {}
    proj = {"attempts": 0, "gates": None}
    status = "failed"
    result = None
    try:
        async with db_factory() as session:
            graph = await graph_dispatch.materialize_graph(
                session, owner_id, graph_spec)
        await _mark_running(db_factory, execution_id)

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

        result = await graph_dispatch.execute_graph(
            db_factory, execution_id, run_dir, graph,
            on_event=_on_event, on_log=ingester.on_log, chain=chain)
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
    if proj.get("gates"):
        # 判定门结论(第 4 处):经事件通道落 config_json,21 页实测值来源
        try:
            async with db_factory() as session:
                ex = await session.get(Execution, execution_id)
                if ex is not None:
                    cfgj = dict(ex.config_json or {})
                    cfgj["gatesEvaluated"] = proj["gates"]
                    ex.config_json = cfgj
                    await session.commit()
        except Exception:  # noqa: BLE001 — 结论留档 best-effort
            pass
    await _finalize_execution(db_factory, execution_id)


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
) -> None:
    """Per-row × per-repeat compose + convert + 执行器调用（双链）。

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
    cancel_local = {"set": False, "done": False}

    async def _poll_cancel() -> None:
        while not cancel_local["done"]:
            try:
                async with db_factory() as s:
                    if await _eq.is_cancel_requested(s, execution_id):
                        cancel_local["set"] = True
                        return
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(0.5)

    cancel_poller = asyncio.create_task(_poll_cancel())

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
                engine_log_path=run_dir / "server-engine.log", cwd=run_dir)
        except Exception as e:  # noqa: BLE001
            await _teardown()
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
            await _resolve_exec_auths(db_factory, owner_id, auth_aliases)
            if auth_aliases
            else []
        )
    except _AuthResolveError as e:
        logger.error(
            "run_dispatcher: auth resolve failed for execution {}: {}",
            execution_id, e,
        )
        total_rows = (sum(len(ds["rows"]) for ds in datasets)
                      * len(injections or [None]))
        await _fail_whole_execution(
            db_factory, log_path, execution_id=execution_id, run_id=run_id,
            total_rows=total_rows, error=str(e),
        )
        await _teardown()
        return

    # 认证解析通过、即将分发行 → queued 置 running(UI 可见"在跑")。
    await _mark_running(db_factory, execution_id)

    # F4 方案 B(2026-09-23):别名 base_url 预解析 —— dispatch 阶段查
    # 一次,纯函数物化时消费(与 resolved_auths/CarryContext 同款传参
    # 模式)。增强链路:查表失败降级空表,绝不阻塞执行。
    try:
        async with db_factory() as _alias_s:
            alias_urls = await service_aliases.base_urls_for(
                _alias_s,
                referenced_services(
                    (definition_from_payload(scenario_payload)
                     .get("steps") or [])),
            )
    except Exception:  # noqa: BLE001
        logger.opt(exception=True).warning(
            "run_dispatcher: alias base_url lookup failed; skipped")
        alias_urls = {}

    sem = asyncio.Semaphore(max(1, parallel))

    # P6:整单固定一次 compose 时间戳 — fill_plate_defaults 对缺失的
    # meta.createTime 注入"当前时刻"(微秒精度),同一行 n_runs 次重复
    # 的 convert 输入会逐次不同,memo 键永不命中。deepcopy 隔离存储
    # payload(防写穿 ORM 行)后预填一次,compose 内 setdefault 语义
    # 即复用同一值 → 同一行重复输入完全一致。
    scenario_payload = copy.deepcopy(scenario_payload)
    # 容器解包一次,fill_plate_defaults(就地补 meta)与 build_carry_context
    # (读 steps)共用 — definition_from_payload 返回的是 payload 内同一
    # dict 引用,重复解包只是多一次 .get。
    definition = definition_from_payload(scenario_payload)
    plate_client.fill_plate_defaults(definition)

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
    built_in_users = _built_in_users(scenario_payload)
    # serviceBindings 原样传给 materialize_run_copy(url 物化只对 steps
    # 实际引用的 service 键生效,见 run_materialize._apply_services)。
    service_bindings = service_bindings or {}

    # carry 预解析(spec §4.1):dispatch 阶段一次,run 内快照一致 —
    # 绑定/契约编辑的生效边界是下次执行。plate 故障在 build 内部降级
    # (空面/空目录);此处再兜一层 — carry 是增强不是前置条件,任何
    # 故障(含 DB)都降级为无 carry,绝不阻塞执行。
    from .carry_injection import build_carry_context
    try:
        async with db_factory() as _carry_db:
            carry_ctx = await build_carry_context(_carry_db, definition)
    except Exception:  # noqa: BLE001 — carry 绝不阻塞执行
        logger.opt(exception=True).warning(
            "run_dispatcher: carry context build failed; skipped")
        carry_ctx = None

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
            composed = _compose_scenario(scenario_payload, row_dict)
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
                        alias_base_urls=alias_urls,
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
                        def _row_on_event(d: dict, _p=proj) -> None:
                            et = d.get("event_type")
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
                                debug=debug, on_event=_row_on_event)
                        else:
                            result = await gimbal_launcher.launch(
                                case_path,
                                step_to=halt_at,
                                report_dir=case_dir / "reports",
                                cwd=case_dir,
                                engine_log_path=case_dir / "engine.log",
                                on_event=_row_on_event,
                                on_log=ingester.on_log,
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
        await asyncio.gather(
            *(_row(ds, i, row, r, seq, inj)
              for seq, (ds, i, row, inj, r) in enumerate(entries))
        )
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


async def _finalize_execution(
    db_factory: Any, execution_id: int, *, status: str | None = None
) -> None:
    """终态收尾:只写 status + 时间戳(计数器由上方增量维护)。

    ``status`` 显式覆盖用于取消终态(canceled);缺省沿用严格规则
    ``failed > 0 → failed``。P8:非 canceled 终态校账
    ``passed + failed == total_runs``,漂移只标记不修正(counterDrift
    供读侧发现"数字对不上",真值以 JSONL 为准)。
    """
    try:
        async with db_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is not None:
                final_status = status or (
                    STATUS_FAILED if ex.failed else STATUS_DONE
                )
                ex.status = final_status
                if ex.started_at is None:
                    ex.started_at = _utcnow()
                ex.finished_at = _utcnow()
                if (
                    final_status != STATUS_CANCELED
                    and ex.passed + ex.failed != ex.total_runs
                ):
                    logger.error(
                        "run_dispatcher: counter drift execution {}: "
                        "total={} passed+failed={}",
                        execution_id, ex.total_runs, ex.passed + ex.failed,
                    )
                    cfg = dict(ex.config_json or {})
                    cfg["counterDrift"] = True
                    ex.config_json = cfg
                await session.commit()
                # 通知接线(P1b/M2.5,权限方案 §3.2):发起人收一条
                # 「执行完成」;带 batch_id 的按批 upsert 单条聚合通知
                # (50 条批次不刷屏),单发执行逐条。通知失败不影响终态
                # 收口(独立会话 + 自吞异常)。
                if final_status in (STATUS_DONE, STATUS_FAILED) and ex.owner_id:
                    await _notify_finished(ex, final_status)
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: failed to update execution {}: {}", execution_id, e)
    # spec §9.1:执行终态化 → 活跃行状态出清(读侧此后走 JSONL 回放)。
    # DB 写失败也出清 —— fanout 已收尾,残留的"活跃"行状态会永久盖住
    # 回放路径。
    _row_states.pop(execution_id, None)


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
                await notify_svc.create_notification(
                    s2,
                    user_id=ex.owner_id,
                    type_="execution_finished",
                    title=("执行完成:" if final_status == STATUS_DONE
                           else "执行失败:") + label,
                    body=f"{ex.scenario_id} · {ex.passed} 通过 / {ex.failed} 失败",
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
        call = step.get("call")
        hints = (call.get("view_hints") or {}) if isinstance(call, dict) else {}   # B:守齐
        eid = hints.get("endpoint_id") if isinstance(hints, dict) else None
        return eid if isinstance(eid, str) and eid else None

    async def _face_of(si: int) -> tuple[int, frozenset[str] | None]:
        eid = _endpoint_id_of(si)
        if eid is None:
            return si, frozenset()            # 无端点 = 真无声明(非得降级)
        return si, await declared_paths_of(eid)   # None = 降级(**不抹平**,Y)

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


def _built_in_users(scenario_payload: dict | None) -> dict[str, Any]:
    """场景 definition.config.users(merge 策略保留基座)。"""
    def_cfg = definition_from_payload(scenario_payload).get("config") or {}
    users = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
    return dict(users or {})


def _compose_scenario(
    scenario_payload: dict, row_dict: dict
) -> dict[str, Any]:
    """配置器:把存储的 Scenario + 一行数据 变换成 Plate 输入。

    源存果算 — 这里是唯一的变换点:存储里只有场景定义(源)与
    数据行(纯值),每个 run 的形态由本函数即时计算:

    * deep-copy 场景定义,行键值合入 ``config.vars``(行值覆盖同名
      场景级 var)。行值按基线类型还原(新数据集编辑器全字符串落库,
      ``_coerce_row_value`` 恢复"int 还是 int"的旧语义,断言
      ``expected: 0`` 不会被字符串化破坏)。
    * 数据集行是稀疏覆盖(缺键 = 继承基线,即场景级 vars 原值;
      ``""`` = 显式空覆盖),与行 0 基线虚行/三态单元格的编辑器
      契约一致 —— 基线行本身不落库,由场景 vars 承担。
    * ``scenario_payload`` 是持久化的 ``ComposerScenario.payload``。
      容器化重构后为 ``{definition, orchestration}``;plate 只吃
      ``definition``(orchestration 是平台侧投影,绝不外发)。
    * plate 必填默认由 :func:`plate_client.fill_plate_defaults` 就地
      补齐(仅 setdefault,不覆盖已有值)—— 与 preview/export 同源。
    """
    raw = scenario_payload or {}
    # Unwrap the container: plate must never see orchestration.
    out = copy.deepcopy(definition_from_payload(raw))
    # plate 必填默认(与 preview/export 路径共用同一份):存量场景
    # meta 可能缺 requirementRef/createTime 等 UI 不采集的字段,
    # 不补会在 plate /convert 处 4xx(plate_rejected 整单失败)。
    plate_client.fill_plate_defaults(out)
    cfg = out.setdefault("config", {})
    if not isinstance(cfg, dict):
        cfg = {}
        out["config"] = cfg
    vars_map = dict(cfg.get("vars") or {})
    # Row wins: a row's `qty` overrides a scenario-level `vars.qty`.
    for k, v in (row_dict or {}).items():
        vars_map[k] = _coerce_row_value(vars_map.get(k), v)
    cfg["vars"] = vars_map
    return out


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


class _AuthResolveError(RuntimeError):
    """执行认证解密失败 — fail-fast,同 V1 executor 的 ``_decrypt_auths``
    语义(解密失败上抛使整个 run 失败,而不是带着空/坏凭证静默打环境)。"""


async def _resolve_exec_auths(
    db_factory: Any, owner_id: int, aliases: list[str]
) -> list["ResolvedAuth"]:
    """Owner 级 alias → ResolvedAuth(解密后的轻量值对象)。owner 过滤
    防跨 owner 同名 alias 解错凭证。

    * 解密失败 → 抛 :class:`_AuthResolveError`(V1 严格语义:
      凭证路径 fail-fast,不静默降级)。
    * alias 不属于该 owner 时解不到 → 告警后继续(与 V1 一致:
      缺 alias 只是注入不到 users,该行 run 在 Gimbal 解析
      ``${auth.*}`` 时步骤级报错)。
    * 明文只存在于返回的值对象上 — 绝不写回 ORM 行(此前
      ``a.username = ...`` 会把明文挂到 session 里的 AuthSession
      实例上,任何一次意外 commit 都会把明文持久化进库)。

    Phase 3 改造:内部先用平台侧标准 RuntimeAuthSession(物理迁移自 gimbal)
    接收解密后的字段,然后通过 ``ResolvedAuth.from_runtime`` 转为兼容 shim。
    这样下游 materialize_run_copy(_apply_users)不动,未来可直接消费
    ``RuntimeAuthSession``。
    """
    if not aliases:
        return []
    from ..core.security import fernet_decrypt

    resolved: list[ResolvedAuth] = []
    async with db_factory() as session:
        rows = (
            (
                await session.execute(
                    select(DBAuthSession).where(
                        DBAuthSession.owner_id == owner_id,
                        DBAuthSession.alias.in_(aliases),
                    )
                )
            )
            .scalars()
            .all()
        )
    for a in rows:
        try:
            # 先构造标准 RuntimeAuthSession(字段对齐 gimbal 侧 AuthSession)
            runtime = RuntimeAuthSession(
                url=a.url,
                username=fernet_decrypt(a.username_enc),
                password=fernet_decrypt(a.password_enc),
                token_type=a.token_type,
                expires_in=a.expires_in,
            )
            # 转兼容 shim(下游消费的字段不变)
            resolved.append(ResolvedAuth.from_runtime(runtime, alias=a.alias))
        except ValueError as e:
            raise _AuthResolveError(
                f"auth alias '{a.alias}' decrypt failed: {e}"
            ) from e
    missing = set(aliases) - {a.alias for a in resolved}
    if missing:
        logger.warning(
            "run_dispatcher: exec auth aliases not found: {}", sorted(missing)
        )
    return resolved


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


def _coerce_row_value(base_val: Any, row_val: Any) -> Any:
    """行值按基线类型还原(新数据集编辑器把所有值存成字符串)。

    转置表格/CSV 导入统一 ``String(v)`` 落库,直接合入会把整型基线
    覆盖成字符串,破坏 ``Assertion{expected: 0}`` 这类强类型断言
    (旧链路"int 还是 int"的语义)。规则:

    * 基线是 bool  → ``"true"/"false"``(大小写不敏感)还原,其余原样;
    * 基线是 int   → ``int(row_val)`` 可解析则还原(int("2.0") 会抛
      ValueError,正好保留原串);
    * 基线是 float → ``float(row_val)`` 可解析则还原;
    * 其余(str/生成式 dict/基线不存在)→ 原样合入 —— 空串仍是显式
      空覆盖,生成式 spec 不受行值影响。
    """
    if not isinstance(row_val, str) or not isinstance(base_val, (bool, int, float)):
        return row_val
    if isinstance(base_val, bool):
        lowered = row_val.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return row_val
    try:
        if isinstance(base_val, int):
            return int(row_val)
        return float(row_val)
    except ValueError:
        return row_val


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


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
) -> Execution:
    """Insert an Execution row(+ 拆表后的快照行)。

    M2:scenario_snapshot 大 JSON 移入 execution_snapshots(1:1),
    executions 主表只留台账轻列(scenario_name/owner_name 快照)。
    重构方案 0014:kind = scenario(默认)/ suite_graph(编排执行,
    scenario_id 写占位 suite-<id>);suite_id 供 21 页归并,无 FK
    (执行台账归执行人,历史不随 Suite 删除消失)。
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
    )
    db.add(ex)
    await db.flush()  # 拿 execution.id,快照行同事务写入
    if scenario_snapshot:
        db.add(ExecutionSnapshot(
            execution_id=ex.id, snapshot=scenario_snapshot))
    await db.commit()
    await db.refresh(ex)
    return ex


# ─── ad-hoc lookups (scenario_id is the string PK) ────────────────
# 单行场景/数据集查询收敛到各自 store 的 get_row(全后端唯一实现)。
from .scenario_store import get_row, steps_from_payload, definition_from_payload
from .scenario_store import _meta_from_row  # noqa: PLC2701 台账快照列(M2)
from .data_set_store import get_row as get_dataset_row


async def _find_dataset_by_id(
    db: AsyncSession, dataset_id: str
) -> ComposerDataSet | None:
    return await get_dataset_row(db, dataset_id)


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
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ── 外部系统集成 P1:私有件提升为公共(方案 §5,与此前 ─────────────
# referenced_services 的处理一致 —— integration_runner 复用同一份
# 组装/解析实现,不在集成路径另开第二份漂移面)。
compose_scenario = _compose_scenario
built_in_users = _built_in_users
resolve_exec_auths = _resolve_exec_auths
find_dataset_by_id = _find_dataset_by_id
