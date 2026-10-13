"""B-1(2026-10-13):suite(graph)执行接入版本模型。

覆盖三面:
* 台账三件套随 graph 派发落库(plate_pins/baseline_*/m2_hash)——与
  单场景 dispatcher 同口径(此前 graph 分支完全不记);
* m2_info 透传执行器(server 链 run_case 收到;legacy 链无 m2 面,
  同单场景限制);
* check_and_resolve_suite_versions 不再静默剔除 resolve 失败的成员
  (声明不存在的修订 → SUITE_REVISION_RESOLVE_FAILED,而非约束凭空
  消失 Suite 照跑)。
"""
from __future__ import annotations

import pytest

from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401



def _capture_graph_launch(monkeypatch, sink: list[dict]) -> None:
    """patch graph_dispatch.launch(模块顶 from-import 绑定;patch
    gimbal_launcher.launch 对它无效,会留真实子进程悬挂)。"""
    import pathlib
    from tests.helpers import launch_ok
    from app.services import graph_dispatch as gd

    async def _cap(case_path, **_kw):
        sink.append(__import__("json").loads(
            pathlib.Path(case_path).read_text(encoding="utf-8")))
        return launch_ok()
    monkeypatch.setattr(gd, "launch", _cap)


def _pinned_steps():
    return [{
        "kind": "step", "endpoint": "fin.orders.get",
        "call": {"service": "fin-service", "method": "GET", "path": "/o"},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]


async def test_graph_ledger_written_on_dispatch(
        client, plate_mock: PlateMock, monkeypatch):
    """钉定+全评审成员的 graph 执行 → 台账三件套落库。"""
    from .test_run_m1_capabilities import _patch_launch_capture

    plate_mock.behaviour = "echo"
    plate_mock.revision_reviews = {"fin": {"fin.orders.get": "reviewed"}}
    cases: list[dict] = []
    _capture_graph_launch(monkeypatch, cases)

    h = await register_and_login(client, "gvl_owner", "pw123456")
    draft = make_draft("sc-gvl-a", steps=_pinned_steps(),
                       plate={"fin": "1.0#1"})
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text

    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-gvl-a",
        "graph": {"mode": "chain",
                  "units": [{"ref": "a", "scenarioId": "sc-gvl-a"}]},
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    d = await _poll(client, h, eid, field="plate_pins")
    assert d["plate_pins"] == {"fin": "1.0#1"}, d.get("plate_pins")
    assert d["m2_hash"] == "mock-m2-hash-0001"
    assert d["baseline_eligible"] is True
    assert d["baseline_block"] is None


async def test_graph_ledger_blocks_on_working_member(
        client, plate_mock: PlateMock, monkeypatch):
    """成员锚定系统未钉(working)→ 台账 block=working(与单场景同判)。"""
    from .test_run_m1_capabilities import _patch_launch_capture

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _capture_graph_launch(monkeypatch, cases)

    h = await register_and_login(client, "gvw_owner", "pw123456")
    draft = make_draft("sc-gvw-a", steps=_pinned_steps())   # 无 plate 声明
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text

    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-gvw-a",
        "graph": {"mode": "chain",
                  "units": [{"ref": "a", "scenarioId": "sc-gvw-a"}]},
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    # 台账在 execute 前写:轮询台账列(不等终态 —— 卡片收口另有维度)
    d = await _poll(client, h, eid, field="baseline_block")
    assert d["baseline_eligible"] is False
    assert d["baseline_block"] == "working"
    assert d["plate_pins"] is None or d["plate_pins"] == {}


async def _poll(client, h, eid, *, field: str, timeout_s: float = 30.0):
    """async 轮询执行详情字段(helpers.wait_until 只收同步谓词)。"""
    import asyncio as _a
    deadline = _a.get_event_loop().time() + timeout_s
    d: dict = {}
    while _a.get_event_loop().time() < deadline:
        d = (await client.get(f"/api/executions/{eid}", headers=h)).json()
        if d.get(field) is not None:
            return d
        await _a.sleep(0.1)
    return d


async def _wait_e(client, h, eid):
    import asyncio as _a
    deadline = _a.get_event_loop().time() + 30.0
    while _a.get_event_loop().time() < deadline:
        d = (await client.get(f"/api/executions/{eid}", headers=h)).json()
        if d.get("status") not in (None, "", "queued", "running"):
            return
        await _a.sleep(0.1)


async def test_graph_m2_info_passed_to_server_chain(
        client, plate_mock: PlateMock, monkeypatch):
    """server 链:materialize 收到的 m2 身份透传 run_case(代际门生效面)。"""
    plate_mock.behaviour = "echo"
    seen: dict = {}

    class _FakeSS:
        def __init__(self): self._proc = object()
        async def start(self, **kw): pass
        async def close(self): pass
        async def run_case(self, case_path, *, n_runs=1, on_event=None,
                           m2_info=None):
            seen["m2_info"] = m2_info
            from tests.helpers import launch_ok
            return launch_ok()

    import app.services.graph_dispatch as gd
    from app.services import gimbal_server_session
    monkeypatch.setattr(gimbal_server_session, "ServerSession", _FakeSS)

    h = await register_and_login(client, "gvm_owner", "pw123456")
    draft = make_draft("sc-gvm-a", steps=_pinned_steps())
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text

    # conftest 把 EXEC_CHAIN 钉回 legacy;本用例覆写为 server(C12 链)
    from app.core.config import settings as _settings
    monkeypatch.setattr(_settings, "EXEC_CHAIN", "server", raising=True)
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": "sc-gvm-a",
        "graph": {"mode": "chain",
                  "units": [{"ref": "a", "scenarioId": "sc-gvm-a"}]},
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    await _wait_e(client, h, eid)
    assert seen.get("m2_info") == {"hash": "mock-m2-hash-0001",
                                   "generation": 1}


async def test_resolve_failure_no_longer_silently_skipped(monkeypatch):
    """成员声明不存在修订 → SUITE_REVISION_RESOLVE_FAILED(不再静默剔出
    交集)。PlateUnavailableError 仍向上(plate 宕机归上层统一处理)。"""
    from app.services import plate_client
    from app.services.suite_version import (
        SuiteVersionError, check_and_resolve_suite_versions,
    )

    async def _boom(meta_plate, endpoints, **kw):
        raise plate_client.PlateRejectedError(
            code="revision_not_found", message="no such revision")

    monkeypatch.setattr(plate_client, "resolve", _boom)
    member = {"definition": {
        "meta": {"plate": {"fin": "1.0#9"}},
        "steps": [{"endpoint": "fin.a"}]}}
    with pytest.raises(SuiteVersionError) as ei:
        await check_and_resolve_suite_versions([member, member])
    assert ei.value.code == "SUITE_REVISION_RESOLVE_FAILED"
    assert ei.value.details["ref"] == "1.0#9"

    async def _down(meta_plate, endpoints, **kw):
        raise plate_client.PlateUnavailableError("plate down")

    monkeypatch.setattr(plate_client, "resolve", _down)
    with pytest.raises(plate_client.PlateUnavailableError):
        await check_and_resolve_suite_versions([member])
