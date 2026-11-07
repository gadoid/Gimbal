"""Execution 读侧投影 + 删除(V3,自 executions 路由收敛)。

exec_runs 子表已随存量数据清理退役(V1 兼容层),删除整单不再需要
子行清理;单-run 删除的计数器回退(MAX(0, col-1))也随端点一并移除。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Execution, ExecutionSnapshot
from ..models.execution import ExecutionEvent, ExecutionJob
from ..models.composer_scenario import ComposerScenario
from ..models.execution import STATUS_FAILED, STATUS_QUEUED, STATUS_RUNNING
from ..schemas.execution import ExecutionListItemOut, ExecutionOut

async def scenario_display_map(
    db: AsyncSession, user, scenario_ids: list[str]
) -> dict[str, tuple[str, bool]]:
    """当页 scenario_id → (可读活名或空串, 场景行是否存在)。

    G1 读侧投影的唯一实现(批量 IN,替代前端自拼映射):活名只在
    「调用者可读该场景」时给出(与列表/详情同一口径 —— 场景被执行后
    转让他人转 private 时,不向历史执行者泄露当前名);不可读/不存在
    由调用方回落自己行上的 scenario_name 快照(快照是执行者自己的
    记录,照常显示)。
    """
    ids = sorted({s for s in scenario_ids if s})
    if not ids:
        return {}
    rows = (await db.execute(
        select(ComposerScenario.scenario_id, ComposerScenario.name,
               ComposerScenario.owner_id, ComposerScenario.project_id)
        .where(ComposerScenario.scenario_id.in_(ids))
    )).all()
    # S1.1:读面谓词单点 can_pure(表 B scenario.read + 项目上下文;
    # ref 读者不进执行展示面 —— 引用是编排读面,执行台账跟发起人)
    from types import SimpleNamespace

    from ..routers._ownership import can_pure
    from .zone import my_project_roles, public_project_id
    ctx = dict(public_project_id=await public_project_id(db),
               project_roles=await my_project_roles(db, user.id))
    return {
        sid: (str(name or "") if can_pure(
                  user, "scenario", "read",
                  SimpleNamespace(owner_id=owner_id, project_id=pid),
                  **ctx)
              else "", True)
        for sid, name, owner_id, pid in rows
    }


def display_kwargs(
    e: Execution, disp: dict[str, tuple[str, bool]]
) -> dict:
    """执行行 → (scenario_display_name, scenario_deleted) 响应 kwargs。"""
    live, exists = disp.get(e.scenario_id, ("", False))
    if live:
        return {"scenario_display_name": live, "scenario_deleted": False}
    return {"scenario_display_name": e.scenario_name or e.scenario_id,
            "scenario_deleted": not exists}


async def has_snapshot(db: AsyncSession, execution_id: int) -> bool:
    """快照存在性(M2 拆表:一次存在性查询,不再依赖整实体加载)。"""
    return (await db.execute(
        select(ExecutionSnapshot.execution_id).where(
            ExecutionSnapshot.execution_id == execution_id).limit(1)
    )).first() is not None


async def snapshot_of(db: AsyncSession, execution_id: int) -> dict | None:
    """快照本体(唯一消费方:GET /executions/{id}/scenario-snapshot)。"""
    row = (await db.execute(
        select(ExecutionSnapshot).where(
            ExecutionSnapshot.execution_id == execution_id)
    )).scalar_one_or_none()
    return row.snapshot if row is not None else None


async def snapshot_ids(db: AsyncSession, execution_ids: list[int]) -> set[int]:
    """批量存在性(列表端点一次 in 查询,替代逐行读大 JSON 列)。"""
    if not execution_ids:
        return set()
    rows = (await db.execute(
        select(ExecutionSnapshot.execution_id).where(
            ExecutionSnapshot.execution_id.in_(execution_ids))
    )).scalars().all()
    return set(rows)


# ── 可取消判定(全量评估 2026-11-02 #1;graph 单元级取消方案 P3/P4)──────

async def uncancelable_graph_ids(db: AsyncSession, execution_ids: list[int]) -> set[int]:
    """已被 worker 认领(job running)且**不支持中途取消**的 graph 执行 id
    (一次 in 查询;列表/详情/cancel 共用)。

    口径按单元级取消能力(方案 §6「可」项 + legacy 通道,2026-11-03 起):
    spawn 期探测并落 ``job payload["unit_cancel"]`` —— server 链读 healthz
    的 cancel_scopes(旧执行器空能力 → False,旧执行器会把 scope=unit 当
    step 处理且带 A0 缺陷);legacy 链读本地 gimbal 包 FEATURES(GIMBAL_BIN
    指向外部安装无法探测 → 保守 False)。能力位缺失 = 尚未探测(物化/执行
    器启动窗口):server 链取消可被接受 —— 启动前命中走「取消先于启动」收
    口、启动期命中由下发任务等 session 就绪后按能力位决定(评审
    2026-11-03 §3.1)→ 可取消;legacy 链按不可取消。graph 不能看 ``Execution.kind``:
    ``POST /api/runs`` 带 graph 的执行 kind 仍是 scenario,只有
    ``execution_jobs.kind`` / payload 如实记了任务体形态与链。按 job
    状态而非执行状态判断 —— 物化窗口里执行仍 queued。queued 的 graph
    两条链都可取消(启动前检查 / 物化窗口检查)。
    """
    if not execution_ids:
        return set()
    rows = (await db.execute(
        select(ExecutionJob.execution_id, ExecutionJob.payload).where(
            ExecutionJob.execution_id.in_(execution_ids),
            ExecutionJob.kind == "graph",
            ExecutionJob.status == "running"))
    ).all()
    return {eid for eid, payload in rows
            if not _graph_unit_cancelable(payload or {})}


def _graph_unit_cancelable(payload: dict) -> bool:
    """graph 任务体 payload → 是否具备单元级取消(uncancelable 的取反)。"""
    flag = payload.get("unit_cancel")
    if flag is not None:
        return bool(flag)
    # 能力位未探测 = 物化/执行器启动窗口:server 链取消可被接受,下发任务
    # 总是先建、session 就绪后按能力位决定发或停(评审 2026-11-03 §3.1)
    # → 可取消;legacy 链 = 旧引擎/未探测,保守不可取消。
    return (payload.get("chain") or "legacy") == "server"


async def graph_job_payload(db: AsyncSession, execution_id: int) -> dict | None:
    """执行的任务体 payload(cancel 端点 409 文案按链/能力位区分用)。"""
    return (await db.execute(
        select(ExecutionJob.payload).where(
            ExecutionJob.execution_id == execution_id)
    )).scalar_one_or_none()


async def cancel_requested_ids(db: AsyncSession, execution_ids: list[int]) -> set[int]:
    """已写取消位、任务仍活的执行 id(P4 投影:running ∧ cancel_requested =
    「取消中」—— graph 要等在飞单元跑完才收口,这段时间按钮隐藏、显示等待)。"""
    if not execution_ids:
        return set()
    rows = (await db.execute(
        select(ExecutionJob.execution_id).where(
            ExecutionJob.execution_id.in_(execution_ids),
            ExecutionJob.cancel_requested.is_(True),
            ExecutionJob.status.in_(("queued", "running")))
    )).scalars().all()
    return set(rows)


def is_cancelable(e: Execution, *, uncancelable_graph: bool,
                  cancel_requested: bool = False) -> bool:
    """已请求取消 → False(取消中);legacy graph 已认领 → False;否则
    queued/running 可取消(cases 链行边界、server graph 单元边界消费)。"""
    if cancel_requested or uncancelable_graph:
        return False
    return e.status in (STATUS_QUEUED, STATUS_RUNNING)


async def active_job_forms(db: AsyncSession, execution_ids: list[int]) -> dict[int, str]:
    """execution id → 活任务体形态 ``graph`` | ``cases``(无活任务的不在表)。

    取消说明按它区分等待面:graph 等在飞单元跑完,cases 等当前行跑完。
    与 :func:`uncancelable_graph_ids` 同坑:``POST /api/runs`` 带 graph 的
    执行 kind 仍是 scenario,只有 ``execution_jobs.kind`` 如实。
    """
    if not execution_ids:
        return {}
    rows = (await db.execute(
        select(ExecutionJob.execution_id, ExecutionJob.kind).where(
            ExecutionJob.execution_id.in_(execution_ids),
            ExecutionJob.status.in_(("queued", "running")))
    )).all()
    return {eid: ("graph" if kind == "graph" else "cases") for eid, kind in rows}


CANCEL_NOTE_GRAPH = "已请求取消:当前单元跑完后停止,后续单元记为已取消"
CANCEL_NOTE_CASES = "已请求取消:当前行跑完后停止,后续行记为已取消"
CANCEL_NOTE_IGNORED = ("已请求取消,但当时所有单元均已启动、没有可停的单元,"
                       "已按真实结果收口")
# cancelIgnored=executor_no_unit_cancel(旧执行器启动窗口取消被接受但未下发)
CANCEL_NOTE_NO_UNIT_CANCEL = ("已请求取消,但执行器版本不支持单元级中途取消,"
                              "取消未下发,已按真实结果收口")


def cancel_note(e: Execution, *, form: str = "cases",
                cancel_requested: bool = False) -> str | None:
    """取消说明文案(服务端给、前端原样显示):

    * 活跃且取消位已写 → 取消中,等的是在飞单元(graph)还是当前行(cases);
    * 终态且 ``config.cancelIgnored`` → 点了取消却按真实结果收口的原因
      (所有单元已启动 vs 执行器不支持单元级取消,按值区分);
    * 其余 None。
    """
    if e.status in (STATUS_QUEUED, STATUS_RUNNING):
        if not cancel_requested:
            return None
        return CANCEL_NOTE_GRAPH if form == "graph" else CANCEL_NOTE_CASES
    cfg = e.config_json if isinstance(e.config_json, dict) else {}
    if cfg.get("cancelIgnored") == "executor_no_unit_cancel":
        return CANCEL_NOTE_NO_UNIT_CANCEL
    return CANCEL_NOTE_IGNORED if cfg.get("cancelIgnored") else None


# 连续失败计数回看的最大行数(执行设计 §3.2「连续第 N 次失败」信号)。
# 内部平台量级下,owner 全量 (id, scenario_id, status) 轻行扫描足够;
# 超出视为断层(信号照报,只是 N 以窗内为准)。
_STREAK_SCAN_LIMIT = 1000


def execution_out(
    e: Execution,
    *,
    consecutive_failures: int = 0,
    has_scenario_snapshot: bool = False,
    scenario_display_name: str = "",
    scenario_deleted: bool = False,
    uncancelable_graph: bool = False,
    cancel_requested: bool = False,
    job_form: str = "cases",
) -> ExecutionOut:
    return ExecutionOut(
        id=e.id,
        scenario_id=e.scenario_id,
        status=e.status,
        total_runs=e.total_runs,
        passed=e.passed,
        failed=e.failed,
        started_at=e.started_at,
        finished_at=e.finished_at,
        config=e.config_json or {},
        has_scenario_snapshot=has_scenario_snapshot,
        batch_id=e.batch_id,
        consecutive_failures=consecutive_failures,
        scenario_display_name=scenario_display_name,
        scenario_deleted=scenario_deleted,
        kind=e.kind or "scenario",
        suite_id=e.suite_id,
        plate_pins=e.plate_pins,
        m2_hash=e.m2_hash,
        baseline_eligible=bool(e.baseline_eligible),
        baseline_block=e.baseline_block,
        baseline_evidence=e.baseline_evidence,
        # B-3:失败原因顶层化(config.dispatcherError 是唯一写点)
        error=(e.config_json or {}).get("dispatcherError")
        if e.status == "failed" else None,
        cancelable=is_cancelable(e, uncancelable_graph=uncancelable_graph,
                                 cancel_requested=cancel_requested),
        cancel_requested=cancel_requested,
        cancel_note=cancel_note(e, form=job_form, cancel_requested=cancel_requested),
        token_id=e.token_id or None,
        identity_mode=((e.config_json or {}).get("token") or {}).get("kind")
        if e.token_id else None,
        token_name=((e.config_json or {}).get("token") or {}).get("name")
        if e.token_id else None,
        client_ref=e.client_ref or None,
    )


# 列表 UI 的非敏感窄投影键(ExecutionsList 行内方案徽标/次数/并发/停步/
# 认证快失败信号;useScenarioRuns 的趋势过滤读 schemeId 做方案溯源)。
# 凭证引用面(injectedAuths/serviceBindings)绝不进列表。
_CONFIG_SUMMARY_KEYS = (
    "schemeId", "schemeName", "authFailFast",
)


def _config_summary(cfg: dict) -> dict:
    """执行参数投影(W19):新行读 runOptions dump 内层键,旧行平铺键
    回退 —— 对外 configSummary 形状不变(nRuns/parallel/stepTo)。"""
    summary = {k: cfg[k] for k in _CONFIG_SUMMARY_KEYS if k in cfg}
    ro = cfg.get("runOptions")
    if isinstance(ro, dict):
        if "n_runs" in ro:
            summary["nRuns"] = ro["n_runs"]
        if "parallel" in ro:
            summary["parallel"] = ro["parallel"]
        if "step_to" in ro:
            summary["stepTo"] = ro["step_to"]
    else:   # 旧行平铺键(W19 之前发起的执行)
        for k in ("nRuns", "parallel", "stepTo"):
            if k in cfg:
                summary[k] = cfg[k]
    return summary


def execution_list_item(
    e: Execution,
    *,
    consecutive_failures: int = 0,
    has_scenario_snapshot: bool = False,
    scenario_display_name: str = "",
    scenario_deleted: bool = False,
    uncancelable_graph: bool = False,
    cancel_requested: bool = False,
    job_form: str = "cases",
) -> ExecutionListItemOut:
    """列表行形态(M1):响应去 config,只带窄投影 config_summary。

    注:服务端仍读 config_json 现算 summary(M1 门禁不含 DB 扫描下降,
    PG迁移方案 §7);响应面的敏感列清除是本函数的全部职责。
    """
    cfg = e.config_json if isinstance(e.config_json, dict) else {}
    # P2-2:ownerName 台账快照;账号注销后(owner_id NULL)带「已注销」
    owner_name = e.owner_name or ""
    if e.owner_id is None and owner_name:
        owner_name = f"{owner_name}(已注销)"
    return ExecutionListItemOut(
        id=e.id,
        scenario_id=e.scenario_id,
        status=e.status,
        total_runs=e.total_runs,
        passed=e.passed,
        failed=e.failed,
        started_at=e.started_at,
        finished_at=e.finished_at,
        owner_name=owner_name,
        config_summary=_config_summary(cfg),
        has_scenario_snapshot=has_scenario_snapshot,
        batch_id=e.batch_id,
        consecutive_failures=consecutive_failures,
        scenario_display_name=scenario_display_name,
        scenario_deleted=scenario_deleted,
        kind=e.kind or "scenario",
        suite_id=e.suite_id,
        plate_pins=e.plate_pins,
        m2_hash=e.m2_hash,
        baseline_eligible=bool(e.baseline_eligible),
        baseline_block=e.baseline_block,
        cancelable=is_cancelable(e, uncancelable_graph=uncancelable_graph,
                                 cancel_requested=cancel_requested),
        cancel_requested=cancel_requested,
        cancel_note=cancel_note(e, form=job_form, cancel_requested=cancel_requested),
    )


async def consecutive_failure_streaks(
    session: AsyncSession, owner_id: int
) -> dict[int, int]:
    """execution id → 「连续第 N 次失败」(执行设计 §3.2 信号列)。

    口径:同 owner 同 scenario 的执行按 id 升序(= 时间序)连续计失败,
    失败单自身计入 N;成功/取消单断链。一次轻行扫描(只取三列,倒序
    取最近 _STREAK_SCAN_LIMIT 条)内存里转回时间正序走一遍:失败链第
    N 单记 N(最新单拿链长 — 「已经连挂 N 次」),非失败单不进返回表
    (前端只在 failed 行渲染信号)。
    """
    rows = (
        (
            await session.execute(
                select(Execution.id, Execution.scenario_id, Execution.status)
                .where(Execution.owner_id == owner_id)
                .order_by(Execution.id.desc())
                .limit(_STREAK_SCAN_LIMIT)
            )
        )
        .all()
    )
    streak_by_scenario: dict[str, int] = {}
    out: dict[int, int] = {}
    for exec_id, scenario_id, exec_status in reversed(rows):
        if exec_status == STATUS_FAILED:
            streak_by_scenario[scenario_id] = (
                streak_by_scenario.get(scenario_id, 0) + 1
            )
            out[exec_id] = streak_by_scenario[scenario_id]
        else:
            streak_by_scenario[scenario_id] = 0
    return out


async def delete_execution(session: AsyncSession, ex: Execution) -> None:
    """删除整单 + 连带清理 case 案卷目录(P2:案卷含明文凭证)。

    调度日志(data/runs/*.jsonl)按日期分文件、不随删(现行设计)。
    """
    from . import run_dispatcher

    run_id = (ex.config_json or {}).get("runId")
    await session.delete(ex)
    await session.commit()
    if run_id:
        run_dispatcher.purge_case_dir(str(run_id))


# ── P2-02/C2:事件与日志落库(统一表)─────────────────────────────

def _dialect_insert(db: AsyncSession):
    """PG insert(SQLite 已退役 2026-10-14,双方言分派随之退役)。"""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    return pg_insert


async def insert_events(db: AsyncSession, execution_id: int,
                        events: list[dict]) -> None:
    """执行器 jsonl 事件批量入库。

    ``events`` = 事件 model_dump dict 列表(含信封标签);``call.exchange``
    的 ``result`` 证据体拆 ``ExecutionEventEvidence``,主表 message 留
    摘要(protocol/status/duration)。同 (execution_id, seq) 冲突跳过
    (崩溃重放窗口不重复入库)。
    """
    from datetime import datetime, timezone

    from ..models.execution import ExecutionEvent, ExecutionEventEvidence
    insert_ = _dialect_insert(db)

    if not events:
        return
    rows: list[dict] = []
    evidences: list[dict] = []
    steps: list[dict] = []
    # step.end 的 error_brief 对断言失败为空(失败文案在先到的 step.failed
    # 里):同批内按 (unit, attempt, step) 记下,补进步骤行
    failed_err: dict[tuple, str] = {}
    for d in events:
        et = str(d.get("event_type") or "")
        if et == "step.failed" and d.get("error"):
            failed_err[(str(d.get("unit") or ""), str(d.get("attempt") or ""),
                        str(d.get("step_id") or d.get("step") or ""))] = str(d["error"])
        payload = dict(d)
        # B3:逐行链在 _row_on_event 注入的行号(不进事件 payload)
        row_seq = payload.pop("row_seq", None)
        message = None
        evidence = None
        if et == "step.end":
            # B3:步骤结果行(报告数据源)。失败证据只进步骤表——事件表
            # 已有 call.exchange 证据,不在 payload 里再存一份
            fe = payload.pop("failure_evidence", None)
            step_row = _step_row(execution_id, payload, row_seq, fe)
            if not step_row["error"] and step_row["status"] in ("failed", "error"):
                step_row["error"] = failed_err.get(
                    (str(d.get("unit") or ""), str(d.get("attempt") or ""),
                     step_row["step_id"]))
            steps.append(step_row)
        if et == "call.exchange":
            evidence = payload.pop("result", None)
            req = evidence.get("request") if isinstance(evidence, dict) else None
            message = "{} {} → {} ({:.0f}ms)".format(
                (req or {}).get("method")
                or payload.get("protocol") or "?",
                (req or {}).get("url") or "?",
                payload.get("status") or "?",
                float(payload.get("duration_ms") or 0.0),
            )
        ts = d.get("timestamp")
        rows.append({
            "execution_id": execution_id,
            "seq": int(d.get("seq") or 0),
            "ts": _parse_ts(ts) or datetime.now(timezone.utc),
            "kind": "event",
            "level": None,
            "category": None,
            "module": d.get("module"),
            "service": d.get("service"),
            "protocol": d.get("protocol"),
            "endpoint": d.get("endpoint"),
            "unit": d.get("unit"),
            "attempt": d.get("attempt"),
            "step": d.get("step"),
            "event_type": et or None,
            "message": message,
            "payload": payload,
        })
        if evidence is not None:
            evidences.append({
                "execution_id": execution_id,
                "seq": int(d.get("seq") or 0),
                "evidence": evidence,
            })

    stmt = insert_(ExecutionEvent).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["execution_id", "seq"])
    await db.execute(stmt)
    if evidences:
        ev_stmt = insert_(ExecutionEventEvidence).values(evidences)
        ev_stmt = ev_stmt.on_conflict_do_nothing(
            index_elements=["execution_id", "seq"])
        await db.execute(ev_stmt)
    if steps:
        await _upsert_steps(db, steps)


# ── B3(2026-11-06 日志报告整理):步骤结果行 ─────────────────────────

_STEP_UPDATE_COLS = (
    "event_seq", "step_name", "description", "call_summary", "status",
    "duration_ms", "error", "assertion_count", "assertion_passed",
    "assertions", "extracts", "failure_evidence", "ended_at",
)


def _step_row(execution_id: int, d: dict, row_seq: Any,
              failure_evidence: Any) -> dict:
    """step.end 事件 dict → execution_steps 行(缺字段的旧引擎事件按缺省落)。"""
    from datetime import datetime, timezone
    try:
        rs = int(row_seq) if row_seq is not None else -1
    except (TypeError, ValueError):
        rs = -1
    return {
        "execution_id": execution_id,
        "row_seq": rs,
        "unit": str(d.get("unit") or d.get("scenario_id") or ""),
        "attempt": str(d.get("attempt") or ""),
        "step_id": str(d.get("step_id") or d.get("step") or ""),
        "event_seq": int(d.get("seq") or 0),
        "step_name": str(d.get("step_name") or "")[:255],
        "description": d.get("description"),
        "call_summary": str(d.get("call_summary") or "")[:1024],
        "status": str(d.get("status") or "")[:16],
        "duration_ms": float(d.get("duration_ms") or 0.0),
        "error": d.get("error_brief"),
        "assertion_count": int(d.get("assertion_count") or 0),
        "assertion_passed": int(d.get("assertion_passed") or 0),
        "assertions": list(d.get("assertions") or []),
        "extracts": list(d.get("extracts") or []),
        "failure_evidence": failure_evidence if isinstance(failure_evidence, dict) else None,
        "ended_at": _parse_ts(d.get("timestamp")) or datetime.now(timezone.utc),
    }


async def _upsert_steps(db: AsyncSession, steps: list[dict]) -> None:
    """同键后到覆盖(恢复重跑重放同一步骤时取最新)。"""
    from ..models.execution import ExecutionStep
    insert_ = _dialect_insert(db)
    # 同批同键去重(PG ON CONFLICT 不允许一条语句内两次命中同一行)
    dedup: dict[tuple, dict] = {}
    for s in steps:
        dedup[(s["row_seq"], s["unit"], s["attempt"], s["step_id"])] = s
    stmt = insert_(ExecutionStep).values(list(dedup.values()))
    stmt = stmt.on_conflict_do_update(
        index_elements=["execution_id", "row_seq", "unit", "attempt", "step_id"],
        set_={c: getattr(stmt.excluded, c) for c in _STEP_UPDATE_COLS},
    )
    await db.execute(stmt)


async def insert_logs(db: AsyncSession, execution_id: int,
                      logs: list[dict], *, seq_base: int) -> None:
    """执行器结构化日志(stderr JSON 行)批量入库。

    平台侧无引擎 seq —— 用 ``seq_base - len(logs) + i`` 递减占位,
    保证与事件流不冲突(事件 seq 恒正且从 1 递增;日志占位取负数或
    大偏移,由调用方保证不与事件撞号:seq_base 传 0 → 日志 seq 为负)。
    """
    from datetime import datetime, timezone

    from ..models.execution import ExecutionEvent
    insert_ = _dialect_insert(db)

    if not logs:
        return
    rows = []
    for i, d in enumerate(logs):
        rows.append({
            "execution_id": execution_id,
            "seq": seq_base - len(logs) + i,
            "ts": _parse_ts(d.get("timestamp")) or datetime.now(timezone.utc),
            "kind": "log",
            "level": d.get("level"),
            "category": d.get("category"),
            "module": d.get("module"),
            "service": d.get("service"),
            "protocol": d.get("protocol"),
            "unit": d.get("unit"),
            "attempt": d.get("attempt"),
            "step": d.get("step"),
            "event_type": None,
            "message": d.get("message"),
            "payload": dict(d),
        })
    stmt = insert_(ExecutionEvent).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["execution_id", "seq"])
    await db.execute(stmt)


def _parse_ts(value) -> "datetime | None":
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def query_events(
    db: AsyncSession, execution_id: int, *,
    kind: "str | None" = None,
    level: "str | None" = None,
    level_min: "str | None" = None,
    category: "str | None" = None,
    module: "str | None" = None,
    service: "str | None" = None,
    unit: "str | None" = None,
    step: "str | None" = None,
    event_type: "str | None" = None,
    search: "str | None" = None,
    after_seq: "int | None" = None,
    after_id: "int | None" = None,
    ts_after: "tuple[datetime, int] | None" = None,
    around: "tuple[datetime, int] | None" = None,
    n_before: int = 50,
    n_after: int = 50,
    order: "str | None" = None,
    limit: int = 500,
) -> list[ExecutionEvent]:
    """事件/日志组合筛选(P2-07 日志分析页与 SSE 续传共用读面)。

    标签精确匹配 + message 全文 search(ILIKE);``after_seq`` 支撑
    Last-Event-ID 续传语义;命中 (execution_id, seq) 索引。

    游标与排序(结构化日志设计 AD4/AD5):
    - ``after_seq``:事件轴游标(seq > ?);
    - ``after_id`` + ``order="id"``:日志流 tail 模式 —— 入库序游标
      (id > ?)按 id 排序。tail 必须用入库序而非 (ts,id):ts 是引擎
      打点时间、入库先后由 flush 时机决定,(ts,id) 游标会稳态漏行
      (先 ts 后入库的行落在已推进的 cursor 之下);
    - ``ts_after``:静态 (ts,id) 时间轴**翻页**锚(严格大于该组合,
      (ts > ?) OR (ts = ? AND id > ?)),与 tail 游标语义无关;
    - ``around``:(ts,id) **上下文窗口**锚(设计 S2)—— 锚点行本身
      + 按 (ts,id) 轴取前 ``n_before`` 行与后 ``n_after`` 行(混合
      时间轴,事件与日志同窗),结果按 (ts,id) 升序;根因几乎总在
      失败事件之前,调用方以失败事件 (ts,id) 为锚;
    - 默认排序(未传 order)走 AD4 语义:event=seq,log/混合=(ts,id)。
    """
    from ..models.execution import ExecutionEvent as EE

    if around is not None:
        return await _query_events_around(
            db, execution_id, around, n_before=n_before, n_after=n_after,
            kind=kind, level=level, level_min=level_min, category=category,
            module=module, service=service, unit=unit, step=step,
            event_type=event_type, search=search)

    stmt = select(EE).where(EE.execution_id == execution_id)
    if after_seq is not None:
        stmt = stmt.where(EE.seq > after_seq)
    if after_id is not None:
        stmt = stmt.where(EE.id > after_id)
    if ts_after is not None:
        anchor_ts, anchor_id = ts_after
        stmt = stmt.where(or_(
            EE.ts > anchor_ts,
            and_(EE.ts == anchor_ts, EE.id > anchor_id)))
    if kind is not None:
        stmt = stmt.where(EE.kind == kind)
    if level is not None:
        stmt = stmt.where(EE.level == level)
    if level_min is not None:
        # 最低级别过滤(日志分析页「warning 以上」口径):按严重度序比较
        # (局部名避开同名参数 order —— 排序模式;曾因此被遮蔽致
        # order="id_desc" 失效、backfill 走了 ts 序重复投递)
        severity = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING",
                    "ERROR", "CRITICAL")
        rank = (severity.index(level_min.upper())
                if level_min.upper() in severity else 0)
        stmt = stmt.where(EE.level.in_(severity[rank:]))
    if category is not None:
        stmt = stmt.where(EE.category == category)
    if module is not None:
        stmt = stmt.where(EE.module == module)
    if service is not None:
        stmt = stmt.where(EE.service == service)
    if unit is not None:
        stmt = stmt.where(EE.unit == unit)
    if step is not None:
        stmt = stmt.where(EE.step == step)
    if event_type is not None:
        stmt = stmt.where(EE.event_type == event_type)
    if search:
        stmt = stmt.where(EE.message.ilike(f"%{search}%"))
    # 排序轴(结构化日志设计 AD4/AD5):默认 event=seq(执行域语义序,SSE
    # 续传依赖)/日志与混合=(ts,id) 统一时间轴;order="id" 为日志流 tail
    # 模式(入库序,负数 seq 对 log 行无序语义,禁止再按 seq 排日志);
    # order="id_desc" 仅供日志流 backfill 取最近 N 行(取后调用方反转)。
    if order == "id":
        stmt = stmt.order_by(EE.id.asc())
    elif order == "id_desc":
        stmt = stmt.order_by(EE.id.desc())
    elif kind == "event":
        stmt = stmt.order_by(EE.seq.asc())
    else:
        stmt = stmt.order_by(EE.ts.asc(), EE.id.asc())
    stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def _query_events_around(
    db: AsyncSession, execution_id: int, anchor: "tuple[datetime, int]", *,
    n_before: int, n_after: int,
    kind: "str | None" = None,
    level: "str | None" = None, level_min: "str | None" = None,
    category: "str | None" = None, module: "str | None" = None,
    service: "str | None" = None, unit: "str | None" = None,
    step: "str | None" = None, event_type: "str | None" = None,
    search: "str | None" = None,
) -> list[ExecutionEvent]:
    """S2 失败上下文窗口:锚点行 + (ts,id) 轴前后各 N 行(混合时间轴)。

    三段式:前窗(严格小于锚,**倒序**取 n_before 再反转)+ 锚段(命中
    筛选的锚行)+ 后窗(严格大于锚,升序取 n_after)——筛选条件对三段
    同面应用。合并按 (ts,id) 升序。
    """
    from ..models.execution import ExecutionEvent as EE

    anchor_ts, anchor_id = anchor

    def _filters(s, *, for_anchor=False):
        if kind is not None:
            s = s.where(EE.kind == kind)
        if for_anchor:
            # 锚段不应用 level/level_min:锚行多为事件行(level=NULL),
            # 按级别筛会被 NULL 语义排除 —— S1 锚点=失败事件,必须无条件
            # 在场;其余维度对锚段同面应用。
            return s
        if level is not None:
            s = s.where(EE.level == level)
        if level_min is not None:
            severity = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING",
                        "ERROR", "CRITICAL")
            rank = (severity.index(level_min.upper())
                    if level_min.upper() in severity else 0)
            s = s.where(EE.level.in_(severity[rank:]))
        if category is not None:
            s = s.where(EE.category == category)
        if module is not None:
            s = s.where(EE.module == module)
        if service is not None:
            s = s.where(EE.service == service)
        if unit is not None:
            s = s.where(EE.unit == unit)
        if step is not None:
            s = s.where(EE.step == step)
        if event_type is not None:
            s = s.where(EE.event_type == event_type)
        if search:
            s = s.where(EE.message.ilike(f"%{search}%"))
        return s

    def _strictly_after(s):
        return s.where(or_(
            EE.ts > anchor_ts,
            and_(EE.ts == anchor_ts, EE.id > anchor_id)))

    def _before(s):
        return s.where(or_(
            EE.ts < anchor_ts,
            and_(EE.ts == anchor_ts, EE.id < anchor_id)))

    # 前窗 n_before 行 + 锚段(ts,id 恰等于锚且命中筛选) + 后窗 n_after 行
    after_stmt = _filters(_strictly_after(
        select(EE).where(EE.execution_id == execution_id))
    ).order_by(EE.ts.asc(), EE.id.asc()).limit(n_after)
    after_rows = list((await db.execute(after_stmt)).scalars().all())

    anchor_stmt = _filters(
        select(EE).where(EE.execution_id == execution_id,
                         EE.ts == anchor_ts, EE.id == anchor_id),
        for_anchor=True)
    anchor_rows = list((await db.execute(anchor_stmt)).scalars().all())

    before_stmt = _filters(_before(
        select(EE).where(EE.execution_id == execution_id))
    ).order_by(EE.ts.desc(), EE.id.desc()).limit(n_before)
    before_rows = list((await db.execute(before_stmt)).scalars().all())
    before_rows.reverse()

    return before_rows + anchor_rows + after_rows


async def event_counts_by_category(
    db: AsyncSession, execution_id: int
) -> dict[str, int]:
    """按 category 聚合计数(P2-07 验收:能展示按 category 聚合的计数)。"""
    from sqlalchemy import func

    from ..models.execution import ExecutionEvent as EE

    stmt = (
        select(EE.category, func.count())
        .where(EE.execution_id == execution_id)
        .group_by(EE.category)
    )
    return {c or "(none)": n for c, n in (await db.execute(stmt)).all()}


async def purge_expired_events(
    db: AsyncSession, *, batch_executions: int = 200,
) -> int:
    """超期执行的事件面清扫(保留 EXEC_EVENTS_RETENTION_DAYS 天;0=禁用)。

    由后台保留期维护任务周期调用(run_dispatcher.run_retention_maintenance;
    整体评审 2026-10-15 #2:此前全仓零调用点,结构化日志入库后表只增
    不减)。执行主行与台账单元行不受影响(它们是审计面)。

    分批:每批最多 ``batch_executions`` 个仍有事件残留的超期执行,删完
    即提交 —— 不对大表做一次性 DELETE 长事务(锁与 WAL 突增)。返回删除
    的事件行数(证据体行另计不返回)。
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete, exists

    from ..core.config import settings
    from ..models.execution import ExecutionEvent, ExecutionEventEvidence

    days = settings.EXEC_EVENTS_RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    has_residue = or_(
        exists().where(ExecutionEvent.execution_id == Execution.id),
        exists().where(ExecutionEventEvidence.execution_id == Execution.id),
    )
    total = 0
    while True:
        ids = list((await db.execute(
            select(Execution.id)
            .where(Execution.finished_at.is_not(None),
                   Execution.finished_at < cutoff, has_residue)
            .order_by(Execution.id)
            .limit(max(1, batch_executions))
        )).scalars().all())
        if not ids:
            return total
        result = await db.execute(
            delete(ExecutionEvent).where(ExecutionEvent.execution_id.in_(ids)))
        total += result.rowcount or 0
        await db.execute(
            delete(ExecutionEventEvidence).where(
                ExecutionEventEvidence.execution_id.in_(ids)))
        await db.commit()


# ── B4(2026-11-06 日志报告整理):执行报告(打开时从步骤表渲染)──────

_STEP_FAIL_STATES = ("failed", "error")


def _step_out(s) -> dict:
    """ExecutionStep → 报告步骤项(camelCase;断言 / 提取原样透出,已脱敏)。"""
    return {
        "rowSeq": s.row_seq, "unit": s.unit, "attempt": s.attempt,
        "stepId": s.step_id, "stepName": s.step_name,
        "description": s.description, "callSummary": s.call_summary,
        "status": s.status, "durationMs": round(float(s.duration_ms or 0.0), 2),
        "error": s.error,
        "assertionCount": s.assertion_count, "assertionPassed": s.assertion_passed,
        "assertions": list(s.assertions or []),
        "extracts": list(s.extracts or []),
        "hasEvidence": s.failure_evidence is not None,
    }


async def build_report(session: AsyncSession, ex: Execution) -> dict:
    """执行报告:概览 + 行/单元分组的步骤表 + 失败聚焦。

    数据源只有 execution_steps + 行台账(不读文本日志、不读事件表),
    所以事件 14 天清扫后报告不变;失败现场取步骤行自带的
    ``failure_evidence``(引擎侧已脱敏 + 截断)。

    分组:逐行链按 ``row_seq`` 对上 execution_rows.seq;graph 链
    (row_seq=-1)按 ``unit`` 成组。还没有行记录的步骤(运行中)归入
    以 unit 命名的临时组。
    """
    from ..models.execution import ExecutionStep
    from . import run_dispatcher

    steps = (await session.execute(
        select(ExecutionStep).where(ExecutionStep.execution_id == ex.id)
        .order_by(ExecutionStep.row_seq, ExecutionStep.unit,
                  ExecutionStep.attempt, ExecutionStep.event_seq,
                  ExecutionStep.id))).scalars().all()
    rows, _total = await run_dispatcher.execution_rows_page(
        session, ex.id, page=1, page_size=1000)

    def _row_key(r: dict) -> int:
        return int(r.get("seq") if r.get("seq") is not None else -1)

    groups: list[dict] = []
    by_seq: dict[int, dict] = {}
    for r in rows:
        g = {
            "key": f"row-{_row_key(r)}", "rowSeq": _row_key(r),
            "unit": r.get("unitId") or r.get("unit_id") or "",
            "datasetId": r.get("datasetId") or r.get("dataset_id"),
            "rowIndex": r.get("rowIndex", r.get("row_index", 0)),
            "rep": r.get("rep", 0),
            "status": r.get("status", ""),
            "caseDir": r.get("caseDir") or r.get("case_dir") or "",
            "serverSlot": r.get("serverSlot", r.get("server_slot")),
            "steps": [],
        }
        groups.append(g)
        by_seq[g["rowSeq"]] = g
    by_unit: dict[str, dict] = {}
    for s in steps:
        item = _step_out(s)
        g = by_seq.get(s.row_seq) if s.row_seq >= 0 else None
        if g is None:
            # graph 链 / 行未落库:按 unit 成组(行台账里同 unit 的行优先)
            g = by_unit.get(s.unit)
            if g is None:
                g = next((x for x in groups
                          if x["unit"] == s.unit and not x["steps"]
                          and s.row_seq < 0), None)
            if g is None:
                g = {"key": f"unit-{s.unit}", "rowSeq": s.row_seq,
                     "unit": s.unit, "datasetId": None, "rowIndex": 0,
                     "rep": 0, "status": "", "caseDir": "",
                     "serverSlot": None, "steps": []}
                groups.append(g)
            by_unit[s.unit] = g
        g["steps"].append(item)

    n_steps = len(steps)
    n_failed = sum(1 for s in steps if s.status in _STEP_FAIL_STATES)
    n_passed = sum(1 for s in steps if s.status == "passed")
    n_assert = sum(int(s.assertion_count or 0) for s in steps)
    n_assert_ok = sum(int(s.assertion_passed or 0) for s in steps)

    failure = None
    first = next((s for s in steps if s.status in _STEP_FAIL_STATES), None)
    if first is not None:
        failure = {
            **_step_out(first),
            "failedAssertions": [a for a in (first.assertions or [])
                                 if not a.get("passed")],
            "evidence": first.failure_evidence,
        }

    duration_ms = None
    if ex.started_at and ex.finished_at:
        duration_ms = round((ex.finished_at - ex.started_at).total_seconds() * 1000, 1)
    return {
        "execution": {
            "id": ex.id, "scenarioId": ex.scenario_id,
            "scenarioName": ex.scenario_name or "", "status": ex.status,
            "kind": ex.kind, "suiteId": ex.suite_id, "batchId": ex.batch_id,
            "startedAt": ex.started_at.isoformat() if ex.started_at else None,
            "finishedAt": ex.finished_at.isoformat() if ex.finished_at else None,
            "durationMs": duration_ms,
            "totalRuns": ex.total_runs, "passed": ex.passed,
            "failed": ex.failed, "skipped": ex.skipped,
        },
        "summary": {
            "steps": n_steps, "stepsPassed": n_passed, "stepsFailed": n_failed,
            "stepsOther": n_steps - n_passed - n_failed,
            "assertions": n_assert, "assertionsPassed": n_assert_ok,
        },
        "groups": groups,
        "failure": failure,
        # 无步骤行 = 早于步骤落库的执行或旧引擎:前端提示看工件 / 事件
        "hasStepData": n_steps > 0,
    }


async def batch_summary(session: AsyncSession, principal: Any,
                        batch_id: str) -> dict:
    """B5:批次汇总——成员执行清单 + 状态计数 + 时间跨度。

    成员逐个过执行可读判定(deps.can_view_execution),不可见的剔除,
    计数只算可见成员(不泄露批次里别人的执行)。
    """
    from ..core.deps import can_view_execution

    members = (await session.execute(
        select(Execution).where(Execution.batch_id == batch_id)
        .order_by(Execution.id))).scalars().all()
    visible = [ex for ex in members
               if await can_view_execution(principal, ex, session)]
    counts: dict[str, int] = {}
    for ex in visible:
        counts[ex.status] = counts.get(ex.status, 0) + 1
    starts = [ex.started_at for ex in visible if ex.started_at]
    ends = [ex.finished_at for ex in visible if ex.finished_at]
    active = any(ex.status in (STATUS_QUEUED, STATUS_RUNNING) for ex in visible)
    return {
        "batchId": batch_id,
        "total": len(visible),
        "counts": counts,
        "startedAt": min(starts).isoformat() if starts else None,
        "finishedAt": (max(ends).isoformat() if ends and not active else None),
        "active": active,
        "members": [{
            "id": ex.id, "scenarioId": ex.scenario_id,
            "scenarioName": ex.scenario_name or "", "status": ex.status,
            "passed": ex.passed, "failed": ex.failed, "totalRuns": ex.total_runs,
        } for ex in visible],
    }
