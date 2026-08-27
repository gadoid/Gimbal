"""执行时场景快照(P-review):dispatch 把 scenario payload 快照进
Execution 行,读侧端点按 owner 暴露;删除执行即删快照(与 case 案卷
同语义,行删即证据链消失)。

快照价值 = 场景后改不影响历史单的"当时跑了什么":本模块用
「跑完 → 改场景 → 快照不变」锁定该不变量。
"""
from __future__ import annotations

import asyncio

import sqlalchemy as sa
from httpx import AsyncClient

from tests.helpers import launch_ok as _ok, make_draft, register_and_login

STEPS = [{
    "api": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]


def _launch_and_convert_mocks(monkeypatch, sent_convert: list | None = None):
    """launch 恒成功 + plate convert 原样回显(基线执行最小依赖)。"""
    from app.services import gimbal_launcher as gl, plate_client as pc

    async def _fake_launch(case_path, *, step_to=None, report_dir=None,
                           cwd=None, timeout=None, engine_log_path=None):
        return _ok()

    async def _fake_convert(scenario):
        if sent_convert is not None:
            sent_convert.append(scenario)
        return {"consumer": "platform", "converted": dict(scenario)}

    monkeypatch.setattr(gl, "launch", _fake_launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)


async def _run_to_done(client: AsyncClient, headers: dict, scenario_id: str) -> int:
    """POST /api/runs + 轮询至终态,返回 executionId。"""
    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": scenario_id, "dataSetIds": [],
    })
    assert r.status_code == 201, r.text
    execution_id = r.json()["executionId"]

    from app.core import db as db_module
    from app.models.execution import Execution

    for _ in range(100):
        async with db_module.SessionLocal() as s:
            row = await s.get(Execution, execution_id)
        if row is not None and row.status == "done":
            return execution_id
        await asyncio.sleep(0.05)
    raise AssertionError(f"execution {execution_id} never reached done")


async def test_dispatch_snapshots_scenario_payload(
    client: AsyncClient, monkeypatch
) -> None:
    """dispatch 时快照 = 当时存储的 payload;场景后改,快照不变。"""
    headers = await register_and_login(client)
    draft = make_draft("sc-snap", steps=STEPS, name="快照版1")
    await client.post("/api/scenarios", headers=headers, json=draft)
    _launch_and_convert_mocks(monkeypatch)

    execution_id = await _run_to_done(client, headers, "sc-snap")

    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as s:
        row = await s.get(Execution, execution_id)
        assert row is not None
        snapshot = row.scenario_snapshot
        # 快照 = 执行时的 draft 容器(definition 含 authored 步骤原文)
        assert snapshot is not None
        assert snapshot["definition"]["meta"]["name"] == "快照版1"
        assert snapshot["definition"]["steps"] == STEPS

    # 改场景(改名)→ 快照保持执行时版本不变
    edited = make_draft("sc-snap", steps=STEPS, name="快照版2")
    r = await client.put("/api/scenarios/sc-snap", headers=headers, json=edited)
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as s:
        row_after = await s.get(Execution, execution_id)
        assert row_after is not None
        assert row_after.scenario_snapshot["definition"]["meta"]["name"] == "快照版1"


async def test_snapshot_endpoint_owner_scoped(
    client: AsyncClient, monkeypatch
) -> None:
    """GET /executions/{id}/scenario-snapshot:owner 拿到快照;他人 404
    (get_owned_execution 不泄露他人执行存在性)。"""
    headers = await register_and_login(client)
    await client.post(
        "/api/scenarios", headers=headers, json=make_draft("sc-snap-acl")
    )
    _launch_and_convert_mocks(monkeypatch)
    execution_id = await _run_to_done(client, headers, "sc-snap-acl")

    r = await client.get(
        f"/api/executions/{execution_id}/scenario-snapshot", headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["definition"]["meta"]["scenarioId"] == "sc-snap-acl"
    assert "orchestration" in body

    # 另一个用户:404(与执行详情同款属主收紧)
    other = await register_and_login(client, username="bob")
    r2 = await client.get(
        f"/api/executions/{execution_id}/scenario-snapshot", headers=other
    )
    assert r2.status_code == 404


async def test_snapshot_endpoint_404_for_rows_without_snapshot(
    client: AsyncClient,
) -> None:
    """存量行(快照功能上线前)无快照 → 404 带明确 code;详情 hasScenarioSnapshot=False。"""
    headers = await register_and_login(client)

    from app.core import db as db_module
    from app.models.execution import Execution

    async with db_module.SessionLocal() as s:
        legacy = Execution(
            scenario_id="sc-legacy",
            owner_id=1,
            status="done",
            total_runs=0,
            passed=0,
            failed=0,
            config_json={"runId": "run-legacy"},
        )
        s.add(legacy)
        await s.commit()
        legacy_id = legacy.id

    r = await client.get(
        f"/api/executions/{legacy_id}/scenario-snapshot", headers=headers
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "scenario_snapshot_not_found"

    detail = await client.get(f"/api/executions/{legacy_id}", headers=headers)
    assert detail.status_code == 200
    # 序列化 snake_case,与 scenario_id 等既有键同款
    assert detail.json()["has_scenario_snapshot"] is False


async def test_delete_execution_removes_snapshot(
    client: AsyncClient, monkeypatch
) -> None:
    """删除执行 = 快照一并删除(行删即删,与 case 案卷清理同哲学)。"""
    headers = await register_and_login(client)
    await client.post(
        "/api/scenarios", headers=headers, json=make_draft("sc-snap-del")
    )
    _launch_and_convert_mocks(monkeypatch)
    execution_id = await _run_to_done(client, headers, "sc-snap-del")

    r = await client.get(
        f"/api/executions/{execution_id}/scenario-snapshot", headers=headers
    )
    assert r.status_code == 200

    r = await client.delete(f"/api/executions/{execution_id}", headers=headers)
    assert r.status_code == 204

    r = await client.get(
        f"/api/executions/{execution_id}/scenario-snapshot", headers=headers
    )
    assert r.status_code == 404
