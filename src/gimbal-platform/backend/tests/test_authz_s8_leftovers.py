"""authz S8 遗留收口(2026-11-10)。

* L1 suite 编排用项目凭证:``POST /suites/{id}/run`` 带 ``credentialSource``
  (编排 = 全图项目池,聚合 = 随成员 RunRequest 透传单场景闸);``POST /runs``
  的 graph 分支同口径(全部单元同属一个普通项目);
* L3 预检缺槽:``POST /run/precheck`` 逐条带 ``missingAuths``(个人池差集)
  与 ``projectMissingAuths``(项目池差集;null = 不适用)。

(令牌调用用项目凭证一项已随 M2b 项目令牌落地,见 m2b-detail。)
"""
from __future__ import annotations

import json

import sqlalchemy as sa

from app.core import db as db_module
from app.models.suite import Suite

from .helpers import make_draft, register_and_login, wait_until
from .test_authz_s8_project_credentials import (
    _STEP, _mk_project, _mk_project_credential, _seed_project_scenario,
)
from .test_run_m1_capabilities import _patch_launch_capture
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


def _graph_launch_capture(monkeypatch, sink: list[dict]):
    """graph 链 launch 替身:读 SuiteGraph 文件进 sink,喂最小事件收口。"""
    import asyncio
    from pathlib import Path

    async def _launch(case_path, *, step_to=None, report_dir=None,
                      cwd=None, timeout=None, engine_log_path=None,
                      on_event=None, on_log=None, log_counters=None,
                      n_runs=1, retry=0, cancel_file=None):
        graph = json.loads(
            Path(case_path).read_text(encoding="utf-8"))
        sink.append(graph)
        for ev in [
            {"event_type": "scenario.start", "seq": 2, "unit": "a",
             "attempt": "1.1", "scenario_id": "sc-a",
             "scenario_name": "a", "step_count": 1},
            {"event_type": "scenario.end", "seq": 3, "unit": "a",
             "scenario_id": "sc-a", "status": "passed", "step_count": 1},
            {"event_type": "run.finished", "seq": 4, "exit_code": 0,
             "total": 1, "passed": 1, "failed": 0, "skipped": 0,
             "attempts": 1, "unit": "a"},
        ]:
            if on_event is not None:
                on_event(dict(ev))
            await asyncio.sleep(0)
        from tests.helpers import launch_ok
        return launch_ok()

    from app.services import graph_dispatch as gd, plate_client as pc

    async def _convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    monkeypatch.setattr(gd, "launch", _launch)
    monkeypatch.setattr(pc, "convert", _convert)


def _unit_users(graph: dict, ref: str) -> dict:
    unit = next(u for u in graph["units"] if u["ref"] == ref)
    return (unit["scenario"]["config"].get("users") or {})


class TestRunsGraphProjectSource:
    async def test_graph_uses_project_pool(self, client, plate_mock, monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "l1_gr", "pw123456")
        pid = await _mk_project("l1-runs", members={"l1_gr": "member"})
        await _seed_project_scenario(client, h, pid, sid="sc-l1a")
        await _seed_project_scenario(client, h, pid, sid="sc-l1b")
        await _mk_project_credential(pid)
        launched: list[dict] = []
        _graph_launch_capture(monkeypatch, launched)
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-l1a",
            "credentialSource": "project",
            "graph": {"mode": "aggregate", "units": [
                {"ref": "a", "scenarioId": "sc-l1a"},
                {"ref": "b", "scenarioId": "sc-l1b"}]}})
        assert r.status_code == 201, r.text
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            ex = await db.get(Execution, r.json()["executionId"])
        assert ex.config_json["credentialSource"] == "project"
        assert ex.config_json["credentialProjectId"] == pid
        await wait_until(lambda: len(launched) >= 1)
        for ref in ("a", "b"):
            assert _unit_users(launched[0], ref)["qa1"]["url"] == \
                "http://proj-auth"

    async def test_graph_gates(self, client, plate_mock):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "l1_gg", "pw123456")
        pid = await _mk_project("l1-gate", members={"l1_gg": "member"})
        await _seed_project_scenario(client, h, pid, sid="sc-l1g")
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-l1-priv", steps=[_STEP]))
        base_graph = {"mode": "aggregate",
                      "units": [{"ref": "a", "scenarioId": "sc-l1g"}]}
        # 混区(单元含私有场景)→ 409
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-l1g", "credentialSource": "project",
            "graph": {**base_graph, "units": [
                {"ref": "a", "scenarioId": "sc-l1g"},
                {"ref": "b", "scenarioId": "sc-l1-priv"}]}})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "credential_source_invalid"
        # 项目凭证缺槽 → 409 auth_aliases_missing(全图口径,含未登记槽文案)
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-l1g", "credentialSource": "project",
            "graph": base_graph})
        assert r.status_code == 409
        det = r.json()["detail"]
        assert det["code"] == "auth_aliases_missing"
        assert det["credentialSource"] == "project"
        assert "项目凭证" in det["message"]


