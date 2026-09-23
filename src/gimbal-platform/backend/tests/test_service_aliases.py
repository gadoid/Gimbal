"""服务别名基础层(服务画像方案 §4.1)— CRUD/注册校验 + 两条解析链。

* 注册校验强约束(拍板):裸声明不猜;plate 宕机(空目录)不能登记;
* carry 解析链:精确别名键稀疏覆盖 > base 服务键 > 全局默认;
* 凭证解析链:别名表精确命中并入注入清单(执行者本人池子解析);
  场景显式绑定优先;存档 serviceBindings 只记原始(拍板)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import AuthSession, User
from app.models.service_alias import ServiceAlias
from app.services import carry_store
from app.services.carry_injection import build_carry_context

from .helpers import make_draft as _draft, wait_until as _wait
from .test_carry_api import _admin
from .test_run_bindings_injection import _last_config_json, _seed_scenario  # noqa: F401 复用
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


async def _seed_alias(**over) -> None:
    row = ServiceAlias(
        alias_name="fin-service-uat", base_service="fin-service",
        credential_alias="uat-cred",
    )
    for k, v in over.items():
        setattr(row, k, v)
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()


# ─── CRUD + 注册校验 ────────────────────────────────────────────
async def test_crud_and_strong_registration(client, fresh_db, plate):
    plate.services = [{"name": "fin-service"}]
    admin = await _admin(client)

    # 强约束:目录内服务可登记;裸声明(base 不在目录)→ 409
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "fin-service-uat", "baseUrl": "https://uat.fin.local",
        "groupTag": "测试", "credentialAlias": "uat-cred",
    })
    assert r.status_code == 201, r.text
    assert r.json()["baseService"] == "fin-service"  # 派生落库

    # URL 必填(2026-09-23):缺省在 body 校验层拦 422
    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "fin-service-qa"})
    assert r.status_code == 422

    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "nope-bare",
                                "baseUrl": "https://nowhere.local"})
    assert r.status_code == 409
    assert "unknown_base_service" in r.text

    # plate 宕机(空目录)→ 不能登记(2026-09-20 拍板:不做 unverified 松绑)
    plate.down = True
    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "fin-service-sit",
                                "baseUrl": "https://sit.fin.local"})
    assert r.status_code == 409
    plate.down = False

    # 读全员 / 写 admin
    member = await _member(client, "alias_member")
    r = await client.get("/api/service-aliases", headers=member)
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    r = await client.post("/api/service-aliases", headers=member,
                          json={"aliasName": "fin-service-x",
                                "baseUrl": "https://x.fin.local"})
    assert r.status_code == 403

    # patch:显式 null = 清空;缺省 = 不动
    r = await client.patch("/api/service-aliases/fin-service-uat",
                           headers=admin, json={"credentialAlias": None})
    assert r.status_code == 200 and r.json()["credentialAlias"] is None
    assert r.json()["groupTag"] == "测试"
    r = await client.delete("/api/service-aliases/fin-service-uat",
                            headers=admin)
    assert r.status_code == 204
    r = await client.get("/api/service-aliases", headers=admin)
    assert r.json()["items"] == []


# ─── 解析链①:carry 别名键稀疏覆盖 ───────────────────────────────
async def test_carry_alias_key_sparse_override(fresh_db, plate):
    plate.services = [{"name": "fin-service"}]
    async with db_module.SessionLocal() as s:
        await carry_store.put_bindings(s, "fin-service",
                                       {"$.a": "base-a", "$.b": "base-b"},
            updated_by_id=None, updated_by_name="x")
        await carry_store.put_bindings(s, "fin-service-uat", {"$.b": "alias-b"}, updated_by_id=None, updated_by_name="x")  # 稀疏:只盖 b
        await s.commit()

    definition = {"steps": [
        {"api": {"service": "fin-service-uat", "headers": {}},
         "request": {"body": {}}},
        {"api": {"service": "fin-service", "headers": {}},
         "request": {"body": {}}},
    ]}
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, definition)

    # 别名键:base 之上字段级 merge(未覆盖字段继承 base)
    assert ctx.service_bindings["fin-service-uat"] == {"$.a": "base-a", "$.b": "alias-b"}
    # 本名键:行为与扩前逐字一致(无额外查询路径可见差异)
    assert ctx.service_bindings["fin-service"] == {"$.a": "base-a", "$.b": "base-b"}


async def test_carry_bare_alias_still_skipped(fresh_db, plate):
    """目录外的裸声明照旧跳过(空目录 → derive_base None),兼容不变。"""
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, {"steps": [
            {"api": {"service": "ghost-svc", "headers": {}},
             "request": {"body": {}}},
        ]})
    assert ctx.service_bindings["ghost-svc"] is None


# ─── 解析链②:凭证注入(执行者本人池子 + 显式绑定优先 + 存档记原始)──
async def _seed_bob_with_uat_cred(client) -> dict:
    """bob + 他本人池子里的 uat-cred 凭证(明文经 Fernet 加密落库)。"""
    headers = await _member(client, "bob")
    async with db_module.SessionLocal() as s:
        s.add(AuthSession(
            owner_id=await _bob_id(), alias="uat-cred",
            url="https://uat.internal",
            username_enc=fernet_encrypt("bob-uat"),
            password_enc=fernet_encrypt("pw"),
        ))
        await s.commit()
    return headers


async def _bob_id() -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(
            sa.select(User).where(User.username == "bob"))).scalar_one().id


async def test_alias_credential_injected_from_executor_pool(
        client, fresh_db, plate_mock: PlateMock, monkeypatch):
    """别名表命中 → 凭证按执行者本人池子解析并注入 users;
    存档 serviceBindings 记原始(空),injectedAuths 记全量清单(拍板②)。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    await _seed_alias()
    bob = await _seed_bob_with_uat_cred(client)
    await _seed_scenario(client, bob)  # 场景 step 引用 ${auth.qa1.token}

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    # 场景引用 fin-service(无别名)→ 别名表未命中,行为与扩前一致
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {}
    assert config_json["injectedAuths"] == ["qa1"]


