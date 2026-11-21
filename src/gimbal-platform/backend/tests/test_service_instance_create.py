"""服务×环境实例创建/编辑用例(``PUT /services/{service}/instances``)。

单事务写 deployments(API 地址)+ system_env_instances(系统×环境登录口)
+ 可选 service_identities(调用身份);Admin/ops.write;失败整单回滚。
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models import Environment, Service
from app.models.deployment import Deployment
from app.models.service_identity import ServiceIdentity
from app.models.system_env_instance import SystemEnvInstance

from .helpers import role_headers


async def _seed() -> int:
    async with db_module.SessionLocal() as s:
        env = Environment(name="dev", is_default=True)
        s.add(env)
        await s.flush()
        s.add(Service(name="fin", system="fin", kind="plate"))
        await s.commit()
        return env.id


async def _count(model) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(sa.func.count()).select_from(
            model))).scalar_one()


@pytest.mark.asyncio
async def test_create_instance_writes_three_tables(client: AsyncClient):
    env = await _seed()
    h = await role_headers(client, "svc-put", role="admin")
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env,
        "baseUrl": "https://fin-dev.example",
        "loginUrl": "https://login.fin-dev",
        "line": "v4.4#3",
        "note": "联调",
        "identity": {"aliasName": "fin-dev", "refMode": "default"},
    })
    assert r.status_code == 200, r.text
    inst = r.json()
    assert inst["envId"] == env
    assert inst["baseUrl"] == "https://fin-dev.example"
    assert inst["loginUrl"] == "https://login.fin-dev"
    assert inst["line"] == "v4.4#3"
    assert [i["aliasName"] for i in inst["identities"]] == ["fin-dev"]

    async with db_module.SessionLocal() as s:
        dep = (await s.execute(sa.select(Deployment).where(
            Deployment.base_service == "fin",
            Deployment.env_id == env))).scalar_one()
        assert dep.base_url == "https://fin-dev.example"
        sysinst = (await s.execute(sa.select(SystemEnvInstance).where(
            SystemEnvInstance.system == "fin",
            SystemEnvInstance.env_id == env))).scalar_one()
        assert sysinst.login_url == "https://login.fin-dev"
        assert sysinst.line == "v4.4#3"
        ident = (await s.execute(sa.select(ServiceIdentity).where(
            ServiceIdentity.alias_name == "fin-dev"))).scalar_one()
        assert (ident.base_service, ident.env_id, ident.ref_mode) == (
            "fin", env, "default")


@pytest.mark.asyncio
async def test_upsert_keeps_identity_and_updates_fields(client: AsyncClient):
    env = await _seed()
    h = await role_headers(client, "svc-put2", role="admin")
    body = {"envId": env, "baseUrl": "https://a.example",
            "identity": {"aliasName": "fin-dev"}}
    assert (await client.put("/api/services/fin/instances", headers=h,
                             json=body)).status_code == 200
    # 二次 upsert:只改地址/登录口,不再建身份
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env, "baseUrl": "https://b.example",
        "loginUrl": "https://login-b"})
    assert r.status_code == 200, r.text
    assert r.json()["baseUrl"] == "https://b.example"
    assert [i["aliasName"] for i in r.json()["identities"]] == ["fin-dev"]
    assert await _count(ServiceIdentity) == 1
    assert await _count(Deployment) == 1


@pytest.mark.asyncio
async def test_env_tag_autocreates_environment(client: AsyncClient):
    await _seed()
    h = await role_headers(client, "svc-tag", role="admin")
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envTag": "qa", "baseUrl": "https://qa.example",
        "identity": {"aliasName": "fin-qa"}})
    assert r.status_code == 200, r.text
    assert r.json()["envName"] == "qa"
    async with db_module.SessionLocal() as s:
        assert (await s.execute(sa.select(Environment.id).where(
            Environment.name == "qa"))).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_requires_base_url_or_identity(client: AsyncClient):
    env = await _seed()
    h = await role_headers(client, "svc-empty", role="admin")
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env})
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "service_instance_empty"


@pytest.mark.asyncio
async def test_rejects_bad_url_and_unknown_service(client: AsyncClient):
    env = await _seed()
    h = await role_headers(client, "svc-bad", role="admin")
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env, "baseUrl": "ftp://nope"})
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["code"] == "deployment_url_invalid"
    r = await client.put("/api/services/nope/instances", headers=h, json={
        "envId": env, "baseUrl": "https://x.example"})
    assert r.status_code == 404, r.text
    assert r.json()["detail"]["code"] == "service_not_found"


@pytest.mark.asyncio
async def test_duplicate_identity_rolls_back_deployment(client: AsyncClient):
    env = await _seed()
    async with db_module.SessionLocal() as s:
        s.add(ServiceIdentity(alias_name="fin-dev", base_service="fin",
                              env_id=env, ref_mode="default"))
        await s.commit()
    h = await role_headers(client, "svc-dup", role="admin")
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env, "baseUrl": "https://x.example",
        "identity": {"aliasName": "fin-dev"}})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "service_instance_identity_taken"
    # 单事务:地址行不得残留
    assert await _count(Deployment) == 0


@pytest.mark.asyncio
async def test_requires_ops_write(client: AsyncClient):
    env = await _seed()
    h = await role_headers(client, "svc-user")
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env, "baseUrl": "https://x.example"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "capability_forbidden"


# ── loginUrl scheme 闸(口径与 baseUrl 一致;引擎登录口直接消费)──

@pytest.mark.asyncio
async def test_rejects_bad_login_url_scheme_both_endpoints(client: AsyncClient):
    """非空 loginUrl 必须 http(s) 开头;空串 = 清除,放行。"""
    env = await _seed()
    h = await role_headers(client, "svc-login", role="admin")
    for bad in ("ftp://x", "not-a-url", "https//missing-colon"):
        r = await client.put("/api/services/fin/instances", headers=h, json={
            "envId": env, "baseUrl": "https://x.example", "loginUrl": bad})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "login_url_invalid"
        # 旧端点(环境配置页)同款闸
        r = await client.put(f"/api/services/instances/fin/{env}",
                             headers=h, json={"loginUrl": bad})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "login_url_invalid"
    # 空串 = 清除;两侧都放行
    r = await client.put("/api/services/fin/instances", headers=h, json={
        "envId": env, "baseUrl": "https://x.example", "loginUrl": ""})
    assert r.status_code == 200, r.text
    assert r.json()["loginUrl"] == ""
    r = await client.put(f"/api/services/instances/fin/{env}",
                         headers=h, json={"loginUrl": ""})
    assert r.status_code in (200, 201), r.text
    assert r.json()["loginUrl"] == ""


def test_integrity_conflict_dispatch_by_constraint_name():
    """提交点完整性冲突按约束名分派(同 scenario_store 教训):
    身份别名唯一 → identity_taken;deployment 等其余约束 → 保守回落
    service_instance_conflict,不再一律误报「身份撞名」。"""
    from types import SimpleNamespace

    from app.routers.services import _instance_integrity_conflict

    def _err(name: str) -> Exception:
        return SimpleNamespace(orig=SimpleNamespace(
            diag=SimpleNamespace(constraint_name=name)))

    code, _ = _instance_integrity_conflict(_err(
        "service_identities_alias_name_key"))
    assert code == "service_instance_identity_taken"
    code, _ = _instance_integrity_conflict(_err("uq_deployments_service_env"))
    assert code == "service_instance_conflict"
    code, msg = _instance_integrity_conflict(_err("uq_instance_system_env"))
    assert code == "service_instance_conflict"
    assert "uq_instance_system_env" in msg     # 约束名随消息,便于诊断
    # 无约束名(驱动差异)→ 保守回落,不抛
    code, _ = _instance_integrity_conflict(Exception("boom"))
    assert code == "service_instance_conflict"
