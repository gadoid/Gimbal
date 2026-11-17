"""身份条目基础层(registry rework §1.3;P1-7 续期)— CRUD/登记校验 +
两条解析链。

* 登记校验强约束(拍板):裸声明不猜;plate 宕机(空目录)且主档
  未登记时不能登记;条目 env 必填(平台默认环境兜底,无环境明确拒);
* carry 解析链:条目键稀疏覆盖 > base 服务键 > 全局默认;
* 凭证解析链:条目 → ref → 执行者本人池子账户(§4.1);场景显式
  绑定优先;存档 serviceBindings 只记原始(拍板)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Service, ServiceIdentity, User
from app.services import carry_store
from app.services.carry_injection import build_carry_context

from .conftest import seed_identity_fixture
from .helpers import make_draft as _draft, wait_until as _wait
from .test_carry_api import _admin
from .test_run_bindings_injection import _last_config_json, _seed_scenario  # noqa: F401 复用
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


async def _env_id() -> int:
    """条目 env 必填(§1.3):布景兜底 —— 没有默认环境就建一个。"""
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


async def _seed_identity(alias: str = "fin-service-uat",
                         base: str = "fin-service",
                         ref_mode: str = "username",
                         ref_username: str = "bob-uat") -> None:
    """只种条目声明(carry 链/分类桶用;账户由四件套另种)。"""
    env = await _env_id()
    async with db_module.SessionLocal() as s:
        s.add(ServiceIdentity(
            alias_name=alias, base_service=base, env_id=env,
            ref_mode=ref_mode,
            ref_username=(ref_username if ref_mode == "username" else "")))
        await s.commit()


# ─── CRUD + 登记校验 ────────────────────────────────────────────
async def test_crud_and_strong_registration(client, fresh_db, plate):
    plate.services = [{"name": "fin-service"}]
    await _env_id()
    admin = await _admin(client)

    # 强约束:目录内服务可登记;退役 slot 入参直接 422(§2.4 不做旧
    # 字段影子 —— extra=forbid;注入键=条目名)
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "fin-service-uat", "slot": "uat-cred",
    })
    assert r.status_code == 422
    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "fin-service-uat"})
    assert r.status_code == 201, r.text
    assert r.json()["baseService"] == "fin-service"  # 派生落库
    assert r.json()["slot"] == "fin-service-uat"  # slot 出参 = 条目名
    assert r.json()["envId"] is not None
    assert r.json()["refMode"] == "default"

    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "nope-bare"})
    assert r.status_code == 409
    assert "unknown_base_service" in r.text

    # plate 宕机(空目录 + 主档未登记)→ 不能登记
    # (2026-09-20 拍板:不做 unverified 松绑)
    plate.down = True
    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "fin-service-sit"})
    assert r.status_code == 409
    plate.down = False

    # 读全员 / 写 admin
    member = await _member(client, "alias_member")
    r = await client.get("/api/service-aliases", headers=member)
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    r = await client.post("/api/service-aliases", headers=member,
                          json={"aliasName": "fin-service-x"})
    assert r.status_code == 403

    # patch:ref/display 可改;缺省 = 不动;退役 slot 入参 422(extra=forbid)
    r = await client.patch("/api/service-aliases/fin-service-uat",
                           headers=admin, json={})
    assert r.status_code == 200 and r.json()["slot"] == "fin-service-uat"
    r = await client.patch("/api/service-aliases/fin-service-uat",
                           headers=admin, json={"slot": None})
    assert r.status_code == 422
    r = await client.patch(
        "/api/service-aliases/fin-service-uat", headers=admin,
        json={"refMode": "username", "refUsername": "bob", "display": "UAT"})
    assert r.status_code == 200
    assert r.json()["refMode"] == "username"
    assert r.json()["refUsername"] == "bob"
    assert r.json()["display"] == "UAT"
    r = await client.delete("/api/service-aliases/fin-service-uat",
                            headers=admin)
    assert r.status_code == 204
    r = await client.get("/api/service-aliases", headers=admin)
    assert r.json()["items"] == []


async def test_create_without_any_environment_422(
        client, fresh_db, plate):
    """env 必填收紧(§1.3):无任何环境 → 明确拒绝(无静默回退)。"""
    plate.services = [{"name": "fin-service"}]
    admin = await _admin(client)
    r = await client.post("/api/service-aliases", headers=admin,
                          json={"aliasName": "fin-service-uat"})
    assert r.status_code == 422, r.text
    assert "no_environment" in r.text


# ─── 解析链①:carry 条目键稀疏覆盖 ───────────────────────────────
async def test_carry_alias_key_sparse_override(fresh_db, plate):
    plate.services = [{"name": "fin-service"}]
    async with db_module.SessionLocal() as s:
        await carry_store.put_bindings(s, "fin-service",
                                       {"$.a": "base-a", "$.b": "base-b"},
            updated_by_id=None, updated_by_name="x")
        await carry_store.put_bindings(s, "fin-service-uat", {"$.b": "alias-b"}, updated_by_id=None, updated_by_name="x")  # 稀疏:只盖 b
        await s.commit()

    definition = {"steps": [
        {"call": {"service": "fin-service-uat", "headers": {}},
         "request": {"body": {}}},
        {"call": {"service": "fin-service", "headers": {}},
         "request": {"body": {}}},
    ]}
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, definition)

    # 条目键:base 之上字段级 merge(未覆盖字段继承 base)
    assert ctx.service_bindings["fin-service-uat"] == {"$.a": "base-a", "$.b": "alias-b"}
    # 本名键:行为与扩前逐字一致(无额外查询路径可见差异)
    assert ctx.service_bindings["fin-service"] == {"$.a": "base-a", "$.b": "base-b"}


async def test_carry_bare_alias_still_skipped(fresh_db, plate):
    """目录外的裸声明照旧跳过(空目录 → derive_base None),兼容不变。"""
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, {"steps": [
            {"call": {"service": "ghost-svc", "headers": {}},
             "request": {"body": {}}},
        ]})
    assert ctx.service_bindings["ghost-svc"] is None


# ─── 解析链②:凭证注入(条目→ref→执行者本人池子 + 显式绑定优先)──
async def _seed_bob_with_accounts(client) -> dict:
    """bob + 本人池账户 + 三条目(uat / qa1 / qa1-换用)四件套布景。"""
    headers = await _member(client, "bob")
    async with db_module.SessionLocal() as s:
        bob_id = (await s.execute(
            sa.select(User).where(User.username == "bob"))).scalar_one().id
        # 同 (system,env) 至多一个默认账户:首行占默认位,其余显式让位
        # (三条目全走 username-ref,与默认位无关)
        await seed_identity_fixture(
            s, alias="fin-service-uat", username="bob-uat", password="pw",
            service="fin-service", owner_id=bob_id)
        await seed_identity_fixture(
            s, alias="qa1", username="qa1-u", password="pw",
            service="fin-service", owner_id=bob_id, is_default=False)
        await seed_identity_fixture(
            s, alias="fin-service-qa1", username="bob-qa1", password="pw",
            service="fin-service", owner_id=bob_id, is_default=False)
    return headers


async def test_alias_credential_injected_from_executor_pool(
        client, fresh_db, plate_mock: PlateMock, monkeypatch):
    """${auth.<条目名>} 模板扫描 → 条目 → ref → bob 池子账户注入;
    存档 serviceBindings 记原始(空),injectedAuths 记全量清单(拍板②)。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    bob = await _seed_bob_with_accounts(client)
    await _seed_scenario(client, bob)  # 场景 step 引用 ${auth.qa1.token}

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob,
                          json=_run_payload(dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)

    # 场景引用 fin-service(无条目引用)→ 行为与扩前一致
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {}
    assert config_json["injectedAuths"] == ["qa1"]