async def test_alias_credential_chain_end_to_end(
        client, fresh_db, plate_mock: PlateMock, monkeypatch):
    """step 引用别名服务 fin-service-uat → 别名表命中 uat-cred →
    bob 池子解析 → users 明文注入;显式绑定优先;存档记原始。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    await _seed_alias()
    bob = await _seed_bob_with_uat_cred(client)

    # 步骤不带 ${auth.*} 模板:注入完全由「别名表默认 / 显式绑定」驱动,
    # 模板扫描不参与(它恒注入,是另一条既有语义)
    alias_step = {
        "kind": "step",
        "api": {"service": "fin-service-uat", "path": "/x",
                "headers": {"Authorization": "Bearer static"}},
    }
    await client.post("/api/scenarios", headers=bob,
                      json=_draft(scenario_id="sc-alias-cred", steps=[alias_step]))
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    # ① 无显式绑定:别名表默认生效
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        scenarioId="sc-alias-cred", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert cfg["users"]["uat-cred"]["username"] == "bob-uat"  # 本人池子明文注入
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {}               # 存档记原始(拍板②)
    assert config_json["injectedAuths"] == ["uat-cred"]

    # ② 显式绑定优先:同键绑 qa1 → 不吃别名表默认
    cases.clear()
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        scenarioId="sc-alias-cred", dataSetIds=[],
        serviceBindings={"fin-service-uat": {"authAlias": "qa1"}},
    ))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    config_json = await _last_config_json()
    assert config_json["injectedAuths"] == ["qa1"]
    assert config_json["serviceBindings"] == {
        "fin-service-uat": {"authAlias": "qa1"},
    }
