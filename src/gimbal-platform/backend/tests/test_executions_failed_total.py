"""列表信封 failedTotal(2026-10-21)。

筛选行「共 N 条 · 失败 M 条」口径修复:N 是服务端全量,M 此前由前端数
当前页 —— 分页后两者打架(总 4 失败 2、首页只 1 条失败单时显示「失败
1 条」)。本批由服务端按同一筛选集合给全口径 failedTotal。
"""
from __future__ import annotations

from app.core import db as db_module
from tests.helpers import register_and_login


async def _seed(owner_id: int, statuses: list[str]) -> None:
    from app.models.execution import Execution

    async with db_module.SessionLocal() as s:
        for i, st in enumerate(statuses):
            s.add(Execution(
                scenario_id=f"sc-ft-{i}", owner_id=owner_id, status=st,
                total_runs=0, passed=0, failed=0, config_json={}))
        await s.commit()


async def test_failed_total_full_scope(client):
    h = await register_and_login(client, "ftuser", "pw123456")
    await _seed(1, ["failed", "failed", "done", "running"])

    # 第 1 页只装 2 条(其中 1 条失败)—— 失败数必须仍是全量 2,
    # 不跟页内可见集合走
    r = await client.get("/api/executions", headers=h,
                         params={"page": 1, "page_size": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 4
    assert body["failedTotal"] == 2

    # 状态筛到 failed:同一口径下 N == M
    r = await client.get("/api/executions", headers=h,
                         params={"status": "failed"})
    body = r.json()
    assert body["total"] == body["failedTotal"] == 2

    # 状态筛到 done:筛后集合里没有失败单
    r = await client.get("/api/executions", headers=h,
                         params={"status": "done"})
    body = r.json()
    assert body["total"] == 1
    assert body["failedTotal"] == 0
