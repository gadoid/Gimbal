"""服务引用注册化(架构终态,2026-11-21)—— 保存闸 + 执行链 ② 层退役
+ 解析预览端点。

三态口径(off / audit / enforce)× 挂载链(场景 create / PUT / 导入):

* off = 现状无痕;audit = 保存成功 + ``X-Service-Warnings`` 头
  (unregistered / declaredUrls 两组;导入响应 ``serviceWarnings`` 键);
* enforce = 422 ``service_not_registered``(键不在主档 ∪ 条目表)先报,
  ``service_url_declared``(引用键带 authored URL)后报;
* 执行链:``materialize_run_copy`` 物化副本 ``config.services`` 从空
  起步、只填 ③ 部署表地址(authored 声明不再生效 —— 直连层退役);
* ``GET /{id}/service-resolution``:标签链 + 逐键注册态/身份面/
  实例/逐环境地址/缺口(只读)。
"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core import db as db_module
from app.models.service import Service
from sqlalchemy import select

from .helpers import make_draft, role_headers
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_import_pipeline import _bundle, _mock_faces, _seed_env


def _steps(svc: str = "fin-service") -> list[dict]:
    return [{
        "kind": "step", "endpoint": "fin.orders.get",
        "call": {"service": svc, "method": "GET", "path": "/o"},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]


def _draft_with_url(sid: str, svc: str, url: str) -> dict:
    d = make_draft(sid, steps=_steps(svc))
    d["definition"]["config"] = {"services": {svc: url}}
    return d


async def _seed_master(name: str) -> None:
    async with db_module.SessionLocal() as s:
        if (await s.execute(select(Service.id).where(
                Service.name == name))).scalar_one_or_none() is None:
            s.add(Service(name=name, system=name, kind="plate"))
        await s.commit()


@pytest.mark.asyncio
async def test_off_mode_no_gate(client, monkeypatch):
    """off:裸键 + authored URL 照常保存,无头(缺省口径钉)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "off")
    h = await role_headers(client, "svg-off")
    r = await client.post("/api/scenarios", headers=h,
                          json=_draft_with_url("sc-svg-off", "ghost-svc",
                                               "https://x"))
    assert r.status_code == 201, r.text
    assert "X-Service-Warnings" not in r.headers


@pytest.mark.asyncio
async def test_audit_mode_warns_both_groups(client, monkeypatch):
    """audit:未注册键 + authored URL 两组同头(保存放行)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "audit")
    await _seed_master("fin-service")
    h = await role_headers(client, "svg-audit")
    d = make_draft("sc-svg-audit", steps=_steps("fin-service")
                   + _steps("ghost-svc"))
    d["definition"]["config"] = {
        "services": {"fin-service": "https://declared",
                     "ghost-svc": "https://g"}}
    r = await client.post("/api/scenarios", headers=h, json=d)
    assert r.status_code == 201, r.text
    warn = json.loads(r.headers["X-Service-Warnings"])
    assert warn["unregistered"] == ["ghost-svc"]
    # declaredUrls = 带声明的引用键(两键都带了 URL)
    assert warn["declaredUrls"] == ["fin-service", "ghost-svc"]


@pytest.mark.asyncio
async def test_enforce_unregistered_first(client, monkeypatch):
    """enforce:两类并存先报未注册(更根本);已注册键的 URL 不连坐。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "enforce")
    await _seed_master("fin-service")
    h = await role_headers(client, "svg-enf1")
    d = make_draft("sc-svg-enf1", steps=_steps("fin-service")
                   + _steps("ghost-svc"))
    d["definition"]["config"] = {"services": {"fin-service": "https://d"}}
    r = await client.post("/api/scenarios", headers=h, json=d)
    assert r.status_code == 422, r.text
    d0 = r.json()["detail"]
    assert d0["code"] == "service_not_registered"
    assert d0["keys"] == ["ghost-svc"]


