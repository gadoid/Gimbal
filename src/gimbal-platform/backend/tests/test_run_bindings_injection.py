"""serviceBindings 注入 + 模板扫描驱动注入清单(spec §5/§6;P1-7 续期)。

capture 读 case.json(_patch_launch_capture),断言物化结果:绑定选条目
(authz M2a S6:服务键 → 条目;条目名即注入键)→ 该条目进注入清单;
steps 里的 ${auth.*} 引用即使无绑定也进注入清单;退役字段 url/authAlias
422。PlateMock 用 echo 行为(converted 带 steps)。
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


async def _env_id() -> int:
    from app.models import Environment
    async with db_module.SessionLocal() as s:
        env = (await s.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.commit()
            env = (await s.execute(sa.select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        return env


async def _seed_pool_auth(username: str, alias: str = "qa1") -> None:
    """S5 失败即中止:注入清单的条目须在执行人池可解 —— 四件套种一条
    (环境+主档+账户+条目;同 (system,env) 第二个起让出默认位)。"""
    from app.models import AuthAccount
    from .conftest import seed_identity_fixture

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()
        have_default = (await s.execute(sa.select(AuthAccount.id).where(
            AuthAccount.owner_id == uid,
            AuthAccount.system == "fin-service",
            AuthAccount.is_default.is_(True)))).scalar_one_or_none() is not None
        await seed_identity_fixture(
            s, alias=alias, username=f"{alias}-u", password="p",
            service="fin-service", owner_id=uid, env_name="测试",
            is_default=not have_default)


async def _seed_scenario(client, headers) -> None:
    r = await client.post("/api/scenarios", headers=headers,
                          json=_draft(steps=[_AUTH_STEP]))
    assert r.status_code in (200, 201), r.text


async def _last_config_json() -> dict:
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(Execution.id.desc()))
              ).scalars().first()
        return ex.config_json


async def _seed_identities(*names: str) -> None:
    """fin-service 基础服务下的身份条目(名即注入键;条目模型无槽)。"""
    from app.models import ServiceIdentity
    env = await _env_id()
    async with db_module.SessionLocal() as s:
        for name in names:
            s.add(ServiceIdentity(alias_name=name.replace("_", "-"),
                                  base_service="fin-service",
                                  env_id=env, ref_mode="default"))
        await s.commit()


async def _seed_deployment() -> None:
    """M3 §8.5:派发硬门要求地址落点 —— fin-service 在默认环境的部署行
    (②③ 双缺 = address_missing 409;此前靠引擎缺口报错兜底)。"""
    from app.models import Deployment
    env = await _env_id()
    async with db_module.SessionLocal() as s:
        if (await s.execute(sa.select(Deployment.id).where(
                Deployment.base_service == "fin-service",
                Deployment.env_id == env))).scalar_one_or_none() is None:
            s.add(Deployment(base_service="fin-service", env_id=env,
                             base_url="https://fin.local"))
            await s.commit()


async def test_binding_alias_switches_identity(client, plate_mock: PlateMock,
                                               monkeypatch):
    """serviceBindings {fin-service: {alias: fin-service-maker}} → 该条目
    进注入清单并注入 users;config_json 留痕原始绑定。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    await _seed_pool_auth("bob", "fin-service-maker")  # 四件套连条目一起建
    await _seed_deployment()
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"alias": "fin-service-maker"}},
    ))
    assert r.status_code == 201, r.text
    # 30s 预算(2026-11-22):满载 xdist 下 fanout 落 case 慢于 5s
    # 缺省 —— 等待耐心放宽,断言不变。
    await _wait(lambda: len(cases) >= 1, timeout_s=30)

    users = cases[0]["config"].get("users") or {}
    assert "qa1" in users and "fin-service-maker" in users   # 扫描 ∪ 绑定换用

    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {
        "fin-service": {"alias": "fin-service-maker"}}
    assert config_json["injectedAuths"] == ["qa1", "fin-service-maker"]
    # 旧键退役(两种历史写法都兜住;实际键名以现码为准,删除后均过)
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
    await _seed_deployment()
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    # 30s 预算(2026-11-22):满载 xdist 下 fanout 落 case 慢于 5s
    # 缺省 —— 等待耐心放宽,断言不变。
    await _wait(lambda: len(cases) >= 1, timeout_s=30)
    config_json = await _last_config_json()
    assert config_json["injectedAuths"] == ["qa1"]
    assert config_json["serviceBindings"] == {}


