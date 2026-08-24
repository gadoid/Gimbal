"""Execution 读侧投影 + 删除(V3,自 executions 路由收敛)。

exec_runs 子表已随存量数据清理退役(V1 兼容层),删除整单不再需要
子行清理;单-run 删除的计数器回退(MAX(0, col-1))也随端点一并移除。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Execution
from ..schemas.execution import ExecutionOut


def execution_out(e: Execution) -> ExecutionOut:
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
    )


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
