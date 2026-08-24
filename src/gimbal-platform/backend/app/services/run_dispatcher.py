"""Run dispatcher (V3.2 Scenario Composer — ``gimbal run launch`` 执行链).

Per-row fan-out of a Scenario's selected DataSets:

1. :func:`_compose_scenario` — 场景 definition + 一行数据集 → 数据驱动的
   gimbal scenario dict(行键注入 ``config.vars``,按基线类型还原)。
2. Plate ``/convert`` — 校验 + 剥平台视图字段(orchestration 绝不外发)。
3. 执行认证/前缀注入 convert 产物(明文不流经 plate)。
4. 落盘 case 文件(``DATA_DIR/runs/cases/<runId>/``)。
5. ``gimbal_launcher.launch`` 子进程执行 ``gimbal run launch <case>``,
   stdout JSON RunResult 驱动行级计数。

Mirrors the in-flight task pattern in ``app/routers/executions.py``
(tracked ``set[asyncio.Task]`` + ``_shutting_down`` flag + ``drain_*``
helper) so the app lifespan can shut down cleanly.

The former Case layer was dissolved — ``RunRequest`` IS the recipe
(env / dataSetIds / auths / …, pure values) applied directly to
the scenario by :func:`_compose_scenario` (the 配置器/transformer).

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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.timeutil import utcnow as _utcnow
from ..models import Execution
from ..models.execution import (
    STATUS_CANCELED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
)
from ..models.auth_session import AuthSession
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import RunRequest, RunResponse
from . import env_store, gimbal_launcher, plate_client


@dataclass(frozen=True, slots=True)
class ResolvedAuth:
    """解密后的执行认证(轻量值对象)。

    明文凭证只存在于该对象的生命周期内,不落在 AuthSession ORM 行
    上 — 避免任何意外 commit 把明文写回数据库。
    """

    alias: str
    url: str
    username: str
    password: str
    token_type: str
    expires_in: int


# ─── in-flight tracking ───────────────────────────────────────────
# 与 routers/executions.py 相同的 task 跟踪模式(tracked
# ``set[asyncio.Task]`` + ``_shutting_down`` flag):app lifespan 调用
# ``drain_in_flight_dispatches()`` 等待取消。
_in_flight: set[asyncio.Task] = set()
_shutting_down: bool = False


def is_shutting_down() -> bool:
    return _shutting_down


def _track(task: asyncio.Task) -> None:
    _in_flight.add(task)
    task.add_done_callback(_in_flight.discard)


def _log_task_exception(task: asyncio.Task) -> None:
    """Done-callback that surfaces unhandled exceptions in background tasks.

    Without this an exception inside ``_fanout`` would be silently lost
    (asyncio doesn't propagate task exceptions to the parent).  We
    already track + discard from ``_in_flight`` in the parent callback;
    this one only logs the exception, never raises.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.exception(
            "run_dispatcher: background fan-out task crashed: {}", exc
        )


async def drain_in_flight_dispatches() -> int:
    """Cancel + await all in-flight dispatch tasks.  Called from lifespan."""
    global _shutting_down
    _shutting_down = True
    n = len(_in_flight)
    if not n:
        return 0
    for t in list(_in_flight):
        t.cancel()
    await asyncio.gather(*_in_flight, return_exceptions=True)
    return n


def reset_shutdown_state() -> None:
    """Clear the shutdown flag (lifespan startup).

    ``_shutting_down`` 只在 drain 时置位;不复位的话,同一进程复用模块
    (测试直接调 drain 后再来一次 app lifespan)时 dispatch 会静默跳过
    fan-out,Execution 永远停在 queued。
    """
    global _shutting_down
    _shutting_down = False


# ─── global launch concurrency gate (P7) ──────────────────────────
# 全局 launch 并发闸(P7):按事件循环缓存 Semaphore——asyncio 原语
# 绑定创建时的 loop,pytest 每用例新 loop,进程级单例会跨 loop 复用
# 报 "attached to a different loop"。
_launch_sems: dict[int, asyncio.Semaphore] = {}


def _global_launch_sem() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    sem = _launch_sems.get(loop_id)
    if sem is None:
        sem = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_LAUNCHES))
        _launch_sems[loop_id] = sem
    return sem


def reset_concurrency_state() -> None:
    """测试隔离:清空按 loop 缓存的信号量(换上限后重建)。"""
    _launch_sems.clear()


