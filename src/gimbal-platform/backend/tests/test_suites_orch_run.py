"""Suite 层重构第 1 步:编排模式运行(suite_graph 全链)。

《Suite 层重构设计方案》第 3/5 处 + run 分流:
- /suites/{id}/run 按 mode 分流:chain/fanout/compose → 一次编排执行
  (入队物化,worker 不回读 Suite;kind=suite_graph、suite_id、占位
  scenario_id、快照=graph_spec+rev);
- 重跑拦截:suite_graph 执行 POST /executions/{id}/rerun → 409 附链接;
- /suites/{id}/runs:只返回本人发起(不变量 2),编排执行逐条;
- rerun-failed:以失败单元为 control.only 重新运行当前 Suite。
"""
from __future__ import annotations

import asyncio
import json
import pathlib

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.execution import Execution, ExecutionRow, ExecutionSnapshot
from tests.helpers import make_draft, register_and_login

STEPS = [{
    "kind": "step", "description": "调用",
    "call": {"service": "fin.order", "method": "POST", "path": "/x"},
    "request": {"kind": "request", "body": {"amount": 1}},
    "strategy": [],
}]


async def _mk(client: AsyncClient, h: dict, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=STEPS))
    assert r.status_code in (200, 201), r.text


def _events(*units: tuple[str, str], gates: dict | None = None) -> list[dict]:
    """(ref, status) 列表 → start/end 事件对(+可选 gates.evaluated)
    + run.finished(exit 0)。"""
    evs: list[dict] = []
    seq = 2
    for ref, st in units:
        evs.append({"event_type": "scenario.start", "seq": seq,
                    "unit": ref, "scenario_id": "sc-x", "timestamp":
                    f"2026-10-09T07:00:{seq:02d}+00:00"})
        seq += 1
        evs.append({"event_type": "scenario.end", "seq": seq,
                    "unit": ref, "scenario_id": "sc-x", "status": st,
                    "timestamp": f"2026-10-09T07:00:{seq:02d}+00:00"})
        seq += 1
    if gates is not None:
        evs.append({"event_type": "gates.evaluated", "seq": seq,
                    "gates": [gates], "passed": gates.get("passed", True),
                    "exit_code": 0})
        seq += 1
    evs.append({"event_type": "run.finished", "seq": seq,
                "exit_code": 0, "attempts": seq})
    return evs


async def _wait_final(exec_id: int) -> Execution:
    ex = None
    for _ in range(400):
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, exec_id)
        if ex and ex.status in ("done", "failed", "canceled"):
            return ex
        await asyncio.sleep(0.05)
    assert ex is not None, "execution 未落库"
    raise AssertionError(f"execution 未终态: {ex.status}")


async def _mk_compose_suite(
    client: AsyncClient, h: dict, name: str,
) -> tuple[int, dict]:
    """两单元 compose(auth → order),mode_config 带 ref/needs。"""
    await _mk(client, h, "sc-or-auth")
    await _mk(client, h, "sc-or-order")
    r = await client.post("/api/suites", headers=h,
                          json={"name": name, "description": ""})
    sid = r.json()["suiteId"]
    cfg = {"units": {
        "sc-or-auth": {"ref": "auth"},
        "sc-or-order": {"ref": "order", "needs": ["sc-or-auth"]},
    }, "gates": [{"metric": "pass_rate", "op": "gte", "value": 1.0}]}
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json={
        "rev": 0, "mode": "compose",
        "members": [{"scenarioId": "sc-or-auth"},
                    {"scenarioId": "sc-or-order"}],
        "modeConfig": cfg})
    assert r.status_code == 200, r.text
    return sid, r.json()


