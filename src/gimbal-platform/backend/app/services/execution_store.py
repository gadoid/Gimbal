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