# ─── cooperative cancel registry (P4) ─────────────────────────────
# 取消注册表(P4 协作式取消):取消请求集合 + 在飞 fanout task 索引。
# 取消语义:协作式 —— 只在未来行边界生效,在飞子进程自然跑完
# (Windows 下 task.cancel 会让 asyncio 放弃收尸、泄漏 gimbal 子进程,
# 不做);未跑行记 ``canceled`` JSONL 行、不进计数器;``total_runs``
# 不变,canceled 单允许 ``passed+failed < total_runs``(finalize 跳过
# 校账)。
_cancel_requested: set[int] = set()
_tasks_by_execution: dict[int, asyncio.Task] = {}


def request_cancel(execution_id: int) -> None:
    """登记取消请求(幂等);由 _fanout 在行边界消费。"""
    _cancel_requested.add(execution_id)


def has_live_fanout(execution_id: int) -> bool:
    return execution_id in _tasks_by_execution


def reset_cancel_state() -> None:
    """测试隔离:清空取消注册表。"""
    _cancel_requested.clear()
    _tasks_by_execution.clear()


# ─── startup reconcile (P3) ────────────────────────────────────────
async def reconcile_stale_executions(db_factory: Any) -> int:
    """启动期 reconcile:进程内 _fanout 随重启丢失,queued 即僵尸。

    全部标 failed + ``config_json.reconciled`` 记录(P3:此前永远
    停在 queued,UI 无从得知)。返回处理行数。
    """
    count = 0
    async with db_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Execution).where(Execution.status == STATUS_QUEUED)
                )
            )
            .scalars()
            .all()
        )
        for ex in rows:
            ex.status = STATUS_FAILED
            if ex.started_at is None:
                ex.started_at = ex.created_at or _utcnow()
            ex.finished_at = _utcnow()
            cfg = dict(ex.config_json or {})
            cfg["reconciled"] = {
                "at": _utcnow().isoformat() + "Z",
                "reason": "backend restarted mid-dispatch",
            }
            ex.config_json = cfg
            count += 1
        await session.commit()
    if count:
        logger.warning(
            "run_dispatcher: reconciled {} stale queued execution(s) after restart",
            count,
        )
    return count


async def startup_recovery() -> tuple[int, int]:
    """启动恢复:reconcile 僵尸执行 + 清扫过期 case 目录(Task 5 接入)。"""
    stale = await reconcile_stale_executions(_session_factory)
    swept = sweep_stale_case_dirs()
    return stale, swept


