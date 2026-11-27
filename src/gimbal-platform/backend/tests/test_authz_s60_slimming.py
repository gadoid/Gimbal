"""authz M2a S6:别名瘦身 + serviceBindings 收窄 + 原 5 区规则。

* 线上形态:绑定 = 服务键 → {alias};url/authAlias → 422(方案写面 /
  执行请求 / 生效预览 / 导出 overlay 四面);重跑回放剥离历史字段;
* 别名路由:退役字段 422,slot 为唯一声明口径,个人别名退役;
* 原 5:项目 / 公共区场景的 ``config.services`` 直连地址与
  ``config.users`` 内置凭证不生效(属主本人执行同样);令牌范围同口径。
"""
from __future__ import annotations
import pytest  # noqa: E402

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from app.models.composer_scenario import ComposerScenario
from app.models import Service, ServiceIdentity

from .helpers import (make_draft as _draft, role_headers, seed_deployment,
                      wait_until as _wait)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


async def _s60_identity(alias_name: str, base: str) -> None:
    """种身份条目(+主档/默认环境;S6 绑定校验同基础服务用)。"""
    from sqlalchemy import select as _sel

    from app.core import db as _dbm
    from app.models import Environment, Service, ServiceIdentity
    async with _dbm.SessionLocal() as s:
        env = (await s.execute(_sel(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(_sel(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        if (await s.execute(_sel(Service.id).where(
                Service.name == base))).scalar_one_or_none() is None:
            s.add(Service(name=base, system=base, kind="plate"))
        s.add(ServiceIdentity(alias_name=alias_name, base_service=base,
                              env_id=env, ref_mode="default"))
        await s.commit()


_STEP = {"kind": "step",
         "call": {"service": "fin-service", "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {}}, "strategy": []}


async def _seed(client, h, sid: str, *, config: dict | None = None) -> None:
    """§3.5 闸(2026-11-20)后铺底:config 携带的 users 弹出、POST 干净
    草稿后注入行 —— _ZONE_CFG 形态(存量明文基座)照常可测。"""
    legacy_users = None
    draft = _draft(sid, steps=[_STEP])
    if config is not None:
        cfg = dict(config)
        legacy_users = cfg.pop("users", None)
        draft["definition"]["config"] = cfg
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    if legacy_users:
        from .helpers import seed_legacy_users
        await seed_legacy_users(sid, legacy_users)


async def _move_to_project(sid: str, username: str) -> None:
    """场景挂进一个普通项目(执行人是成员 —— 公共项目不开执行)。"""
    from app.models.project import Project, ProjectMember
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()
        proj = Project(name=f"s60-{sid}")
        s.add(proj)
        await s.flush()
        from tests.helpers import add_project_admin
        await add_project_admin(s, proj.id)   # UPC §20:出生即有 admin
        s.add(ProjectMember(project_id=proj.id, user_id=uid, role="member"))
        from sqlalchemy import text as _text

        from app.models.composer_run_scheme import ComposerRunScheme

        # §20.2:跨项目移动 = 专门事务(延迟复合 FK + 方案随迁)
        await s.execute(_text(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(sa.update(ComposerScenario).where(
            ComposerScenario.scenario_id == sid).values(project_id=proj.id))
        await s.execute(sa.update(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == sid).values(
                project_id=proj.id))
        await s.commit()


# ── ① 线上形态 422 ───────────────────────────────────────────────────

async def test_scheme_preview_overlay_reject_retired_fields(
        client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60wire")
    await _seed(client, h, "sc-s60-wire")
    bad = {"fin-service": {"url": "http://x"}}
    # 方案写面
    r = await client.post("/api/scenarios/sc-s60-wire/run-schemes",
                          headers=h, json={"name": "坏", "serviceBindings": bad})
    assert r.status_code == 422 and "binding_field_retired" in r.text, r.text
    # 生效预览
    r = await client.post("/api/runs/preview", headers=h, json={
        "scenarioId": "sc-s60-wire",
        "serviceBindings": {"fin-service": {"authAlias": "qa1"}}})
    assert r.status_code == 422 and "binding_field_retired" in r.text, r.text
    # 导出 overlay
    r = await client.post("/api/scenarios/preview-plate", headers=h, json={
        **_draft("sc-s60-wire", steps=[_STEP]),
        "overlay": {"serviceBindings": bad}})
    assert r.status_code == 422, r.text
    # 方案选不存在 / 跨基础服务的别名 → 422
    await _s60_identity("fin-service-s60x", "fin-service")
    await _s60_identity("crm-x", "crm")
    for alias, code in (("ghost", "binding_alias_unknown"),
                        ("crm-x", "binding_alias_mismatch")):
        r = await client.post(
            "/api/scenarios/sc-s60-wire/run-schemes", headers=h,
            json={"name": f"选{alias}",
                  "serviceBindings": {"fin-service": {"alias": alias}}})
        assert r.status_code == 422 and code in r.text, r.text


async def test_rerun_scrubs_legacy_bindings(
        client, plate_mock: PlateMock, monkeypatch):
    """归档 config_json 带退役的 url/authAlias → 重跑剥离(不 422)。
    架构终态:地址来源 = 部署表(声明不再供址,私有区同口径)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60rerun")
    await _seed(client, h, "sc-s60-rerun",
                config={"services": {"fin-service": "http://direct"}})
    await _seed_dep()   # 架构终态:地址来源 = 部署表(声明不再供址)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s60-rerun", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        ex.config_json = {**ex.config_json, "serviceBindings": {
            "fin-service": {"url": "http://legacy", "authAlias": "qa1"}}}
        await s.commit()
        ex_id = ex.id
    r = await client.post(f"/api/executions/{ex_id}/rerun", headers=h)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    assert cases[1]["config"]["services"].get("fin-service") != \
        "http://legacy"
    async with db_module.SessionLocal() as s:
        ex2 = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        assert ex2.config_json["serviceBindings"] == {}


# ── ② 别名路由瘦身 ─────────────────────────────────────────────────

async def test_alias_router_slimmed(client):
    adm = await role_headers(client, "s60adm", role="admin")
    # 退役字段 → 422(不静默丢弃)
    for extra in ({"baseUrl": "http://x"}, {"environmentId": 1},
                  {"credentialAlias": "qa1"}, {"ownerUserId": 1}):
        r = await client.post("/api/service-aliases", headers=adm, json={
            "aliasName": "pay-s60", "kind": "external",
            "baseService": "pay", **extra})
        assert r.status_code == 422, (extra, r.text)
    await _s60_identity("pay-s60", "pay")
    # slot 请求入参已退役(2026-11-17 复核清扫,redesign §6.0 偏离 7):
    # AliasPatch extra=forbid —— 发送即 422;输出面 slot=条目名契约保留
    r = await client.patch("/api/service-aliases/pay-s60", headers=adm,
                           json={"slot": "maker"})
    assert r.status_code == 422, r.text
    r = await client.patch("/api/service-aliases/pay-s60", headers=adm,
                           json={"baseUrl": "http://x"})
    assert r.status_code == 422, r.text
    r = await client.patch("/api/service-aliases/pay-s60", headers=adm,
                           json={"slot": None})
    assert r.status_code == 422, r.text
    # 输出面:列表回显 slot = 条目名,退役字段不再出现(单条 GET 端点无)
    r = await client.get("/api/service-aliases", headers=adm,
                         params={"q": "pay-s60"})
    assert r.status_code == 200, r.text
    out = next(a for a in r.json()["items"] if a["aliasName"] == "pay-s60")
    assert out["slot"] == "pay-s60"
    assert not ({"baseUrl", "environmentId", "credentialAlias",
                 "ownerUserId"} & set(out))
    # 部署冲突读面退役
    r = await client.get("/api/deployments/conflicts", headers=adm)
    assert r.status_code in (404, 405, 422), r.text


# ── ③ 原 5 区规则 ─────────────────────────────────────────────────

# 架构终态(2026-11-21):authored 声明不再供地址 —— 场景引用走
# 部署表(标签链环境)。保留同值声明仅作 audit 面(服务闸测试缺省
# off 不拦);_seed_dep 为 (fin-service, 默认环境) 落部署行。
async def _seed_dep() -> None:
    """(fin-service, 默认环境) 部署行 —— 架构终态的执行地址来源。"""
    from app.core import db as db_module
    from app.models import Environment
    from app.models.deployment import Deployment

    async with db_module.SessionLocal() as s:
        env = (await s.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(sa.select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        if (await s.execute(sa.select(Deployment.id).where(
                Deployment.base_service == "fin-service",
                Deployment.env_id == env))).scalar_one_or_none() is None:
            s.add(Deployment(base_service="fin-service", env_id=env,
                             base_url="http://authored"))
        await s.commit()


_ZONE_CFG = {"services": {"fin-service": "http://authored"},
             "users": {"builtin": {"url": "http://auth", "username": "u",
                                   "password": "p",
                                   "token_type": "Bearer"}}}


async def test_private_zone_keeps_direct_builtin_retired(
        client, plate_mock: PlateMock, monkeypatch):
    """私有区:authored 直连地址保留(地址面不在 §11.1 五开关清单);
    内置凭证执行链已退役(v2.10 §11.1 —— 禁止资产内嵌秘密,改授权
    凭证引用,私有区属主也不例外;明文仅剩导出面 10-14 口径)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60priv")
    await _seed(client, h, "sc-s60-priv", config=_ZONE_CFG)
    await _seed_dep()
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s60-priv", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert cfg["services"]["fin-service"] == "http://authored"
    assert "builtin" not in cfg["users"]


async def test_project_zone_ignores_direct_and_builtin(
        client, plate_mock: PlateMock, monkeypatch):
    """项目区(公共区同口径):属主本人执行也不吃直连地址与内置凭证;
    地址落部署表;生效预览同口径(source=deployment)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60pub")
    await _seed(client, h, "sc-s60-pub", config=_ZONE_CFG)
    await _seed_dep()
    await _move_to_project("sc-s60-pub", "s60pub")
    async with db_module.SessionLocal() as s:
        await seed_deployment(s, "fin-service", "http://deploy")
        await s.commit()
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s60-pub", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert cfg["services"]["fin-service"] == "http://deploy"
    assert "builtin" not in cfg["users"]

    r = await client.post("/api/runs/preview", headers=h, json={
        "scenarioId": "sc-s60-pub"})
    assert r.status_code == 200, r.text
    assert r.json()["services"]["fin-service"] == {
        "url": "http://deploy", "source": "deployment", "alias": "fin-service"}


async def test_project_zone_precheck_and_token_scope_no_direct(
        client, fresh_db):
    """架构终态:地址/范围全区一态(部署表供址;引用键一律进范围)。"""
    from app.services import access_token as at_svc, scheme_store
    from app.services.scenario_store import definition_from_payload

    h = await _member(client, "s60pre")
    await _seed(client, h, "sc-s60-pre", config=_ZONE_CFG)
    await _seed_dep()
    await _move_to_project("sc-s60-pre", "s60pre")
    async with db_module.SessionLocal() as s:
        sch = await scheme_store.create_scheme(
            s, "sc-s60-pre", name="预检", payload={})
    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": "sc-s60-pre", "schemeId": sch["schemeId"]}])
    assert r.status_code == 200, r.text
    # 架构终态:部署表已供址(_seed_dep)→ 预检不缺;旧断言
    # 「项目区不吃声明 → unbound」随 ② 层退役(全区一态)。
    assert r.json()[0]["unboundServices"] == []

    async with db_module.SessionLocal() as s:
        scen = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-s60-pre"))).scalar_one()
        defn = definition_from_payload(scen.payload)
        pub = await at_svc.used_sets_for_definition(
            s, defn, {}, project_id=scen.project_id)
        priv = await at_svc.used_sets_for_definition(
            s, defn, {}, project_id=None)
    # 架构终态:引用键一律别名形态进范围 —— 公共/私有同集(区规则
    # 随 ② 直连层退役消失)。
    assert "fin-service" in pub.aliases
    assert "fin-service" in priv.aliases


async def test_graph_units_get_deployment_address(client, monkeypatch):
    """回归(S6 暴露的存量缺陷):编排单元的 ③ 地址此前从未生效 —— 引用
    服务按容器形状取 steps 恒空,被绑定 url 层掩盖;绑定 url 退役后单元
    须从部署表拿到地址。"""
    from app.models.user import User
    from app.services import graph_dispatch, plate_client as pc
    from app.services.env_chain import resolve_execution_tag

    async def _fake_convert(scenario):
        return {"consumer": "gimbal", "converted": scenario}
    monkeypatch.setattr(pc, "convert", _fake_convert)
    h = await _member(client, "s60graph")
    for sid in ("sc-s60-g1", "sc-s60-g2"):
        await _seed(client, h, sid)
    async with db_module.SessionLocal() as s:
        await seed_deployment(s, "fin-service", "http://graph-sut")
        await s.commit()
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.select(User.id).where(
            User.username == "s60graph"))).scalar_one()
        g = await graph_dispatch.materialize_graph(s, uid, {
            "mode": "chain", "units": [
                {"ref": "u1", "scenarioId": "sc-s60-g1"},
                {"ref": "u2", "scenarioId": "sc-s60-g2"}]},
            env=await resolve_execution_tag(s))   # §8.2:平台默认位
    for u in g["units"]:
        assert u["scenario"]["config"]["services"] == {
            "fin-service": "http://graph-sut"}, u["ref"]
