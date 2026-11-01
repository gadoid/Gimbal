"""入站身份 P1(webhook 设计 v3 §4):认证分流、管理 API、入口改造、
可见性(D8)与 grant 运行前重校验(P1-5)。

令牌形状:gic_ 入站凭证(Authorization: Bearer)/ ggt_ grant
(X-Gimbal-Grant);库中只存 sha256。认证矩阵见设计 §9:

* gic_/JWT 分流;凭证吊销 401;别名未启用入站 401;
* grant 过期 / 撤销 / 不属于该别名 403;JWT 带 grant 头 400;
* 认证失败入审计(v3 定案);
* 平台模式写接口 403(只读闸);个人模式按 grant 用户可见性;
* identityMode 与请求体冲突 422;grant 失效 → 暂停 grant_revoked。
"""
from __future__ import annotations

import hashlib

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.core.security import fernet_encrypt, hash_password
from app.models import Execution, User
from app.models.inbound_identity import InboundCredential, InboundGrant
from app.models.integration_task import IntegrationTask
from app.models.permission import AuditLog
from app.models.service_alias import ServiceAlias
from app.services import integration_runner
from app.services.inbound_identity import (
    generate_credential_token, generate_grant_token, sha256_hex,
)

from .helpers import make_draft as _draft, wait_until as _wait

# ── 种子助手(直插 DB,绕过 plate 目录校验 —— 校验面归别名基础层用例)──


async def _seed_platform_user() -> None:
    async with db_module.SessionLocal() as db:
        exists = (await db.execute(
            sa.select(User).where(User.is_system == True))).scalar()  # noqa: E712
        if exists is None:
            db.add(User(username="__platform__", display_name="平台系统",
                        password_hash=hash_password("x"), is_system=True))
            await db.commit()


async def _seed_alias(name: str = "agent-sys", **over) -> None:
    row = ServiceAlias(
        alias_name=name, base_service="pay-service", kind="external",
        base_url="https://cb.example.local", inbound_enabled=True,
        callback_enabled=True, callback_path="/gimbal/callback",
        callback_secret=fernet_encrypt("cb-secret-1"))
    for k, v in over.items():
        setattr(row, k, v)
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()


async def _mk_credential(alias: str = "agent-sys", *,
                         revoked=False) -> str:
    token = generate_credential_token()
    from datetime import datetime, timezone
    async with db_module.SessionLocal() as s:
        s.add(InboundCredential(
            alias_name=alias, token_hash=sha256_hex(token), name="t",
            revoked_at=datetime.now(timezone.utc) if revoked else None))
        await s.commit()
    return token


async def _mk_grant(alias: str, user_id: int, *,
                    days=30, revoked=False, expired=False,
                    other_alias: str | None = None) -> str:
    from datetime import datetime, timedelta, timezone
    token = generate_grant_token()
    now = datetime.now(timezone.utc)
    exp = now - timedelta(days=1) if expired else now + timedelta(days=days)
    async with db_module.SessionLocal() as s:
        s.add(InboundGrant(
            alias_name=other_alias or alias, user_id=user_id,
            token_hash=sha256_hex(token), expires_at=exp,
            revoked_at=now if revoked else None))
        await s.commit()
    return token


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(
            sa.select(User.id).where(User.username == username))).scalar_one()