# ─── main entry point ─────────────────────────────────────────────
async def dispatch_run(
    db: AsyncSession,
    user_id: int,
    req: RunRequest,
    *,
    preloaded_scenario: ComposerScenario | None = None,
) -> RunResponse:
    """Validate + fan out + return runId.

    Caller (the runs router) wraps any exception in HTTPException.  This
    function NEVER raises for "Plate is down" — it records the failure
    and returns the runId so the user can still see the run in
    ``/executions`` (per the agreed run-failure semantics).

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

    # 2. Validate env + datasets.  list_envs() is sync (cached) — safe to
    # call inline here because it returns from an lru_cache on the
    # happy path; the first call does a one-shot YAML parse.
    server_env = next(
        (e for e in env_store.list_envs() if e.env_id == req.env.env_id), None
    )
    if server_env is None:
        raise NotFound("env_not_found", f"env not found: {req.env.env_id}")
    # P5 服务端权威:name/baseUrl 一律取 env_store 记录;请求体携带的
    # 值不一致时告警(此前客户端可传 envId=dev + baseUrl=任意内网地址,
    # env 治理形同虚设)。
    if (req.env.name, req.env.base_url) != (server_env.name, server_env.base_url):
        logger.warning(
            "run_dispatcher: env mismatch for {} — client ({}, {}), "
            "server ({}, {}); using server record",
            req.env.env_id, req.env.name, req.env.base_url,
            server_env.name, server_env.base_url,
        )

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

    selected_datasets: list[ComposerDataSet] = []
    for ds_id in req.data_set_ids:
        ds = await _find_dataset_by_id(db, ds_id)
        if ds is None or ds.scenario_id != scen.scenario_id:
            raise NotFound(
                "data_set_not_found", f"data set not found: {ds_id}"
            )
        selected_datasets.append(ds)

    # append 合并策略冲突预检(V1 executor 同语义):所选认证 alias 与
    # 场景内置 Config.users 同名 → 409 拒绝整单(而不是行级静默覆盖)。
    if req.inject_credentials and req.merge_policy == "append" and req.auths:
        built_in_users = _built_in_users(scen.payload)
        collisions = sorted(set(req.auths) & set(built_in_users.keys()))
        if collisions:
            raise Conflict(
                "append_policy_conflict",
                f"append policy conflict: auth alias {collisions} already "
                f"defined in scenario config.users",
            )

    # 3. Allocate runId + Execution row
    # total_runs 必须按实际行数算(与 _fanout 的迭代口径一致)— 旧的
    # row_count 列在 raw-SQL 迁移路径下不回填,NULL/过期会让计数器
    # 超过 total_runs 出现 failed > total 的怪状态。
    run_id = _new_run_id()
    # D12 基线执行:未选数据集 = 一个隐式空覆盖行(纯基线,行键空集
    # 全部回落 config.vars)。datasetId=None 在 JSONL 里如实记录。
    # 新编辑器里行 0 基线虚行不落库 → 0 行数据集 = "只有基线",同样
    # 回退一个隐式空覆盖行(否则 entries 为空,执行 0/0/0 秒完结)。
    fanout_datasets = [
        {"datasetId": ds.dataset_id, "rows": list(ds.rows or []) or [{}]}
        for ds in selected_datasets
    ] or [{"datasetId": None, "rows": [{}]}]
    total_runs = sum(len(d["rows"]) for d in fanout_datasets) * req.n_runs
    # P7:总量闸——行数 × nRuns 无上限时,万行数据集 × n_runs 会派生
    # 出十万级子进程。
    if total_runs > settings.MAX_RUNS_PER_EXECUTION:
        raise Conflict(
            "too_many_runs",
            f"total runs {total_runs} exceed platform cap "
            f"{settings.MAX_RUNS_PER_EXECUTION} (rows x nRuns)",
        )
    execution = await _create_execution(
        db,
        # (Case 层解散后执行的挂载点就是场景)。
        scenario_id=scen.scenario_id,
        owner_id=user_id,
        total_runs=total_runs,
        config_json={
            "runId": run_id,
            "scenarioId": scen.scenario_id,
            "dataSetIds": req.data_set_ids,
            "envId": req.env.env_id,
            # 读侧契约是 exec_auth_alias(同 V1 executor 路径);此前误写
            # "auth" 导致 Execution 详情认证列恒空。injectCredentials=false
            # 时 aliases 根本不会被解析/注入,记录原始选择会误导详情页。
            "exec_auth_alias": list(req.auths) if req.inject_credentials else [],
            "stepTo": req.step_to,
            "injectCredentials": req.inject_credentials,
            "nRuns": req.n_runs,
            "parallel": req.parallel,
            "prefix": req.prefix,
            "mergePolicy": req.merge_policy,
        },
    )

    # 4. Spawn the background fan-out (cancel-cleanly tracked)
    if not is_shutting_down():
        task = asyncio.create_task(
            _fanout(
                db_factory=_session_factory,
                execution_id=execution.id,
                run_id=run_id,
                scenario_payload=dict(scen.payload or {}),
                datasets=fanout_datasets,
                env=server_env.model_dump(by_alias=True, mode="json"),
                owner_id=user_id,
                auth_aliases=list(req.auths) if req.inject_credentials else [],
                halt_at=req.step_to,
                n_runs=req.n_runs,
                parallel=req.parallel,
                prefix=req.prefix,
                merge_policy=req.merge_policy,
            ),
            name=f"v3-dispatch-{run_id}",
        )
        task.add_done_callback(_log_task_exception)
        _track(task)
        # P4:在飞 fanout 索引(cancel 端点据此区分"活单等行边界收敛"与
        # "僵尸单立即终态化")。出清回调与 _in_flight.discard 并存。
        _tasks_by_execution[execution.id] = task
        task.add_done_callback(
            lambda _t, eid=execution.id: _tasks_by_execution.pop(eid, None)
        )

    return RunResponse(runId=run_id, executionId=execution.id)


# ─── background fan-out ──────────────────────────────────────────
async def _fanout(
    *,
    db_factory: Any,
    execution_id: int,
    run_id: str,
    scenario_payload: dict,
    datasets: list[dict],
    env: dict,
    owner_id: int,
    auth_aliases: list[str],
    halt_at: int | None = None,
    n_runs: int = 1,
    parallel: int = 1,
    prefix: str | None = None,
    merge_policy: str = "merge",
) -> None:
    """Per-row × per-repeat compose + convert + ``gimbal run launch`` 子进程。

    ``halt_at``(V1 step_to 移植):0-based 含端点,透传 CLI
    ``--step-to`` —— RuntimeControl 在该步后停(剩余步显示 skipped)。

    M1(V1 executor 移植):``n_runs`` 每行重复次数、``parallel`` 并发度
    (asyncio.Semaphore)、``prefix`` 提单号前缀变量注入、``merge_policy``
    执行认证合并策略(override/merge/append;append 冲突已在 dispatch
    侧预检拒绝)。

    V3.2:执行调用从 gimbal HTTP POST /run 改为落盘 case 文件后
    ``gimbal run launch <case>`` 子进程(设计:2026-08-24 spec)。
    case 文件即数据驱动用例快照(含注入后的明文 users —— 与 V1 临时
    yaml 同语义,落在平台 DATA_DIR 权限域内)。
    """
    # P4:防御性出清该 id 的历史残留取消请求(僵尸单由 cancel 端点
    # inline 终态化,没有 fanout 来消费;测试的 fresh 库会复用执行 id)。
    # 活跃请求只可能在本 task 启动之后到达(dispatch 先 spawn、后返回
    # 响应,行边界检查更在其后),此处不会误吞。
    _cancel_requested.discard(execution_id)
    log_path = _jsonl_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # 每个 run 一个 case 目录:case 文件 + 引擎原生报告,并发 fan-out
    # 互不互踩;与 JSONL 同域构成执行审计面(什么数据真的打给了引擎)。
    run_dir = _run_dir(run_id)

    # 执行用认证:owner 级解密一次,逐行注入 run 副本的 Config.users。
    # 解密失败 = fail-fast(V1 严格语义):整单 execution 记为
    # failed,所有行计入 failed 计数,不带着空/坏凭证打环境。
    try:
        # injectCredentials=False 时 dispatch 侧已清空 aliases,这里直接
        # 跳过解析(与 V1 executor 的 inject_credentials=False 同语义)。
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
        total_rows = sum(len(ds["rows"]) for ds in datasets) * n_runs
        await _fail_whole_execution(
            db_factory, log_path, execution_id=execution_id, run_id=run_id,
            total_rows=total_rows, error=str(e),
        )
        return

    sem = asyncio.Semaphore(max(1, parallel))

    # P6:整单固定一次 compose 时间戳 — fill_plate_defaults 对缺失的
    # meta.createTime 注入"当前时刻"(微秒精度),同一行 n_runs 次重复
    # 的 convert 输入会逐次不同,memo 键永不命中。deepcopy 隔离存储
    # payload(防写穿 ORM 行)后预填一次,compose 内 setdefault 语义
    # 即复用同一值 → 同一行重复输入完全一致。
    scenario_payload = copy.deepcopy(scenario_payload)
    plate_client.fill_plate_defaults(definition_from_payload(scenario_payload))

    # P6:fan-out 级 convert memo + plate 连续不可用熔断计数。
    convert_cache: dict[str, dict] = {}
    plate_state = {"consecutive_unavailable": 0}

    def _breaker_open() -> bool:
        return (
            plate_state["consecutive_unavailable"]
            >= settings.PLATE_BREAKER_THRESHOLD
        )

    # 内置认证(definition.config.users)merge 策略的保留基座 —— plate
    # /convert 的产物可能剥掉平台视图字段,凭证合并不依赖 converted
    # 自带 users,而是以场景定义为源(与 V1 在原始 yaml 上渲染同语义)。
    built_in_users = _built_in_users(scenario_payload)

    async def _row(ds: dict, row_idx: int, rep: int, seq: int) -> None:
        """One (dataset row × repeat) entry — compose + convert + launch."""
        async with sem:
            # P4 协作式取消:行边界在信号量准入处(全部行 task 在 fanout
            # 启动时就已创建并排队,准入前检查永远看不到晚到的取消请求)。
            # 已准入的行视为在飞、自然跑完;排队中的行在准入时刻检查,
            # 未启动的直接记 canceled,不进计数器。
            if execution_id in _cancel_requested:
                await _append_log(log_path, {
                    "ts": _utcnow().isoformat() + "Z",
                    "runId": run_id,
                    "executionId": execution_id,
                    "datasetId": ds["datasetId"],
                    "rowIndex": row_idx,
                    "rep": rep,
                    "status": "canceled",
                })
                return
            row_dict = dict(ds["rows"][row_idx] or {})
            composed = _compose_scenario(scenario_payload, row_dict)
            # 每个 case 独立子目录:case.json(数据驱动用例快照)+ 引擎
            # 原生报告目录;stem 带 dataset/row/rep 定位,便于事后审计。
            stem = (
                f"case-{seq:03d}-{ds['datasetId'] or 'baseline'}"
                f"-r{row_idx}-n{rep}"
            )
            case_dir = run_dir / stem
            log_line = {
                "ts": _utcnow().isoformat() + "Z",
                "runId": run_id,
                "executionId": execution_id,
                "scenarioId": composed.get("scenarioId"),
                "datasetId": ds["datasetId"],
                "rowIndex": row_idx,
                "rep": rep,
                "env": env,
                "status": "dispatched",
                "casePath": str((case_dir / "case.json")),
                "reportDir": str((case_dir / "reports")),
            }
            await _append_log(log_path, log_line)

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
                        convert_data = convert_cache[cache_key]
                    else:
                        convert_data = await plate_client.convert(composed)
                        convert_cache[cache_key] = convert_data
                    plate_state["consecutive_unavailable"] = 0
                    # Convert succeeded — hand the gimbal-shaped product to the
                    # engine. 明文 users 只进 run 副本(convert 那份不带,防明文
                    # 流进 plate 校验/日志);注入形状同 V1 executor 生产路径。
                    # convert_data = {consumer, converted};converted 是
                    # GimbalScenarioExporter 的产物(已剥平台视图扩展字段)。
                    converted = convert_data.get("converted") or {}
                    composed_exec = _inject_exec_users(
                        converted,
                        exec_auths,
                        merge_policy=merge_policy,
                        built_in_users=built_in_users,
                    )
                    if prefix:
                        # 前缀变量注入进 run 副本(post-convert,防 plate 剥掉)。
                        _inject_prefix_vars(composed_exec, prefix)
                    # services 物化:未映射服务名 → env.baseUrl(见函数 docstring)。
                    _inject_services(composed_exec, env)
                    # 落盘数据驱动用例快照后交给 CLI 子进程执行。
                    case_path = _write_case_file(case_dir, composed_exec)
                    # P7 全局并发闸:进程级 launch 在飞上限(跨 execution
                    # 合并生效;行级 sem 只管单 execution 的 parallel)。
                    async with _global_launch_sem():
                        result = await gimbal_launcher.launch(
                            case_path,
                            step_to=halt_at,
                            report_dir=case_dir / "reports",
                            cwd=case_dir,
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
                            result.launch_status, ds["datasetId"], row_idx, rep,
                            result.error,
                        )
                    elif result.exit_code == 0:
                        log_line["status"] = "passed"
                        logger.info(
                            "run_dispatcher: row {}/{}#{} executed: exit=0 passed={} failed={}",
                            ds["datasetId"], row_idx, rep,
                            result.passed, result.failed,
                        )
                    elif result.exit_code == 2:
                        # 引擎 Scenario 校验拒绝(与 HTTP 422 同源)。
                        log_line["status"] = "gimbal_rejected"
                        log_line["runError"] = result.error
                        logger.warning(
                            "run_dispatcher: gimbal rejected row {}/{}#{}: {}",
                            ds["datasetId"], row_idx, rep, result.error,
                        )
                    else:
                        # exit 1 = 测试失败(正常业务结果);>=3 = 引擎侧错误。
                        log_line["status"] = "failed"
                        log_line["runError"] = result.error
                        logger.info(
                            "run_dispatcher: row {}/{}#{} executed: exit={} passed={} failed={}",
                            ds["datasetId"], row_idx, rep, result.exit_code,
                            result.passed, result.failed,
                        )
            except plate_client.PlateUnavailableError as e:
                plate_state["consecutive_unavailable"] += 1
                log_line["status"] = "plate_unavailable"
                log_line["error"] = str(e)
                logger.warning("run_dispatcher: plate unavailable for row {}/{}#{}: {}", ds["datasetId"], row_idx, rep, e)
            except plate_client.PlateRejectedError as e:
                log_line["status"] = "plate_rejected"
                log_line["error"] = e.message
                log_line["errors"] = list(e.errors or [])
                logger.warning("run_dispatcher: plate rejected row {}/{}#{}: {}", ds["datasetId"], row_idx, rep, e.message)
            except Exception as e:  # noqa: BLE001  defensive — never let a row kill the fan-out
                log_line["status"] = "dispatcher_error"
                log_line["error"] = repr(e)
                logger.exception("run_dispatcher: unexpected error row {}/{}#{}", ds["datasetId"], row_idx, rep)

            # P1:引擎结果全量证据落盘(仅真实拿到 LaunchResult 的路径;
            # plate 异常分支不设 runResult,短路跳过)。
            if "runResult" in log_line:
                _write_result_evidence(case_dir, result, log_line["status"])

            # Append the final log line for this row (covers all
            # success / failure branches — previously the rejected
            # branches ``continue``'d before this and lost the line).
            await _append_log(log_path, log_line)

            # Atomic per-row counter bump.  Deltas (not absolute
            # write-backs) so concurrent rows and concurrent UI
            # deletions (MAX(0, col-1) SQL) compose correctly.
            passed = 1 if log_line["status"] == "passed" else 0
            await _bump_counters(
                db_factory, execution_id, passed=passed, failed=1 - passed
            )

    # (dataset, row, repeat) 笛卡尔积;n_runs=1 时与旧逐行行为完全一致。
    # seq 为 case 文件名里的全局序号(与 entries 顺序一致,单测可断言)。
    entries = [
        (ds, row_idx, rep)
        for ds in datasets
        for row_idx in range(len(ds["rows"]))
        for rep in range(n_runs)
    ]
    await asyncio.gather(
        *(_row(ds, i, r, seq) for seq, (ds, i, r) in enumerate(entries))
    )

    # Terminal status + timestamps only (counters already maintained
    # incrementally above).
    if execution_id in _cancel_requested:
        # P4 协作式取消:未跑行已在行边界记 canceled,在飞子进程已自然
        # 跑完;canceled 允许 passed+failed < total_runs(finalize 跳过
        # 校账)。请求在此消费出清(终态后状态归零,同 id 空间不被污染)。
        await _finalize_execution(db_factory, execution_id, status=STATUS_CANCELED)
        _cancel_requested.discard(execution_id)
    else:
        await _finalize_execution(db_factory, execution_id)


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
    db_factory: Any, execution_id: int, *, passed: int, failed: int
) -> None:
    """Atomic Execution counter bump(P8:失败重试一次,双败 JSONL 记账)。

    Deltas(not absolute write-backs)so concurrent rows and concurrent
    UI deletions compose correctly.
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
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: failed to update execution {}: {}", execution_id, e)


