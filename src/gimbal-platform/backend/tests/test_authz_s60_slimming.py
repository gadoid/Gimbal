"""authz M2a S6:别名瘦身 + serviceBindings 收窄 + 原 5 区规则。

* 线上形态:绑定 = 服务键 → {alias};url/authAlias → 422(方案写面 /
  执行请求 / 生效预览 / 导出 overlay 四面);重跑回放剥离历史字段;
* 别名路由:退役字段 422,slot 为唯一声明口径,个人别名退役;
* 原 5:项目 / 公共区场景的 ``config.services`` 直连地址与
  ``config.users`` 内置凭证不生效(属主本人执行同样);令牌范围同口径。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from app.models.composer_scenario import ComposerScenario
from app.models.service_alias import ServiceAlias

from .helpers import (make_draft as _draft, role_headers, seed_deployment,
                      wait_until as _wait)
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member

_STEP = {"kind": "step",
         "call": {"service": "fin-service", "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {}}, "strategy": []}


async def _seed(client, h, sid: str, *, config: dict | None = None) -> None:
    draft = _draft(sid, steps=[_STEP])
    if config is not None:
        draft["definition"]["config"] = config
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text


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
        s.add(ProjectMember(project_id=proj.id, user_id=uid, role="member"))
        await s.execute(sa.update(ComposerScenario).where(
            ComposerScenario.scenario_id == sid).values(project_id=proj.id))
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
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="crm-x", base_service="crm",
                           kind="external"))
        await s.commit()
    for alias, code in (("ghost", "binding_alias_unknown"),
                        ("crm-x", "binding_alias_mismatch")):
        r = await client.post(
            "/api/scenarios/sc-s60-wire/run-schemes", headers=h,
            json={"name": f"选{alias}",
                  "serviceBindings": {"fin-service": {"alias": alias}}})
        assert r.status_code == 422 and code in r.text, r.text


async def test_rerun_scrubs_legacy_bindings(
        client, plate_mock: PlateMock, monkeypatch):
    """归档 config_json 带退役的 url/authAlias → 重跑剥离(不 422)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60rerun")
    await _seed(client, h, "sc-s60-rerun")
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
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="pay-s60", base_service="pay",
                           kind="external"))
        await s.commit()
    r = await client.patch("/api/service-aliases/pay-s60", headers=adm,
                           json={"slot": "maker"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["slot"] == "maker"
    assert not ({"baseUrl", "environmentId", "credentialAlias",
                 "ownerUserId"} & set(out))
    r = await client.patch("/api/service-aliases/pay-s60", headers=adm,
                           json={"baseUrl": "http://x"})
    assert r.status_code == 422, r.text
    r = await client.patch("/api/service-aliases/pay-s60", headers=adm,
                           json={"slot": None})
    assert r.status_code == 200 and r.json()["slot"] is None, r.text
    # 部署冲突读面退役
    r = await client.get("/api/deployments/conflicts", headers=adm)
    assert r.status_code in (404, 405, 422), r.text


# ── ③ 原 5 区规则 ─────────────────────────────────────────────────

_ZONE_CFG = {"services": {"fin-service": "http://authored"},
             "users": {"builtin": {"url": "http://auth", "username": "u",
                                   "password": "p",
                                   "token_type": "Bearer"}}}


async def test_private_zone_keeps_direct_and_builtin(
        client, plate_mock: PlateMock, monkeypatch):
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60priv")
    await _seed(client, h, "sc-s60-priv", config=_ZONE_CFG)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s60-priv", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert cfg["services"]["fin-service"] == "http://authored"
    assert "builtin" in cfg["users"]


async def test_project_zone_ignores_direct_and_builtin(
        client, plate_mock: PlateMock, monkeypatch):
    """项目区(公共区同口径):属主本人执行也不吃直连地址与内置凭证;
    地址落部署表;生效预览同口径(source=deployment)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s60pub")
    await _seed(client, h, "sc-s60-pub", config=_ZONE_CFG)
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
    """项目区 authored 不算落点(预检缺口如实报)/ 令牌范围不按直连放过。"""
    from app.services import access_token as at_svc, scheme_store
    from app.services.scenario_store import definition_from_payload

    h = await _member(client, "s60pre")
    await _seed(client, h, "sc-s60-pre", config=_ZONE_CFG)
    await _move_to_project("sc-s60-pre", "s60pre")
    async with db_module.SessionLocal() as s:
        sch = await scheme_store.create_scheme(
            s, "sc-s60-pre", name="预检", payload={})
    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": "sc-s60-pre", "schemeId": sch["schemeId"]}])
    assert r.status_code == 200, r.text
    assert r.json()[0]["unboundServices"] == ["fin-service"]

    async with db_module.SessionLocal() as s:
        scen = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-s60-pre"))).scalar_one()
        defn = definition_from_payload(scen.payload)
        pub = await at_svc.used_sets_for_definition(
            s, defn, {}, project_id=scen.project_id)
        priv = await at_svc.used_sets_for_definition(
            s, defn, {}, project_id=None)
    assert "fin-service" in pub.aliases          # 进范围判定
    assert "fin-service" not in priv.aliases     # 私有区 authored = 直连


async def test_graph_units_get_deployment_address(client, monkeypatch):
    """回归(S6 暴露的存量缺陷):编排单元的 ③ 地址此前从未生效 —— 引用
    服务按容器形状取 steps 恒空,被绑定 url 层掩盖;绑定 url 退役后单元
    须从部署表拿到地址。"""
    from app.models.user import User
    from app.services import graph_dispatch, plate_client as pc
    from app.services.env_chain import resolve_environment

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
            env=await resolve_environment(s, user_id=uid))
    for u in g["units"]:
        assert u["scenario"]["config"]["services"] == {
            "fin-service": "http://graph-sut"}, u["ref"]