def _gic(token: str, grant: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if grant:
        h["X-Gimbal-Grant"] = grant
    return h


GET_STEP = {"kind": "step", "id": "s1", "call": {
    "protocol": "http", "service": "svc", "method": "GET", "path": "/x"},
    "request": {"kind": "request", "body": {}}, "strategy": []}
POST_STEP = {"kind": "step", "id": "s1", "call": {
    "protocol": "http", "service": "svc", "method": "POST", "path": "/x"},
    "request": {"kind": "request", "body": {}}, "strategy": []}


# ── 认证分流矩阵 ─────────────────────────────────────────────────


class TestAuthFork:
    async def test_jwt_path_unchanged(self, client: AsyncClient):
        h = await _register(client, "p1_alice")
        r = await client.get("/api/executions", headers=h)
        assert r.status_code == 200

    async def test_bad_credential_401_and_audited(self, client):
        await _seed_alias()
        r = await client.get(
            "/api/executions", headers=_gic("gic_" + "nonsense" * 6))
        assert r.status_code == 401
        assert "credential_invalid" in r.text
        async with db_module.SessionLocal() as s:
            n = (await s.execute(sa.select(sa.func.count()).where(
                AuditLog.action == "inbound.auth_failed"))).scalar_one()
        assert n >= 1

    async def test_revoked_credential_401(self, client):
        await _seed_alias()
        token = await _mk_credential(revoked=True)
        r = await client.get("/api/executions", headers=_gic(token))
        assert r.status_code == 401

    async def test_alias_inbound_disabled_401(self, client):
        await _seed_alias(inbound_enabled=False)
        token = await _mk_credential()
        r = await client.get("/api/executions", headers=_gic(token))
        assert r.status_code == 401
        assert "inbound_disabled" in r.text

    async def test_grant_ok_personal_mode(self, client):
        await _seed_platform_user()
        await _seed_alias()
        await _register(client, "p1_bob")
        uid = await _user_id("p1_bob")
        token = await _mk_credential()
        grant = await _mk_grant("agent-sys", uid)
        r = await client.get("/api/executions", headers=_gic(token, grant))
        assert r.status_code == 200

    async def test_grant_revoked_403(self, client):
        await _seed_alias()
        await _register(client, "p1_bob")
        uid = await _user_id("p1_bob")
        token = await _mk_credential()
        grant = await _mk_grant("agent-sys", uid, revoked=True)
        r = await client.get("/api/executions", headers=_gic(token, grant))
        assert r.status_code == 403
        assert "grant_invalid" in r.text

    async def test_grant_expired_403(self, client):
        await _seed_alias()
        await _register(client, "p1_bob")
        uid = await _user_id("p1_bob")
        token = await _mk_credential()
        grant = await _mk_grant("agent-sys", uid, expired=True)
        r = await client.get("/api/executions", headers=_gic(token, grant))
        assert r.status_code == 403
        assert "grant_expired" in r.text

    async def test_grant_other_alias_403(self, client):
        await _seed_alias("agent-sys")
        await _seed_alias("agent-other")
        await _register(client, "p1_bob")
        uid = await _user_id("p1_bob")
        token = await _mk_credential("agent-sys")
        grant = await _mk_grant("agent-other", uid, other_alias="agent-other")
        r = await client.get("/api/executions", headers=_gic(token, grant))
        assert r.status_code == 403
        assert "grant_alias_mismatch" in r.text

    async def test_jwt_with_grant_header_400(self, client):
        h = await _register(client, "p1_alice")
        h["X-Gimbal-Grant"] = "ggt_whatever"
        r = await client.get("/api/executions", headers=h)
        assert r.status_code == 400
        assert "grant_header_on_jwt" in r.text


async def _register(client: AsyncClient, username: str) -> dict:
    await client.post("/api/auth/register", json={
        "username": username, "password": "pw123456",
        "display_name": username})
    r = await client.post("/api/auth/login", json={
        "username": username, "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── 别名管理 API(§4.5)──────────────────────────────────────────


class TestAliasManagementApi:
    async def test_credential_lifecycle_token_once(self, client):
        await _seed_alias()
        h_admin = await _register(client, "p1_admin")
        await _promote("p1_admin")
        # 非属主(团队共享别名 owner_user_id 空)非 admin → 403
        # (首个真人注册会被提为 admin —— 显式压回 user,不依赖注册顺序)
        h_member = await _register(client, "p1_member")
        await _set_role("p1_member", "user")
        r = await client.post(
            "/api/service-aliases/agent-sys/inbound-credentials",
            headers=h_member, json={"name": "a"})
        assert r.status_code == 403
        # admin 生成:明文只此一次
        r = await client.post(
            "/api/service-aliases/agent-sys/inbound-credentials",
            headers=h_admin, json={"name": "a"})
        assert r.status_code == 201, r.text
        token = r.json()["token"]
        assert token.startswith("gic_")
        # 吊销后 401
        cred_id = r.json()["id"]
        r = await client.delete(
            f"/api/service-aliases/agent-sys/inbound-credentials/{cred_id}",
            headers=h_admin)
        assert r.status_code == 204
        r = await client.get("/api/executions", headers=_gic(token))
        assert r.status_code == 401

    async def test_plate_alias_cannot_enable_inbound(self, client):
        await _seed_alias("plate-one", kind="plate", inbound_enabled=False)
        h = await _register(client, "p1_admin")
        await _promote("p1_admin")
        r = await client.put(
            "/api/service-aliases/plate-one/inbound",
            headers=h, json={"inboundEnabled": True})
        assert r.status_code == 422
        assert "kind_not_external" in r.text

    async def test_put_inbound_settings_validation(self, client):
        await _seed_alias("agent-cfg", callback_enabled=False,
                          callback_path=None, callback_secret=None)
        h = await _register(client, "p1_admin")
        await _promote("p1_admin")
        # 开回调但缺 callback_path → 422
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound",
            headers=h, json={"callbackEnabled": True})
        assert r.status_code == 422
        assert "callback_target_missing" in r.text
        # 路径含协议 → 422
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound",
            headers=h, json={"callbackPath": "https://evil/x"})
        assert r.status_code == 422
        assert "callback_path_invalid" in r.text
        # 齐备 + 首次开启:密钥自动生成,**明文随本响应返回一次**
        # (否则接收方永远拿不到密钥、无法验签)
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound", headers=h,
            json={"callbackEnabled": True, "callbackPath": "/cb"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["callbackEnabled"] is True
        first_secret = body["callbackSecret"]
        assert first_secret and not first_secret.startswith(("gic_", "ggt_"))
        # 再查设置(密钥已存在、不轮换)不回明文
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound", headers=h,
            json={"callbackEnabled": True})
        assert r.status_code == 200
        assert r.json()["callbackSecret"] is None
        assert r.json()["callbackSecretSet"] is True
        # 显式轮换 → 新明文且与首次不同(旧密钥即时失效)
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound", headers=h,
            json={"rotateSecret": True})
        assert r.status_code == 200, r.text
        assert r.json()["callbackSecret"]
        assert r.json()["callbackSecret"] != first_secret
        # 回调关闭时 rotateSecret 无意义 → 422
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound", headers=h,
            json={"callbackEnabled": False})
        assert r.status_code == 200
        r = await client.put(
            "/api/service-aliases/agent-cfg/inbound", headers=h,
            json={"rotateSecret": True})
        assert r.status_code == 422
        assert "rotate_requires_callback" in r.text

    async def test_grant_api_lifecycle(self, client):
        await _seed_alias()
        h = await _register(client, "p1_bob")
        r = await client.post("/api/service-aliases/agent-sys/grants",
                              headers=h, json={})
        assert r.status_code == 201, r.text
        token = r.json()["token"]
        assert token.startswith("ggt_")
        assert r.json()["username"] == "p1_bob"
        # 自己的列表可见
        r = await client.get("/api/service-aliases/agent-sys/grants",
                             headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 1
        # ttl 超上限 422
        r = await client.post("/api/service-aliases/agent-sys/grants",
                              headers=h, json={"ttlDays": 366})
        assert r.status_code == 422
        assert "grant_ttl_too_long" in r.text
        # 撤销后带 grant 403
        gid = (await client.get(
            "/api/service-aliases/agent-sys/grants", headers=h)).json()[0]["id"]
        r = await client.delete(
            f"/api/service-aliases/agent-sys/grants/{gid}", headers=h)
        assert r.status_code == 204
        async with db_module.SessionLocal() as s:
            row = await s.get(InboundGrant, gid)
            assert row.revoked_at is not None
        # 他人不可撤销
        r2 = await client.post("/api/service-aliases/agent-sys/grants",
                               headers=h, json={})
        gid2 = r2.json()["id"]
        h2 = await _register(client, "p1_carol")
        r = await client.delete(
            f"/api/service-aliases/agent-sys/grants/{gid2}", headers=h2)
        assert r.status_code == 403


async def _promote(username: str) -> None:
    await _set_role(username, "admin")


async def _set_role(username: str, role: str) -> None:
    async with db_module.SessionLocal() as s:
        u = (await s.execute(
            sa.select(User).where(User.username == username))).scalar_one()
        u.role = role
        await s.commit()


# ── 入口改造(§4.4)───────────────────────────────────────────────


class TestRunEntry:
    async def test_platform_mode_readonly_gate(
            self, client, monkeypatch):
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        h = await _register(client, "p1_owner")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-ro", steps=[POST_STEP]))
        # 写步骤 → 403(只读闸,D6)
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-p1-ro"})
        assert r.status_code == 403, r.text
        assert "not_read_only" in r.text
        # GET 步骤 → 过闸;fanout 打桩(fanout 面归执行族用例)
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-get", steps=[GET_STEP]))
        from app.services import run_dispatcher as rd
        fin = []

        async def _fake_fanout(*, db_factory, execution_id, **kw):
            await rd.transition_with_retry(
                db_factory, execution_id, rd.STATUS_DONE)
            fin.append(execution_id)

        monkeypatch.setattr(rd, "_fanout", _fake_fanout)
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-p1-get", "clientRef": "agent-task-1",
            "callbackPath": "/override"})
        assert r.status_code == 201, r.text
        assert r.json()["identityMode"] == "platform"
        await _wait(lambda: len(fin) == 1)
        async with db_module.SessionLocal() as s:
            ex = (await s.execute(
                sa.select(Execution).order_by(Execution.id.desc()))
            ).scalars().first()
            assert ex.owner_id is not None
            assert ex.caller_alias_name == "agent-sys"
            assert ex.client_ref == "agent-task-1"
            assert ex.callback_path_override == "/override"
            assert ex.grant_id is None
            # owner 是系统用户(平台模式)
            owner = await s.get(User, ex.owner_id)
            assert owner.is_system

    async def test_platform_mode_graph_rejected(self, client):
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        h = await _register(client, "p1_owner")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-g", steps=[GET_STEP]))
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-p1-g",
            "graph": {"units": [
                {"ref": "u1", "scenarioId": "sc-p1-g"}]}})
        assert r.status_code == 403
        assert "graph_not_supported_for_platform" in r.text

    async def test_callback_path_with_scheme_422(self, client):
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        h = await _register(client, "p1_owner")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-get2", steps=[GET_STEP]))
        r = await client.post("/api/runs", headers=_gic(token), json={
            "scenarioId": "sc-p1-get2", "callbackPath": "https://x/y"})
        assert r.status_code == 422
        assert "callback_path_invalid" in r.text


