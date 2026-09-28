"""P2-04/P2-05 验收:台账从事件投影 + 乘法下沉。

Goals 验收:
  - P2-05:nRuns=3 时平台只启动一个执行器进程,台账 attempts=3;
  - P2-04:行状态由 scenario.end 事件投影(非 exit code 推导);
    投影出的状态与 run.finished 计数逐字段一致。
"""
from __future__ import annotations

import asyncio
import json

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.execution import Execution, ExecutionRow
from tests.helpers import make_draft, register_and_login, wait_until

STEPS = [{
    "call": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]


def _row_events(unit: str, *, status: str = "passed", attempts: int = 3) -> list[dict]:
    """单单元 × n_runs=3 的执行器事件流(末线 run.finished 带 attempts 单列)。"""
    return [
        {"event_type": "run.meta", "seq": 1, "meta": {}},
        {"event_type": "scenario.start", "seq": 2, "scenario_id": "sc-p",
         "scenario_name": "n", "step_count": 1, "unit": unit, "attempt": "1.1"},
        {"event_type": "scenario.end", "seq": 3, "scenario_id": "sc-p",
         "status": status, "step_count": 1, "unit": unit, "attempt": "3.1"},
        {"event_type": "run.finished", "seq": 4, "exit_code": 0
         if status == "passed" else 1,
         "total": 1, "passed": 1 if status == "passed" else 0,
         "failed": 0 if status == "passed" else 1, "skipped": 0,
         "attempts": attempts, "unit": unit,
         "details": [{"scenario_id": "sc-p", "status": status}]},
    ]


async def _dispatch_and_project(client, monkeypatch, *, n_runs=3,
                                events=None, exit_code=0) -> Execution:
    headers = await register_and_login(client)
    draft = make_draft("sc-p", steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"}, "vars": {"customer_id": "261"}}
    await client.post("/api/scenarios", headers=headers, json=draft)

    spawn_kwargs: list[dict] = []
    events = events if events is not None else _row_events("u")

    async def _launch(case_path, *, step_to=None, report_dir=None, cwd=None,
                      timeout=None, engine_log_path=None,
                      on_event=None, on_log=None, n_runs=1, retry=0):
        spawn_kwargs.append({"n_runs": n_runs, "retry": retry})
        for ev in events:
            if on_event is not None:
                on_event(dict(ev))
            await asyncio.sleep(0)
        import dataclasses
        from tests.helpers import launch_ok
        r = launch_ok()
        if exit_code:
            r = dataclasses.replace(r, exit_code=exit_code)
        return r

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-p", "dataSetIds": [], "nRuns": n_runs,
    })
    assert r.status_code == 201, r.text

    # 每次迭代开新 session(identity map 缓存会读到 stale 的 queued)
    ex = None
    for _ in range(400):
        async with db_module.SessionLocal() as s:
            ex = (await s.execute(
                sa.select(Execution).order_by(Execution.id.desc()).limit(1))
            ).scalar_one()
        if ex.status in ("done", "failed"):
            break
        await asyncio.sleep(0.05)
    assert ex.status in ("done", "failed"), ex.status
    assert len(spawn_kwargs) == 1, spawn_kwargs      # P2-05:一个执行器进程
    assert spawn_kwargs[0]["n_runs"] == n_runs        # 乘法经 --n-runs 下沉
    return ex


async def test_multiplication_sinkdown_and_projection(
    client: AsyncClient, monkeypatch
) -> None:
    ex = await _dispatch_and_project(client, monkeypatch, n_runs=3)
    async with db_module.SessionLocal() as s:
        row = (await s.execute(
            sa.select(ExecutionRow).where(ExecutionRow.execution_id == ex.id))
        ).scalar_one()
        # P2-05:单元口径 + 展开计数入 attempts 列
        assert ex.total_runs == 1
        assert row.attempts == 3
        assert row.unit_id == "u" and row.branch == "main"
        # P2-04:状态由 scenario.end 事件投影(与 run.finished 一致)
        assert row.status == "passed"


async def test_projection_authoritative_over_exit_code(
    client: AsyncClient, monkeypatch
) -> None:
    """事件投影优先:scenario.end=passed 时 exit=1(如 after 失败类边缘)
    不改写行状态 —— 台账由事件决定(P2-04 验收口径)。"""
    ex = await _dispatch_and_project(
        client, monkeypatch, n_runs=1,
        events=_row_events("u", status="passed", attempts=1),
        exit_code=1)
    async with db_module.SessionLocal() as s:
        row = (await s.execute(
            sa.select(ExecutionRow).where(ExecutionRow.execution_id == ex.id))
        ).scalar_one()
        assert row.status == "passed"


async def test_failed_projection(
    client: AsyncClient, monkeypatch
) -> None:
    ex = await _dispatch_and_project(
        client, monkeypatch, n_runs=2,
        events=_row_events("u", status="failed", attempts=2))
    # 行失败投影进计数;执行级终态按平台口径(failed 行 → execution failed)
    assert ex.failed == 1 and ex.passed == 0
    async with db_module.SessionLocal() as s:
        row = (await s.execute(
            sa.select(ExecutionRow).where(ExecutionRow.execution_id == ex.id))
        ).scalar_one()
        assert row.status == "failed" and row.attempts == 2
