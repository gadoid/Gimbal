"""P7:总量上限拒单 + launch 全局并发闸。"""
import asyncio

from tests.helpers import make_draft, register_and_login


# ─── 测试基座(同 test_run_cancel:轮询终态 + mock convert)──
async def _get_execution(execution_id: int):
    from sqlalchemy import select

    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as session:
        return (
            await session.execute(
                select(Execution).where(Execution.id == execution_id)
            )
        ).scalar_one()


async def _wait_terminal(execution_id: int, timeout_s: float = 5.0):
    """轮询 Execution 至终态(done/failed/canceled)后返回该行。"""
    for _ in range(int(timeout_s / 0.05)):
        row = await _get_execution(execution_id)
        if row.status in ("done", "failed", "canceled"):
            return row
        await asyncio.sleep(0.05)
    raise TimeoutError(f"execution {execution_id} not terminal in {timeout_s}s")


async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}


async def test_dispatch_rejects_over_cap(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_RUNS_PER_EXECUTION", 3)
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cap", vars_map={"customer_id": "1"}))
    r = await client.post("/api/scenarios/sc-cap/data-sets", headers=headers,
                          json={"name": "ds", "rows": [
                              {"customer_id": "1"}, {"customer_id": "2"},
                              {"customer_id": "3"}, {"customer_id": "4"}]})
    ds_id = r.json()["datasetId"]

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cap", "dataSetIds": [ds_id],
        "nRuns": 2,                      # P2-05:nRuns 不进总量闸;4 行 > 3 触发
    })
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "too_many_runs"


async def test_worker_serializes_executions_across_queue(client, monkeypatch):
    """C11(P3-01):全局 launch 信号量已退役——跨 execution 并发上限改由
    队列 worker 数界定(EXEC_WORKERS=1 → 串行:两 execution 的 launch
    时间线互不重叠;行级 parallel 仍由行 sem 承担)。"""
    from app.services import gimbal_launcher as gl, plate_client as pc,         execution_queue as eq

    eq.reset_worker_state()

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-sem"))
    # convert 必须一起断流:否则测试环境无 plate,行全部 plate_unavailable,
    # launch 根本不被调用,并发断言空转通过。
    monkeypatch.setattr(pc, "convert", _fake_convert)
    state = {"live": 0, "peak": 0}

    async def launch(*a, **k):
        state["live"] += 1
        state["peak"] = max(state["peak"], state["live"])
        await asyncio.sleep(0.02)
        state["live"] -= 1
        return gl.LaunchResult(launch_status="ok", exit_code=0, total=1, passed=1)

    monkeypatch.setattr(gl, "launch", launch)

    eids = []
    for _ in range(2):                   # 两个 execution,各 1 行 × nRuns=4
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-sem", "dataSetIds": [],
            "nRuns": 4, "parallel": 4,
        })
        assert r.status_code == 201, r.text
        eids.append(r.json()["executionId"])

    for eid in eids:
        await _wait_terminal(eid)
    # 单 worker 串行:任一时刻至多一个 launch 在飞(原全局闸的等价收敛,
    # 上界从 MAX_CONCURRENT_LAUNCHES 换成 worker 数)
    assert state["peak"] == 1