class TestSuiteRunWithProjectSource:
    async def _mk_suite(self, client, h, pid: int, mode: str) -> int:
        await _seed_project_scenario(client, h, pid, sid="sc-l1s-a")
        await _seed_project_scenario(client, h, pid, sid="sc-l1s-b")
        r = await client.post("/api/suites", headers=h,
                              json={"name": "l1-suite", "description": "",
                                    "projectId": pid})
        assert r.status_code in (200, 201), r.text
        sid = r.json()["suiteId"]
        r = await client.post(f"/api/suites/{sid}/members", headers=h,
                              json={"scenarioIds": ["sc-l1s-a", "sc-l1s-b"]})
        assert r.status_code == 200, r.text
        if mode != "aggregate":
            async with db_module.SessionLocal() as db:
                row = (await db.execute(sa.select(Suite).where(
                    Suite.id == sid))).scalar_one()
                row.mode = mode
                await db.commit()
        return sid

    async def test_orchestration_project_pool(self, client, plate_mock,
                                              monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "l1_so", "pw123456")
        pid = await _mk_project("l1-orch", members={"l1_so": "member"})
        sid = await self._mk_suite(client, h, pid, "chain")
        launched: list[dict] = []
        _graph_launch_capture(monkeypatch, launched)
        # 缺槽先拒(项目凭证未登记)
        r = await client.post(f"/api/suites/{sid}/run", headers=h,
                              json={"credentialSource": "project"})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "auth_aliases_missing"
        await _mk_project_credential(pid)
        r = await client.post(f"/api/suites/{sid}/run", headers=h,
                              json={"credentialSource": "project"})
        assert r.status_code == 201, r.text
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            ex = await db.get(Execution, r.json()["executionId"])
        assert ex.config_json["credentialSource"] == "project"
        assert ex.config_json["credentialProjectId"] == pid
        await wait_until(lambda: len(launched) >= 1)
        from .test_authz_s8_project_credentials import _uid
        unit_scen = {u["ref"]: u for u in launched[0]["units"]}
        for ref in ("sc-l1s-a", "sc-l1s-b"):
            users = (unit_scen[ref]["scenario"]["config"].get("users") or {})
            assert users["qa1"]["url"] == "http://proj-auth"
        assert await _uid("l1_so")  # noqa: B018 — 成员身份占位

    async def test_orchestration_gates_and_aggregate_passthrough(
            self, client, plate_mock, monkeypatch):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "l1_sa", "pw123456")
        # 私有 suite 编排 → 409(项目凭证要求普通项目 + 成员)
        r = await client.post("/api/suites", headers=h,
                              json={"name": "l1-priv", "description": ""})
        priv_id = r.json()["suiteId"]
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-l1-priv2", steps=[_STEP]))
        await client.post(f"/api/suites/{priv_id}/members", headers=h,
                          json={"scenarioIds": ["sc-l1-priv2"]})
        async with db_module.SessionLocal() as db:
            row = (await db.execute(sa.select(Suite).where(
                Suite.id == priv_id))).scalar_one()
            row.mode = "chain"
            await db.commit()
        r = await client.post(f"/api/suites/{priv_id}/run", headers=h,
                              json={"credentialSource": "project"})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "credential_source_invalid"
        # 聚合模式:credentialSource 随成员 RunRequest 走单场景闸/取用池
        pid = await _mk_project("l1-agg", members={"l1_sa": "member"})
        sid = await self._mk_suite(client, h, pid, "aggregate")
        await _mk_project_credential(pid)
        cases: list[dict] = []
        _patch_launch_capture(monkeypatch, cases)
        r = await client.post(f"/api/suites/{sid}/run", headers=h,
                              json={"credentialSource": "project"})
        assert r.status_code == 201, r.text
        out = r.json()
        # 两成员都成功发起(单场景闸对项目成员放行)
        assert len(out["started"]) == 2 and not out["skipped"], out
        from app.models.execution import Execution
        async with db_module.SessionLocal() as db:
            rows = (await db.execute(sa.select(Execution.config_json).where(
                Execution.batch_id == out["batchId"]))).scalars().all()
        assert rows and all(
            (c or {}).get("credentialSource") == "project" for c in rows)

    async def test_validate_with_credential_source(self, client, plate_mock):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "l1_sv", "pw123456")
        pid = await _mk_project("l1-val", members={"l1_sv": "member"})
        sid = await self._mk_suite(client, h, pid, "chain")
        # 个人池缺 → warn(缺槽语义);项目池缺 → 文案指向项目凭证
        r = await client.post(
            f"/api/suites/{sid}/validate?credentialSource=project", headers=h)
        assert r.status_code == 200, r.text
        msgs = [it["message"] for it in r.json()["items"]
                if it.get("code") == "auth_alias_unresolved"]
        assert msgs and any("项目凭证" in m for m in msgs)
        await _mk_project_credential(pid)
        r = await client.post(
            f"/api/suites/{sid}/validate?credentialSource=project", headers=h)
        assert r.status_code == 200, r.text
        assert not [it for it in r.json()["items"]
                    if it.get("code") == "auth_alias_unresolved"]


