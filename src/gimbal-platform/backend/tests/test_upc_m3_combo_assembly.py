"""UPC M3 执行装配:组合垫底(八装配面同基础,v4 §3.2)+ 里程碑出口
「复跑 M2 样例完整装配」e2e。

account_combo.scheme_bindings_with_combo / combo_base / pad_bindings 是
M2 立好的读取面(模块 docstring:「执行装配的垫底合并随 M3 执行装配
接入」)—— 本文件钉七面接入后的**同基础断言**(§9 测试面):同一
方案显式列绑定组合、payload serviceBindings 为空时,各执行面生效身份
一律 = 组合条目(垫底),面内覆盖序不变;外加 M3 出口条件的完整装配
链路(blocked → 修复 → dispatch → done,config_json 见证垫底终值)。

查询面(第 8 面)按 §7.1(schemeId 解析 + 垫底)单独立项,不在本文件
—— 见 docs/upc-assembly-entry-registry.md。"""
from __future__ import annotations

import asyncio

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.execution import Execution
from app.services import run_dispatcher
from tests.conftest import seed_identity_fixture
from tests.helpers import default_space_id, make_draft, register_and_login

_STEPS = [{
    "kind": "step", "description": "查单",
    "call": {"service": "fin-service", "method": "GET", "path": "/o"},
    "request": {"kind": "request", "body": {}},
    "strategy": [],
}]
ALIAS = "m3qa-alias"


async def _seed(client: AsyncClient, tag: str):
    """M2 样例拓扑(§9 同基础布景):身份四件套 + 组合 + 场景(带
    fin-service 步骤)+ 数据集 + 默认方案 + 绑组合的回归方案(payload
    serviceBindings **空** —— 组合是身份唯一来源,垫底断言才有效)。"""
    me = f"m3c_{tag}"
    h = await register_and_login(client, me, "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias=ALIAS, username="u", password="p",
            service="fin-service", owner_id=uid)
        space = await default_space_id(s, uid)
        await s.commit()
    combo_id = (await client.post(
        f"/api/projects/{space}/account-combos", headers=h,
        json={"name": f"装配组合-{tag}", "entries": [
            {"service": "fin-service", "alias": ALIAS}]}
    )).json()["id"]
    sid = f"sc-m3c{tag}"
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid, steps=_STEPS,
                                          vars_map={"x": 0}))
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/api/scenarios/{sid}/data-sets", headers=h,
                          json={"name": "行", "rows": [{"x": 1}, {"x": 2}]})
    assert r.status_code in (200, 201), r.text
    ds_id = r.json()["datasetId"]
    qa_id = (await client.post(f"/api/scenarios/{sid}/run-schemes",
                               headers=h,
                               json={"name": "回归方案", "isDefault": False,
                                     "accountComboId": combo_id,
                                     "dataSetSelection": [
                                         {"datasetId": ds_id,
                                          "rowIndexes": [0]}],
                                     "injectionEntryIds": [],
                                     "serviceBindings": {}, "options": {
                                         "step_from": None, "step_to": None,
                                         "n_runs": 1, "parallel": 1,
                                         "subscribe": None}})
             ).json()["schemeId"]
    return h, uid, combo_id, sid, ds_id, qa_id


# ── 同基础断言:七面各自消费垫底后的生效身份 ───────────────────────

async def test_face_token_recipe_pad(client: AsyncClient):
    """令牌面:_apply_scheme_recipe 覆写源 = {**组合, **方案}(v4 §3.2
    装载时合并)—— 方案 serviceBindings 空时,body 终值含组合条目。"""
    from app.models.composer_scenario import ComposerScenario
    from app.routers.runs import _apply_scheme_recipe
    from app.schemas.scenario_composer import RunRequest

    h, _uid, _combo, sid, _ds, qa_id = await _seed(client, "tk")
    async with db_module.SessionLocal() as s:
        scen = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        body = RunRequest(scenarioId=sid, schemeId=qa_id)
        await _apply_scheme_recipe(s, scen, body)
        await s.rollback()
    assert body.scheme_id == qa_id
    assert body.service_bindings["fin-service"].alias == ALIAS


async def test_face_preview_pad(client: AsyncClient):
    """预览面:组合 < 方案 < 请求(v4 §3.2)—— 预览按垫底后的生效
    绑定解析凭证终值(auths 命中组合别名)。"""
    h, _uid, _combo, sid, _ds, qa_id = await _seed(client, "pv")
    r = await client.post("/api/runs/preview", headers=h, json={
        "scenarioId": sid, "schemeId": qa_id})
    assert r.status_code == 200, r.text
    auths = r.json()["auths"]
    assert ALIAS in auths, auths
    assert auths[ALIAS]["bindingId"] > 0


