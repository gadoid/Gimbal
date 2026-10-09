"""Suite 层重构第 3 步:POST /suites/{id}/validate(不入队的预检)。

- 编排模式:物化 + 执行器编译 —— 成环(CYCLE)在运行前报出并定位单元;
- 多行方案只跑一行的提示(约束 5,未选行 → 裸基线 / 已选 → 只跑该行);
- 聚合:逐成员方案有效性(run_precheck 同一份实现)+ 无方案 → 裸基线提示;
- 在途批次 → error + inFlight;空 Suite → suite_empty;全过 → ok=true。
"""
from __future__ import annotations

import asyncio
import json
import pathlib

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.execution import Execution
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


def _patch_convert(monkeypatch) -> None:
    """plate convert 透传 + 执行器编译打桩(返回 [] = 编译通过)。

    编译桩打在 suites 路由的 ``_executor_compile`` 边界上 —— 单测不必
    伪造合法 gimbal 场景形状(物化链的 fake convert 产物过不了 RunUnion
    schema);执行器编译本体的行为由 gimbal 侧测试覆盖。
    """
    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}
    from app.services import plate_client as pc
    monkeypatch.setattr(pc, "convert", _fake_convert)
    from app.routers import suites as suites_router
    monkeypatch.setattr(suites_router, "_executor_compile", lambda g: [])


def _patch_compile_error(monkeypatch, code: str, unit: str | None = None):
    """编译桩改为抛 CompileError(定位单元)。"""
    from gimbal.compiler.errors import CompileError
    from app.routers import suites as suites_router

    def _raise(graph):
        raise CompileError(
            f"[{code}] 预检桩注入的编译错误",
            code=code, location={"unit": unit} if unit else None)
    monkeypatch.setattr(suites_router, "_executor_compile", _raise)


async def _mk_suite(client: AsyncClient, h: dict, name: str, *,
                    mode: str = "compose",
                    units: dict | None = None,
                    members: list[dict] | None = None) -> int:
    await _mk(client, h, "sc-va")
    await _mk(client, h, "sc-vb")
    r = await client.post("/api/suites", headers=h,
                          json={"name": name, "description": ""})
    sid = r.json()["suiteId"]
    body = {
        "rev": 0, "mode": mode,
        "members": members or [{"scenarioId": "sc-va"},
                               {"scenarioId": "sc-vb"}],
        "modeConfig": {"units": units or {
            "sc-va": {"ref": "a"}, "sc-vb": {"ref": "b", "needs": ["sc-va"]},
        }}}
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json=body)
    assert r.status_code == 200, r.text
    return sid


async def test_validate_ok_compose(client, monkeypatch):
    """两单元无环 compose:预检通过(ok=true,pass 条目,判定门计数)。"""
    await register_and_login(client, "va_boot", "va_bootpass123")
    h = await register_and_login(client, "va_ok", "va_okpass123")
    _patch_convert(monkeypatch)
    sid = await _mk_suite(client, h, "通过集", units={
        "sc-va": {"ref": "a"},
        "sc-vb": {"ref": "b", "needs": ["sc-va"]},
    }, )
    # 加判定门(再整体保存一次推进 rev)
    r = await client.get(f"/api/suites/{sid}", headers=h)
    cfg = r.json()["modeConfig"]
    cfg["gates"] = [{"metric": "pass_rate", "op": "gte", "value": 1.0}]
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json={
        "rev": r.json()["rev"], "mode": "compose",
        "members": [{"scenarioId": "sc-va"}, {"scenarioId": "sc-vb"}],
        "modeConfig": cfg})
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["unitCount"] == 2 and out["estimatedRuns"] == 2
    assert out["gates"] == 1 and out["inFlight"] is None
    assert any(i["code"] == "pass" and i["level"] == "ok" for i in out["items"])


async def test_validate_cycle_reported_before_run(client, monkeypatch):
    """needs 成环(a→b→a):保存可过(结构校验不查环),编译报
    CYCLE 并定位单元 —— 运行前拦下,而不是执行器运行期才炸。"""
    await register_and_login(client, "vc_boot", "vc_bootpass123")
    h = await register_and_login(client, "vc_cyc", "vc_cycpass123")
    _patch_convert(monkeypatch)
    _patch_compile_error(monkeypatch, "CYCLE", unit="a")
    sid = await _mk_suite(client, h, "成环集", units={
        "sc-va": {"ref": "a", "needs": ["sc-vb"]},
        "sc-vb": {"ref": "b", "needs": ["sc-va"]},
    })
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is False
    cyc = [i for i in out["items"] if i["code"] == "CYCLE"]
    assert cyc, out["items"]
    assert cyc[0].get("units") == ["sc-va"]   # ref a → 定位到成员