@pytest.mark.asyncio
async def test_enforce_url_declared(client, monkeypatch):
    """enforce:键全注册但带 authored URL → 422 service_url_declared
    (② 层退役:场景不持有地址);无 URL 的纯引用放行。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "enforce")
    await _seed_master("fin-service")
    h = await role_headers(client, "svg-enf2")
    r = await client.post("/api/scenarios", headers=h,
                          json=_draft_with_url("sc-svg-enf2",
                                               "fin-service", "https://d"))
    assert r.status_code == 422, r.text
    d0 = r.json()["detail"]
    assert d0["code"] == "service_url_declared"
    assert d0["keys"] == ["fin-service"]

    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-svg-enf2b",
                                          steps=_steps("fin-service")))
    assert r.status_code == 201, r.text
    assert "X-Service-Warnings" not in r.headers


@pytest.mark.asyncio
async def test_put_same_gate(client, monkeypatch):
    """PUT 同闸:off 建场景 → audit 更新带 URL → 200 + 头。"""
    h = await role_headers(client, "svg-put")
    await _seed_master("fin-service")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-svg-put", steps=_steps()))
    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "audit")
    r = await client.put("/api/scenarios/sc-svg-put", headers=h,
                         json=_draft_with_url("sc-svg-put",
                                              "fin-service", "https://d"))
    assert r.status_code == 200, r.text
    warn = json.loads(r.headers["X-Service-Warnings"])
    assert warn["declaredUrls"] == ["fin-service"]


@pytest.mark.asyncio
async def test_import_audit_and_enforce(client, plate_mock, monkeypatch):
    """导入同口径:audit serviceWarnings 键;enforce 422(先未注册后
    URL —— bundle 的 fin-service 键带 config.services 源 URL)。"""
    _mock_faces(plate_mock)
    await _seed_env()
    await _seed_master("fin-service")
    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "audit")
    h1 = await role_headers(client, "svg-imp-a", role="admin")
    r = await client.post("/api/scenarios/import", headers=h1, json={
        "bundle": _bundle(sid="sc-svg-imp-a"),
        "mappings": [{"serviceKey": "fin-service-qa",
                      "decision": "create"}],
    })
    assert r.status_code == 201, r.text
    # bundle 声明了 fin-service / fin-service-qa 的 URL;qa 侧条目在
    # 映射 create 后入库(键注册)→ 两组各自归位
    warn = r.json().get("serviceWarnings") or {}
    assert warn.get("declaredUrls") == ["fin-service", "fin-service-qa"]

    monkeypatch.setattr(settings, "REGISTRY_ONLY_SERVICES", "enforce")
    h2 = await role_headers(client, "svg-imp-e", role="admin")
    r = await client.post("/api/scenarios/import", headers=h2, json={
        "bundle": _bundle(sid="sc-svg-imp-e"),
        # 上一测已建 fin-service-qa 条目 → reuse(键已注册,纯验 URL 闸)
        "mappings": [{"serviceKey": "fin-service-qa",
                      "decision": "reuse"}],
    })
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "service_url_declared"


@pytest.mark.asyncio
async def test_materialize_ignores_authored_urls():
    """执行链 ② 退役(单源物化):authored 声明整表不进物化副本,
    地址只来自 ③(base_urls_for 预解析形态)。"""
    from app.services.run_materialize import materialize_run_copy

    converted = {
        "meta": {"scenarioId": "sc-m"},
        "steps": _steps("fin-service"),
        "config": {"services": {"fin-service": "https://authored",
                                "unused-key": "https://u"}},
    }
    out = materialize_run_copy(
        converted, alias_base_urls={"fin-service": "https://deploy"})
    assert out["config"]["services"] == {"fin-service": "https://deploy"}
    # 入参不可变(纯函数)
    assert converted["config"]["services"]["fin-service"] == \
        "https://authored"


@pytest.mark.asyncio
async def test_service_resolution_endpoint(client, monkeypatch):
    """解析预览:环境链 + 逐键注册态/身份面/实例/逐环境地址/缺口。"""
    from app.models.deployment import Deployment
    from app.models.environment import Environment
    from app.models.service_identity import ServiceIdentity
    from app.models.system_env_instance import SystemEnvInstance

    h = await role_headers(client, "svg-res")
    await _seed_master("fin-service")
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-svg-res", steps=_steps()))
    assert r.status_code == 201, r.text
    async with db_module.SessionLocal() as s:
        env = (await s.execute(select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        s.add(ServiceIdentity(alias_name="fin-service",
                              base_service="fin-service", env_id=env,
                              ref_mode="default"))
        s.add(Deployment(base_service="fin-service", env_id=env,
                         base_url="https://dep1"))
        s.add(SystemEnvInstance(system="fin-service", env_id=env,
                                login_url="https://login", line="1.0#1"))
        await s.commit()

    r = await client.get("/api/scenarios/sc-svg-res/service-resolution",
                         headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["environment"]["envId"] == env   # 身份条目标签链
    svc = body["services"][0]
    assert svc["key"] == "fin-service"
    assert svc["registered"] is True
    assert svc["identityEntry"]["refMode"] == "default"
    assert svc["instance"] == {"loginUrl": "https://login", "line": "1.0#1"}
    assert svc["urls"][0]["url"] == "https://dep1"
    assert svc["currentUrl"] == "https://dep1"
    assert svc["gap"] is False