async def test_face_precheck_pad(client: AsyncClient):
    """预检面:与执行同基础(v4 §3.2)—— 组合条目垫底后,组合别名
    不再被误报 identity_missing(missingAuths 为空)。"""
    h, _uid, _combo, sid, _ds, qa_id = await _seed(client, "pc")
    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": sid, "schemeId": qa_id}])
    assert r.status_code == 200, r.text
    one = r.json()[0]
    assert one["missingAuths"] == [], one
    assert one["repairBlocked"] is False


async def test_face_graph_unit_pad(client: AsyncClient):
    """Suite 图面:resolve_graph_units 取方案处垫底(v4 §3.2)——
    单元生效绑定 = {**组合, **方案, **单元级}(此处方案/单元皆空)。"""
    from app.services import graph_dispatch as gd

    _h, uid, _combo, sid, _ds, qa_id = await _seed(client, "gr")
    async with db_module.SessionLocal() as s:
        resolved = await gd.resolve_graph_units(
            s, [{"ref": "a", "scenarioId": sid, "schemeId": qa_id}],
            owner_id=uid)
        await s.rollback()
    unit = resolved[0]["unit"]
    assert unit["serviceBindings"]["fin-service"]["alias"] == ALIAS, unit


async def test_face_integration_shape_pad(client: AsyncClient):
    """集成面:_load_exec_shape 返回规范化 scheme_payload(v4 §3.2
    「合并终值写回该视图」)—— 绑定与视图三面(环境标签/指纹/slot)
    同源;ORM payload 不被写回。"""
    from app.models.composer_scenario import ComposerScenario
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import integration_runner as ir

    _h, _uid, _combo, sid, _ds, qa_id = await _seed(client, "ig")
    async with db_module.SessionLocal() as s:
        scen = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        scheme, scheme_payload, bindings, _row, _name = \
            await ir._load_exec_shape(s, qa_id, scen)
        await s.rollback()
    assert bindings["fin-service"]["alias"] == ALIAS
    assert scheme_payload["serviceBindings"]["fin-service"]["alias"] == ALIAS
    # ORM 行不被污染(视图副本;方案 wire 形状不含 accountComboId)
    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa.select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == qa_id))).scalar_one()
        assert "fin-service" not in (row.payload or {}).get(
            "serviceBindings") or {}, row.payload
        assert row.account_combo_id is not None


async def test_face_suite_direct_run_pad(client: AsyncClient):
    """Suite 直跑面:调用方垫底(v4 §3.2「取默认方案后先合并再传入,
    _req_from_scheme 纯函数签名不改」)—— 默认方案本例无组合,回归
    方案垫底后进配方。"""
    from app.routers.suites import _combo_padded_scheme, _req_from_scheme

    _h, _uid, combo_id, sid, ds_id, qa_id = await _seed(client, "sr")
    async with db_module.SessionLocal() as s:
        from app.services import scheme_store
        scheme = await scheme_store.get_row(s, sid, qa_id)
        revision = scheme.revision        # 会话内取纯值(rollback 后实例 detach)
        await s.rollback()
    # 模拟 list_schemes DTO 形态(accountComboId 随行)
    dto = {"schemeId": qa_id, "name": "回归方案", "isDefault": False,
           "accountComboId": combo_id, "revision": revision,
           "dataSetSelection": [{"datasetId": ds_id, "rowIndexes": [0]}],
           "injectionEntryIds": [], "serviceBindings": {},
           "options": {"step_from": None, "step_to": None, "n_runs": 1,
                       "parallel": 1, "subscribe": None}}
    async with db_module.SessionLocal() as s:
        padded = await _combo_padded_scheme(s, dto)
        await s.rollback()
    assert padded["serviceBindings"]["fin-service"]["alias"] == ALIAS
    req = _req_from_scheme(sid, padded, "batch-x")
    assert req.service_bindings["fin-service"].alias == ALIAS
    # 原函数对未垫底 DTO 签名不变(空绑定直传)
    req2 = _req_from_scheme(sid, dto, "batch-y")
    assert not req2.service_bindings


# ── M3 出口条件:复跑 M2 样例完整装配(blocked → 修复 → done)────

