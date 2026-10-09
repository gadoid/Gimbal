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

        # patch 打在调用方模块(execute_graph 用 from-import 绑定,
        # 只 patch gimbal_launcher.launch 顺序敏感、时灵时不灵)
        from app.services import graph_dispatch as gd, plate_client as pc
        monkeypatch.setattr(gd, "launch", _launch)
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

        # 台账(重构方案第 3 处):seq=0 图行(总状态/attempts)+
        # seq=1.. 逐单元行(a 有事件 → passed;b 无事件 → blocked)
        async with db_module.SessionLocal() as s:
            rows = (await s.execute(sa.select(ExecutionRow).where(
                ExecutionRow.execution_id == exec_id)
                .order_by(ExecutionRow.seq))).scalars().all()
        assert [(r.seq, r.unit_id, r.status) for r in rows] == [
            (0, "graph", "passed"), (1, "a", "passed"), (2, "b", "blocked")]
        assert rows[0].attempts == 3

    async def test_total_status_follows_exit_code(self, client, monkeypatch):
        """总状态取 run.finished 的 exit_code(第 3 处修正):主体失败、
        后置 teardown 通过时不得被「最后一个 scenario.end」覆盖成通过;
        计数按单元累累加。"""
        await register_and_login(client, "ts_boot", "ts_bootpass123")
        h = await register_and_login(client, "ts_owner", "ts_ownerpass123")
        await _mk_scenario(client, h, "sc-ts-a")
        await _mk_scenario(client, h, "sc-ts-b")

        async def _launch(case_path, *, on_event=None, **_kw):
            for ev in [
                {"event_type": "scenario.end", "seq": 2, "unit": "main",
                 "scenario_id": "sc-ts-a", "status": "failed",
                 "timestamp": "2026-10-09T07:00:00+00:00"},
                # 后置通过 —— 旧口径会把它当作总状态
                {"event_type": "scenario.end", "seq": 3, "unit": "teardown",
                 "scenario_id": "sc-ts-b", "status": "passed",
                 "timestamp": "2026-10-09T07:00:01+00:00"},
                {"event_type": "run.finished", "seq": 4, "exit_code": 1,
                 "attempts": 2},
            ]:
                if on_event is not None:
                    on_event(dict(ev))
                await asyncio.sleep(0)
            from app.services.gimbal_launcher import LaunchResult
            return LaunchResult(launch_status="ok", exit_code=1,
                                total=2, passed=1, failed=1)

        from app.services import graph_dispatch as gd
        monkeypatch.setattr(gd, "launch", _launch)

        async def _fake_convert(scenario):
            return {"consumer": "platform", "converted": dict(scenario)}
        from app.services import plate_client as pc
        monkeypatch.setattr(pc, "convert", _fake_convert)

        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-ts-a",
            "graph": {"mode": "compose",
                      "units": [{"ref": "main", "scenarioId": "sc-ts-a"}],
                      "after": [{"ref": "teardown", "scenarioId": "sc-ts-b"}]},
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
        assert ex is not None and ex.status == "failed", ex and ex.status
        # 计数按单元累加:主体失败 1、后置通过 1(不再整图计 1/0)
        assert ex.failed == 1 and ex.passed == 1
        async with db_module.SessionLocal() as s:
            rows = (await s.execute(sa.select(ExecutionRow).where(
                ExecutionRow.execution_id == exec_id)
                .order_by(ExecutionRow.seq))).scalars().all()
        assert [(r2.unit_id, r2.status) for r2 in rows] == [
            ("graph", "failed"), ("main", "failed"),
            ("teardown", "passed")]


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


