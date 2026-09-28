"""Execution 读侧投影 + 删除(V3,自 executions 路由收敛)。

exec_runs 子表已随存量数据清理退役(V1 兼容层),删除整单不再需要
子行清理;单-run 删除的计数器回退(MAX(0, col-1))也随端点一并移除。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Execution, ExecutionSnapshot
from ..models.composer_scenario import ComposerScenario
from ..models.execution import STATUS_FAILED
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
    from ..routers._ownership import can_read_scenario

    ids = sorted({s for s in scenario_ids if s})
    if not ids:
        return {}
    rows = (await db.execute(
        select(ComposerScenario.scenario_id, ComposerScenario.name,
               ComposerScenario.owner_id, ComposerScenario.visibility)
        .where(ComposerScenario.scenario_id.in_(ids))
    )).all()
    return {
        sid: (str(name or "") if can_read_scenario(
                  user, owner_id=owner_id, visibility=vis or "private")
              else "", True)
        for sid, name, owner_id, vis in rows
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
    )


# 列表 UI 的非敏感窄投影键(ExecutionsList 行内方案徽标/次数/并发/停步/
# 认证快失败信号;useScenarioRuns 的趋势过滤读 schemeId 做方案溯源)。
# 凭证引用面(injectedAuths/serviceBindings)绝不进列表。
_CONFIG_SUMMARY_KEYS = (
    "schemeId", "schemeName", "nRuns", "parallel", "stepTo", "authFailFast",
)


def execution_list_item(
    e: Execution,
    *,
    consecutive_failures: int = 0,
    has_scenario_snapshot: bool = False,
    scenario_display_name: str = "",
    scenario_deleted: bool = False,
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
        config_summary={k: cfg[k] for k in _CONFIG_SUMMARY_KEYS if k in cfg},
        has_scenario_snapshot=has_scenario_snapshot,
        batch_id=e.batch_id,
        consecutive_failures=consecutive_failures,
        scenario_display_name=scenario_display_name,
        scenario_deleted=scenario_deleted,
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
    """双方言 insert(PG/SQLite;照 notifications.py 的自律模式)。"""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    return pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert


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
    for d in events:
        et = str(d.get("event_type") or "")
        payload = dict(d)
        message = None
        evidence = None
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
    from datetime import datetime
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
    limit: int = 500,
) -> list[ExecutionEvent]:
    """事件/日志组合筛选(P2-07 日志分析页与 SSE 续传共用读面)。

    标签精确匹配 + message 全文 search(ILIKE);``after_seq`` 支撑
    Last-Event-ID 续传语义;命中 (execution_id, seq) 索引。
    """
    from ..models.execution import ExecutionEvent as EE

    stmt = select(EE).where(EE.execution_id == execution_id)
    if after_seq is not None:
        stmt = stmt.where(EE.seq > after_seq)
    if kind is not None:
        stmt = stmt.where(EE.kind == kind)
    if level is not None:
        stmt = stmt.where(EE.level == level)
    if level_min is not None:
        # 最低级别过滤(日志分析页「warning 以上」口径):按严重度序比较
        order = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING",
                 "ERROR", "CRITICAL")
        rank = order.index(level_min.upper()) if level_min.upper() in order else 0
        stmt = stmt.where(EE.level.in_(order[rank:]))
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
    stmt = stmt.order_by(EE.seq.asc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


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


async def purge_expired_events(db: AsyncSession) -> int:
    """超期执行的事件面清扫(保留 EXEC_EVENTS_RETENTION_DAYS 天;0=禁用)。

    与 case 案卷清扫同节奏由 dispatch 收口/维护入口调用;执行主行与
    台账单元行不受影响(它们是审计面)。
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete

    from ..core.config import settings
    from ..models.execution import ExecutionEvent, ExecutionEventEvidence

    days = settings.EXEC_EVENTS_RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    subq = (
        select(Execution.id)
        .where(Execution.finished_at.is_not(None),
               Execution.finished_at < cutoff)
    )
    ev_del = delete(ExecutionEvent).where(ExecutionEvent.execution_id.in_(subq))
    result = await db.execute(ev_del)
    n = result.rowcount or 0
    await db.execute(
        delete(ExecutionEventEvidence).where(
            ExecutionEventEvidence.execution_id.in_(subq)))
    return n
