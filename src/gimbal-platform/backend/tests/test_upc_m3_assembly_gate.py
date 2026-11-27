"""UPC M3:§20.3 统一装配闸 —— execute / preview / schedule 各入口接入
回归(评审出口条件「全部装配入口负向」)。

已收口面(此前轮次):probe = run_precheck(_precheck_one repair_blocked)、
Suite 编排 validate/run(_assembly_gate + resolve_graph_units 单源)。
本文件补齐剩余执行族:单场景 JWT 执行(dispatch_target 溯源复核)、
令牌执行(_apply_scheme_recipe)、生效配置预览(preview)、集成调度
(integration_runner.run_instance)。query 面(取数)定义级无方案
引用 —— 豁免(登记于 docs/upc-assembly-entry-registry.md)。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core import db as db_module
from app.models.composer_run_scheme import ComposerRunScheme
from app.models.execution import Execution
from tests.helpers import make_draft, register_and_login
from tests.test_suites_validate import STEPS
from tests.test_integration import (  # noqa: F401  布景单源
    _mk_scenario, _task_body,
)


async def _mk_scheme(client: AsyncClient, h: dict, scen: str, name: str,
                     *, is_default: bool = False) -> str:
    r = await client.post(f"/api/scenarios/{scen}/run-schemes",
                          headers=h,
                          json={"name": name, "isDefault": is_default,
                                "dataSetSelection": [],
                                "injectionEntryIds": [],
                                "serviceBindings": {}, "options": {
                                    "step_from": None, "step_to": None,
                                    "n_runs": 1, "parallel": 1,
                                    "subscribe": None}})
    assert r.status_code == 201, r.text
    return r.json()["schemeId"]


async def _block(scheme_id: str, actor_id: int) -> None:
    from app.services import scheme_repair

    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=actor_id, actor_name="seed")
        await s.commit()


async def _uid_of(client: AsyncClient, username: str) -> int:
    h = await register_and_login(client, username, "pw123456")
    return (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]


# ── execute 面:dispatch_target(JWT 单场景 / suite 直跑 / 重跑)─────

async def test_dispatch_target_blocked_scheme_rejected_before_assembly(
        client: AsyncClient):
    """JWT 执行面:blocked 方案(前端按其内联配方 + 溯源 schemeId)
    → Conflict scheme_repair_required,**先于执行配置/凭证解析与执行行
    创建**(库内零 Execution 行)。"""
    from app.schemas.scenario_composer import RunRequest
    from app.services import run_dispatcher

    h = await register_and_login(client, "m3ex_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    await client.post("/api/scenarios", headers=h,
                     json=make_draft("sc-m3ex", steps=STEPS))
    blocked_id = await _mk_scheme(client, h, "sc-m3ex", "受阻方案")
    await _block(blocked_id, uid)

    async with db_module.SessionLocal() as s:
        from app.models.user import User

        user_id = (await s.execute(select(User.id).where(
            User.username == "m3ex_own"))).scalar_one()
        req = RunRequest(scenarioId="sc-m3ex", schemeId=blocked_id)
        with pytest.raises(run_dispatcher.Conflict) as ei:
            await run_dispatcher.dispatch_run(s, user_id, req)
            await s.commit()
        assert ei.value.code == "scheme_repair_required"
        n_exec = (await s.execute(select(func.count()).select_from(
            Execution))).scalar_one()
        assert n_exec == 0, "blocked 方案不得创建执行行"


async def test_dispatch_target_stale_scheme_id_recipes_from_request(
        client: AsyncClient, monkeypatch):
    """悬空溯源 schemeId(方案已删/他属)按 §7 回落**默认方案**复核闸
    (与令牌面/查询面同口径):默认方案 ready → 闸放行、执行照常入队
    (此腿只验「回落复核不过度拦截」,执行成败与闸无关,断言拿到
    executionId;blocked 默认方案的拦截腿 = 下一个用例)。"""
    from app.schemas.scenario_composer import RunRequest
    from app.services import run_dispatcher

    h = await register_and_login(client, "m3st_own", "pw123456")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m3st", steps=STEPS))
    from tests.helpers import seed_service_runtime

    await seed_service_runtime("fin.order")     # M3 §8.5:地址硬门落点
    async with db_module.SessionLocal() as s:
        from app.models.user import User

        user_id = (await s.execute(select(User.id).where(
            User.username == "m3st_own"))).scalar_one()
        req = RunRequest(scenarioId="sc-m3st", schemeId="rs-999")
        try:
            resp = await run_dispatcher.dispatch_run(s, user_id, req)
            await s.commit()
        except run_dispatcher.Conflict as e:
            # 唯一不允许的是闸码本身;其它 Conflict 只证明闸已放行
            assert e.code != "scheme_repair_required", \
                "悬空溯源 id 经默认方案复核(ready)不应触发装配闸"
            pytest.fail(f"布景意外: {e.code}")
        # 执行行已建(闸放行;后续阶段与本断言无关)
        assert resp.execution_id > 0


async def test_dispatch_target_blocked_default_scheme_rejected_without_scheme_id(
        client: AsyncClient):
    """schemeId 缺省不再绕过闸:默认方案 blocked → dispatch Conflict
    scheme_repair_required(§7 回落单源,与令牌面/查询面同口径 ——
    服务端强制,不依赖客户端诚实传溯源字段)。"""
    from app.schemas.scenario_composer import RunRequest
    from app.services import run_dispatcher

    h = await register_and_login(client, "m3ex_own2", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m3ex2", steps=STEPS))
    # 场景创建钩子已物化默认方案(ready);置 blocked
    async with db_module.SessionLocal() as s:
        default_row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m3ex2",
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
    await _block(default_row.scheme_id, uid)

    async with db_module.SessionLocal() as s:
        from app.models.user import User

        user_id = (await s.execute(select(User.id).where(
            User.username == "m3ex_own2"))).scalar_one()
        req = RunRequest(scenarioId="sc-m3ex2")     # 不带 schemeId
        with pytest.raises(run_dispatcher.Conflict) as ei:
            await run_dispatcher.dispatch_run(s, user_id, req)
            await s.commit()
        assert ei.value.code == "scheme_repair_required"


# ── execute 面:令牌执行(_apply_scheme_recipe)────────────────────

async def test_token_recipe_blocked_default_scheme_rejected(
        client: AsyncClient):
    """令牌面:配方一律取服务端方案 —— 默认方案 blocked → 409
    scheme_repair_required,先于绑定/数据集装配;ready 对照腿照常
    应用(闸不过度拦截)。"""
    from fastapi import HTTPException

    from app.models.composer_scenario import ComposerScenario
    from app.routers.runs import _apply_scheme_recipe
    from app.schemas.scenario_composer import RunRequest

    h = await register_and_login(client, "m3tk_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m3tk", steps=STEPS))
    # 场景创建钩子已物化默认方案;置 blocked
    async with db_module.SessionLocal() as s:
        default_row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m3tk",
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
    await _block(default_row.scheme_id, uid)

    async with db_module.SessionLocal() as s:
        scen = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-m3tk"))).scalar_one()
        body = RunRequest(scenarioId="sc-m3tk")
        with pytest.raises(HTTPException) as ei:
            await _apply_scheme_recipe(s, scen, body)
        assert ei.value.status_code == 409
        assert ei.value.detail["code"] == "scheme_repair_required"
    # ready 对照:修复后(rebind 或 confirm)再取配方不再拦 —— 直接以
    # 第二场景的 ready 默认方案验证
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m3tk2", steps=STEPS))
    async with db_module.SessionLocal() as s:
        scen2 = (await s.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-m3tk2"))).scalar_one()
        body = RunRequest(scenarioId="sc-m3tk2")
        applied = await _apply_scheme_recipe(s, scen2, body)
        assert applied is not None and applied.is_default


# ── preview 面:生效配置预览 ────────────────────────────────────────

async def test_preview_blocked_scheme_refuses_assembly(
        client: AsyncClient):
    """预览会解析别名/凭证终值(与执行同一受控装配面)—— blocked
    方案 409 scheme_repair_required;ready 方案照常 200。"""
    h = await register_and_login(client, "m3pv_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m3pv", steps=STEPS))
    blocked_id = await _mk_scheme(client, h, "sc-m3pv", "受阻方案")
    ready_id = await _mk_scheme(client, h, "sc-m3pv", "对照方案")
    await _block(blocked_id, uid)

    r = await client.post("/api/runs/preview", headers=h, json={
        "scenarioId": "sc-m3pv", "schemeId": blocked_id})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
    r = await client.post("/api/runs/preview", headers=h, json={
        "scenarioId": "sc-m3pv", "schemeId": ready_id})
    assert r.status_code == 200, r.text


# ── schedule 面:集成调度 + 手动触发(run_instance)─────────────────

async def test_integration_run_blocked_scheme_channel_finish(
        client: AsyncClient):
    """集成面:模板方案 blocked → 当轮 channel 收口(实例 failed +
    人话原因),先于任何装配/凭证解析(与 working_preview 同位)。"""
    from app.models.integration_task import IntegrationTask
    from app.services import integration_runner as ir

    h = await register_and_login(client, "m3ig_own", "m3ig_pass123")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    await _mk_scenario(client, h, "sc-m3ig", [{
        "kind": "step", "description": "查单",
        "call": {"service": "fin.order", "method": "GET", "path": "/o"},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }])
    r = await client.post(
        "/api/integration/tasks", headers=h,
        json=_task_body("sc-m3ig", identityMode="personal"))
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]
    # 默认方案(场景钩子物化)置 blocked
    async with db_module.SessionLocal() as s:
        default_row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m3ig",
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
    await _block(default_row.scheme_id, uid)

    async with db_module.SessionLocal() as s:
        tpl = (await s.execute(select(IntegrationTask).where(
            IntegrationTask.id == tid))).scalar_one()
        inst = await ir.ensure_instance(tpl, holder_id=tpl.owner_id)
        out = await ir.run_instance(inst.id)
    assert out["status"] == "failed", out
    assert "待修复" in (out.get("error") or ""), out


# ── execute 面:Suite 直跑成员(default 方案 blocked → skipped)────

async def test_suite_aggregate_member_blocked_skipped(
        client: AsyncClient):
    """Suite 直跑:成员默认方案 blocked → dispatch 闸 Conflict 归
    skipped(reason=scheme_repair_required,单成员禁跑不掀批次),
    无执行行落库。"""
    h = await register_and_login(client, "m3sa_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-m3sa", steps=STEPS))
    async with db_module.SessionLocal() as s:
        default_row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-m3sa",
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
    await _block(default_row.scheme_id, uid)

    sid = (await client.post("/api/suites", headers=h,
                             json={"name": "直跑闸", "description": ""})
           ).json()["suiteId"]
    r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                         json={"rev": 0, "mode": "aggregate",
                               "members": [{"scenarioId": "sc-m3sa"}],
                               "modeConfig": {}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/suites/{sid}/run", headers=h, json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["started"] == [], body
    assert any(e["scenarioId"] == "sc-m3sa"
               and e["reason"] == "scheme_repair_required"
               for e in body["skipped"]), body
    async with db_module.SessionLocal() as s:
        n_exec = (await s.execute(select(func.count()).select_from(
            Execution))).scalar_one()
        assert n_exec == 0


# ── schedule 面:创建/绑定更新/订阅确认/恢复(§20.3「创建、启用、
#    更新执行绑定及每次派发均检查」的写点补齐)────────────────────────

async def test_integration_create_blocked_scheme_rejected(client: AsyncClient):
    """创建模板显式绑定 blocked 方案 → 409 scheme_repair_required,
    模板行不落库;ready 对照腿放行。"""
    from app.models.integration_task import IntegrationTask

    h = await register_and_login(client, "m3sch_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    sid = await _mk_scenario(client, h, "sc-m3sch", STEPS)
    blocked_id = await _mk_scheme(client, h, sid, "受阻")
    ready_id = await _mk_scheme(client, h, sid, "可用", is_default=True)
    await _block(blocked_id, uid)

    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body(sid, identityMode="personal",
                                          schemeId=blocked_id, name="绑受阻方案"))
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
    async with db_module.SessionLocal() as s:
        n = (await s.execute(select(func.count()).select_from(
            IntegrationTask).where(
            IntegrationTask.name == "绑受阻方案"))).scalar_one()
    assert n == 0, "blocked 绑定不得创建模板行"

    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body(sid, identityMode="personal",
                                          schemeId=ready_id, name="绑可用方案"))
    assert r.status_code in (200, 201), r.text


async def test_integration_patch_rebind_blocked_scheme_rejected(
        client: AsyncClient):
    """换绑 blocked 方案(PATCH schemeId)→ 409;原绑定不被覆盖。"""
    h = await register_and_login(client, "m3ptc_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    sid = await _mk_scenario(client, h, "sc-m3ptc", STEPS)
    ready_id = await _mk_scheme(client, h, sid, "先绑", is_default=True)
    blocked_id = await _mk_scheme(client, h, sid, "后换")
    await _block(blocked_id, uid)
    tid = (await client.post("/api/integration/tasks", headers=h,
                             json=_task_body(sid, identityMode="personal", schemeId=ready_id))
           ).json()["id"]
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=h,
                           json={"schemeId": blocked_id})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
    # 库内绑定未被覆盖
    from app.models.integration_task import IntegrationTask

    async with db_module.SessionLocal() as s:
        bound = (await s.execute(select(IntegrationTask.scheme_id).where(
            IntegrationTask.id == tid))).scalar_one()
    assert bound == ready_id


async def test_integration_subscribe_blocked_default_scheme_rejected(
        client: AsyncClient):
    """订阅确认面:模板未指定方案、默认方案 blocked → 409(§11.5 将生效
    配方核对;不把阻塞方案确认成可派发订阅)。创建面同口径已先拦
    (创建闸),此腿从 ready 创建后转 blocked 起步。"""
    h = await register_and_login(client, "m3sub_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    sid = await _mk_scenario(client, h, "sc-m3sub", STEPS)
    tid = (await client.post("/api/integration/tasks", headers=h,
                             json=_task_body(sid, identityMode="personal"))).json()["id"]
    # 场景创建钩子已物化默认方案 —— 阻断的就是它(将生效配方)
    async with db_module.SessionLocal() as s:
        drow = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid,
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
    await _block(drow.scheme_id, uid)
    fp = (await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary",
        headers=h)).json()["fingerprint"]
    r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                          headers=h, json={"fingerprint": fp})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"


async def test_integration_create_unbound_blocked_default_rejected(
        client: AsyncClient):
    """§11.5 将生效配方(复核):创建不传 schemeId → 将生效 = 默认方案;
    默认 blocked → 409(写点闸,不再等订阅/派发)。"""
    from app.models.integration_task import IntegrationTask

    h = await register_and_login(client, "m3ubd_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    sid = await _mk_scenario(client, h, "sc-m3ubd", STEPS)
    async with db_module.SessionLocal() as s:
        drow = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid,
            ComposerRunScheme.is_default == True))).scalar_one()  # noqa: E712
    await _block(drow.scheme_id, uid)
    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body(sid, identityMode="personal",
                                          name="默认受阻创建"))
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
    async with db_module.SessionLocal() as s:
        n = (await s.execute(select(func.count()).select_from(
            IntegrationTask).where(
            IntegrationTask.name == "默认受阻创建"))).scalar_one()
    assert n == 0, "将生效配方受阻不得创建模板行"


async def test_integration_patch_clear_scheme_blocked_default_rejected(
        client: AsyncClient):
    """§11.5 将生效配方(复核):PATCH 显式清空 schemeId → 回落默认方案;
    默认 blocked → 409(写点闸),原显式绑定保留。"""
    from app.models.integration_task import IntegrationTask

    h = await register_and_login(client, "m3clr_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    sid = await _mk_scenario(client, h, "sc-m3clr", STEPS)
    bound_id = await _mk_scheme(client, h, sid, "显式绑定")   # 非默认
    tid = (await client.post("/api/integration/tasks", headers=h,
                             json=_task_body(sid, identityMode="personal",
                                             schemeId=bound_id))
           ).json()["id"]
    # 阻断默认方案(清空后将生效 = 默认)
    async with db_module.SessionLocal() as s:
        drow = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid,
            ComposerRunScheme.is_default == True))).scalar_one()
    await _block(drow.scheme_id, uid)
    r = await client.patch(f"/api/integration/tasks/{tid}", headers=h,
                           json={"schemeId": ""})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
    async with db_module.SessionLocal() as s:
        kept = (await s.get(IntegrationTask, tid)).scheme_id
    assert kept == bound_id, "闸拒后原显式绑定不得被清除"


async def test_integration_resume_blocked_scheme_rejected(client: AsyncClient):
    """恢复面:可恢复暂停(fail_streak)在恢复前核对将生效方案 ——
    blocked → 409,实例保持暂停。"""
    h = await register_and_login(client, "m3res_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    sid = await _mk_scenario(client, h, "sc-m3res", STEPS)
    tid = (await client.post("/api/integration/tasks", headers=h,
                             json=_task_body(sid, identityMode="personal"))).json()["id"]
    # 先订阅(方案 ready)→ 手动暂停(可恢复类)→ 方案转 blocked → 恢复 409
    fp = (await client.get(
        f"/api/integration/tasks/{tid}/subscription-summary",
        headers=h)).json()["fingerprint"]
    r = await client.post(f"/api/integration/tasks/{tid}/subscribe",
                          headers=h, json={"fingerprint": fp})
    assert r.status_code in (200, 201), r.text
    async with db_module.SessionLocal() as s:
        drow = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid,
            ComposerRunScheme.is_default == True))).scalar_one()
    await _block(drow.scheme_id, uid)
    r = await client.post(
        f"/api/integration/tasks/{tid}/subscription/pause", headers=h)
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/api/integration/tasks/{tid}/subscription/resume",
                          headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_repair_required"