class TestGraphCompositionInline:
    """重构方案 B1:单行内联(schemeId/row)、map / control 透传。

    约束 5:编排单元只跑一行 —— schemeId(空=默认方案)+ row
    {datasetId, rowIndex} 选定;方案的服务绑定随行合入。
    第 6 处:map 改名透传到 UnitDecl.map;第 2 处:control 只落
    only / to_node(执行器 snake_case),fromNode 拼装侧拒绝。
    """

    STEPS_SVC = [{
        "kind": "step", "description": "下单",
        "call": {"service": "fin.order", "method": "POST", "path": "/x"},
        "request": {"kind": "request", "body": {"amount": 1}},
        "strategy": [],
    }]

    async def _mk_svc_scenario(self, client, h, sid) -> None:
        draft = make_draft(sid, steps=self.STEPS_SVC)
        draft["definition"]["config"] = {
            "timePolicy": {"kind": "record"},
            "vars": {"customer_id": "261"},
        }
        r = await client.post("/api/scenarios", headers=h, json=draft)
        assert r.status_code in (200, 201), r.text

    async def _fake_convert_patch(self, monkeypatch):
        from app.services import plate_client as pc

        async def _fake_convert(scenario):
            return {"consumer": "platform", "converted": dict(scenario)}
        monkeypatch.setattr(pc, "convert", _fake_convert)

    async def test_row_and_scheme_inline(self, client, monkeypatch):
        await register_and_login(client, "gi_boot", "gi_bootpass123")
        h = await register_and_login(client, "gi_owner", "gi_ownerpass123")
        await self._mk_svc_scenario(client, h, "sc-gi-a")
        r = await client.post("/api/scenarios/sc-gi-a/data-sets", headers=h,
                              json={"datasetId": "ds-gi-rows", "name": "行集",
                                    "rows": [{"customer_id": "111"},
                                             {"customer_id": "222"}]})
        assert r.status_code == 201, r.text
        ds_id = r.json()["datasetId"]
        r = await client.post("/api/scenarios/sc-gi-a/run-schemes", headers=h,
                              json={"name": "带绑定", "dataSetSelection": [],
                                    "injectionEntryIds": [],
                                    "serviceBindings": {
                                        "fin.order": {"url": "http://fin:1"}},
                                    "stepTo": None, "nRuns": 1, "parallel": 1})
        assert r.status_code == 201, r.text
        scheme_id = r.json()["schemeId"]
        await self._fake_convert_patch(monkeypatch)

        from app.core import db as db_module
        from app.models.user import User
        from app.services import graph_dispatch, scheme_store
        async with db_module.SessionLocal() as s:
            uid = (await s.execute(sa.select(User.id).where(
                User.username == "gi_owner"))).scalar_one()
            await scheme_store.ensure_default_scheme(s, "sc-gi-a")  # 默认分支可查
        async with db_module.SessionLocal() as s:
            graph = await graph_dispatch.materialize_graph(s, uid, {
                "mode": "chain",
                "units": [{"ref": "a", "scenarioId": "sc-gi-a",
                           "schemeId": scheme_id,
                           "row": {"datasetId": ds_id,
                                   "rowIndex": 1}}],
            })
        unit = graph["units"][0]
        # 单行内联:所选那一行的值合入(默认方案语境)
        assert str(unit["scenario"]["config"]["vars"]["customer_id"]) == "222"
        # 方案的服务绑定随行合入(step 引用 fin.order → url 生效;
        # services 物化值 = url 字符串,run_materialize ① 优先级链)
        assert unit["scenario"]["config"]["services"]["fin.order"] \
            == "http://fin:1"
        # 无 row = 裸基线(此前的唯一行为,保持兼容)
        async with db_module.SessionLocal() as s:
            graph0 = await graph_dispatch.materialize_graph(s, uid, {
                "mode": "chain",
                "units": [{"ref": "a", "scenarioId": "sc-gi-a"}],
            })
        assert str(graph0["units"][0]["scenario"]["config"]
                   ["vars"]["customer_id"]) == "261"

    async def test_map_and_control_passthrough(self, client, monkeypatch):
        import pytest

        await register_and_login(client, "gc_boot", "gc_bootpass123")
        h = await register_and_login(client, "gc_owner", "gc_ownerpass123")
        await self._mk_svc_scenario(client, h, "sc-gc-1")
        await self._mk_svc_scenario(client, h, "sc-gc-2")
        await self._fake_convert_patch(monkeypatch)

        from app.core import db as db_module
        from app.models.user import User
        from app.services import graph_dispatch
        async with db_module.SessionLocal() as s:
            uid = (await s.execute(sa.select(User.id).where(
                User.username == "gc_owner"))).scalar_one()
        req = {"mode": "compose",
               "units": [
                   {"ref": "auth", "scenarioId": "sc-gc-1",
                    "map": {"token": "authToken"}},
                   {"ref": "order", "scenarioId": "sc-gc-2",
                    "needs": ["auth"]}],
               "control": {"only": ["order"], "toNode": "order"}}
        async with db_module.SessionLocal() as s:
            graph = await graph_dispatch.materialize_graph(s, uid, req)
        by_ref = {u["ref"]: u for u in graph["units"]}
        assert by_ref["auth"]["map"] == {"token": "authToken"}
        assert graph["control"] == {"only": ["order"], "to_node": "order"}
        # fromNode 不透传:拼装侧直接拒绝
        async with db_module.SessionLocal() as s:
            with pytest.raises(graph_dispatch.GraphDispatchError):
                await graph_dispatch.materialize_graph(s, uid, {
                    "mode": "chain",
                    "units": [{"ref": "a", "scenarioId": "sc-gc-1"}],
                    "control": {"fromNode": "a"}})

    async def test_api_accepts_new_unit_fields(self, client, monkeypatch):
        """GraphSpec/GraphUnitSpec 别名接线:row/schemeId/map/control 经
        POST /api/runs 可达物化层(launched 产物携带)。"""
        launched: list[dict] = []

        async def _launch(case_path, **_kw):
            import pathlib
            launched.append(json.loads(
                pathlib.Path(case_path).read_text(encoding="utf-8")))
            from tests.helpers import launch_ok
            return launch_ok()

        # 打在调用方模块上(execute_graph 用的是 from-import 绑定,
        # 只 patch gimbal_launcher.launch 在部分顺序下不生效)
        from app.services import graph_dispatch as gd
        monkeypatch.setattr(gd, "launch", _launch)
        await self._fake_convert_patch(monkeypatch)

        await register_and_login(client, "ga_boot", "ga_bootpass123")
        h = await register_and_login(client, "ga_owner", "ga_ownerpass123")
        await self._mk_svc_scenario(client, h, "sc-ga-1")
        await self._mk_svc_scenario(client, h, "sc-ga-2")
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-ga-1",
            "graph": {
                "mode": "compose",
                "units": [
                    {"ref": "auth", "scenarioId": "sc-ga-1",
                     "map": {"token": "authToken"}},
                    {"ref": "order", "scenarioId": "sc-ga-2",
                     "needs": ["auth"]},
                ],
                "control": {"only": ["order"]},
            },
        })
        assert r.status_code == 201, r.text
        exec_id = r.json()["executionId"]
        for _ in range(400):
            async with db_module.SessionLocal() as s:
                ex = await s.get(Execution, exec_id)
            if ex and ex.status in ("done", "failed"):
                break
            await asyncio.sleep(0.05)
        assert ex is not None
        if not launched:
            from app.services.run_dispatcher import _run_dir
            rd = _run_dir(ex.config_json["runId"])
            logs = []
            for f in sorted(rd.rglob("*.log")) + sorted(rd.rglob("*.jsonl")):
                logs.append(f"== {f} ==")
                try:
                    logs.append(f.read_text(encoding="utf-8", errors="replace")[-1500:])
                except Exception as e:
                    logs.append(f"<{e}>")
            raise AssertionError(
                f"graph 未下发 status={ex.status} dir={rd} :: "
                + " | ".join(logs))
        assert launched
        assert launched[0]["control"] == {"only": ["order"]}
        assert launched[0]["units"][0]["map"] == {"token": "authToken"}