def _patch_pipeline(monkeypatch, events: list[dict]) -> list[dict]:
    """mock 物化链:convert 透传 + graph_dispatch.launch 喂事件;返回
    launched 清单(每次下发的 SuiteGraph)。"""
    launched: list[dict] = []

    async def _launch(case_path, *, on_event=None, **_kw):
        launched.append(json.loads(
            pathlib.Path(case_path).read_text(encoding="utf-8")))
        for ev in events:
            if on_event is not None:
                on_event(dict(ev))
            await asyncio.sleep(0)
        from app.services.gimbal_launcher import LaunchResult
        all_pass = all(
            e.get("status") == "passed" for e in events
            if e.get("event_type") == "scenario.end")
        return LaunchResult(launch_status="ok", exit_code=0 if all_pass else 1,
                            total=1, passed=1)

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import graph_dispatch as gd, plate_client as pc
    monkeypatch.setattr(gd, "launch", _launch)
    monkeypatch.setattr(pc, "convert", _fake_convert)
    return launched


async def test_orchestration_run_suite_graph(client, monkeypatch):
    """编排执行全链:分流/归属/占位/快照/逐单元台账/needs 换 ref。"""
    await register_and_login(client, "or_boot", "or_bootpass123")
    h = await register_and_login(client, "or_owner", "or_ownerpass123")
    sid, detail = await _mk_compose_suite(client, h, "编排集")
    assert detail["rev"] == 1
    launched = _patch_pipeline(monkeypatch, _events(
        ("auth", "passed"), ("order", "passed"),
        gates={"metric": "pass_rate", "op": "gte", "value": 1.0,
               "actual": 1.0, "passed": True}))

    r = await client.post(f"/api/suites/{sid}/run", headers=h)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["mode"] == "compose" and out["units"] == 2
    assert out["batchId"].startswith(f"suite-{sid}-")
    ex = await _wait_final(out["executionId"])
    assert ex.status == "done"

    # 归属(第 5 处):kind/suite_id/占位 scenario_id/台账名
    assert ex.kind == "suite_graph" and ex.suite_id == sid
    assert ex.scenario_id == f"suite-{sid}"
    assert ex.scenario_name == "编排集"

    # 快照 = 入队时解析完成的 graph_spec + 当时 rev(不变量 5 证据)
    async with db_module.SessionLocal() as s:
        snap = (await s.execute(
            sa.select(ExecutionSnapshot.snapshot).where(
                ExecutionSnapshot.execution_id == ex.id))).scalar_one()
    assert snap["rev"] == 1 and snap["suiteId"] == sid
    assert snap["graphSpec"]["mode"] == "compose"

    # 下发产物:needs 由 scenarioId 换成 ref;无 control
    g = launched[0]
    by_ref = {u["ref"]: u for u in g["units"]}
    assert by_ref["order"]["needs"] == ["auth"]
    assert "control" not in g

    # 台账(第 3 处):seq0 图行 + 逐单元行
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(
            sa.select(ExecutionRow).where(
                ExecutionRow.execution_id == ex.id)
            .order_by(ExecutionRow.seq))).scalars().all()
    assert [(x.seq, x.unit_id, x.status) for x in rows] == [
        (0, "graph", "passed"), (1, "auth", "passed"),
        (2, "order", "passed")]
    assert rows[1].started_at is not None and rows[1].finished_at is not None

    # 判定门结论(第 4 处):执行器事件经通道落 config_json(21 页数据源)
    async with db_module.SessionLocal() as s:
        ex2 = await s.get(Execution, ex.id)
    ge = ex2.config_json.get("gatesEvaluated")
    assert ge == {"gates": [{"metric": "pass_rate", "op": "gte",
                             "value": 1.0, "actual": 1.0, "passed": True}],
                  "passed": True}