async def test_legacy_payload_fields_silently_ignored(client, plate_mock: PlateMock,
                                                      monkeypatch):
    """旧客户端发 auths/prefix/mergePolicy → 不 422,仅失效(spec §6)。"""
    bob = await _member(client, "bob")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("bob", "qa1")
    await _seed_deployment()
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    payload = _run_payload(dataSetIds=[])
    payload.update({"auths": ["qa1"], "prefix": "T-1",
                    "mergePolicy": "override", "injectCredentials": False})
    r = await client.post("/api/runs", headers=bob, json=payload)
    assert r.status_code == 201, r.text
    # 30s 预算(2026-11-22):满载 xdist 下 fanout 落 case 慢于 5s
    # 缺省 —— 等待耐心放宽,断言不变。
    await _wait(lambda: len(cases) >= 1, timeout_s=30)
    cfg = cases[0]["config"]
    assert (cfg.get("vars") or {}).get("order_no_prefix") is None   # prefix 失效


async def test_retired_binding_fields_422(client, plate_mock: PlateMock):
    """S6:绑定带 url / authAlias → 422 binding_field_retired(不静默丢弃)。"""
    bob = await _member(client, "retired")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("retired", "qa1")
    for bad in ({"url": "https://bound"}, {"authAlias": "qa1"},
                {"alias": "fin-service", "url": "https://x"}):
        r = await client.post("/api/runs", headers=bob, json=_run_payload(
            dataSetIds=[], serviceBindings={"fin-service": bad}))
        assert r.status_code == 422, r.text
        assert "binding_field_retired" in r.text


async def test_binding_alias_validation(client, plate_mock: PlateMock):
    """S6:选的条目不存在 / 不同基础服务 → 拒发(不借道改地址)。"""
    from app.models import Service, ServiceIdentity
    bob = await _member(client, "badalias")
    await _seed_scenario(client, bob)
    await _seed_pool_auth("badalias", "qa1")
    await _seed_identities("fin-service-maker")
    env = await _env_id()
    async with db_module.SessionLocal() as s:
        s.add(Service(name="crm", system="crm", kind="plate"))
        s.add(ServiceIdentity(alias_name="crm-x", base_service="crm",
                              env_id=env, ref_mode="default"))
        await s.commit()
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings={"fin-service": {"alias": "ghost"}}))
    assert r.status_code == 409 and "binding_alias_unknown" in r.text, r.text
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings={"fin-service": {"alias": "crm-x"}}))
    assert r.status_code == 409 and "binding_alias_mismatch" in r.text, r.text


async def test_missing_auth_slot_refuses_dispatch(client, plate_mock: PlateMock):
    """S5 失败即中止:注入清单的条目在执行人池解不到账户 → 整单 409
    (M3 §8.5 起 code = account_missing,旧 auth_aliases_missing 随硬门
    细分为 identity/account 两码;此前告警继续、执行期步骤级报错)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "missauth")
    await _seed_scenario(client, bob)
    # 条目登记了,但执行人池无账户可解(不种四件套 —— default-ref 会吃
    # 池内默认账户,故本用例连 qa1 一起缺;qa1 也种条目行,聚焦缺账户)
    await _seed_identities("qa1", "fin-service-x")
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[],
        serviceBindings={"fin-service": {"alias": "fin-service-x"}}))
    assert r.status_code == 409, r.text
    det = r.json()["detail"]
    assert det["code"] == "account_missing"
    assert det["credentialSource"] == "personal"
    assert "fin-service-x" in det["message"]
