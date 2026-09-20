"""Execution 读侧投影 + 删除(V3,自 executions 路由收敛)。

exec_runs 子表已随存量数据清理退役(V1 兼容层),删除整单不再需要
子行清理;单-run 删除的计数器回退(MAX(0, col-1))也随端点一并移除。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Execution
from ..models.execution import STATUS_FAILED
from ..schemas.execution import ExecutionOut

# 连续失败计数回看的最大行数(执行设计 §3.2「连续第 N 次失败」信号)。
# 内部平台量级下,owner 全量 (id, scenario_id, status) 轻行扫描足够;
# 超出视为断层(信号照报,只是 N 以窗内为准)。
_STREAK_SCAN_LIMIT = 1000


def execution_out(e: Execution, *, consecutive_failures: int = 0) -> ExecutionOut:
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
        has_scenario_snapshot=e.scenario_snapshot is not None,
        batch_id=e.batch_id,
        consecutive_failures=consecutive_failures,
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