async def test_runs_endpoint_batches(client):
    """/runs 聚合归并:同批多成员执行合并成一条 batch 项、计数累加、
    finishedAt 取批内最晚(比较用原始 datetime —— 浏览器验收抓过
    datetime>str 的 500);单人执行单列。"""
    from datetime import datetime, timezone
    from app.models.execution import Execution as Ex

    await register_and_login(client, "rb_boot", "rb_bootpass123")
    h = await register_and_login(client, "rb_owner", "rb_ownerpass123")
    await _mk(client, h, "sc-rb-1")
    await _mk(client, h, "sc-rb-2")
    r = await client.post("/api/suites", headers=h,
                          json={"name": "归并集", "description": ""})
    sid = r.json()["suiteId"]
    roster = (await client.get("/api/users/roster", headers=h)).json()["items"]
    uid = next(u["id"] for u in roster if u["username"] == "rb_boot")
    async with db_module.SessionLocal() as s:
        from app.models.user import User
        uid = (await s.execute(sa.select(User.id).where(
            User.username == "rb_owner"))).scalar_one()
        base = datetime.now(timezone.utc).replace(tzinfo=None)
        for i, (sidsc, fin) in enumerate((
                ("sc-rb-1", base.replace(microsecond=100000)),
                ("sc-rb-2", base.replace(microsecond=200000)))):
            s.add(Ex(scenario_id=sidsc, scenario_name=sidsc, kind="scenario",
                     suite_id=sid, owner_id=uid, owner_name="rb_owner",
                     status="done", total_runs=1, passed=1, failed=0,
                     skipped=0, batch_id="suite-batch-1",
                     created_at=base, finished_at=fin,
                     config_json={"batchId": "suite-batch-1"}))
        s.add(Ex(scenario_id="sc-rb-1", scenario_name="sc-rb-1",
                 kind="scenario", suite_id=sid, owner_id=uid,
                 owner_name="rb_owner", status="done", total_runs=1,
                 passed=1, failed=0, skipped=0, batch_id=None,
                 created_at=base, finished_at=base,
                 config_json={}))
        await s.commit()

    r = await client.get(f"/api/suites/{sid}/runs", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    by_kind = {i["kind"]: i for i in items}
    assert set(by_kind) == {"batch", "single"}
    b = next(i for i in items if i["kind"] == "batch")
    assert b["batchId"] == "suite-batch-1" and b["status"] == "done"
    assert len(b["executions"]) == 2 and b["totalRuns"] == 2 and b["passed"] == 2
    assert b["finishedAt"] is not None      # 归并比较不再 500
    single = next(i for i in items if i["kind"] == "single")
    assert single["executions"] and single["batchId"].startswith("single-")


async def test_rerun_intercepted_and_runs_visibility(client, monkeypatch):
    """suite_graph 重跑 409 附链接;/runs 只返回本人发起(不变量 2)。"""
    await register_and_login(client, "rv_boot", "rv_bootpass123")
    owner = await register_and_login(client, "rv_owner", "rv_ownerpass123")
    bob = await register_and_login(client, "rv_bob", "rv_bobpass123")
    sid, _ = await _mk_compose_suite(client, owner, "可见集")
    _patch_pipeline(monkeypatch, _events(("auth", "passed"),
                                         ("order", "passed")))
    r = await client.post(f"/api/suites/{sid}/run", headers=owner)
    exec_id = r.json()["executionId"]
    await _wait_final(exec_id)

    # 重跑拦截:409 + Suite 链接
    r = await client.post(f"/api/executions/{exec_id}/rerun", headers=owner)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["code"] == "suite_graph_rerun_unsupported"
    assert d["link"] == f"/suites/{sid}"

    # 属主:runs 逐条可见;被引用者(admin 同)只见自己发起的(空)
    r = await client.get(f"/api/suites/{sid}/runs", headers=owner)
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "suite_graph"
    assert items[0]["mode"] == "compose" and items[0]["status"] == "done"

    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "rv_bob")
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201, r.text
    r = await client.get(f"/api/suites/{sid}/runs", headers=bob)
    assert r.status_code == 200 and r.json()["items"] == []
    # 真 admin = fresh_db 首个注册者(rv_boot);admin 同样只见自己发起的
    admin = await register_and_login(client, "rv_boot", "rv_bootpass123")
    r = await client.get(f"/api/suites/{sid}/runs", headers=admin)
    assert r.status_code == 200 and r.json()["items"] == []