class _OkPool:
    """假执行器会话池:start/close 空转,run_case 直接成功(fanout
    teardown 测试同款 LaunchResult 形态)。构造签名对齐
    ServerSessionPool(size=...)。"""

    def __init__(self, *, size: int = 1) -> None:
        self.size = size

    async def start(self, *, engine_log_path=None, cwd=None,
                    on_log=None, log_counters=None) -> None:
        return None

    async def run_case(self, case_path, **kwargs):
        from app.services.gimbal_launcher import LaunchResult
        return LaunchResult(launch_status="ok", exit_code=0, total=1,
                            passed=1, failed=0, skipped=0, attempts=1)

    async def close(self) -> None:
        return None


async def _wait_final(execution_id: int, timeout_s: float = 30.0):
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, execution_id)
            if ex.status in ("done", "failed", "canceled"):
                return ex
        await asyncio.sleep(0.1)
    raise AssertionError(f"execution {execution_id} not final in {timeout_s}s")


async def test_m2_sample_full_assembly_e2e(client: AsyncClient, monkeypatch):
    """M3 里程碑出口「复跑 M2 样例完整装配」:M2 样例拓扑(场景 +
    数据集 + 方案 + 组合绑定)走完整 §20.3 弧线 —— blocked(装配闸
    拒执行、零执行行)→ rebind-combo 修复(ready)→ JWT 面发起
    (请求绑定留空 = 后端权威垫底)→ 全链装配 → 执行 done;config_json
    见证组合垫底终值与方案溯源。"""
    from app.services import gimbal_server_session
    from app.services import plate_client as pc
    from app.services import scheme_repair
    from app.models.composer_run_scheme import ComposerRunScheme
    from app.schemas.scenario_composer import RunRequest

    async def _fake_convert(scenario: dict) -> dict:
        return {"consumer": "gimbal", "converted": dict(scenario)}

    monkeypatch.setattr(pc, "convert", _fake_convert)
    monkeypatch.setattr(gimbal_server_session, "ServerSessionPool", _OkPool)

    h, uid, combo_id, sid, ds_id, qa_id = await _seed(client, "e2e")

    # ── blocked:装配闸拒执行(先于凭证解析与执行行)─────────────────
    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa.select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == qa_id))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=uid, actor_name="seed")
        await s.commit()
        blocked_rev = row.revision
    async with db_module.SessionLocal() as s:
        from app.models.user import User

        user_id = (await s.execute(sa.select(User.id).where(
            User.username == "m3c_e2e"))).scalar_one()
        req = RunRequest(scenarioId=sid, schemeId=qa_id)
        try:
            await run_dispatcher.dispatch_run(s, user_id, req)
            raise AssertionError("blocked 方案不得进入执行装配")
        except run_dispatcher.Conflict as e:
            assert e.code == "scheme_repair_required", e.code
        n_exec = (await s.execute(sa.select(sa.func.count()).select_from(
            Execution))).scalar_one()
        assert n_exec == 0, "blocked 弧线不得创建执行行"
        await s.rollback()

    # ── 修复:rebind-combo(§20.3 修复命令,CAS)→ ready ──────────
    r = await client.post(
        f"/api/scenarios/{sid}/run-schemes/{qa_id}/rebind-combo",
        headers=h, json={"comboId": combo_id,
                         "expectedRevision": blocked_rev})
    assert r.status_code == 200, r.text
    assert r.json()["repairStatus"] == "ready", r.text

    # ── 完整装配:JWT 面发起,请求绑定留空(垫底权威在后端)──────────
    req = RunRequest(
        scenarioId=sid, schemeId=qa_id,
        dataSetSelection=[{"datasetId": ds_id, "rowIndexes": [0]}])
    async with db_module.SessionLocal() as s:
        from app.models.user import User

        user_id = (await s.execute(sa.select(User.id).where(
            User.username == "m3c_e2e"))).scalar_one()
        resp = await run_dispatcher.dispatch_run(s, user_id, req)
        await s.commit()

    ex = await _wait_final(resp.execution_id)
    assert ex.status == "done", ex.status
    assert ex.passed == 1 and ex.failed == 0

    # ── 装配终值见证:组合垫底 + 方案溯源 + 别名解析 ─────────────────
    cfg = ex.config_json or {}
    assert cfg["schemeId"] == qa_id
    assert cfg["serviceBindings"] == {"fin-service": {"alias": ALIAS}}, cfg
    assert ALIAS in (cfg.get("injectedAuths") or []), cfg
