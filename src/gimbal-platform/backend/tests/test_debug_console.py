"""C6(P3-04)+C12(P3-02):调试执行 — 校验/入队配方/代理端点/server 链端到端。

* 调试前置:多 case 或 nRuns>1 → 409;graph → 409;
* 入队配方:debug 恒走 server 链(payload.chain=server + debug 段);
* 代理端点:非调试执行 409;伪造会话走通 output/command 投影;
* server 链端到端(引擎可用时):真实拉起 ``gimbal run server`` 实例,
  POST /runs + SSE 事件入库,结束无残留进程。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.core import db as db_module
from app.core.config import settings
from app.models.execution import ExecutionJob
from app.services import run_dispatcher
from app.services.gimbal_server_session import ServerSession
from tests.helpers import make_draft, register_and_login


def _engine_available() -> bool:
    if settings.GIMBAL_BIN:
        return Path(settings.GIMBAL_BIN).exists()
    import importlib.util
    return importlib.util.find_spec("gimbal") is not None


# ── 1. 校验与入队配方 ─────────────────────────────────────────

async def test_debug_rejects_multi_case(client):
    h = await register_and_login(client, "dbg1", "pw123456")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-dbg", vars_map={"a": "1"}))
    r = await client.post("/api/scenarios/sc-dbg/data-sets", headers=h,
                          json={"name": "ds", "rows": [{"a": "1"}, {"a": "2"}]})
    ds_id = r.json()["datasetId"]
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-dbg", "dataSetIds": [ds_id],
        "debug": {"pause": "on_failure"},
    })
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "debug_single_case"


async def test_debug_rejects_n_runs_above_one(client):
    h = await register_and_login(client, "dbg2", "pw123456")
    await client.post("/api/scenarios", headers=h, json=make_draft("sc-dbg"))
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-dbg", "dataSetIds": [],
        "nRuns": 3, "debug": {"pause": "every_step"},
    })
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "debug_single_run"


async def test_debug_dispatch_forces_server_chain(client, monkeypatch):
    """入队配方:debug 恒 server 链 + debug 段随配方落档。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    h = await register_and_login(client, "dbg3", "pw123456")
    await client.post("/api/scenarios", headers=h, json=make_draft("sc-dbg"))
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-dbg", "dataSetIds": [],
        "debug": {"pause": "every_step", "breakpoints": ["step-000:before"]},
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    from sqlalchemy import select
    async with db_module.SessionLocal() as s:
        job = (await s.execute(select(ExecutionJob)
                               .where(ExecutionJob.execution_id == eid))
               ).scalar_one()
        assert job.payload["chain"] == "server"
        assert job.payload["debug"]["pause"] == "every_step"
        assert job.payload["debug"]["breakpoints"] == ["step-000:before"]
    # config_json 留档同拍
    from app.models.execution import Execution
    async with db_module.SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert (ex.config_json or {}).get("chain") == "server"


# ── 2. 代理端点 ───────────────────────────────────────────────

class _FakeSession:
    def __init__(self) -> None:
        self.commands: list[dict] = []
        self.outputs: list[str] = ["[debug 暂停] step.before step=step-000"]

    @property
    def run_id(self) -> str:
        return "fake-run"

    async def debug_output(self) -> list[str]:
        out, self.outputs = self.outputs, []
        return out

    async def debug_command(self, command: dict) -> dict:
        self.commands.append(command)
        return {"accepted": True, "output": ["[debug] resumed"]}


