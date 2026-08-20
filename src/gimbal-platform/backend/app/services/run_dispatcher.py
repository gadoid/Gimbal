"""Run dispatcher (V3 Scenario Composer).

Per-row fan-out of a Scenario's selected DataSets into Plate ``/convert``
calls.  Mirrors the in-flight task pattern in
``app/routers/executions.py`` (tracked ``set[asyncio.Task]`` +
``_shutting_down`` flag + ``drain_*`` helper) so the app lifespan can
shut down cleanly.

The former Case layer was dissolved — ``RunRequest`` IS the recipe
(env / dataSetIds / auths / retry / …, pure values) applied directly to
the scenario by :func:`_compose_scenario` (the 配置器/transformer).

Returns ``RunResponse(runId)`` to the caller immediately, and the
``Execution`` row (re-used from Spec-2) holds the aggregate counters
so the existing ``/executions`` UI shows the run without any frontend
changes.
"""
from __future__ import annotations

import asyncio
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import Execution
from ..models.auth_session import AuthSession
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import RunRequest, RunResponse
from . import env_store, gimbal_client, plate_client


# ─── in-flight tracking ───────────────────────────────────────────
# Same pattern as ``app/services/run_lifecycle.py``'s _in_flight_runners /
# drain_in_flight_runners: the app lifespan calls
# ``drain_in_flight_dispatches()`` to wait for cancellation.
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
    # 1. Load the scenario (PK is the string scenario_id, not the int id)
    scen = (
        preloaded_scenario
        if preloaded_scenario is not None
        else await _find_scenario_by_id(db, req.scenario_id)
    )
    if scen is None:
        raise _NotFound("scenario_not_found", f"scenario not found: {req.scenario_id}")

    # 2. Validate env + datasets.  list_envs() is sync (cached) — safe to
    # call inline here because it returns from an lru_cache on the
    # happy path; the first call does a one-shot YAML parse.
    env_ids = {e.env_id for e in env_store.list_envs()}
    if req.env.env_id not in env_ids:
        raise _NotFound("env_not_found", f"env not found: {req.env.env_id}")
    if not req.data_set_ids:
        raise _Conflict("no_data_selected", "no data sets selected")

    # step_to 校验(同 V1 executions:与场景 steps 数比对,越界 409)
    steps = ((scen.payload or {}).get("definition") or {}).get("steps") or []
    if req.step_to is not None:
        if not steps:
            raise _NotFound("no_steps", "scenario has no steps; step_to cannot be set")
        if req.step_to >= len(steps):
            raise _Conflict(
                "step_to_out_of_range",
                f"step_to={req.step_to} out of range (0..{len(steps) - 1})",
            )

    selected_datasets: list[ComposerDataSet] = []
    for ds_id in req.data_set_ids:
        ds = await _find_dataset_by_id(db, ds_id)
        if ds is None or ds.scenario_id != scen.scenario_id:
            raise _NotFound(
                "data_set_not_found", f"data set not found: {ds_id}"
            )
        selected_datasets.append(ds)

    # append 合并策略冲突预检(V1 executor 同语义):所选认证 alias 与
    # 场景内置 Config.users 同名 → 409 拒绝整单(而不是行级静默覆盖)。
    if req.inject_credentials and req.merge_policy == "append" and req.auths:
        built_in_users = _built_in_users(scen.payload)
        collisions = sorted(set(req.auths) & set(built_in_users.keys()))
        if collisions:
            raise _Conflict(
                "append_policy_conflict",
                f"append policy conflict: auth alias {collisions} already "
                f"defined in scenario config.users",
            )

    # 3. Allocate runId + Execution row
    run_id = _new_run_id()
    total_runs = sum(int(ds.row_count or 0) for ds in selected_datasets) * req.n_runs
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
            # "auth" 导致 Execution 详情认证列恒空
            "exec_auth_alias": list(req.auths),
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
                datasets=[
                    {
                        "datasetId": ds.dataset_id,
                        "rows": list(ds.rows or []),
                    }
                    for ds in selected_datasets
                ],
                env=req.env.model_dump(by_alias=True, mode="json"),
                owner_id=user_id,
                auth_aliases=list(req.auths) if req.inject_credentials else [],
                halt_at=req.step_to,
                n_runs=req.n_runs,
                parallel=req.parallel,
                prefix=req.prefix,
                merge_policy=req.merge_policy,
                retry=req.retry.model_dump(by_alias=True, mode="json")
                if req.retry
                else None,
            ),
            name=f"v3-dispatch-{run_id}",
        )
        task.add_done_callback(_log_task_exception)
        _track(task)

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
    retry: dict | None,
    halt_at: int | None = None,
    n_runs: int = 1,
    parallel: int = 1,
    prefix: str | None = None,
    merge_policy: str = "merge",
) -> None:
    """Per-row × per-repeat convert + run; updates Execution counters in place.

    ``halt_at``(V1 step_to 移植):0-based 含端点,透传 gimbal HTTP
    ``halt_at`` —— RuntimeControl 在该步后停(剩余步显示 skipped)。

    M1(V1 executor 移植):``n_runs`` 每行重复次数、``parallel`` 并发度
    (asyncio.Semaphore)、``prefix`` 提单号前缀变量注入、``merge_policy``
    执行认证合并策略(override/merge/append;append 冲突已在 dispatch
    侧预检拒绝)。
    """
    log_path = _jsonl_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

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
        try:
            _append_jsonl(log_path, {
                "ts": datetime.utcnow().isoformat() + "Z",
                "runId": run_id,
                "executionId": execution_id,
                "status": "auth_resolve_failed",
                "error": str(e),
            })
        except Exception:  # noqa: BLE001
            pass
        try:
            async with db_factory() as session:
                await session.execute(
                    sqlalchemy_update(Execution)
                    .where(Execution.id == execution_id)
                    .values(failed=Execution.failed + total_rows)
                )
                await session.commit()
        except Exception as ex:  # noqa: BLE001
            logger.warning(
                "run_dispatcher: counter bump failed for execution {}: {}",
                execution_id, ex,
            )
        await _finalize_execution(db_factory, execution_id)
        return

    sem = asyncio.Semaphore(max(1, parallel))

    # 内置认证(definition.config.users)merge 策略的保留基座 —— plate
    # /convert 的产物可能剥掉平台视图字段,凭证合并不依赖 converted
    # 自带 users,而是以场景定义为源(与 V1 在原始 yaml 上渲染同语义)。
    built_in_users = _built_in_users(scenario_payload)

    async def _row(ds: dict, row_idx: int, rep: int) -> None:
        """One (dataset row × repeat) entry — convert + run + counters."""
        async with sem:
            row_dict = dict(ds["rows"][row_idx] or {})
            composed = _compose_scenario(scenario_payload, row_dict)
            log_line = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "runId": run_id,
                "executionId": execution_id,
                "scenarioId": composed.get("scenarioId"),
                "datasetId": ds["datasetId"],
                "rowIndex": row_idx,
                "rep": rep,
                "env": env,
                "status": "dispatched",
            }
            try:
                _append_jsonl(log_path, log_line)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "run_dispatcher: failed to write JSONL log line for {}: {}",
                    log_line, e,
                )

            try:
                convert_data = await plate_client.convert(composed)
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
                try:
                    run_out = await gimbal_client.run(composed_exec, halt_at=halt_at)
                except gimbal_client.GimbalUnavailableError as e:
                    # convert 已过(结构合法),引擎不可达是执行层故障:
                    # 记失败但不中断后续行(fan-out 永不因单行崩溃)。
                    log_line["status"] = "gimbal_unavailable"
                    log_line["runError"] = str(e)
                    logger.warning("run_dispatcher: gimbal unavailable for row {}/{}#{}: {}", ds["datasetId"], row_idx, rep, e)
                except gimbal_client.GimbalRejectedError as e:
                    log_line["status"] = "gimbal_rejected"
                    log_line["runError"] = e.message
                    logger.warning("run_dispatcher: gimbal rejected row {}/{}#{}: {}", ds["datasetId"], row_idx, rep, e.message)
                else:
                    exit_code = int(run_out.get("exitCode", 2))
                    log_line["status"] = "passed" if exit_code == 0 else "failed"
                    log_line["runResult"] = {
                        k: run_out.get(k)
                        for k in ("exitCode", "total", "passed", "failed", "skipped", "halted")
                    }
                    logger.info(
                        "run_dispatcher: row {}/{}#{} executed: exit={} passed={} failed={}",
                        ds["datasetId"], row_idx, rep, exit_code,
                        run_out.get("passed"), run_out.get("failed"),
                    )
            except plate_client.PlateUnavailableError as e:
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

            # Append the final log line for this row (covers all
            # success / failure branches — previously the rejected
            # branches ``continue``'d before this and lost the line).
            try:
                _append_jsonl(log_path, log_line)
            except Exception:  # noqa: BLE001
                pass

            # Atomic per-row counter bump.  Deltas (not absolute
            # write-backs) so concurrent rows and concurrent UI
            # deletions (MAX(0, col-1) SQL) compose correctly.
            ok = 1 if log_line["status"] == "passed" else 0
            bad = 1 - ok
            try:
                async with db_factory() as session:
                    await session.execute(
                        sqlalchemy_update(Execution)
                        .where(Execution.id == execution_id)
                        .values(
                            passed=Execution.passed + ok,
                            failed=Execution.failed + bad,
                        )
                    )
                    await session.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "run_dispatcher: counter bump failed for execution {}: {}",
                    execution_id, e,
                )

    # (dataset, row, repeat) 笛卡尔积;n_runs=1 时与旧逐行行为完全一致。
    entries = [
        (ds, row_idx, rep)
        for ds in datasets
        for row_idx in range(len(ds["rows"]))
        for rep in range(n_runs)
    ]
    await asyncio.gather(*(_row(ds, i, r) for ds, i, r in entries))

    # Terminal status + timestamps only (counters already maintained
    # incrementally above).
    await _finalize_execution(db_factory, execution_id)


