"""C5(P3-05)graph 编排执行链测试。

覆盖:GraphSpec 校验、materialize_graph(场景解析/convert/物化/乘法与
横切面透传)、_fanout_graph 端到端(mock launch 流式事件 → 台账投影)。
"""
from __future__ import annotations

import asyncio
import json

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.execution import Execution, ExecutionRow
from tests.helpers import make_draft, register_and_login

STEPS = [{
    "call": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]


async def _mk_scenario(client, headers, sid="sc-g") -> None:
    draft = make_draft(sid, steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"},
        "vars": {"customer_id": "261"},
    }
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code in (200, 201), r.text


class TestGraphSpecValidation:

    async def test_rejects_unknown_mode(self, client):
        headers = await register_and_login(client)
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-x",
            "graph": {"mode": "bogus",
                      "units": [{"ref": "a", "scenarioId": "sc-x"}]},
        })
        assert r.status_code == 422


class TestGraphRunEndToEnd:

    async def test_graph_run_projects_units(self, client, monkeypatch):
        headers = await register_and_login(client)
        await _mk_scenario(client, headers, "sc-a")
        await _mk_scenario(client, headers, "sc-b")

        launched: list[dict] = []

        async def _launch(case_path, *, step_to=None, report_dir=None,
                          cwd=None, timeout=None, engine_log_path=None,
                          on_event=None, on_log=None, n_runs=1, retry=0):
            graph = json.loads(
                __import__("pathlib").Path(case_path).read_text(encoding="utf-8"))
            launched.append(graph)
            for ev in [
                {"event_type": "scenario.start", "seq": 2,
                 "scenario_id": "sc-a", "scenario_name": "a", "step_count": 1,
                 "unit": "a", "attempt": "1.1"},
                {"event_type": "scenario.end", "seq": 3,
                 "scenario_id": "sc-a", "status": "passed", "step_count": 1,
                 "unit": "a", "attempt": "1.1"},
                {"event_type": "run.finished", "seq": 4, "exit_code": 0,
                 "total": 2, "passed": 2, "failed": 0, "skipped": 0,
                 "attempts": 3, "unit": "a"},
            ]:
                if on_event is not None:
                    on_event(dict(ev))
                await asyncio.sleep(0)
            import dataclasses
            from tests.helpers import launch_ok
            return launch_ok()

        async def _fake_convert(scenario):
            return {"consumer": "platform", "converted": dict(scenario)}

        from app.services import gimbal_launcher as gl, plate_client as pc
        monkeypatch.setattr(gl, "launch", _launch)
        monkeypatch.setattr(pc, "convert", _fake_convert)

        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-a",
            "graph": {
                "mode": "aggregate",
                "units": [
                    {"ref": "a", "scenarioId": "sc-a", "nRuns": 3},
                    {"ref": "b", "scenarioId": "sc-b"},
                ],
                "gates": [{"metric": "pass_rate", "op": "gte", "value": 1.0}],
            },
        })
        assert r.status_code == 201, r.text
        exec_id = r.json()["executionId"]

        ex = None
        for _ in range(400):
            async with db_module.SessionLocal() as s:
                ex = await s.get(Execution, exec_id)
            if ex and ex.status in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        assert ex is not None and ex.status in ("done", "failed"), ex and ex.status

        # 下发的 SuiteGraph:单元 ref/乘法/gates 透传
        assert len(launched) == 1
        graph = launched[0]
        assert graph["kind"] == "graph" and graph["mode"] == "aggregate"
        by_ref = {u["ref"]: u for u in graph["units"]}
        assert by_ref["a"]["policy_kwargs"]["n_runs"] == 3
        assert graph["gates"] == [{"metric": "pass_rate", "op": "gte",
                                   "value": 1.0}]

        # 台账:graph 行(unit/attempts 投影)
        async with db_module.SessionLocal() as s:
            row = (await s.execute(sa.select(ExecutionRow).where(
                ExecutionRow.execution_id == exec_id))).scalar_one()
            assert row.unit_id == "a" and row.attempts == 3
            assert row.status == "passed"