async def test_debug_endpoints_proxy_session(client):
    h = await register_and_login(client, "dbg4", "pw123456")
    await client.post("/api/scenarios", headers=h, json=make_draft("sc-dbg"))
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-dbg", "dataSetIds": [],
    })
    eid = r.json()["executionId"]

    # 非调试执行:409 no_debug_session
    r = await client.get(f"/api/executions/{eid}/debug", headers=h)
    assert r.status_code == 200 and r.json()["active"] is False
    r = await client.post(f"/api/executions/{eid}/debug/command", headers=h,
                          json={"kind": "continue"})
    assert r.status_code == 409

    # 等 job 终态(Execution 终态先于 fanout _teardown 的 debug_sessions
    # pop——job finish 在任务体返回之后,teardown 必已跑完;直接等
    # Execution 会注入后被 pop,偶发 409 即本测试的历史抖动根因)
    from app.models.execution import ExecutionJob as _Job
    from sqlalchemy import select as _sel
    for _ in range(300):
        async with db_module.SessionLocal() as s:
            job_status = (await s.execute(
                _sel(_Job.status).where(_Job.execution_id == eid))).scalar()
            if job_status in ("done", "failed", "canceled"):
                break
        await asyncio.sleep(0.05)

    # 注入伪造会话 → 代理走通(token 不出后端)
    fake = _FakeSession()
    run_dispatcher.debug_sessions[eid] = {"session": fake}
    try:
        r = await client.get(f"/api/executions/{eid}/debug", headers=h)
        assert r.json()["active"] is True and r.json()["runId"] == "fake-run"
        r = await client.get(f"/api/executions/{eid}/debug/output", headers=h)
        assert "暂停" in r.json()["output"][0]
        r = await client.post(f"/api/executions/{eid}/debug/command", headers=h,
                              json={"kind": "write", "variable": "x",
                                    "value": 5})
        assert r.status_code == 200 and r.json()["accepted"] is True
        assert fake.commands[-1]["kind"] == "write"
        assert fake.commands[-1]["variable"] == "x"
        assert fake.commands[-1]["value"] == 5
        # 结构化校验:write 缺 variable → 422(镜像红线)
        r = await client.post(f"/api/executions/{eid}/debug/command", headers=h,
                              json={"kind": "write", "value": 5})
        assert r.status_code == 422
    finally:
        run_dispatcher.debug_sessions.pop(eid, None)


# ── 3. server 链端到端(引擎可用时)────────────────────────────

class _StubSut(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: list[dict] = []

    def do_GET(self):  # noqa: N802
        _StubSut.hits.append({"path": self.path})
        out = json.dumps({"code": "0"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture
def stub_sut():
    _StubSut.hits = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubSut)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_server_chain_end_to_end(client, monkeypatch, stub_sut):
    """C12:chain_override=server → 执行器 server 实例真实跑通一个 case。

    事件经 SSE 入库(execution_events 有行);结束无残留(会话已关闭)。
    """
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    # 钉住当前解释器(-m gimbal):.env 的 GIMBAL_BIN 可能指向旧安装
    # (D:\Gimbal venv 的 gimbal.exe 不带新参数),server 链需本仓库引擎
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")
    h = await register_and_login(client, "dbg5", "pw123456")
    await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-dbg",
        steps=[{
            "id": "s1", "kind": "step",
            "call": {"kind": "call", "protocol": "http", "service": "svc",
                     "method": "GET", "path": "/ping"},
            "request": {"kind": "request", "body": {}},
            "strategy": [{"kind": "assertion",
                          "target": "$.call.response.body.code",
                          "operator": "eq", "expected": "0"}],
        }],
        description="server chain", author="t", owner="dbg5", tags=[],
        version="1", createTime="2026-09-29T00:00:00Z", expire=False,
        requirementRef=[],
    ))

    from app.schemas.scenario_composer import RunRequest, ServiceBinding
    from sqlalchemy import select
    from app.models.execution import Execution, ExecutionEvent

    req = RunRequest(
        scenarioId="sc-dbg",
        serviceBindings={"svc": ServiceBinding(url=stub_sut)},
    )
    async with db_module.SessionLocal() as db:
        user_row = (await db.execute(
            __import__("sqlalchemy").select(
                __import__("app.models.user", fromlist=["User"]).User)
        )).scalars().first()
        resp = await run_dispatcher.dispatch_run(
            db, user_row.id, req, chain_override="server")
        await db.commit()
    eid = resp.execution_id

    for _ in range(600):
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, eid)
            if ex.status in ("done", "failed", "canceled"):
                break
        await asyncio.sleep(0.1)
    assert ex.status == "done", ex.status
    assert ex.passed == 1 and ex.failed == 0
    assert len(_StubSut.hits) == 1                      # 真引擎发出去了

    async with db_module.SessionLocal() as s:
        n_events = (await s.execute(
            select(__import__("sqlalchemy").func.count())
            .select_from(ExecutionEvent)
            .where(ExecutionEvent.execution_id == eid))).scalar_one()
    assert n_events > 0                                  # SSE 事件已入库