async def test_rerun_failed_units(client, monkeypatch):
    """rerun-failed:失败单元为 control.only 重跑当前 Suite;非发起人 403。"""
    await register_and_login(client, "rf_boot", "rf_bootpass123")
    owner = await register_and_login(client, "rf_owner", "rf_ownerpass123")
    bob = await register_and_login(client, "rf_bob", "rf_bobpass123")
    sid, _ = await _mk_compose_suite(client, owner, "重跑集")
    # 第一次:auth 过、order 败 → 执行失败
    launched = _patch_pipeline(monkeypatch, _events(
        ("auth", "passed"), ("order", "failed")))
    r = await client.post(f"/api/suites/{sid}/run", headers=owner)
    exec_id = r.json()["executionId"]
    ex = await _wait_final(exec_id)
    assert ex.status == "failed"

    # 非发起人(引用者)重跑失败单元 → 403(不变量 2)
    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "rf_bob")
    await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "ref"})
    r = await client.post(
        f"/api/suites/{sid}/runs/{exec_id}/rerun-failed", headers=bob)
    assert r.status_code == 403, r.text

    # 属主:重跑失败单元 → control.only=[order](上游 auth 随闭包重跑)
    launched2 = _patch_pipeline(monkeypatch, _events(("auth", "passed"),
                                                      ("order", "passed")))
    r = await client.post(
        f"/api/suites/{sid}/runs/{exec_id}/rerun-failed", headers=owner)
    assert r.status_code == 201, r.text
    ex2 = await _wait_final(r.json()["executionId"])
    assert ex2.status == "done"
    assert len(launched2) == 1
    assert launched2[0]["control"] == {"only": ["order"]}

    # 全过后再 rerun-failed → 409 no_failed_units(对最近一次执行)
    r = await client.post(
        f"/api/suites/{sid}/runs/{ex2.id}/rerun-failed", headers=owner)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "no_failed_units"


async def test_run_control_only_and_to_node(client, monkeypatch):
    """第 2 步:run 带 control(only / toNode)透传到下发产物;
    from_node 刻意不开放(schema extra=forbid 拒收)。"""
    await register_and_login(client, "rc_boot", "rc_bootpass123")
    h = await register_and_login(client, "rc_owner", "rc_ownerpass123")
    sid, _ = await _mk_compose_suite(client, h, "控制集")

    launched = _patch_pipeline(monkeypatch, _events(
        ("auth", "passed"), ("order", "passed")))
    r = await client.post(f"/api/suites/{sid}/run", headers=h,
                          json={"only": ["order"]})
    assert r.status_code == 201, r.text
    ex = await _wait_final(r.json()["executionId"])
    assert ex.status == "done"
    assert launched[0]["control"] == {"only": ["order"]}

    # from_node 不开放:透传即 422(schema extra=forbid)
    r = await client.post(f"/api/suites/{sid}/run", headers=h,
                          json={"fromNode": "auth"})
    assert r.status_code == 422, r.text


async def test_list_latest_run_summary_own_initiated_only(client, monkeypatch):
    """第 2 步:GET /suites 附最近运行摘要 —— 只算本人发起(不变量 2);
    编排执行 kind=suite_graph,无本人发起 = null。"""
    await register_and_login(client, "lr_boot", "lr_bootpass123")
    h = await register_and_login(client, "lr_owner", "lr_ownerpass123")
    other = await register_and_login(client, "lr_other", "lr_otherpass123")
    sid, _ = await _mk_compose_suite(client, h, "摘要集")

    # 本人发起前:latestRun 为 null
    r = await client.get("/api/suites", headers=h, params={"scope": "mine"})
    item = next(x for x in r.json()["items"] if x["suiteId"] == sid)
    assert item["latestRun"] is None

    launched = _patch_pipeline(monkeypatch, _events(
        ("auth", "passed"), ("order", "passed")))
    r = await client.post(f"/api/suites/{sid}/run", headers=h)
    assert r.status_code == 201, r.text
    await _wait_final(r.json()["executionId"])

    r = await client.get("/api/suites", headers=h, params={"scope": "mine"})
    item = next(x for x in r.json()["items"] if x["suiteId"] == sid)
    assert item["latestRun"]["kind"] == "suite_graph"
    assert item["latestRun"]["status"] == "done"
    assert item["latestRun"]["executionId"] > 0
    assert item["latestRun"]["batchId"].startswith(f"suite-{sid}-")
