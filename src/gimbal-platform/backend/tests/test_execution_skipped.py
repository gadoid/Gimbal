"""S5(P0):run.finished 的 skipped 计数落库 + API 暴露。

引擎 `run.finished` 携带 skipped(blocked/skip 口径);此前只留在
per-case result.json 工件,executions 表无列。本批:模型列 + 计数器
delta + 响应字段。
"""
from __future__ import annotations

from app.core import db as db_module
from tests.helpers import register_and_login


async def _seed_exec(owner_id: int) -> int:
    from app.models.execution import Execution

    async with db_module.SessionLocal() as s:
        ex = Execution(scenario_id="sc-skip", owner_id=owner_id, status="done",
                       total_runs=3, passed=2, failed=1, config_json={})
        s.add(ex)
        await s.commit()
        return ex.id


async def test_bump_counters_records_skipped(client):
    """_bump_counters 的 skipped delta 落库并可累加。"""
    from sqlalchemy import select

    from app.models.execution import Execution
    from app.services.run_dispatcher import _bump_counters

    await register_and_login(client, "skip1", "pw123456")
    eid = await _seed_exec(1)

    await _bump_counters(db_module.SessionLocal, eid, passed=1, failed=0, skipped=2)
    await _bump_counters(db_module.SessionLocal, eid, passed=0, failed=1, skipped=1)

    async with db_module.SessionLocal() as s:
        ex = (await s.execute(
            select(Execution).where(Execution.id == eid))).scalar_one()
    assert ex.skipped == 3          # delta 累加,非覆盖
    assert (ex.passed, ex.failed) == (3, 2)


async def test_execution_detail_and_list_expose_skipped(client):
    """读侧:详情与列表响应均携带 skipped 字段(缺省 0)。"""
    h = await register_and_login(client, "skip2", "pw123456")
    eid = await _seed_exec(1)

    r = await client.get(f"/api/executions/{eid}", headers=h)
    assert r.status_code == 200
    assert r.json()["skipped"] == 0

    r = await client.get("/api/executions", headers=h)
    assert r.status_code == 200
    item = next(it for it in r.json()["items"] if it["id"] == eid)
    assert item["skipped"] == 0