class TestPrecheckMissingAuths:
    async def test_missing_and_project_pool(self, client, plate_mock):
        plate_mock.behaviour = "echo"
        h = await register_and_login(client, "l3_pk", "pw123456")
        pid = await _mk_project("l3-pc", members={"l3_pk": "member"})
        await _seed_project_scenario(client, h, pid, sid="sc-l3")
        # 默认方案 id:方案工作台约定「default」?—— 实际取列表首个
        r = await client.get("/api/scenarios/sc-l3/run-schemes", headers=h)
        schemes = r.json()
        scheme_id = schemes[0]["schemeId"]
        item = {"scenarioId": "sc-l3", "schemeId": scheme_id}
        # 个人池缺 + 项目池缺(成员 → projectMissingAuths 非空)
        out = (await client.post("/api/run/precheck", headers=h,
                                 json=[item])).json()[0]
        assert out["missingAuths"] == ["qa1"]
        assert out["projectMissingAuths"] == ["qa1"]
        # 项目凭证补齐 → projectMissingAuths 空(提示可切项目凭证)
        await _mk_project_credential(pid)
        out = (await client.post("/api/run/precheck", headers=h,
                                 json=[item])).json()[0]
        assert out["missingAuths"] == ["qa1"]
        assert out["projectMissingAuths"] == []
        # 私有场景 → 不适用(None)
        await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-l3-priv", steps=[_STEP]))
        r = await client.get("/api/scenarios/sc-l3-priv/run-schemes", headers=h)
        priv_scheme = r.json()[0]["schemeId"]
        out = (await client.post("/api/run/precheck", headers=h, json=[
            {"scenarioId": "sc-l3-priv", "schemeId": priv_scheme}])).json()[0]
        assert out["missingAuths"] == ["qa1"]
        assert out["projectMissingAuths"] is None
