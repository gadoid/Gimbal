"""Run dispatcher (V3 Scenario Composer).

Per-row fan-out of a Case's selected DataSets into Plate ``/convert``
calls.  Mirrors the in-flight task pattern in
``app/routers/executions.py`` (tracked ``set[asyncio.Task]`` +
``_shutting_down`` flag + ``drain_*`` helper) so the app lifespan can
shut down cleanly.

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
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import Execution
from ..models.auth_session import AuthSession
from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import RunRequest, RunResponse
from . import data_set_store, env_store, plate_client, scenario_store


# ─── in-flight tracking ───────────────────────────────────────────
# Same pattern as ``app/routers/executions.py``'s _in_flight_runners /
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
) -> RunResponse:
    """Validate + fan out + return runId.

    Caller (the runs router) wraps any exception in HTTPException.  This
    function NEVER raises for "Plate is down" — it records the failure
    and returns the runId so the user can still see the run in
    ``/executions`` (per the agreed run-failure semantics).
    """
    # 1. Load the case + scenario (PK is the string case_id, not the int id)
    case = await _find_case_by_id(db, req.case_id)
    if case is None:
        raise _NotFound("case_not_found", f"case not found: {req.case_id}")
    scen = await _find_scenario_by_id(db, case.scenario_id)
    if scen is None:
        raise _NotFound(
            "scenario_not_found", f"scenario not found: {case.scenario_id}"
        )

    # 2. Validate env + datasets.  list_envs() is sync (cached) — safe to
    # call inline here because it returns from an lru_cache on the
    # happy path; the first call does a one-shot YAML parse.
    env_ids = {e.env_id for e in env_store.list_envs()}
    if req.env.env_id not in env_ids:
        raise _NotFound("env_not_found", f"env not found: {req.env.env_id}")
    if not req.data_set_ids:
        raise _Conflict("no_data_selected", "no data sets selected")

    selected_datasets: list[ComposerDataSet] = []
    for ds_id in req.data_set_ids:
        ds = await _find_dataset_by_id(db, ds_id)
        if ds is None or ds.case_id != case.case_id:
            raise _NotFound(
                "data_set_not_found", f"data set not found: {ds_id}"
            )
        selected_datasets.append(ds)

    # 3. Allocate runId + Execution row
    run_id = _new_run_id()
    total_runs = sum(int(ds.row_count or 0) for ds in selected_datasets)
    execution = await _create_execution(
        db,
        case_id=case.case_id,
        owner_id=user_id,
        total_runs=total_runs,
        config_json={
            "runId": run_id,
            "caseId": case.case_id,
            "scenarioId": case.scenario_id,
            "dataSetIds": req.data_set_ids,
            "envId": req.env.env_id,
            # 读侧契约是 exec_auth_alias(同 V1 executor 路径);此前误写
            # "auth" 导致 Execution 详情认证列恒空
            "exec_auth_alias": list(req.auths),
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
                case_payload=dict(case.payload or {}),
                datasets=[
                    {
                        "datasetId": ds.dataset_id,
                        "caseId": ds.case_id,
                        "rows": list(ds.rows or []),
                    }
                    for ds in selected_datasets
                ],
                env=req.env.model_dump(by_alias=True, mode="json"),
                auth_aliases=list(req.auths),
                retry=req.retry.model_dump(by_alias=True, mode="json")
                if req.retry
                else None,
            ),
            name=f"v3-dispatch-{run_id}",
        )
        task.add_done_callback(_log_task_exception)
        _track(task)

    return RunResponse(runId=run_id)


# ─── background fan-out ──────────────────────────────────────────
async def _fanout(
    *,
    db_factory: Any,
    execution_id: int,
    run_id: str,
    scenario_payload: dict,
    case_payload: dict,
    datasets: list[dict],
    env: dict,
    auth_aliases: list[str],
    retry: dict | None,
) -> None:
    """Per-row convert + run; updates Execution counters in place."""
    plate_ok = 0
    plate_failed = 0
    log_path = _jsonl_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 执行用认证:owner 级解密一次,逐行注入 run 副本的 Config.users。
    # 失败(别名不存在/解密异常)不中断 fan-out — 该行 run 会在 Gimbal
    # 解析 ${auth.*} 时步骤级报错,与"仅警告放行"的前端语义一致。
    exec_auths = await _resolve_exec_auths(db_factory, auth_aliases)

    for ds in datasets:
        for row_idx, row in enumerate(ds["rows"]):
            row_dict = dict(row or {})
            composed = _compose_scenario(
                scenario_payload, case_payload, row_dict
            )
            log_line = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "runId": run_id,
                "executionId": execution_id,
                "caseId": case_payload.get("caseId"),
                "scenarioId": composed.get("scenarioId"),
                "datasetId": ds["datasetId"],
                "rowIndex": row_idx,
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
                await plate_client.convert(composed)
                plate_ok += 1
                log_line["status"] = "convert_ok"
            except plate_client.PlateUnavailableError as e:
                plate_failed += 1
                log_line["status"] = "plate_unavailable"
                log_line["error"] = str(e)
                logger.warning("run_dispatcher: plate unavailable for row {}/{}: {}", ds["datasetId"], row_idx, e)
            except plate_client.PlateRejectedError as e:
                plate_failed += 1
                log_line["status"] = "plate_rejected"
                log_line["error"] = e.message
                log_line["errors"] = list(e.errors or [])
                logger.warning("run_dispatcher: plate rejected row {}/{}: {}", ds["datasetId"], row_idx, e.message)
            except Exception as e:  # noqa: BLE001  defensive — never let a row kill the fan-out
                plate_failed += 1
                log_line["status"] = "dispatcher_error"
                log_line["error"] = repr(e)
                logger.exception("run_dispatcher: unexpected error row {}/{}", ds["datasetId"], row_idx)
            else:
                # Convert succeeded — try the optional D2 run call.
                # 明文 users 只进 run 副本(convert 那份不带,防明文流进
                # plate 校验/日志);注入形状同 V1 executor 生产路径。
                composed_exec = _inject_exec_users(composed, exec_auths)
                try:
                    await plate_client.run(composed_exec)
                except Exception as e:  # noqa: BLE001
                    log_line["status"] = "run_stub_or_failed"
                    log_line["runError"] = repr(e)
                    logger.info("run_dispatcher: D2 stub for row {}/{}: {}", ds["datasetId"], row_idx, e)

            # Append the final log line for this row (covers all
            # success / failure branches — previously the rejected
            # branches ``continue``'d before this and lost the line).
            try:
                _append_jsonl(log_path, log_line)
            except Exception:  # noqa: BLE001
                pass

    # Update the Execution row counters (Spec-2 ``Execution`` shape).
    try:
        async with db_factory() as session:
            ex = await session.get(Execution, execution_id)
            if ex is not None:
                ex.passed = plate_ok
                ex.failed = plate_failed
                ex.status = "failed" if plate_failed and not plate_ok else "done"
                if ex.started_at is None:
                    ex.started_at = datetime.utcnow()
                ex.finished_at = datetime.utcnow()
                await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("run_dispatcher: failed to update execution {}: {}", execution_id, e)


# ─── helpers ──────────────────────────────────────────────────────
def _compose_scenario(
    scenario_payload: dict, case_payload: dict, row_dict: dict
) -> dict[str, Any]:
    """Build a per-row Scenario dict for Plate.

    The shape Plate expects is the V3.2 ``Scenario`` model.  We deep-copy
    the stored scenario, then layer the row's key/value pairs into
    ``config.vars`` so Plate's runtime can resolve them.  This is
    best-effort: we do not implement a full templating engine; the row
    values are serialised as strings, which is what most
    ``${var.x}`` substitutions in the existing fixtures rely on.

    ``scenario_payload`` is the persisted ``ComposerScenario.payload``.
    Since the container refactor that is ``{definition, orchestration,
    caseMeta}``; plate only wants the ``definition`` (orchestration /
    caseMeta are platform-only).  Legacy rows that predate the container
    are passed through as-is.
    """
    raw = scenario_payload or {}
    # Unwrap the container: plate must never see orchestration/caseMeta.
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
    # Carry the env's baseUrl into services so Plate can resolve
    # ${tidb-test-service} → https://test-a.fin.local/... later.
    if case_payload:
        env_base = case_payload.get("env") or case_payload.get("envId")
        if env_base and isinstance(env_base, str):
            services = dict(cfg.get("services") or {})
            # Only auto-fill for the common dev-local case where the
            # services map is empty; real services should be set in the
            # scenario editor.
            if not services:
                services["__env__"] = env_base
                cfg["services"] = services
    return out


def _new_run_id() -> str:
    return f"run-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6]}"


async def _resolve_exec_auths(
    db_factory: Any, aliases: list[str]
) -> list["AuthSession"]:
    """Owner-agnostic alias → AuthSession(解密)。同 V1 executor 的
    ``_decrypt_auths`` 语义,但 owner 过滤在 fan-out 语境不可用
    (dispatch_run 的 user_id 没有透传到这里)——按 alias 全局解。
    aliases 为空直接返回;任何异常返回已解出的部分并告警(fan-out
    不因认证失败中断,与"仅警告放行"语义一致)。
    """
    if not aliases:
        return []
    from ..core.security import fernet_decrypt

    resolved: list[AuthSession] = []
    async with db_factory() as session:
        rows = (
            (
                await session.execute(
                    select(AuthSession).where(AuthSession.alias.in_(aliases))
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
            logger.warning(
                "run_dispatcher: auth alias '{}' decrypt failed: {}", a.alias, e
            )
    missing = set(aliases) - {a.alias for a in resolved}
    if missing:
        logger.warning(
            "run_dispatcher: exec auth aliases not found: {}", sorted(missing)
        )
    return resolved


def _inject_exec_users(
    composed: dict[str, Any], exec_auths: list[AuthSession]
) -> dict[str, Any]:
    """返回注入 ``Config.users`` 的 run 副本(不改动入参)。

    形状与 V1 executor 生产路径一致,Gimbal preprocessor 已消费验证::

        users[<alias>] = {url, username, password, token_type, expires_in}

    同名覆盖(merge 语义);``exec_auths`` 为空时原样返回同一引用
    (run stub 不会外发,无明文泄漏面)。
    """
    if not exec_auths:
        return composed
    out = copy.deepcopy(composed)
    cfg = out.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
        out["config"] = cfg
    users = dict(cfg.get("users") or {})
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
    case_id: str,
    owner_id: int,
    total_runs: int,
    config_json: dict,
) -> Execution:
    """Insert an Execution row (Spec-2 shape)."""
    ex = Execution(
        case_id=case_id,
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


# ─── ad-hoc lookups (since case_id / scenario_id are string PKs) ──
async def _find_case_by_id(db: AsyncSession, case_id: str) -> ComposerCase | None:
    res = await db.execute(
        select(ComposerCase).where(ComposerCase.case_id == case_id)
    )
    return res.scalar_one_or_none()


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
