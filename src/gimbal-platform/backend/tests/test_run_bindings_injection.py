"""serviceBindings 注入 + 模板扫描驱动注入清单(spec §5/§6)。

capture 读 case.json(_patch_launch_capture),断言物化结果:绑定选别名
(authz M2a S6:服务键 → 别名)→ 该别名声明的槽位进注入清单;steps 里的
${auth.*} 引用即使无绑定也进注入清单;退役字段 url/authAlias 422。
PlateMock 用 echo 行为(converted 带 steps)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Execution
from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


_AUTH_STEP = {
    "kind": "step",
    "call": {"service": "fin-service", "path": "/x",
            "headers": {"Authorization": "${auth.qa1.token}"}},
}


async def _seed_pool_auth(username: str, alias: str = "qa1") -> None:
    """S5 失败即中止:注入清单的槽位须在执行人池 —— 测试种一行。"""
    from app.core import db as db_module
    from app.core.security import fernet_encrypt
    from app.models.auth_session import AuthSession as _AS
    from sqlalchemy import select as _sel, text as _txt

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(_txt(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()
        s.add(_AS(owner_id=uid, alias=alias, url="http://auth",
                  username_enc=fernet_encrypt("u"),
                  password_enc=fernet_encrypt("p"),
                  slot=alias, is_default=True))
        await s.commit()


async def _seed_scenario(client, headers) -> None:
    r = await client.post("/api/scenarios", headers=headers,
                          json=_draft(steps=[_AUTH_STEP]))
    assert r.status_code in (200, 201), r.text


async def _last_config_json() -> dict:
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(Execution.id.desc()))
              ).scalars().first()
        return ex.config_json


async def _seed_aliases(**slots: str | None) -> None:
    """fin-service 基础服务下的别名(名 → 声明槽位)。"""
    from app.models.service_alias import ServiceAlias
    async with db_module.SessionLocal() as s:
        for name, slot in slots.items():
            s.add(ServiceAlias(alias_name=name.replace("_", "-"),
                               base_service="fin-service",
                               kind="external", slot=slot))
        await s.commit()


async def test_binding_alias_switches_slot(client, plate_mock: PlateMock,
                                           monkeypatch):
    """serviceBindings {fin-service: {alias: fin-service-maker}} → 该别名
    声明的槽位进注入清单并注入 users;config_json 留痕原始绑定。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    await _seed_pool_auth("bob", "maker")
    await _seed_aliases(fin_service=None, fin_service_maker="maker")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"alias": "fin-service-maker"}},
    ))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    users = cases[0]["config"].get("users") or {}
    assert "qa1" in users and "maker" in users   # 扫描 ∪ 生效别名槽位

    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {
        "fin-service": {"alias": "fin-service-maker"}}
    assert config_json["injectedAuths"] == ["qa1", "maker"]
    # 旧键退役(两种历史写法都兜住;实际键名以 :368-383 现码为准,删除后均过)
    for gone in ("prefix", "mergePolicy", "injectCredentials",
                 "execAuthAlias", "exec_auth_alias"):
        assert gone not in config_json


async def test_template_scan_without_binding_injects(client, plate_mock: PlateMock,
                                                     monkeypatch):
    """steps 引用 ${auth.qa1.token}(无绑定)→ qa1 仍进注入清单留痕。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    config_json = await _last_config_json()
    assert config_json["injectedAuths"] == ["qa1"]
    assert config_json["serviceBindings"] == {}


async def test_legacy_payload_fields_silently_ignored(client, plate_mock: PlateMock,
                                                      monkeypatch):
    """旧客户端发 auths/prefix/mergePolicy → 不 422,仅失效(spec §6)。"""
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    payload = _run_payload(dataSetIds=[])
    payload.update({"auths": ["qa1"], "prefix": "T-1",
                    "mergePolicy": "override", "injectCredentials": False})
    r = await client.post("/api/runs", headers=bob, json=payload)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert (cfg.get("vars") or {}).get("order_no_prefix") is None   # prefix 失效


async def test_retired_binding_fields_422(client, plate_mock: PlateMock):
    """S6:绑定带 url / authAlias → 422 binding_field_retired(不静默丢弃)。"""
    bob = await _member(client, "retired")
    await _seed_scenario(client, bob)
    for bad in ({"url": "https://bound"}, {"authAlias": "qa1"},
                {"alias": "fin-service", "url": "https://x"}):
        r = await client.post("/api/runs", headers=bob, json=_run_payload(
            dataSetIds=[], serviceBindings={"fin-service": bad}))
        assert r.status_code == 422, r.text
        assert "binding_field_retired" in r.text


async def test_binding_alias_validation(client, plate_mock: PlateMock):
    """S6:选的别名不存在 / 不同基础服务 → 拒发(不借道改地址)。"""
    from app.models.service_alias import ServiceAlias
    bob = await _member(client, "badalias")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("badalias", "qa1")
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="crm-x", base_service="crm",
                           kind="external"))
        await s.commit()
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings={"fin-service": {"alias": "ghost"}}))
    assert r.status_code == 409 and "binding_alias_unknown" in r.text, r.text
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings={"fin-service": {"alias": "crm-x"}}))
    assert r.status_code == 409 and "binding_alias_mismatch" in r.text, r.text


async def test_missing_auth_slot_refuses_dispatch(client, plate_mock: PlateMock):
    """S5 失败即中止:注入清单的槽位不在执行人池 → 整单 409
    auth_aliases_missing(此前告警继续、执行期步骤级报错)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "missauth")
    await _seed_scenario(client, bob)
    await _seed_aliases(fin_service_x="qa-none")
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"alias": "fin-service-x"}}))
    assert r.status_code == 409, r.text
    assert "auth_aliases_missing" in r.text
    assert "qa-none" in r.text
