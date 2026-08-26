"""P4 协作式取消:行边界生效、canceled 终态、终态单 409。
running 状态:fanout 行分发前置 running(+started_at),终态覆盖。"""
import asyncio
import json

from tests.helpers import (
    launch_ok as _ok,
    make_draft,
    register_and_login,
    test_env,
    wait_until,
)


# ─── 测试基座(同 test_run_log_integrity / test_run_case_retention)──
async def _seed_execution(
    owner_id: int, *, status: str, total_runs: int = 1,
    passed: int = 0, failed: int = 0,
) -> int:
    """Insert one Execution row; return its id."""
    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as session:
        ex = Execution(
            scenario_id="sc-cancel",
            owner_id=owner_id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
            config_json={},
        )
        session.add(ex)
        await session.commit()
        return ex.id


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


async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None):
    return _ok()


async def _fake_convert(scenario):
    return {"consumer": "platform", "converted": dict(scenario)}


def _jsonl_records(run_dispatcher) -> list:
    """读当日调度日志(JSONL)的全部记录。"""
    path = run_dispatcher._jsonl_path()
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def test_cancel_skips_remaining_rows(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cancel", vars_map={"customer_id": "1"}))
    r = await client.post("/api/scenarios/sc-cancel/data-sets", headers=headers,
                          json={"name": "ds", "rows": [
                              {"customer_id": str(i)} for i in range(6)]})
    ds_id = r.json()["datasetId"]

    done = {"n": 0}

    async def _slow_launch(*a, **k):
        await asyncio.sleep(0.02)
        done["n"] += 1
        return _ok()

    monkeypatch.setattr(gl, "launch", _slow_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cancel", "dataSetIds": [ds_id], "env": test_env(),
        "parallel": 1,
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    await wait_until(lambda: done["n"] >= 1)     # 至少一行落地后取消
    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text

    row = await _wait_terminal(eid)
    assert row.status == "canceled"
    assert row.passed + row.failed < row.total_runs   # 有行被跳过

    records = _jsonl_records(run_dispatcher)
    assert any(rec.get("status") == "canceled" for rec in records)


async def test_cancel_terminal_conflicts(client, monkeypatch):
    from app.services import gimbal_launcher as gl, plate_client as pc

    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-cancel-done"))
    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-cancel-done", "dataSetIds": [], "env": test_env(),
    })
    eid = r.json()["executionId"]
    await _wait_terminal(eid)

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 409, cr.text
    assert cr.json()["detail"]["code"] == "not_cancelable"


async def test_cancel_zombie_finalizes_immediately(client):
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    eid = await _seed_execution(me["user"]["id"], status="queued")  # MeOut 信封

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["status"] == "canceled"


async def test_cancel_running_zombie_finalizes_immediately(client):
    """running 单可取消:无 live fanout 的 running = 重启僵尸,inline 终态化。

    (cancel 闸 = queued|running;done/failed/canceled 仍 409。)
    """
    from app.services import run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    me = (await client.get("/api/auth/me", headers=headers)).json()
    eid = await _seed_execution(me["user"]["id"], status="running")

    cr = await client.post(f"/api/executions/{eid}/cancel", headers=headers)
    assert cr.status_code == 200, cr.text
    assert cr.json()["status"] == "canceled"


async def test_fanout_marks_running(client, monkeypatch):
    """认证解析通过、行分发开始前 → status=running + started_at 落定;
    终态(done)覆盖 running。"""
    import asyncio

    from app.services import gimbal_launcher as gl, plate_client as pc, run_dispatcher

    run_dispatcher.reset_cancel_state()
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers,
                      json=make_draft("sc-running"))

    gate = asyncio.Event()
    entered = {"n": 0}

    async def _gated_launch(*a, **k):
        entered["n"] += 1         # launch 被调 ⇒ _mark_running 已提交
        await gate.wait()          # 卡住首行,让 running 窗口可观测
        return _ok()

    monkeypatch.setattr(gl, "launch", _gated_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-running", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    await wait_until(lambda: entered["n"] >= 1)
    row = await _get_execution(eid)
    assert row.status == "running"
    assert row.started_at is not None

    gate.set()                    # 放行 → 自然跑完
    row = await _wait_terminal(eid)
    assert row.status == "done"
