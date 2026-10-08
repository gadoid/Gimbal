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


class TestGraphUnitAuthz:
    """请求侧 unit 属主闸(《Suite成员层、引用分享与浏览镜头-设计方案》
    §8.2 必修缺口)。

    顶层场景闸此前已存在;units / before / after 括号场景此前只在
    worker 侧物化时查存在性、无归属检查——本组测试钉住「编排不能
    绕过属主闸」(P0 阶段 = 属主 ∨ admin,与顶层闸同款契约)。
    """

    async def test_non_owner_unit_rejected(self, client):
        await register_and_login(client, "gauth0", "gauth0pass123")  # bootstrap
        alice = await register_and_login(client, "gauth1", "gauth1pass123")
        bob = await register_and_login(client, "gauth2", "gauth2pass123")
        await _mk_scenario(client, alice, "sc-g-alice")
        await _mk_scenario(client, alice, "sc-g-alice2")
        await _mk_scenario(client, bob, "sc-g-bob")
        # 顶层是 bob 自己的(过顶层闸);unit 与 before 括号引 alice 的
        # 私有场景 → 403 not_owner(编排不再是绕过属主闸的通道)
        r = await client.post("/api/runs", headers=bob, json={
            "scenarioId": "sc-g-bob",
            "graph": {
                "mode": "aggregate",
                "units": [
                    {"ref": "mine", "scenarioId": "sc-g-bob"},
                    {"ref": "stolen", "scenarioId": "sc-g-alice"},
                ],
                "before": [{"ref": "pre", "scenarioId": "sc-g-alice2"}],
            },
        })
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "not_owner"

    async def test_nonexistent_unit_404(self, client):
        h = await register_and_login(client, "gauth3", "gauth3pass123")
        await _mk_scenario(client, h, "sc-g-own3")
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-g-own3",
            "graph": {"units": [{"ref": "a", "scenarioId": "sc-g-ghost"}]},
        })
        assert r.status_code == 404, r.text
        assert r.json()["detail"]["code"] == "scenario_not_found"

    async def test_admin_gate_open_for_units(self, client):
        admin = await register_and_login(client, "gauth4", "gauth4pass123")
        member = await register_and_login(client, "gauth5", "gauth5pass123")
        await _mk_scenario(client, member, "sc-g-mem5")
        await _mk_scenario(client, admin, "sc-g-adm4")
        # admin 对 unit 场景有矩阵授权(全量可见可管可跑)→ 过闸
        r = await client.post("/api/runs", headers=admin, json={
            "scenarioId": "sc-g-adm4",
            "graph": {"units": [
                {"ref": "a", "scenarioId": "sc-g-adm4"},
                {"ref": "b", "scenarioId": "sc-g-mem5"},
            ]},
        })
        assert r.status_code == 201, r.text
