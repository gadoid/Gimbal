"""authz M2a S3.1:槽位绑定解析分层 + /auths 写面。

存量兼容不变式:slot=alias、每槽一行、env 空、默认 —— 解析与旧按名
链路逐行相同(由既有 /auths·token·执行链测试守着);本文件钉**新**
行为:分层取用、多绑定、写面校验、置默认原子切换。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import Environment
from app.models.auth_session import AuthSession
from app.models.service_alias import ServiceAlias
from app.services import run_prepare, service_aliases

from .helpers import register_and_login


async def _binding(s, owner, *, alias, slot=None, system="", env_id=None,
                   is_default=False, url="http://x") -> AuthSession:
    row = AuthSession(
        owner_id=owner, alias=alias, url=url,
        username_enc=fernet_encrypt("u"), password_enc=fernet_encrypt("p"),
        token_type="Bearer", expires_in=7200,
        system=system, env_id=env_id, slot=slot or alias,
        is_default=is_default)
    s.add(row)
    await s.flush()
    return row


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"), {"u": username})
        ).scalar()


# ── ① 解析分层 ─────────────────────────────────────────────────────

async def test_resolve_tier_env_hit_over_envless(client, fresh_db):
    await register_and_login(client, "s31a0", "pw123456")
    uid = await _uid("s31a0")
    async with db_module.SessionLocal() as s:
        env = Environment(name="s31-dev", lines={})
        s.add(env)
        await s.flush()
        base = await _binding(s, uid, alias="qa", is_default=True)
        dev = await _binding(s, uid, alias="qa-dev", slot="qa",
                             env_id=env.id, url="http://dev")
        dev_env = dev.env_id
        await s.commit()

    factory = db_module.SessionLocal
    # 无环境 → 默认行(env 空层)
    got = await run_prepare.resolve_exec_auths(factory, uid, ["qa"])
    assert [a.alias for a in got] == ["qa"] and got[0].url == "http://x"
    # 环境命中 → 该环境绑定(users 键仍是槽名 qa,alias=槽名)
    got = await run_prepare.resolve_exec_auths(factory, uid, ["qa"],
                                               env_id=dev_env)
    assert [a.alias for a in got] == ["qa"] and got[0].url == "http://dev"
    # 环境未命中任何绑定 → 默认行兜底(名字解析不落空)
    got = await run_prepare.resolve_exec_auths(factory, uid, ["qa"],
                                               env_id=99999)
    assert got[0].url == "http://x"
    # 缺槽名照旧:告警后继续(不抛)
    assert await run_prepare.resolve_exec_auths(factory, uid, ["nope"]) == []


# ── ② /auths 写面 ──────────────────────────────────────────────────

async def test_create_slot_defaults_and_second_binding(client):
    h = await register_and_login(client, "s31a", "pw123456")
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa", "username": "u", "password": "p"})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["slot"] == "qa" and first["isDefault"] is True
    assert first["system"] == "" and first["envId"] is None

    # 同名 alias(应用层名字唯一)→ 409
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa", "username": "u", "password": "p"})
    assert r.status_code == 409

    # 同槽第二绑定(不同环境)→ 非默认;默认仍指向第一行
    r = await client.post("/api/environments", headers=h, json={
        "name": "s31-api", "lines": {}})
    env_id = r.json()["id"]
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa-sit", "slot": "qa", "envId": env_id,
        "username": "u", "password": "p"})
    assert r.status_code == 201, r.text
    second = r.json()
    assert second["slot"] == "qa" and second["isDefault"] is False

    # 置默认端点:原子切换
    r = await client.post(f"/api/auths/{second['id']}/default", headers=h)
    assert r.status_code == 200 and r.json()["isDefault"] is True
    r = await client.get(f"/api/auths/{first['id']}", headers=h)
    assert r.json()["isDefault"] is False

    # 同 system+env+slot 重复 → 409(四元组键)
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa-sit2", "slot": "qa", "envId": env_id,
        "username": "u", "password": "p"})
    assert r.status_code == 409

    # 环境不存在 → 404
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa-ghost", "envId": 99999,
        "username": "u", "password": "p"})
    assert r.status_code == 404

    # 静态令牌(url 空)不回归
    r = await client.post("/api/auths", headers=h, json={
        "alias": "plat-token", "url": "",
        "username": "static", "password": "gtk_x"})
    assert r.status_code == 201 and r.json()["url"] == ""


async def test_patch_slot_fields_and_default_switch(client):
    h = await register_and_login(client, "s31b", "pw123456")
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa", "username": "u", "password": "p"})
    aid = r.json()["id"]
    r = await client.post("/api/environments", headers=h, json={
        "name": "s31-patch", "lines": {}})
    env_id = r.json()["id"]

    r = await client.patch(f"/api/auths/{aid}", headers=h, json={
        "system": "fin-service", "envId": env_id,
        "accountFields": {"orgNo": "1001"}})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["system"] == "fin-service" and out["envId"] == env_id
    assert out["accountFields"] == {"orgNo": "1001"}

    # env 显式 null = 清空;未传字段(system)不动
    r = await client.patch(f"/api/auths/{aid}", headers=h,
                           json={"envId": None})
    assert r.json()["envId"] is None
    assert r.json()["system"] == "fin-service"

    # 同 system('fin-service')+env(None)+slot('qa') 重复 → 409;
    # 换 system 可建,PATCH isDefault=true 同槽清旧默认
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa2", "slot": "qa", "system": "fin-service",
        "username": "u", "password": "p"})
    assert r.status_code == 409
    r = await client.post("/api/auths", headers=h, json={
        "alias": "qa2", "slot": "qa", "system": "crm",
        "username": "u", "password": "p"})
    assert r.status_code == 201, r.text
    r = await client.patch(f"/api/auths/{r.json()['id']}", headers=h,
                           json={"isDefault": True})
    assert r.status_code == 200 and r.json()["isDefault"] is True
    r = await client.get(f"/api/auths/{aid}", headers=h)
    assert r.json()["isDefault"] is False


# ── ③ 别名凭证默认命中:声明槽位 ────────────────────────────────────

async def test_credential_hits_use_declared_slot(client, fresh_db):
    from app.services.run_materialize import referenced_services
    steps = [{"kind": "step",
              "call": {"service": "qa-svc", "method": "GET", "path": "/x"}},
             {"kind": "step",
              "call": {"service": "legacy-svc", "method": "GET",
                       "path": "/x"}}]
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="qa-svc", base_service="qa",
                           credential_alias="qa", slot="qa"))
        # 声明槽位与旧列分叉时(直插形态),命中取 slot
        s.add(ServiceAlias(alias_name="legacy-svc", base_service="legacy",
                           credential_alias="old-name", slot="new-name"))
        await s.commit()
        hits = await service_aliases.credential_aliases_for(
            s, referenced_services(steps))
    assert hits == {"qa-svc": "qa", "legacy-svc": "new-name"}
