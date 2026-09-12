"""T5 真链路:声明面放宽后,锚在 carry 字段的注入条目真的执行,且引擎 Assign
把偏离值写到线上 —— spec §2.3/§7。

与其余集成用例的差别:launcher **不 patch**(走真 gimbal CLI),被测服务是
进程内 stub HTTP(断言到达的 body)。缺 GIMBAL_BIN 的环境跳过。

本文件两条用例**各证一半,声称与实测一一对应**(P8):
  * ``..._runs_and_overrides_on_the_wire`` —— **归因唯一**:平台无值可带入
    (carry 面降级),``case.json`` 里该字段**只**出现在 Assign 的 target 上,
    故 stub 实收的值只能由该 Assign 产生;
  * ``..._overrides_platform_carried_value`` —— **覆盖**:平台 carry 已带入一个
    非空值,线上到达的仍是条目的偏离值(spec §2.3 的立论根基)。

为何本文件不做红先:验证的行为已由 Task 4 实现,红先阶段(条目被 skip →
``injectionId == None``)由 Task 4 的
``test_dispatcher_keeps_entry_anchored_on_declared_carry_path`` 承担。本文件的
不可替代价值是**真引擎的 wire 证据**。若此处 FAIL 在 ``injectionId`` 上,说明
Task 4 的放宽未真正生效(条目仍被 skip),回 Task 4 查 —— 不要改本文件的断言。
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
    """归因唯一:条目未被 skip,且平台侧**没有**值可带入(carry face 缺服务
    目录 → 降级),故 ``case.json`` 里 ``customer_id`` 只出现在 Assign 的
    target 上 —— stub 实收的 261 只能由该 Assign 产生。

    「覆盖平台带入值」那半由
    :func:`test_carry_anchored_entry_overrides_platform_carried_value` 负责。
    """
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


async def test_carry_anchored_entry_overrides_platform_carried_value(
    client, plate_mock, stub_sut, tmp_path
):
    """覆盖(spec §2.3 的立论根基):平台 carry 已把该字段带成**非空**值
    (服务进目录 + 值表种 ``999``),条目偏离 ``261`` 在真引擎里压过它 ——
    交给 CLI 的 ``case.json`` 里该字段是平台带入的 ``999``,而 stub 实收
    ``261``。

    两步缺一不可:只断 wire 分不清「Assign 覆盖了带入值」与「平台本来就没
    带值」——后者正是上一条用例的场景,也正是本条必须自带 carry 值的原因。
    """
    from .helpers import make_draft as _draft
    from .test_scenario_visibility_and_copy import _member
    from app.core import db as _db_module
    from app.services import carry_store
    from app.services.endpoint_declarations import _reset_declared_paths_cache

    _reset_declared_paths_cache()
    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{
            "id": "s1",
            "kind": "step",
            "api": {"kind": "api", "service": "stubsvc", "method": "POST", "path": "/pay",
                    "headers": {"Content-Type": "application/json"},
                    "view_hints": {"endpoint_id": "ep-carry-wire"}},
            "request": {"kind": "request", "body": {"bl_no": "${var.bl_no}"}},
            "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                          "operator": "eq", "expected": "0"}],
        }],
        vars_map={"bl_no": "BL1"},
        description="carry wire override", author="t", owner="bob", tags=[], version="1",
        createTime="2026-09-12T00:00:00Z", expire=False, requirementRef=[],
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-carry", "name": "carry 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 261, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    # ① 服务进目录:否则 derive_base 解析失败 → carry 面 fail-closed 降级,
    #    平台带不进任何值,本条就退化成上一条的场景(覆盖无从谈起)。
    plate_mock.services = [{"name": "stubsvc"}]
    # ② 种一个与条目 value **不同**的值(999 ≠ 261),覆盖才有观察面。
    async with _db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "stubsvc", {"$.customer_id": 999}, "bob")
        await db.commit()
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
    assert rows[0]["injectionId"] == "inj-carry"       # 前置:条目未被 skip

    # 交给 CLI 的 case:平台 carry 确实把值带进了 body(非空,且不同于偏离值)
    case_files = sorted(tmp_path.glob("runs/cases/*/*/case.json"))
    assert len(case_files) == 1, case_files
    body = json.loads(case_files[0].read_text(encoding="utf-8"))["steps"][0]["request"]["body"]
    assert str(body.get("customer_id")) == "999", body   # 平台带入值

    # 线上:条目的偏离值压过了它(spec §2.3)
    assert len(_StubSut.hits) == 1
    assert _StubSut.hits[0].get("customer_id") == 261    # 覆盖生效