class TestIntegrationEntry:
    async def test_identity_mode_from_auth_and_caller_columns(
            self, client):
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "p1_reg")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-int", steps=[GET_STEP]))
        # JWT 注册:维持既有自由选择(platform 缺省可建)—— Principal
        # 的 identity_mode 只锁入站调用面
        token = await _mk_credential()
        r = await client.post("/api/integration/tasks", headers=h,
                              json={"name": "t-jwt", "scenarioId": "sc-p1-int",
                                    "identityMode": "platform"})
        assert r.status_code == 201, r.text
        # 入站无 grant(认证 = platform)传 personal → 422
        r = await client.post(
            "/api/integration/tasks", headers=_gic(token),
            json={"name": "t", "scenarioId": "sc-p1-int",
                  "identityMode": "personal"})
        assert r.status_code == 422
        assert "identity_mode_mismatch" in r.text
        # 无 grant(platform)→ 通过;模板行落 caller 台账
        r = await client.post("/api/integration/tasks", headers=_gic(token), json={
            "name": "t", "scenarioId": "sc-p1-int", "identityMode": "platform",
            "clientRef": "sched-1"})
        assert r.status_code == 201, r.text
        async with db_module.SessionLocal() as s:
            tpl = (await s.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id.is_(None),
                IntegrationTask.name == "t"))).scalar_one()
            assert tpl.caller_alias_name == "agent-sys"
            assert tpl.client_ref == "sched-1"
            assert tpl.grant_id is None

    async def test_personal_grant_registration(self, client):
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "p1_reg2")
        uid = await _user_id("p1_reg2")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-int2", steps=[POST_STEP]))
        token = await _mk_credential()
        grant = await _mk_grant("agent-sys", uid)
        r = await client.post(
            "/api/integration/tasks", headers=_gic(token, grant),
            json={"name": "t2", "scenarioId": "sc-p1-int2",
                  "identityMode": "personal"})
        assert r.status_code == 201, r.text
        async with db_module.SessionLocal() as s:
            tpl = (await s.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id.is_(None),
                IntegrationTask.name == "t2"))).scalar_one()
            assert tpl.caller_alias_name == "agent-sys"
            assert tpl.grant_id is not None
            assert tpl.identity_mode == "personal"

    async def test_public_template_hides_caller_from_non_owner(
            self, client):
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "p1_reg3")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-int3", steps=[GET_STEP]))
        token = await _mk_credential()
        r = await client.post(
            "/api/integration/tasks", headers=_gic(token), json={
                "name": "t3", "scenarioId": "sc-p1-int3",
                "identityMode": "platform", "visibility": "public",
                "clientRef": "sched-3"})
        assert r.status_code == 201
        tid = r.json()["id"]
        assert r.json()["callerAliasName"] == "agent-sys"
        # 非属主视角:caller/client_ref 不出现(D12)
        other = await _register(client, "p1_other")
        r = await client.get(f"/api/integration/tasks/{tid}",
                             headers=other)
        assert r.status_code == 200
        assert "callerAliasName" not in r.json()
        assert "clientRef" not in r.json()
        r = await client.get("/api/integration/tasks", headers=other)
        row = [t for t in r.json()["items"] if t["id"] == tid][0]
        assert "callerAliasName" not in row


