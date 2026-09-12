"""T5 真链路:声明面放宽后,锚在 carry 字段的注入条目真的执行,
且引擎 Assign 把偏离值写到线上(平台 carry 注入被覆盖)—— spec §2.3/§7。

与其余集成用例的差别:launcher **不 patch**(走真 gimbal CLI),被测服务是
进程内 stub HTTP(断言到达的 body)。缺 GIMBAL_BIN 的环境跳过。

为何本用例不做红先:它验证的行为已由 Task 4 实现,红先阶段(条目被 skip →
``injectionId == None``)由 Task 4 的
``test_dispatcher_keeps_entry_anchored_on_declared_carry_path`` 承担。本用例
不可替代的价值是**真引擎的 wire 证据**:断言 stub 被测服务**真的收到了**
``customer_id == 261``,即放宽后条目不仅"不被 skip",而且偏离确实覆盖了平台
带入值。若此处 FAIL,说明 Task 4 的放宽未真正生效(条目仍被 skip),回 Task 4
查 —— 不要改本测试的断言。
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.core.config import settings

# plate_mock 是显式夹具(非 conftest 级):本仓库其余集成用例同款 re-export。
from .test_scenario_composer_plate_integration import (  # noqa: F401
    PlateMock,
    plate_mock,
)

pytestmark = pytest.mark.skipif(
    not settings.GIMBAL_BIN and os.environ.get("GIMBAL_FORCE_REAL") != "1",
    reason="需要真 gimbal CLI(settings.GIMBAL_BIN)",
)

_EXEC_FINAL = {"done", "failed", "canceled"}


class _StubSut(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: list[dict] = []

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        try:
            type(self).hits.append(json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            type(self).hits.append({"_raw": raw})
        out = json.dumps({"code": "0", "msg": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture
def stub_sut():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubSut)
    _StubSut.hits = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def test_carry_anchored_entry_runs_and_overrides_on_the_wire(
    client, plate_mock, stub_sut
):
    from .helpers import make_draft as _draft
    from .test_scenario_visibility_and_copy import _member
    from app.services.endpoint_declarations import _reset_declared_paths_cache

    _reset_declared_paths_cache()
    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{
            "id": "s1",
            # 真引擎 Scenario 的两个判别式 + plate 必填 meta:brief 的
            # echo 桩把 convert 短路了,真 plate 的 GimbalScenarioExporter
            # 平时才会补上这些(step.kind / request.kind / meta.* 必填)。
            # 不补则引擎 Scenario 校验 union_tag_not_found → exit 2
            # (gimbal_rejected),永远到不了 wire —— 断言面一字未动。
            "kind": "step",
            "api": {"kind": "api", "service": "stubsvc", "method": "POST", "path": "/pay",
                    "headers": {"Content-Type": "application/json"},
                    "view_hints": {"endpoint_id": "ep-carry-wire"}},
            "request": {"kind": "request", "body": {"bl_no": "${var.bl_no}"}},
            "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                          "operator": "eq", "expected": "0"}],
        }],
        vars_map={"bl_no": "BL1"},
        description="carry wire", author="t", owner="bob", tags=[], version="1",
        createTime="2026-09-12T00:00:00Z", expire=False, requirementRef=[],
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-carry", "name": "carry 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 261, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"           # convert 原样回灌 → case 保留 Assign
    plate_mock.fulls["ep-carry-wire"] = {"request": {"declarations": [
        {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
        {"name": "customer_id", "path": "$.customer_id", "state": "carry", "required": True},
    ]}}

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-carry"],
        "serviceBindings": {"stubsvc": {"url": stub_sut}},
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    for _ in range(600):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
        if ex["status"] in _EXEC_FINAL:
            break
        await asyncio.sleep(0.1)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)).json()["items"]
    assert len(rows) == 1
    assert rows[0]["injectionId"] == "inj-carry"      # 未被 skip(放宽生效)
    assert len(_StubSut.hits) == 1                    # 真引擎发出去了
    assert _StubSut.hits[0].get("customer_id") == 261 # Assign 覆盖:偏离落到线上