async def _finalize_execution(db_factory: Any, execution_id: int) -> None:
    """终态收尾:只写 status + 时间戳(计数器由上方增量维护)。

    严格规则(与 V1 executor / run_lifecycle reconcile 一致):
    ``failed > 0 → failed`` — 任何一个 run 失败即整单失败,部分
    通过不再被标成 done(此前 ``failed and not passed`` 会让
    3 过 1 败显示为"完成")。
    """
    try:
        async with db_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is not None:
                ex.status = "failed" if ex.failed else "done"
                if ex.started_at is None:
                    ex.started_at = datetime.utcnow()
                ex.finished_at = datetime.utcnow()
                await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: failed to update execution {}: {}", execution_id, e)


# ─── helpers ──────────────────────────────────────────────────────
def _built_in_users(scenario_payload: dict | None) -> dict[str, Any]:
    """场景 definition.config.users(merge 策略保留基座)。"""
    raw = scenario_payload or {}
    defn = raw.get("definition") if isinstance(raw.get("definition"), dict) else raw
    def_cfg = (defn or {}).get("config") or {}
    users = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
    return dict(users or {})


def _compose_scenario(
    scenario_payload: dict, row_dict: dict
) -> dict[str, Any]:
    """配置器:把存储的 Scenario + 一行数据 变换成 Plate 输入。

    源存果算 — 这里是唯一的变换点:存储里只有场景定义(源)与
    数据行(纯值),每个 run 的形态由本函数即时计算:

    * deep-copy 场景定义,行键值合入 ``config.vars``(行值覆盖同名
      场景级 var;JSON 类型原样保留 — int 还是 int,断言
      ``expected: 0`` 不会被字符串化破坏)。
    * ``scenario_payload`` 是持久化的 ``ComposerScenario.payload``。
      容器化重构后为 ``{definition, orchestration}``;plate 只吃
      ``definition``(orchestration 是平台侧投影,绝不外发)。
      容器化之前的 legacy 行原样透传。
    """
    raw = scenario_payload or {}
    # Unwrap the container: plate must never see orchestration.
    if isinstance(raw.get("definition"), dict):
        raw = raw["definition"]
    out = copy.deepcopy(raw)
    out.setdefault("kind", "scenario")
    cfg = out.setdefault("config", {})
    if not isinstance(cfg, dict):
        cfg = {}
        out["config"] = cfg
    vars_map = dict(cfg.get("vars") or {})
    # Row wins: a row's `qty` overrides a scenario-level `vars.qty`.
    for k, v in (row_dict or {}).items():
        vars_map[k] = v
    cfg["vars"] = vars_map
    return out


