"""authz M2a S2.2:部署表 CRUD / 冲突清单 / 默认环境切换 / 项目默认
环境 / 偏好 run.environment / 方案环境校验。"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import Environment
from app.models.permission import AuditLog
from app.services.env_chain import EnvChoice, resolve_environment

from .helpers import make_draft as _draft, role_headers


async def _env_id(client, h, name: str) -> int:
    r = await client.post("/api/environments", headers=h, json={
        "name": name, "description": "", "lines": {}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _audit_ops(action: str) -> list[str]:
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(sa.select(AuditLog).where(
            AuditLog.action == action).order_by(AuditLog.id))).scalars()
        return [r.detail.get("op") for r in rows]


# ── 部署表 CRUD + 权限 + 审计 ───────────────────────────────────────

async def test_deployment_crud_gates_and_audit(client):
    adm = await role_headers(client, "s22_adm", role="admin")
    usr = await role_headers(client, "s22_usr", role="user")
    env = await _env_id(client, adm, "s22-dev")

    body = {"baseService": "fin-service", "envId": env,
            "baseUrl": "http://fin-dev"}
    r = await client.post("/api/deployments", headers=usr, json=body)
    assert r.status_code == 403, r.text            # 写 = ops.write
    r = await client.post("/api/deployments", headers=adm, json=body)
    assert r.status_code == 201, r.text
    dep = r.json()
    assert dep["baseService"] == "fin-service" and dep["envId"] == env
    r = await client.post("/api/deployments", headers=adm, json=body)
    assert r.status_code == 409, r.text            # 同键重复
    r = await client.post("/api/deployments", headers=adm, json={
        **body, "baseService": "crm", "baseUrl": "ftp://x"})
    assert r.status_code == 422, r.text            # 地址须 http(s)
    r = await client.post("/api/deployments", headers=adm, json={
        **body, "baseService": "crm", "envId": 99999})
    assert r.status_code == 404, r.text            # 环境不存在

    # 读 = 登录用户;按环境过滤
    r = await client.get("/api/deployments", headers=usr,
                         params={"envId": env})
    assert r.status_code == 200 and len(r.json()) == 1

    r = await client.patch(f"/api/deployments/{dep['id']}", headers=adm,
                           json={"baseUrl": "http://fin-dev-2"})
    assert r.status_code == 200 and r.json()["baseUrl"] == "http://fin-dev-2"
    r = await client.delete(f"/api/deployments/{dep['id']}", headers=usr)
    assert r.status_code == 403
    r = await client.delete(f"/api/deployments/{dep['id']}", headers=adm)
    assert r.status_code == 204
    assert await _audit_ops("deployment.write") == [
        "create", "update", "delete"]


async def test_default_environment_switch(client):
    adm = await role_headers(client, "s22_def", role="admin")
    usr = await role_headers(client, "s22_defu", role="user")
    a = await _env_id(client, adm, "s22-a")
    b = await _env_id(client, adm, "s22-b")

    r = await client.post(f"/api/environments/{a}/default", headers=usr)
    assert r.status_code == 403
    r = await client.post(f"/api/environments/{a}/default", headers=adm)
    assert r.status_code == 200 and r.json()["is_default"] is True
    r = await client.post(f"/api/environments/{b}/default", headers=adm)
    assert r.status_code == 200 and r.json()["is_default"] is True
    async with db_module.SessionLocal() as s:
        defaults = (await s.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalars().all()
        assert defaults == [b]                     # 恰一行,旧默认已清
    r = await client.delete(f"/api/environments/{b}/default", headers=adm)
    assert r.status_code == 200 and r.json()["is_default"] is False
    assert "set_default" in await _audit_ops("environment.write")


# ── 项目默认环境 ────────────────────────────────────────────────────

async def test_project_default_environment(client):
    adm = await role_headers(client, "s22_padm", role="admin")
    member = await role_headers(client, "s22_pm", role="user")
    env = await _env_id(client, adm, "s22-proj-env")
    async with db_module.SessionLocal() as s:
        pm_id = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='s22_pm'"))).scalar()
    r = await client.post("/api/projects", headers=adm, json={
        "name": "s22-proj", "firstAdminUserId": pm_id})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["defaultEnvironmentId"] is None

    # 项目管理员可设;不存在的环境 422
    r = await client.patch(f"/api/projects/{pid}", headers=member,
                           json={"defaultEnvironmentId": 99999})
    assert r.status_code == 422, r.text
    r = await client.patch(f"/api/projects/{pid}", headers=member,
                           json={"defaultEnvironmentId": env})
    assert r.status_code == 200 and r.json()["defaultEnvironmentId"] == env
    # 只改名不动默认环境(未传 = 不动)
    r = await client.patch(f"/api/projects/{pid}", headers=member,
                           json={"description": "x"})
    assert r.json()["defaultEnvironmentId"] == env
    async with db_module.SessionLocal() as s:
        assert await resolve_environment(s, project_id=pid) == \
            EnvChoice(env, "project")
    # 显式 null = 清空
    r = await client.patch(f"/api/projects/{pid}", headers=member,
                           json={"defaultEnvironmentId": None})
    assert r.json()["defaultEnvironmentId"] is None


# ── 偏好 run.environment ────────────────────────────────────────────

async def test_run_environment_preference(client):
    adm = await role_headers(client, "s22_pref_adm", role="admin")
    usr = await role_headers(client, "s22_pref", role="user")
    env = await _env_id(client, adm, "s22-pref-env")
    r = await client.put("/api/me/preferences/run.environment", headers=usr,
                         json={"value": {"environmentId": 99999}})
    assert r.status_code == 422 and "environment_not_found" in r.text
    r = await client.put("/api/me/preferences/run.environment", headers=usr,
                         json={"value": {"environmentId": env}})
    assert r.status_code == 200, r.text
    r = await client.get("/api/me/preferences", headers=usr)
    assert r.json()["items"]["run.environment"] == {"environmentId": env}
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='s22_pref'"))).scalar()
        assert await resolve_environment(s, user_id=uid) == \
            EnvChoice(env, "preference")


# ── 方案环境写时校验 ────────────────────────────────────────────────

async def test_scheme_environment_validated_on_write(client):
    adm = await role_headers(client, "s22_sch", role="admin")
    env = await _env_id(client, adm, "s22-sch-env")
    r = await client.post("/api/scenarios", headers=adm,
                          json=_draft("sc-s22-sch"))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/scenarios/sc-s22-sch/run-schemes",
                          headers=adm,
                          json={"name": "坏环境", "environmentId": 99999})
    assert r.status_code == 422 and "environment_not_found" in r.text
    r = await client.post("/api/scenarios/sc-s22-sch/run-schemes",
                          headers=adm,
                          json={"name": "好环境", "environmentId": env})
    assert r.status_code == 201, r.text
    assert r.json()["environmentId"] == env
