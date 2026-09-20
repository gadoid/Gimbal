"""执行设计(2026-09)E1/E1末 后端改造测试。

覆盖面(对应 §3.5 / §6 / §1.6 / §1.2):

* ``GET /executions/summary`` — KPI 带(路由顺序:``/summary`` 不被
  ``/{execution_id}`` 的 int Path 吃掉)与口径(owner 隔离、active 不受窗约束)
* ``GET /api/executions`` — status / 发起时间范围 / batch_id 筛选
* ``Execution.batch_id`` — POST /runs 带 batchId 落列 + config_json 双写
* ``POST /executions/{id}/rerun`` — 按 config_json 重建配方;重跑不带原批
* ``POST /run/precheck`` — 「用例 × 方案」失效判定的服务端唯一实现:
  数据集已删 / 注入条目悬空 / 未落点服务引用 / 场景不可读不泄露存在性

执行 mock 同 M1 测试:gimbal_launcher.launch 捕获式假实现,plate 走
PlateMock(behaviour ok)。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from .helpers import (
    launch_ok as _ok,
    make_draft as _draft,
    register_and_login as _register_and_login,
    wait_until as _wait,
)
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)
from .test_scenario_visibility_and_copy import _member, _seed_ds


def _patch_launch_capture(
    monkeypatch: pytest.MonkeyPatch, sink: list[dict]
) -> None:
    """把 ``gimbal_launcher.launch`` 换成读 case.json 并捕获的假实现。"""

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        sink.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        return _ok()

    from app.services import gimbal_launcher as gl
    monkeypatch.setattr(gl, "launch", _capture)


async def _insert_execution(
    *,
    owner_id: int,
    scenario_id: str = "sc-e2e",
    status: str = "done",
    total_runs: int = 1,
    passed: int = 1,
    failed: int = 0,
    batch_id: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> int:
    from app.core.db import SessionLocal
    from app.models import Execution

    async with SessionLocal() as s:
        ex = Execution(
            scenario_id=scenario_id,
            owner_id=owner_id,
            status=status,
            total_runs=total_runs,
            passed=passed,
            failed=failed,
            batch_id=batch_id,
        )
        if created_at is not None:
            ex.created_at = created_at
        if started_at is not None:
            ex.started_at = started_at
        if finished_at is not None:
            ex.finished_at = finished_at
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        return ex.id


async def _alice_id() -> int:
    from app.core.db import SessionLocal
    from app.models import User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        return alice.id


# ── summary(KPI 带)───────────────────────────────────────────────
async def test_summary_route_order_and_kpi(client: AsyncClient) -> None:
    """/summary 在 /{execution_id} 之前声明 — 字面量不被 int Path 吃成 422;
    窗口锚 created_at;active 不受窗约束;执行维度 owner 硬隔离(§5.1)。"""
    auth = await _register_and_login(client)
    alice = await _alice_id()
    now = datetime.utcnow()
    await _insert_execution(
        owner_id=alice, status="done", total_runs=2, passed=1, failed=1,
        created_at=now - timedelta(days=1),
        started_at=now - timedelta(days=1), finished_at=now - timedelta(days=1),
    )
    await _insert_execution(
        owner_id=alice, status="failed", total_runs=1, passed=0, failed=1,
        created_at=now - timedelta(days=10),   # 窗外
    )
    await _insert_execution(owner_id=alice, status="running", created_at=now - timedelta(days=30))

    r = await client.get("/api/executions/summary", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    # 窗内(近 7 天)只有第一单;running 单在窗内计入 total_executions
    assert body["totalExecutions"] == 1
    assert body["totalRuns"] == 2 and body["passedRuns"] == 1 and body["failedRuns"] == 1
    assert abs(body["passRate"] - 0.5) < 1e-6
    assert body["activeExecutions"] == 1      # running 不受窗约束
    assert body["repeatFailureScenarios"] == 0


async def test_summary_owner_isolation(client: AsyncClient) -> None:
    await _register_and_login(client, "alice", "alicepass123")
    await _insert_execution(owner_id=await _alice_id(), status="done", total_runs=3, passed=3)
    bob = await _register_and_login(client, "bob", "bobpass456")
    r = await client.get("/api/executions/summary", headers=bob)
    body = r.json()
    assert body["totalExecutions"] == 0
    assert body["totalRuns"] == 0 and body["passRate"] is None


# ── list 筛选(status / 时间 / 批次)──────────────────────────────
async def test_list_filters_status_batch_window(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    alice = await _alice_id()
    now = datetime.utcnow()
    b1 = await _insert_execution(owner_id=alice, status="done", batch_id="b-001",
                                 created_at=now - timedelta(days=1))
    b1f = await _insert_execution(owner_id=alice, status="failed", batch_id="b-001",
                                  created_at=now - timedelta(days=1))
    await _insert_execution(owner_id=alice, status="failed", batch_id="b-002",
                            created_at=now - timedelta(days=9))

    r = await client.get("/api/executions", params={"batch_id": "b-001"}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {i["batch_id"] for i in body["items"]} == {"b-001"}

    r = await client.get("/api/executions", params={"status": "failed"}, headers=auth)
    assert r.json()["total"] == 2

    r = await client.get("/api/executions", params={"status": "nope"}, headers=auth)
    assert r.status_code == 422

    # 发起时间范围(锚 created_at):只命中昨天的两单
    r = await client.get("/api/executions", params={
        "created_from": (now - timedelta(days=2)).isoformat(),
        "created_to": now.isoformat(),
    }, headers=auth)
    assert r.json()["total"] == 2
    ids = {b1, b1f}
    assert {i["id"] for i in r.json()["items"]} == ids


# ── 批次键(§1.2:平台一次只发一条,批只是归并键)─────────────────
async def test_run_with_batch_id_lands_column_and_config(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = await _member(client, "alice")
    r = await client.post("/api/scenarios", headers=auth, json=_draft())
    assert r.status_code == 201, r.text
    calls: list[dict] = []
    _patch_launch_capture(monkeypatch, calls)

    r = await client.post("/api/runs", headers=auth, json={
        "scenarioId": "sc-test", "batchId": "b-run-1",
    })
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]

    from app.core.db import SessionLocal
    from app.models import Execution

    async with SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex is not None and ex.batch_id == "b-run-1"
        assert (ex.config_json or {}).get("batchId") == "b-run-1"


# ── rerun(§3.4/§3.5:config_json 已存完整配方,重建即可)──────────
async def test_rerun_rebuilds_recipe_from_config(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = await _member(client, "alice")
    r = await client.post("/api/scenarios", headers=auth,
                          json=_draft(vars_map={"qty": 0}))
    assert r.status_code == 201
    await _seed_ds(client, auth)
    calls: list[dict] = []
    _patch_launch_capture(monkeypatch, calls)

    r = await client.post("/api/runs", headers=auth, json={
        "scenarioId": "sc-test", "dataSetIds": ["ds-001"], "batchId": "b-org",
        "nRuns": 2, "parallel": 1, "schemeId": "rs-001", "schemeName": "冒烟",
    })
    assert r.status_code == 201, r.text
    origin = r.json()["executionId"]

    r = await client.post(f"/api/executions/{origin}/rerun", headers=auth)
    assert r.status_code == 201, r.text
    new_id = r.json()["executionId"]
    assert new_id != origin

    from app.core.db import SessionLocal
    from app.models import Execution

    async with SessionLocal() as s:
        new_ex = await s.get(Execution, new_id)
        origin_ex = await s.get(Execution, origin)
        assert new_ex is not None and origin_ex is not None
        cfg = new_ex.config_json or {}
        # 配方保真:数据集 / 方案溯源 / 参数逐键还原
        assert cfg.get("dataSetIds") == ["ds-001"]
        assert cfg.get("schemeId") == "rs-001" and cfg.get("schemeName") == "冒烟"
        assert cfg.get("nRuns") == 2
        # 重跑是新的一次独立发起:不带原批
        assert new_ex.batch_id is None and cfg.get("batchId") is None
        assert origin_ex.batch_id == "b-org"


async def test_rerun_missing_scenario_404(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    from app.core.db import SessionLocal
    from app.models import Execution, User

    async with SessionLocal() as s:
        alice = (
            await s.execute(select(User).where(User.username == "alice"))
        ).scalar_one()
        ex = Execution(scenario_id="sc-gone", owner_id=alice.id, status="done",
                       total_runs=1, passed=1,
                       config_json={"runId": "r-x", "scenarioId": "sc-gone"})
        s.add(ex)
        await s.commit()
        await s.refresh(ex)
        eid = ex.id
    r = await client.post(f"/api/executions/{eid}/rerun", headers=auth)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "scenario_not_found"


# ── precheck(§1.6:失效判定服务端唯一实现)────────────────────────
async def _seed_empty_ds(client: AsyncClient, headers: dict) -> None:
    """存在性即够的数据集(空行;预检/配方重建不消费行内容)。"""
    r = await client.post(
        "/api/scenarios/sc-test/data-sets",
        headers=headers,
        json={"name": "ds", "rows": [{}]},
    )
    assert r.status_code == 201, r.text


def _steps_draft(services: dict | None = None, body: dict | None = None) -> dict:
    steps = [{
        "kind": "step", "description": "下单",
        "api": {"service": "fin.order", "method": "POST", "path": "/x"},
        "request": {"kind": "request", "body": body if body is not None else {"amount": 1}},
        "strategy": [],
    }]
    d = _draft(steps=steps)
    if services is not None:
        d["definition"]["config"]["services"] = services
    return d


async def _setup_scenario(
    client: AsyncClient, headers: dict, *, services: dict | None = None,
) -> None:
    r = await client.post(
        "/api/scenarios", headers=headers,
        json={
            **_steps_draft(services=services),
            "assertion_registry": {"entries": [
                {"id": "inj-live", "name": "金额", "value": -1, "asserts": [],
                 "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"}},
                {"id": "inj-dead", "name": "缺失字段", "value": 1, "asserts": [],
                 "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.nope"}},
            ]},
        },
    )
    assert r.status_code == 201, r.text


async def _make_scheme(client: AsyncClient, headers: dict, name: str, **over) -> str:
    body = {"name": name, "dataSetSelection": [], "injectionEntryIds": [],
            "serviceBindings": {}, "stepTo": None, "nRuns": 1, "parallel": 1,
            "plugins": None, "logSub": None}
    body.update(over)
    r = await client.post("/api/scenarios/sc-test/run-schemes", headers=headers,
                          json=body)
    assert r.status_code == 201, r.text
    return r.json()["schemeId"]


async def test_precheck_reports_dead_dataset_dangling_and_unbound(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    auth = await _member(client, "alice")
    await _setup_scenario(client, auth)          # steps 引用 fin.order,声明 services 缺
    await _seed_empty_ds(client, auth)

    good = await _make_scheme(client, auth, "好方案",
                              injectionEntryIds=["inj-live"],
                              serviceBindings={"fin.order": {"url": "http://fin"}})
    bad = await _make_scheme(client, auth, "坏方案",
                             dataSetSelection=[{"datasetId": "ds-gone", "rowIndexes": []}],
                             injectionEntryIds=["inj-live", "inj-dead"])

    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": good},
        {"scenarioId": "sc-test", "schemeId": bad},
    ])
    assert r.status_code == 200, r.text
    res = {x["schemeId"]: x for x in r.json()}
    good_res, bad_res = res[good], res[bad]
    # 好方案:数据集在、条目活、绑定给了 URL → 可跑
    assert good_res["schemeValid"] is True
    assert good_res["deadDatasetIds"] == [] and good_res["danglingEntryIds"] == []
    assert good_res["unboundServices"] == []
    # 坏方案:数据集已删 + 条目悬空;换一个方案就能跑(不是用例禁跑)
    assert bad_res["schemeValid"] is False
    assert bad_res["deadDatasetIds"] == ["ds-gone"]
    assert bad_res["danglingEntryIds"] == ["inj-dead"]
    # fin.order 无声明 URL、坏方案未绑 → 未落点(好方案绑了 URL 所以干净)
    assert bad_res["unboundServices"] == ["fin.order"]


async def test_precheck_found_and_scheme_found_gates(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    auth = await _member(client, "alice")
    await _setup_scenario(client, auth)
    gone_scheme = await _make_scheme(client, auth, "将删方案")

    # 别人的私有场景:found=false(不泄露存在性,§5.3)
    bob = await _member(client, "bob")
    r = await client.post("/api/run/precheck", headers=bob, json=[
        {"scenarioId": "sc-test", "schemeId": gone_scheme},
    ])
    assert r.status_code == 200
    item = r.json()[0]
    assert item["found"] is False and item["schemeValid"] is False

    # 方案不存在:schemeFound=false
    r = await client.post("/api/run/precheck", headers=auth, json=[
        {"scenarioId": "sc-test", "schemeId": "rs-999"},
        {"scenarioId": "sc-none", "schemeId": gone_scheme},
    ])
    assert r.status_code == 200
    items = r.json()
    assert items[0]["schemeFound"] is False and items[0]["schemeValid"] is False
    assert items[1]["found"] is False