# ─── helpers ──────────────────────────────────────────────────────
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
    """
    if not aliases:
        return []
    from ..core.security import fernet_decrypt

    resolved: list[ResolvedAuth] = []
    async with db_factory() as session:
        rows = (
            (
                await session.execute(
                    select(AuthSession).where(
                        AuthSession.owner_id == owner_id,
                        AuthSession.alias.in_(aliases),
                    )
                )
            )
            .scalars()
            .all()
        )
    for a in rows:
        try:
            resolved.append(ResolvedAuth(
                alias=a.alias,
                url=a.url,
                username=fernet_decrypt(a.username_enc),
                password=fernet_decrypt(a.password_enc),
                token_type=a.token_type,
                expires_in=a.expires_in,
            ))
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


def _inject_prefix_vars(composed: dict[str, Any], prefix: str) -> None:
    """提单号前缀变量注入(就地修改 composed.config.vars;V1
    ``_render_temp_yaml`` 同语义):

    * ``vars.order_no_prefix = prefix`` — 步骤里可用 `${var.order_no_prefix}` 拼前缀
    * ``vars.order_no = "<prefix>-{{ seq }}"`` — 引擎渲染期展开为 ``P-1 / P-2 / …``
    * ``vars.seq = {"kind": "seq"}`` — 序列生成器声明(幂等覆盖)
    """
    cfg = composed.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
        composed["config"] = cfg
    vars_map = dict(cfg.get("vars") or {})
    vars_map["order_no_prefix"] = prefix
    vars_map["order_no"] = f"{prefix}-{{{{ seq }}}}"
    vars_map["seq"] = {"kind": "seq"}
    cfg["vars"] = vars_map


def _inject_services(composed: dict[str, Any], env: dict[str, Any]) -> None:
    """services 物化:steps 引用而 config.services 未映射的服务名 →
    注入选定环境的 baseUrl(就地修改)。

    plate 的端点模型没有 host 概念(service = 业务域,如 fin 下的
    audit/order_fee),部署主机只存在于执行环境(RunEnv.baseUrl)——
    引擎侧 URL 解析需要的 service→base_url 映射只能由运行时环境补:

    * 只补缺口:场景显式写过的 services(如自建 mock)原样保留,
      环境不覆盖 authored 映射;
    * env.baseUrl 为空(RunDialog 兜底构造/环境配置缺失)时不注入,
      保持"步骤无映射"的引擎报错可见,不静默造出假 URL;
    * post-convert 注入 run 副本,与凭证/前缀同一模式(convert 的
      输入始终是 authored 原文,审计面不失真)。
    """
    base_url = (env or {}).get("baseUrl") or ""
    if not base_url:
        return
    referenced: set[str] = {
        api["service"]
        for step in composed.get("steps") or []
        if isinstance(step, dict)
        and isinstance(api := step.get("api"), dict)
        and api.get("service")
    }
    if not referenced:
        return
    cfg = composed.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
        composed["config"] = cfg
    services = dict(cfg.get("services") or {})
    for name in sorted(referenced):
        services.setdefault(name, base_url)
    cfg["services"] = services


def _inject_exec_users(
    composed: dict[str, Any],
    exec_auths: list[ResolvedAuth],
    *,
    merge_policy: str = "merge",
    built_in_users: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """返回注入 ``Config.users`` 的 run 副本(不改动入参)。

    形状与 V1 executor 生产路径一致,Gimbal preprocessor 已消费验证::

        users[<alias>] = {url, username, password, token_type, expires_in}

    ``merge_policy``(V1 merge_policy 移植):
      * ``merge``(默认)— 同名覆盖、场景内置其余保留。保留基座是
        ``built_in_users``(场景 definition.config.users)而非 converted
        自带的 users —— plate /convert 会剥平台视图字段,内置认证以
        场景定义为唯一可信源。
      * ``override`` — 整块替换为所选认证(内置 users 丢弃)
      * ``append`` — 同 merge;与内置 users 的别名冲突已在 dispatch
        侧预检拒绝(409),此处不再重复校验
    ``exec_auths`` 为空时原样返回同一引用(run stub 不会外发,无明文
    泄漏面)。
    """
    if not exec_auths:
        return composed
    out = copy.deepcopy(composed)
    cfg = out.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
        out["config"] = cfg
    if merge_policy == "override":
        users: dict[str, Any] = {}
    else:
        users = {**(built_in_users or {}), **(cfg.get("users") or {})}
    for a in exec_auths:
        users[a.alias] = {
            "url": a.url,
            "username": a.username,
            "password": a.password,
            "token_type": a.token_type,
            "expires_in": a.expires_in,
        }
    cfg["users"] = users
    return out


def _jsonl_path() -> Path:
    return settings.DATA_DIR / "runs" / f"{_utcnow().strftime('%Y-%m-%d')}.jsonl"


def _run_dir(run_id: str) -> Path:
    """一个 run 的 case 文件根目录(与 JSONL 同域的执行审计面)。"""
    return settings.DATA_DIR / "runs" / "cases" / run_id


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
) -> Execution:
    """Insert an Execution row."""
    ex = Execution(
        scenario_id=scenario_id,
        owner_id=owner_id,
        status=STATUS_QUEUED,
        total_runs=total_runs,
        passed=0,
        failed=0,
        config_json=config_json,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return ex


# ─── ad-hoc lookups (scenario_id is the string PK) ────────────────
# 单行场景/数据集查询收敛到各自 store 的 get_row(全后端唯一实现)。
from .scenario_store import get_row, steps_from_payload, definition_from_payload
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
