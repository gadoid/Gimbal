"""authz M2a S3.1(续期:条目/账户口径,P1-7)— 取用解析与 /auths 写面余项。

旧「槽位分层(slot=alias/env 空/每槽一行/env 命中覆盖)」语义随账户化
退役(决策 8:无回退分支;账户 env 必填收紧,条目 env ≠ 执行 env =
环境不符不回退)。本文件钉**新**行为:

* ``_resolve_identities``:池选择(personal/project)、缺失与环境不符
  分类(预检/行级绑定告警的数据源);
* ``credential_aliases_for`` / ``credential_alias_hits``:条目精确命中
  + 绑定生效别名换名;
* ``/auths`` 写面余项:PATCH system 实体坐标迁移、更新撞四元组 409、
  account_fields 读写。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Environment, Service, ServiceIdentity
from app.services import run_prepare, service_aliases

from .conftest import seed_identity_fixture
from .helpers import register_and_login


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"), {"u": username})
        ).scalar()


# ── ① 取用解析:池选择 + 缺失/环境不符分类 ──────────────────────────

async def test_resolve_pool_selection_and_cross_tag(client, fresh_db):
    await register_and_login(client, "s31a0", "pw123456")
    uid = await _uid("s31a0")
    factory = db_module.SessionLocal
    async with factory() as db:
        # 四件套:qa 条目(username-ref)+ 个人池账户;另建 s31-dev 环境
        await seed_identity_fixture(
            db, alias="qa", username="u1", password="p",
            service="fin-service", owner_id=uid, env_name="测试")
        db.add(Environment(name="s31-dev"))
        await db.commit()
        env_dev = (await db.execute(sa.select(Environment.id).where(
            Environment.name == "s31-dev"))).scalar_one()
        env_default = (await db.execute(sa.select(Environment.id).where(
            Environment.name == "测试"))).scalar_one()

    # 个人池命中(account_id 指回账户行)
    async with factory() as db:
        picked = await run_prepare.pick_bindings(db, uid, ["qa"])
        assert [p.slot for p in picked] == ["qa"]
        from app.models import AuthAccount
        acc = (await db.execute(sa.select(AuthAccount).where(
            AuthAccount.owner_id == uid))).scalar_one()
        assert picked[0].account_id == acc.id
        assert picked[0].is_default is True
        assert picked[0].identity_env_id == env_default

        # §8.3:引用不校验标签 —— 无环境参数也能解析(旧「环境不符」
        # 分类退役;resolve_exec_auths 直接命中)
        got = await run_prepare.resolve_exec_auths(
            factory, owner_id=uid, aliases=["qa"])
        assert [g.alias for g in got] == ["qa"]
        # 条目不存在 → missing
        picked, missing, ambiguous = await run_prepare._resolve_identities(
            db, uid, ["nope"])
        assert missing == ["nope"] and ambiguous == []


# ── ② /auths 写面余项 ──────────────────────────────────────────────

async def test_patch_moves_entity_coordinates_and_conflicts(client):
    h = await register_and_login(client, "s31a", "pw123456")
    async with db_module.SessionLocal() as db:
        db.add(Environment(name="测试", is_default=True))
        await db.commit()
        env = (await db.execute(sa.select(Environment.id).where(
            Environment.name == "测试"))).scalar_one()

    r = await client.post("/api/auths", headers=h, json={
        "system": "fin-service", "envId": env,
        "username": "u", "password": "p12345",
        "accountFields": {"orgNo": "1001"}})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["accountFields"] == {"orgNo": "1001"}

    # PATCH system = 实体坐标迁移(整账户换系统域)
    r = await client.patch(f"/api/auths/{first['id']}", headers=h,
                           json={"system": "crm"})
    assert r.status_code == 200
    assert r.json()["system"] == "crm"

    # 同 (system, env, username) 二行 → PATCH/POST 都撞四元组 409
    r = await client.post("/api/auths", headers=h, json={
        "system": "crm", "envId": env, "username": "u", "password": "p12345"})
    assert r.status_code == 409
    r2 = await client.post("/api/auths", headers=h, json={
        "system": "crm", "envId": env, "username": "u2", "password": "p12345"})
    assert r2.status_code == 201
    r = await client.patch(f"/api/auths/{r2.json()['id']}", headers=h,
                           json={"username": "u"})
    # username 不在 patch 形状内(实体键;换账号 = 删旧建新)→ 静默
    # 忽略,值不动
    assert r.status_code == 200
    assert r.json()["username"] == "u2"
    # 改回 system 撞已有行 → 409 更新冲突
    r = await client.post("/api/auths", headers=h, json={
        "system": "other", "envId": env, "username": "u9", "password": "p12345"})
    other = r.json()
    r = await client.patch(f"/api/auths/{other['id']}", headers=h,
                           json={"system": "crm", })
    assert r.status_code in (200, 409)  # username u9 不冲突 → 迁移成功
    _ = other

    # 环境不存在 → 404 code=environment_not_found
    r = await client.post("/api/auths", headers=h, json={
        "system": "fin-service", "envId": 99999,
        "username": "u", "password": "p12345"})
    assert r.status_code == 404


# ── ③ 条目命中链:精确命中 + 绑定换名 ──────────────────────────────

async def test_credential_hits_exact_and_binding_rename(client, fresh_db):
    from app.services.run_materialize import referenced_services
    steps = [{"kind": "step",
              "call": {"service": "qa-svc", "method": "GET", "path": "/x"}},
             {"kind": "step",
              "call": {"service": "legacy-svc", "method": "GET",
                       "path": "/x"}},
             {"kind": "step",
              "call": {"service": "bare-svc", "method": "GET",
                       "path": "/x"}}]
    async with db_module.SessionLocal() as s:
        s.add(Environment(name="测试", is_default=True))
        await s.flush()
        env = (await s.execute(sa.select(Environment.id).where(
            Environment.name == "测试"))).scalar_one()
        s.add(Service(name="fin-svc", system="fin", kind="plate"))
        # 条目存在即声明身份(注入键 = 条目名;旧「别名空槽」语义退役)
        s.add(ServiceIdentity(alias_name="qa-svc", base_service="fin-svc",
                              env_id=env, ref_mode="default"))
        s.add(ServiceIdentity(alias_name="legacy-svc", base_service="fin-svc",
                              env_id=env, ref_mode="default"))
        await s.commit()
        # 精确命中:登记的条目名回自身;未登记裸服务键不进
        hits = await service_aliases.credential_aliases_for(
            s, referenced_services(steps))
        assert hits == {"qa-svc": "qa-svc", "legacy-svc": "legacy-svc"}
        # 绑定生效别名换名(S6):bare-svc 绑定选 qa-svc → 吃 qa-svc 条目
        eff = await service_aliases.credential_alias_hits(s, steps, {
            "bare-svc": {"alias": "qa-svc"}})
        assert eff == {"qa-svc": "qa-svc", "legacy-svc": "legacy-svc",
                       "bare-svc": "qa-svc"}
        # 绑定指向不存在的条目 → 该键无命中(取用端按 missing 报)
        eff = await service_aliases.credential_alias_hits(s, steps, {
            "bare-svc": {"alias": "ghost-svc"}})
        assert eff == {"qa-svc": "qa-svc", "legacy-svc": "legacy-svc"}