def _new_run_id() -> str:
    return f"run-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6]}"


class _AuthResolveError(RuntimeError):
    """执行认证解密失败 — fail-fast,同 V1 executor 的 ``_decrypt_auths``
    语义(解密失败上抛使整个 run 失败,而不是带着空/坏凭证静默打环境)。"""


async def _resolve_exec_auths(
    db_factory: Any, owner_id: int, aliases: list[str]
) -> list["AuthSession"]:
    """Owner 级 alias → AuthSession(解密)。owner 过滤防跨 owner 同名
    alias 解错凭证。

    * 解密失败 → 抛 :class:`_AuthResolveError`(V1 严格语义:
      凭证路径 fail-fast,不静默降级)。
    * alias 不属于该 owner 时解不到 → 告警后继续(与 V1 一致:
      缺 alias 只是注入不到 users,该行 run 在 Gimbal 解析
      ``${auth.*}`` 时步骤级报错)。
    """
    if not aliases:
        return []
    from ..core.security import fernet_decrypt

    resolved: list[AuthSession] = []
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
            a.username = fernet_decrypt(a.username_enc)
            a.password = fernet_decrypt(a.password_enc)
            resolved.append(a)
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


def _inject_exec_users(
    composed: dict[str, Any],
    exec_auths: list[AuthSession],
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
    return settings.DATA_DIR / "runs" / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"


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
        status="queued",
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
async def _find_scenario_by_id(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario | None:
    res = await db.execute(
        select(ComposerScenario).where(
            ComposerScenario.scenario_id == scenario_id
        )
    )
    return res.scalar_one_or_none()


async def _find_dataset_by_id(
    db: AsyncSession, dataset_id: str
) -> ComposerDataSet | None:
    res = await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.dataset_id == dataset_id
        )
    )
    return res.scalar_one_or_none()


# ─── session factory (for the background task) ───────────────────
def _session_factory() -> AsyncSession:
    """Open a fresh AsyncSession — the background task outlives the
    request-scoped session the router passed in."""
    from ..core.db import SessionLocal
    return SessionLocal()


# ─── error sentinels (router translates to HTTPException) ─────────
class _NotFound(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _Conflict(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