async def test_validate_multi_row_warning(client, monkeypatch):
    """约束 5:方案选多行但单元未选行 → 裸基线警告(action=unit 可直达);
    选定行 → 只跑该行的提示。"""
    await register_and_login(client, "vm_boot", "vm_bootpass123")
    h = await register_and_login(client, "vm_row", "vm_rowpass123")
    _patch_convert(monkeypatch)
    # 场景(声明 amount 变量,数据集列须 ⊆ 已声明变量)+ 两行数据集
    # (datasetId 服务端生成,取回执里的真实 id)
    await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-mr", steps=STEPS, vars_map={"amount": 1}))
    r = await client.post("/api/scenarios/sc-mr/data-sets", headers=h, json={
        "name": "两行集", "description": "",
        "rows": [{"amount": 1}, {"amount": 2}],
    })
    assert r.status_code == 201, r.text
    ds_id = r.json()["datasetId"]
    # 非默认方案引用该数据集(默认方案被 _sanitize_default 清空 selection,
    # 多行引用走专属方案 —— 单元以 schemeId 选定,正是约束 5 的路径)
    r = await client.post("/api/scenarios/sc-mr/run-schemes", headers=h, json={
        "name": "多行方案", "dataSetIds": [ds_id],
        "dataSetSelection": [{"datasetId": ds_id}]})
    assert r.status_code == 201, r.text
    scheme_id = r.json()["schemeId"]

    r = await client.post("/api/suites", headers=h,
                          json={"name": "多行集", "description": ""})
    sid = r.json()["suiteId"]
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json={
        "rev": 0, "mode": "chain",
        "members": [{"scenarioId": "sc-mr"}],
        "modeConfig": {"units": {
            "sc-mr": {"ref": "mr", "schemeId": scheme_id}}}})
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    out = r.json()
    warn = [i for i in out["items"] if i["code"] == "row_unselected"]
    assert warn and warn[0]["action"] == "unit"
    assert out["ok"] is True   # 警告不拦跑

    # 选定行 → 变成 row_single(只跑该行),无裸基线提示
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json={
        "rev": 1, "mode": "chain",
        "members": [{"scenarioId": "sc-mr"}],
        "modeConfig": {"units": {
            "sc-mr": {"ref": "mr", "schemeId": scheme_id,
                      "row": {"datasetId": ds_id, "rowIndex": 1}}}}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    out = r.json()
    assert any(i["code"] == "row_single" for i in out["items"])
    assert not any(i["code"] == "row_unselected" for i in out["items"])


async def test_validate_aggregate_member_precheck(client):
    """聚合:逐成员可运行性复用 run_precheck._precheck_one —— steps 引用
    未绑定 URL 的服务 → unbound_services 提示;空 Suite → suite_empty 拦跑。"""
    await register_and_login(client, "vg_boot", "vg_bootpass123")
    h = await register_and_login(client, "vg_agg", "vg_aggpass123")
    await client.post("/api/scenarios", headers=h, json=make_draft(
        "sc-agg", steps=STEPS))

    r = await client.post("/api/suites", headers=h,
                          json={"name": "聚合集", "description": ""})
    sid = r.json()["suiteId"]
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json={
        "rev": 0, "mode": "aggregate",
        "members": [{"scenarioId": "sc-agg"}],
        "modeConfig": {"units": {}}})
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    out = r.json()
    assert out["mode"] == "aggregate"
    bad = [i for i in out["items"] if i["code"] == "unbound_services"]
    assert bad and "fin.order" in bad[0]["message"]
    assert out["estimatedRuns"] >= 1

    # 空 Suite → 拦跑
    r = await client.post("/api/suites", headers=h,
                          json={"name": "空集", "description": ""})
    empty = r.json()["suiteId"]
    r = await client.post(f"/api/suites/{empty}/validate", headers=h)
    out = r.json()
    assert out["ok"] is False
    assert any(i["code"] == "suite_empty" for i in out["items"])


async def test_validate_in_flight(client, monkeypatch):
    """在途批次 → error 条目 + inFlight 回执(30 页「查看」)。"""
    await register_and_login(client, "vf_boot", "vf_bootpass123")
    h = await register_and_login(client, "vf_run", "vf_runpass123")
    _patch_convert(monkeypatch)
    sid = await _mk_suite(client, h, "在途集")
    batch = f"suite-{sid}-running-x"
    async with db_module.SessionLocal() as s:
        s.add(Execution(
            scenario_id=f"suite-{sid}", owner_id=1, total_runs=1,
            scenario_name="在途集", batch_id=batch, status="running",
            kind="suite_graph", suite_id=sid))
        await s.commit()
        # owner_id 修正为当前用户(上面 1 是占位)
        uid_row = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='vf_run'"))).scalar_one()
        await s.execute(sa.text(
            "UPDATE executions SET owner_id=:u WHERE batch_id=:b"),
            {"u": uid_row, "b": batch})
        await s.commit()

    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    out = r.json()
    assert out["ok"] is False
    assert out["inFlight"] == {"batchId": batch}
    assert any(i["code"] == "suite_run_in_progress" for i in out["items"])
