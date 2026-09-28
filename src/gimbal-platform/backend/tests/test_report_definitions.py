"""P3-07/C7:报告定义 CRUD + 执行时选择 + 工件下载。"""
from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from app.models.report_definition import ReportDefinitionRow
from tests.helpers import register_and_login

DEF = {
    "name": "failures-html",
    "description": "失败步骤分析",
    "selection": {"events": ["step.end"], "where": {"status": "failed"}},
    "projection": {"source": "payload",
                   "fields": ["seq", "step_id", "status", "error_brief"]},
    "presentation": {"format": "html", "title": "失败分析"},
}


async def _create_def(client, headers, *, name="failures-html",
                      public=False) -> int:
    r = await client.post("/api/report-definitions", headers=headers,
                          json={**DEF, "name": name, "public": public})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


class TestCrud:

    async def test_create_and_list(self, client):
        headers = await register_and_login(client)
        did = await _create_def(client, headers, name="my-def")
        assert did > 0

        r = await client.get("/api/report-definitions", headers=headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(i["id"] == did and i["name"] == "my-def" for i in items)

    async def test_private_vs_public_visibility(self, client):
        h1 = await register_and_login(client, "alice")
        h2 = await register_and_login(client, "bob")
        # 用户1 创建公共定义
        pub_id = await _create_def(client, h1, name="pub-def", public=True)
        # 用户1 创建私有定义
        priv_id = await _create_def(client, h1, name="priv-def")

        # 用户2 能看到公共 + 自己的(不含用户1的私有)
        r = await client.get("/api/report-definitions", headers=h2)
        ids = [i["id"] for i in r.json()["items"]]
        assert pub_id in ids
        assert priv_id not in ids

    async def test_update_and_delete(self, client):
        headers = await register_and_login(client)
        did = await _create_def(client, headers, name="updatable")
        r = await client.put(f"/api/report-definitions/{did}", headers=headers,
                             json={**DEF, "name": "updated"})
        assert r.status_code == 200
        assert r.json()["name"] == "updated"

        r = await client.delete(f"/api/report-definitions/{did}",
                                headers=headers)
        assert r.status_code == 204
        r = await client.get("/api/report-definitions", headers=headers)
        assert not any(i["id"] == did for i in r.json()["items"])

    async def test_other_user_cannot_modify(self, client):
        h1 = await register_and_login(client, "alice")
        h2 = await register_and_login(client, "bob")
        did = await _create_def(client, h1, name="h1-only")
        r = await client.put(f"/api/report-definitions/{did}", headers=h2,
                             json={**DEF, "name": "stolen"})
        assert r.status_code == 404   # 404/403 合一(不泄漏存在性)


class TestExecutionIntegration:

    async def test_run_with_report_definition(self, client, monkeypatch):
        """执行时选择报告定义 → 引擎以 definition reporter 产出工件;
        平台从执行工件目录读到报告文件。"""
        import asyncio

        headers = await register_and_login(client)
        did = await _create_def(client, headers, name="run-def")

        # mock launch:产物目录写一个 report-run-def.html(模拟 definition
        # reporter 的输出;真链路经 --reporter definition:<file>)
        async def _launch_with_report(case_path, *, step_to=None,
                                      report_dir=None, cwd=None,
                                      timeout=None, engine_log_path=None,
                                      on_event=None, on_log=None,
                                      n_runs=1, retry=0):
            Path(report_dir).mkdir(parents=True, exist_ok=True)
            (Path(report_dir) / "report-run-def.html").write_text(
                "<html><body>failures</body></html>", encoding="utf-8")
            from tests.helpers import launch_ok
            return launch_ok()

        async def _fake_convert(scenario):
            return {"consumer": "platform", "converted": dict(scenario)}

        from app.services import gimbal_launcher as gl, plate_client as pc
        monkeypatch.setattr(gl, "launch", _launch_with_report)
        monkeypatch.setattr(pc, "convert", _fake_convert)

        from tests.helpers import make_draft
        draft = make_draft("sc-rd", steps=[{
            "call": {"view_hints": {"endpoint_id": "fin.order.add"}},
            "request": {"body": {}},
        }])
        await client.post("/api/scenarios", headers=headers, json=draft)

        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-rd", "dataSetIds": [],
            "reportDefinitionId": did,
        })
        assert r.status_code == 201, r.text
        exec_id = r.json()["executionId"]

        # 等终态
        from app.models.execution import Execution
        for _ in range(100):
            async with db_module.SessionLocal() as s:
                ex = await s.get(Execution, exec_id)
                if ex and ex.status in ("done", "failed"):
                    break
            await asyncio.sleep(0.05)

        # config_json 记录了定义选择
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, exec_id)
            assert ex.config_json.get("reportDefinitionId") == did