async def test_alias_credential_chain_end_to_end(
        client, fresh_db, plate_mock: PlateMock, monkeypatch):
    """step 引用条目名 fin-service-uat → 条目 ref → bob 池子账户 →
    users 明文注入;方案选别名换条目(S6);存档记原始。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    bob = await _seed_bob_with_accounts(client)

    # 步骤不带 ${auth.*} 模板:注入完全由「条目名步骤 / 绑定换用」驱动,
    # 模板扫描不参与(它恒注入,是另一条既有语义)
    alias_step = {
        "kind": "step",
        "call": {"service": "fin-service-uat", "path": "/x",
                "headers": {"Authorization": "Bearer static"}},
    }
    await client.post("/api/scenarios", headers=bob,
                      json=_draft(scenario_id="sc-alias-cred", steps=[alias_step]))
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    # ① 无显式绑定:条目声明默认生效(注入键 = 条目名)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        scenarioId="sc-alias-cred", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = cases[0]["config"]
    assert cfg["users"]["fin-service-uat"]["username"] == "bob-uat"  # 本人池子明文注入
    config_json = await _last_config_json()
    assert config_json["serviceBindings"] == {}               # 存档记原始(拍板②)
    assert config_json["injectedAuths"] == ["fin-service-uat"]

    # ② 绑定换用条目(S6):同基础服务的 fin-service-qa1
    cases.clear()
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        scenarioId="sc-alias-cred", dataSetIds=[],
        serviceBindings={"fin-service-uat": {"alias": "fin-service-qa1"}},
    ))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    config_json = await _last_config_json()
    assert config_json["injectedAuths"] == ["fin-service-qa1"]
    assert config_json["serviceBindings"] == {
        "fin-service-uat": {"alias": "fin-service-qa1"},
    }


# ─── 三态接入 kind(P1.0/W2-W4;kind 自服务主档)─────────────────
async def test_kind_default_plate_and_external_requires_base_service(
        client, fresh_db, plate):
    """plate 态缺省、目录强约束不变;external 态(b2-8/归一 v1.0 §1.6)
    不派生 —— 必须显式 base_service 且指向主档第三方服务
    (重构:external 校验源从 plate 目录切主档,不受可达性影响);
    非法 kind 422(Literal)。"""
    plate.services = [{"name": "fin-service"}]
    await _env_id()
    admin = await _admin(client)
    # 主档登记 integration 服务(external 条目的指向落点)
    async with db_module.SessionLocal() as s:
        s.add(Service(name="pay-service", system="pay", kind="integration"))
        await s.commit()

    # 缺省 kind='plate':目录内派生照旧 + 出参带 kind(主档 miss → plate)
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "fin-service-uat"})
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "plate"
    assert r.json()["baseService"] == "fin-service"

    # external:不派生 —— 缺 base_service 422;显式指向主档服务 201
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "pay-gw",
        "kind": "external"})
    assert r.status_code == 422, r.text
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "pay-gw",
        "kind": "external", "baseService": "pay-service"})
    assert r.status_code == 201, r.text
    assert r.json()["baseService"] == "pay-service"
    # kind 出参自主档带出(integration 服务如实显示)
    assert r.json()["kind"] == "integration"

    # external 指向主档外服务 → 409(不猜;先在主档登记)
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "gw2", "kind": "external", "baseService": "ghost-pay"})
    assert r.status_code == 409, r.text
    assert "unknown_base_service" in r.text

    # 非法 kind → 422
    r = await client.post("/api/service-aliases", headers=admin, json={
        "aliasName": "x-svc", "kind": "weird"})
    assert r.status_code == 422

    # 列表出参带 kind
    r = await client.get("/api/service-aliases", headers=admin)
    kinds = {i["aliasName"]: i["kind"] for i in r.json()["items"]}
    assert kinds["fin-service-uat"] == "plate"
    assert kinds["pay-gw"] == "integration"


async def test_classify_services_three_buckets(fresh_db, plate):
    """判定链(W3):alias_name 条目精确 > 主档服务名精确;未命中 →
    unknown(保存告警口径的数据源)。kind 自主档。"""
    from app.services import service_aliases as svc
    env = await _env_id()
    async with db_module.SessionLocal() as s:
        s.add(Service(name="fin-service", system="fin", kind="plate"))
        s.add(Service(name="pay-service", system="pay", kind="external"))
        s.add(ServiceIdentity(alias_name="fin-service-uat",
                              base_service="fin-service", env_id=env,
                              ref_mode="default"))
        s.add(ServiceIdentity(alias_name="pay-service",
                              base_service="pay-service", env_id=env,
                              ref_mode="default"))
        await s.commit()
    async with db_module.SessionLocal() as s:
        out = await svc.classify_services(s, [
            "fin-service-uat", "pay-service", "fin-service",
            "never-registered"])
    assert out == {
        "plate": ["fin-service-uat", "fin-service"],
        "external": ["pay-service"],
        "unknown": ["never-registered"],
    }
    # 空入参 → 全空桶
    async with db_module.SessionLocal() as s:
        assert await svc.classify_services(s, []) == {
            "plate": [], "external": [], "unknown": []}


async def test_classify_endpoint_read_face(client, fresh_db, plate):
    """W11 读面:GET /service-aliases/classify(member 可读,编排器徽标
    + 保存告警的数据源);repeated-param 传服务键集。"""
    env = await _env_id()
    async with db_module.SessionLocal() as s:
        s.add(Service(name="fin-service", system="fin", kind="plate"))
        s.add(Service(name="pay-service", system="pay", kind="external"))
        s.add(ServiceIdentity(alias_name="fin-service-uat",
                              base_service="fin-service", env_id=env,
                              ref_mode="default"))
        s.add(ServiceIdentity(alias_name="pay-service",
                              base_service="pay-service", env_id=env,
                              ref_mode="default"))
        await s.commit()
    member = await _member(client, "clfmem")
    r = await client.get("/api/service-aliases/classify", headers=member,
                         params=[("services", "fin-service"),
                                 ("services", "pay-service"),
                                 ("services", "ghost-svc")])
    assert r.status_code == 200, r.text
    assert r.json() == {"plate": ["fin-service"],
                        "external": ["pay-service"],
                        "unknown": ["ghost-svc"]}
    # 未带参数 → 全空桶(不报错)
    r = await client.get("/api/service-aliases/classify", headers=member)
    assert r.status_code == 200
    assert r.json() == {"plate": [], "external": [], "unknown": []}
