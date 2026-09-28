"""P2-03(C1)+P2-02(C2)集成:dispatch 执行中事件流式入库。

验收(Goals P2-02/P2-03):
  - 执行尚未结束时(dones 前),数据库已经可以查到该执行的 step 事件;
  - 事件条数与执行器 jsonl 的行数一致;
  - 执行结束后(run done)事件全量可查,call.exchange 证据体入独立表。
"""
from __future__ import annotations

import asyncio
import json

from httpx import AsyncClient

from tests.helpers import make_draft, register_and_login, wait_until

STEPS = [{
    "call": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]

# 模拟执行器 jsonl 事件流(信封标签齐全 —— P1-02 之后引擎的真实形态)
def _engine_events() -> list[dict]:
    return [
        {"event_type": "run.meta", "seq": 1,
         "meta": {"trigger": "platform"}},
        {"event_type": "scenario.start", "seq": 2,
         "scenario_id": "sc-ev", "scenario_name": "n", "step_count": 1,
         "unit": "u", "attempt": "1.1", "module": "fin"},
        {"event_type": "step.start", "seq": 3, "step_id": "step-000",
         "step_name": "step-000", "scenario_id": "sc-ev",
         "unit": "u", "attempt": "1.1", "step": "step-000",
         "module": "fin", "service": "fin-service", "protocol": "http"},
        {"event_type": "call.exchange", "seq": 4, "step_id": "step-000",
         "protocol": "http", "status": "passed", "duration_ms": 42.0,
         "unit": "u", "attempt": "1.1", "step": "step-000",
         "service": "fin-service", "module": "fin",
         "result": {"protocol": "http",
                    "request": {"method": "POST", "url": "/api/x"},
                    "response": {"status": 200, "body": {"echo": "hi"}}}},
        {"event_type": "step.end", "seq": 5, "step_id": "step-000",
         "status": "passed", "duration_ms": 42.0, "scenario_id": "sc-ev",
         "unit": "u", "attempt": "1.1", "step": "step-000", "module": "fin"},
        {"event_type": "scenario.end", "seq": 6, "scenario_id": "sc-ev",
         "status": "passed", "step_count": 1, "unit": "u", "attempt": "1.1"},
        {"event_type": "run.finished", "seq": 7, "exit_code": 0,
         "total": 1, "passed": 1, "failed": 0, "skipped": 0,
         "details": [{"scenario_id": "sc-ev", "status": "passed"}]},
    ]


async def test_events_ingested_during_execution(
    client: AsyncClient, monkeypatch
) -> None:
    headers = await register_and_login(client)
    draft = make_draft("sc-ev", steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"},
        "vars": {"customer_id": "261"},
    }
    await client.post("/api/scenarios", headers=headers, json=draft)

    events = _engine_events()
    launched = asyncio.Event()
    release = asyncio.Event()

    async def _streaming_launch(case_path, *, step_to=None, report_dir=None,
                                cwd=None, timeout=None, engine_log_path=None,
                                on_event=None, on_log=None):
        # 模拟执行器:逐行回调事件流,然后挂起等测试放行
        for ev in events:
            if on_event is not None:
                on_event(dict(ev))
            await asyncio.sleep(0)   # 让出循环,触发阈值冲刷路径
        launched.set()
        await release.wait()
        from tests.helpers import launch_ok
        return launch_ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_launcher as gl, plate_client as pc
    monkeypatch.setattr(gl, "launch", _streaming_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-ev", "dataSetIds": [],
    })
    assert r.status_code == 201, r.text

    await wait_until(launched.is_set)

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models.execution import Execution
    from app.models.execution import ExecutionEventEvidence
    from app.services import execution_store

    # ① 执行尚未结束(done 之前):事件已经可查(launcher 仍在挂起中;
    # 入库经 0.5s 周期冲刷 —— 轮询等待,但执行必须仍在 running 窗口)
    async def _mid_events() -> list:
        async with db_module.SessionLocal() as s:
            ex = (await s.execute(
                sa.select(Execution).order_by(Execution.id.desc()).limit(1))
            ).scalar_one()
            if ex.status != "running":
                return []
            return await execution_store.query_events(s, ex.id)

    mid: list = []
    for _ in range(100):
        mid = await _mid_events()
        if len(mid) == 7:
            break
        await asyncio.sleep(0.05)
    assert [e.seq for e in mid] == [1, 2, 3, 4, 5, 6, 7]
    # call.exchange 证据体已拆表 + 执行 id 供收口后对拍
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(
            sa.select(Execution).order_by(Execution.id.desc()).limit(1))
        ).scalar_one()
        evi_row = (await s.execute(
            sa.select(ExecutionEventEvidence).where(
                ExecutionEventEvidence.seq == 4))
        ).scalar_one()
        assert evi_row.evidence["response"]["status"] == 200
        eid = ex.id

    release.set()   # 放行收口

    # ② done 后:全量仍在,条数与 jsonl 行数一致(7 事件)
    for _ in range(100):
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, eid)
            if ex.status == "done":
                break
        await asyncio.sleep(0.05)
    assert ex.status == "done"
    async with db_module.SessionLocal() as s:
        final_events = await execution_store.query_events(s, eid)
        assert len(final_events) == len(events)
        assert final_events[-1].event_type == "run.finished"
        # 标签列可筛(P2-07 日志分析页的读面)
        hits = await execution_store.query_events(s, eid, unit="u",
                                                  event_type="step.end")
        assert [h.seq for h in hits] == [5]