# ── 可见性(D8/§5.6)与 grant 重校验(P1-5)─────────────────────────


class TestVisibility:
    async def test_platform_execution_visibility(self, client):
        await _seed_platform_user()
        await _seed_alias()
        # 平台模式执行:owner=系统用户,caller=agent-sys
        await _register(client, "p1_owner4")
        owner_id = await _user_id("p1_owner4")
        async with db_module.SessionLocal() as s:
            sys_uid = (await s.execute(sa.select(User.id).where(
                User.is_system == True))).scalar_one()  # noqa: E712
            ex = Execution(scenario_id="sc-x", scenario_name="X",
                           owner_id=sys_uid, owner_name="平台系统",
                           status="done", total_runs=1, passed=1,
                           caller_alias_name="agent-sys")
            s.add(ex)
            await s.commit()
            ex_id = ex.id
        # 别名属主可见(agent-sys 归属 p1_owner4?—— 本用例把属主设为该用户)
        async with db_module.SessionLocal() as s:
            alias = await s.get(ServiceAlias, "agent-sys")
            alias.owner_user_id = owner_id
            await s.commit()
        h = await _register(client, "p1_owner4")
        r = await client.get(f"/api/executions/{ex_id}", headers=h)
        assert r.status_code == 200, r.text
        # 其他 member → 404(不泄露)
        h2 = await _register(client, "p1_stranger")
        r = await client.get(f"/api/executions/{ex_id}", headers=h2)
        assert r.status_code == 404
        # admin 可见
        await _promote("p1_stranger")
        r = await client.get(f"/api/executions/{ex_id}", headers=h2)
        assert r.status_code == 200
        # 入站凭证:本别名的执行可见
        token = await _mk_credential()
        r = await client.get(f"/api/executions/{ex_id}",
                             headers=_gic(token))
        assert r.status_code == 200
        # 入站列表:只见本别名执行
        r = await client.get("/api/executions", headers=_gic(token))
        ids = [i["id"] for i in r.json()["items"]]
        assert ids == [ex_id]

    async def test_jwt_list_excludes_platform_executions(self, client):
        """「我的执行」按 owner 过滤 —— 平台模式执行(owner=系统用户)
        不进任何 JWT 用户的列表(设计 §5.6)。"""
        await _seed_platform_user()
        async with db_module.SessionLocal() as s:
            sys_uid = (await s.execute(sa.select(User.id).where(
                User.is_system == True))).scalar_one()  # noqa: E712
            s.add(Execution(scenario_id="sc-y", scenario_name="Y",
                            owner_id=sys_uid, owner_name="平台系统",
                            status="done", total_runs=1, passed=1,
                            caller_alias_name="agent-sys"))
            await s.commit()
        await _seed_alias()
        h = await _register(client, "p1_z")
        r = await client.get("/api/executions", headers=h)
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestGrantRevalidation:
    async def test_revoked_grant_pauses_instance(self, client):
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "p1_reg5")
        uid = await _user_id("p1_reg5")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-p1-g5", steps=[GET_STEP]))
        token = await _mk_credential()
        grant = await _mk_grant("agent-sys", uid)
        r = await client.post(
            "/api/integration/tasks", headers=_gic(token, grant), json={
                "name": "t5", "scenarioId": "sc-p1-g5",
                "identityMode": "personal"})
        assert r.status_code == 201, r.text
        # 撤销 grant(签发人本人)
        gid = (await client.get(
            "/api/service-aliases/agent-sys/grants", headers=h)).json()[0]["id"]
        r = await client.delete(
            f"/api/service-aliases/agent-sys/grants/{gid}", headers=h)
        assert r.status_code == 204
        # 运行 → grant_revoked 暂停(不重试)
        async with db_module.SessionLocal() as s:
            inst = (await s.execute(sa.select(IntegrationTask).where(
                IntegrationTask.template_id.isnot(None)))).scalars().one()
            inst_id = inst.id
        await integration_runner.run_instance(inst_id)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "paused"
            assert inst.paused_reason == "grant_revoked"
            assert inst.run_status == "auth"


# sha256_hex 对拍(实现一致性钉住)
def test_sha256_hex_matches_hashlib():
    tok = "gic_abc"
    assert sha256_hex(tok) == hashlib.sha256(tok.encode()).hexdigest()
