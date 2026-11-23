"""D10 补口:suite 编排模式端到端(真引擎,2026-11-23)。

自举登记册 D10「server 链 / 空库启动 / CLI 退出码 / suite 执行」四路径
中,前三已有真形态测试(p35 真引擎 server 链 / 空库启动 / CLI 退出码);
本文件补最后一项 —— **编排模式经真 gimbal 引擎**的一次完整执行:

    composition 落库 → 编排入队(kind=suite_graph)→ _fanout_graph →
    逐单元 plate convert → 执行器 server 会话 spawn + SSE → 行台账 /
    计数 / 事件全链断言。

此前编排链只有假引擎覆盖(mock launch 流式事件),图物化产物与真执行器
方言是否咬合无测试证据 —— 测试≠生产路径,正是 D10 登记的缺口。

plate /convert 用 p35 同款直通替身(真引擎兼容平台方言;回包无 m2 即
自然略过 M2 §5.1 代际门);被测系统为本文件自带桩(独立 hits 面)。
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.core.config import settings
from app.models.execution import Execution, ExecutionEvent, ExecutionRow
from tests.helpers import make_draft, register_and_login, seed_deployment

# 引擎可用性判据复用 C12 e2e(同 p35)
from tests.test_debug_console import _engine_available


_STEPS = [{"kind": "step",
    "call": {"kind": "call", "protocol": "http", "service": "svc",
             "method": "GET", "path": "/ping"},
    "request": {"kind": "request", "body": {}},
    "strategy": [{"kind": "assertion",
                  "target": "$.call.response.body.code",
                  "operator": "eq", "expected": "0"}],
}]


class _StubSut(BaseHTTPRequestHandler):
    """桩被测系统:任何 GET 回 {"code": "0"},按路径记命中。"""

    protocol_version = "HTTP/1.1"
    hits: list[str] = []

    def do_GET(self):  # noqa: N802
        _StubSut.hits.append(self.path)
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


async def _wait_final(execution_id: int, timeout_s: float = 90.0) -> Execution:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, execution_id)
            if ex.status in ("done", "failed", "canceled"):
                return ex
        await asyncio.sleep(0.1)
    raise AssertionError(f"execution {execution_id} not final in {timeout_s}s")


@pytest.mark.skipif(not _engine_available(),
                    reason="真 gimbal 引擎不可用(GIMBAL_BIN / importable gimbal)")
async def test_suite_orchestration_real_engine_e2e(
        client, monkeypatch, stub_sut, real_engine_session):
    """编排 chain:两单元真引擎执行 → done;逐单元行 passed;被测系统
    每单元各命中一次;事件完整(整图 run.finished ×1 + 逐单元
    scenario.end ×2);台账 chain=server。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": scenario}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(settings, "GIMBAL_BIN", "")   # 钉当前解释器引擎

    h = await register_and_login(client, "d10owner", "pw123456")
    for sid in ("sc-d10-a", "sc-d10-b"):
        r = await client.post("/api/scenarios", headers=h, json=make_draft(
            sid, steps=_STEPS, vars_map={"a": "1"},
            description="d10", author="t", owner="d10owner", tags=[],
            version="1", createTime="2026-09-24T00:00:00Z", expire=False,
            requirementRef=[],
        ))
        assert r.status_code in (200, 201), r.text

    # 地址只来自部署表(authz M2a S6):默认环境登记桩被测系统
    async with db_module.SessionLocal() as s:
        await seed_deployment(s, "svc", stub_sut)
        await s.commit()

    r = await client.post("/api/suites", headers=h,
                          json={"name": "d10 编排", "description": ""})
    assert r.status_code == 201, r.text
    suite_id = r.json()["suiteId"]
    r = await client.post(f"/api/suites/{suite_id}/members", headers=h,
                          json={"scenarioIds": ["sc-d10-a", "sc-d10-b"]})
    assert r.status_code == 200, r.text

    # 编排模式落库(rev 乐观锁:取当前 rev)
    r = await client.get(f"/api/suites/{suite_id}", headers=h)
    assert r.status_code == 200, r.text
    rev = r.json()["rev"]
    r = await client.put(f"/api/suites/{suite_id}/composition", headers=h,
                         json={
                             "rev": rev,
                             "mode": "chain",
                             "members": [
                                 {"scenarioId": "sc-d10-a", "role": "main"},
                                 {"scenarioId": "sc-d10-b", "role": "main"},
                             ],
                             "modeConfig": {"units": {
                                 "sc-d10-a": {"ref": "ua"},
                                 "sc-d10-b": {"ref": "ub"},
                             }},
                         })
    assert r.status_code == 200, r.text

    # 发起编排(一次编排执行,非逐成员聚合)
    r = await client.post(f"/api/suites/{suite_id}/run", headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mode"] == "chain" and body["units"] == 2, body
    eid = body["executionId"]

    ex = await _wait_final(eid)
    assert ex.status == "done", ex.status
    assert ex.kind == "suite_graph"
    assert ex.passed == 2 and ex.failed == 0, (ex.passed, ex.failed)
    assert ex.config_json.get("chain") == "server"
    assert ex.config_json.get("mode") == "chain"

    # 被测系统:每单元各真打一次
    assert _StubSut.hits == ["/ping", "/ping"], _StubSut.hits

    async with db_module.SessionLocal() as s:
        rows = (await s.execute(
            sa.select(ExecutionRow.seq, ExecutionRow.unit_id,
                      ExecutionRow.status)
            .where(ExecutionRow.execution_id == eid)
            .order_by(ExecutionRow.seq))).all()
        n_fin = (await s.execute(
            sa.select(sa.func.count()).where(
                ExecutionEvent.execution_id == eid,
                ExecutionEvent.event_type == "run.finished"))).scalar()
        n_end = (await s.execute(
            sa.select(sa.func.count()).where(
                ExecutionEvent.execution_id == eid,
                ExecutionEvent.event_type == "scenario.end"))).scalar()

    # 行台账:seq=0 图行 + 逐单元行(ref 为 unit 标签)
    assert [(r.seq, r.unit_id, r.status) for r in rows] == [
        (0, "graph", "passed"), (1, "ua", "passed"), (2, "ub", "passed"),
    ], [tuple(r) for r in rows]
    # 事件完整性:整图一次 run.finished + 逐单元 scenario.end
    assert n_fin == 1, f"run.finished 丢失: {n_fin}/1"
    assert n_end == 2, f"scenario.end 丢失: {n_end}/2"
