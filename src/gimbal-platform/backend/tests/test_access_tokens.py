"""访问令牌(webhook v4 §2–§5)— 认证分流、生命周期、范围、权限矩阵。

替代 v3 的 test_inbound_identity.py;共享助手(GET_STEP/_register/_gtk
等)在此导出,test_adhoc_run / test_token_scope 复用。
"""
from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.access_token import AccessToken
from app.models.auth_session import AuthSession
from app.models.permission import AuditLog
from app.models.user import User
from app.services import access_token as at_svc

from .helpers import make_draft as _draft, wait_until as _wait
from .inbound_fixtures import (
    mk_token, seed_alias, seed_platform_user,
)

# ── 共享助手(供 test_adhoc_run / test_token_scope 复用)─────────

GET_STEP = {"kind": "step", "id": "s1", "call": {
    "protocol": "http", "service": "svc", "method": "GET", "path": "/x"},
    "request": {"kind": "request", "body": {}}, "strategy": []}
POST_STEP = {"kind": "step", "id": "s1", "call": {
    "protocol": "http", "service": "svc", "method": "POST", "path": "/x"},
    "request": {"kind": "request", "body": {}}, "strategy": []}


async def _register(client: AsyncClient, username: str) -> dict:
    await client.post("/api/auth/register", json={
        "username": username, "password": "pw123456",
        "display_name": username})
    r = await client.post("/api/auth/login", json={
        "username": username, "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _register_role(client: AsyncClient, username: str,
                         role: str) -> dict:
    """注册后直插提权到 role(测试直改,免 admin 走管理面的副作用)。"""
    h = await _register(client, username)
    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa.select(User).where(
            User.username == username))).scalar_one()
        row.role = role
        await s.commit()
    # role 不进 JWT,每请求查库 → 头不用换
    return h


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(
            sa.select(User.id).where(User.username == username))).scalar_one()


def _gtk(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _api_token(client: AsyncClient, h: dict, body: dict) -> dict:
    r = await client.post("/api/access-tokens", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _add_credential(username: str, alias: str = "qa-cred") -> int:
    from app.core.security import fernet_encrypt
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.select(User.id).where(
            User.username == username))).scalar_one()
        row = AuthSession(owner_id=uid, alias=alias, url="https://a.local",
                          username_enc=fernet_encrypt("u"),
                          password_enc=fernet_encrypt("p"))
        s.add(row)
        await s.commit()
        return row.id


async def _exec_done(execution_id: int) -> None:
    """等队列任务体收口到终态(测试收尾的跨 schema 泄漏防线;
    helpers._wait 只吃同步谓词,这里自旋)。"""
    import asyncio
    from app.models.execution import Execution as _E

    async def _done() -> bool:
        async with db_module.SessionLocal() as s:
            ex = await s.get(_E, execution_id)
            return ex is not None and ex.status in ("done", "failed",
                                                    "canceled")

    for _ in range(200):
        if await _done():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"execution {execution_id} 未在 10s 内终态")


async def _recent_audit(token_id: int) -> list[AuditLog]:
    async with db_module.SessionLocal() as s:
        return list((await s.execute(sa.select(AuditLog).where(
            AuditLog.resource_type == "access_token",
            AuditLog.resource_id == str(token_id))
            .order_by(AuditLog.id.desc()))).scalars().all())


# ── 认证分流矩阵(§3.1 ① / §5.4)─────────────────────────────────


class TestAuthFork:
    async def test_jwt_path_unchanged(self, client: AsyncClient):
        h = await _register(client, "p1_alice")
        r = await client.get("/api/executions", headers=h)
        assert r.status_code == 200

    async def test_bad_token_401_and_audited(self, client):
        r = await client.get("/api/executions", headers=_gtk("gtk_nope"))
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "token_invalid"
        # 未命中:资源列为空,只进审计面板
        async with db_module.SessionLocal() as s:
            rows = (await s.execute(sa.select(AuditLog).where(
                AuditLog.action == "inbound.denied"))).scalars().all()
            assert rows and rows[-1].resource_id is None

    async def test_revoked_same_as_missing(self, client):
        await seed_platform_user()
        uid = await _user_id((await _register(client, "rv_u")) and "rv_u")
        tid, plain = await mk_token(user_id=uid, revoked=True)
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "token_invalid"
        # hash 命中已吊销令牌 → 被拒请求归到该令牌名下(§7.2)
        rows = await _recent_audit(tid)
        assert rows and rows[0].action == "inbound.denied"
        assert rows[0].resource_id == str(tid)

    async def test_expired_401(self, client):
        await seed_platform_user()
        h = await _register(client, "exp_u")
        uid = await _user_id("exp_u")
        _, plain = await mk_token(user_id=uid, days=-1)
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "token_expired"

    async def test_invalidated_401(self, client):
        await seed_platform_user()
        await _register(client, "inv_u")
        uid = await _user_id("inv_u")
        _, plain = await mk_token(user_id=uid, invalidated=True)
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "token_invalidated"

    async def test_owner_role_user_403(self, client):
        await seed_platform_user()
        await _register(client, "role_first")   # 占首注(admin)
        from .inbound_fixtures import mk_user
        uid = await mk_user("role_u", role="user")
        _, plain = await mk_token(user_id=uid)
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "token_owner_ineligible"

    async def test_owner_deactivated_401(self, client):
        await seed_platform_user()
        await _register(client, "deact_u")
        uid = await _user_id("deact_u")
        _, plain = await mk_token(user_id=uid)
        async with db_module.SessionLocal() as s:
            row = await s.get(User, uid)
            row.is_active = False
            await s.commit()
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 401
        assert r.json()["detail"]["code"] == "token_invalidated"

    async def test_platform_token_role_user_ok(self, client):
        """平台令牌不因 __platform__ role='user' 被拒(§3.1)。"""
        await seed_platform_user()
        _, plain = await mk_token(kind="platform", name="pt")
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 200

    async def test_legacy_prefixes_401_with_message(self, client):
        for legacy in ("gic_abc", "ggt_abc"):
            r = await client.get("/api/executions", headers=_gtk(legacy))
            assert r.status_code == 401
            assert r.json()["detail"]["code"] == "token_invalid"
            assert "gtk_" in r.json()["detail"]["message"]

    async def test_token_cannot_call_management(self, client):
        """令牌不能管理令牌(§2.2:D8)——管理端点只认 JWT → 401。"""
        await seed_platform_user()
        await _register(client, "mgmt_u")
        uid = await _user_id("mgmt_u")
        tid, plain = await mk_token(user_id=uid)
        r = await client.get("/api/access-tokens", headers=_gtk(plain))
        assert r.status_code == 401


# ── 令牌 API:创建 / 额度 / 明文一次性(§5.1)─────────────────────


class TestTokenApi:
    async def test_create_one_time_plaintext(self, client):
        await seed_platform_user()
        h = await _register_role(client, "mk_member", "admin")
        out = await _api_token(client, h, {
            "kind": "personal", "name": "agent", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        assert out["token"].startswith("gtk_")
        # 列表不返回明文,只有 hint
        r = await client.get("/api/access-tokens", headers=h)
        item = next(t for t in r.json()["items"] if t["name"] == "agent")
        assert "…" in item["tokenHint"] and "gtk_" not in item["tokenHint"]
        assert len(item["tokenHint"]) == 9
        assert item["status"] == "active"

    async def test_create_with_callback_returns_secret_once(self, client):
        from app.core.config import settings
        await seed_platform_user()
        h = await _register_role(client, "cb_member", "admin")
        from app.core import db as dbm
        import app.services.access_token as at
        orig = at.callback_allowlist
        at.callback_allowlist = lambda: ["cb.example.local"]
        try:
            out = await _api_token(client, h, {
                "kind": "personal", "name": "cbt", "ttlDays": 30,
                "callbackUrl": "https://cb.example.local/hook",
                "scope": {"aliases": [], "authIds": []}})
            assert out.get("callbackSecret")
            r = await client.get("/api/access-tokens", headers=h)
            item = next(t for t in r.json()["items"] if t["name"] == "cbt")
            assert item["callbackSecretSet"] is True
            assert "callbackSecret" not in item
        finally:
            at.callback_allowlist = orig

    async def test_callback_host_not_allowed_422(self, client):
        await seed_platform_user()
        h = await _register_role(client, "cb2_member", "admin")
        r = await client.post("/api/access-tokens", headers=h, json={
            "kind": "personal", "name": "bad", "ttlDays": 30,
            "callbackUrl": "https://evil.example.com/hook",
            "scope": {"aliases": [], "authIds": []}})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "callback_host_not_allowed"

    async def test_personal_quota_5(self, client):
        await seed_platform_user()
        h = await _register_role(client, "q_member", "admin")
        for i in range(5):
            await _api_token(client, h, {
                "kind": "personal", "name": f"t{i}", "ttlDays": 30,
                "scope": {"aliases": [], "authIds": []}})
        r = await client.post("/api/access-tokens", headers=h, json={
            "kind": "personal", "name": "t5", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "token_limit_reached"
        # 吊销一张后腾出额度(吊销不占)
        first = (await client.get("/api/access-tokens", headers=h)
                 ).json()["items"][-1]
        await client.delete(f"/api/access-tokens/{first['id']}", headers=h)
        r = await client.post("/api/access-tokens", headers=h, json={
            "kind": "personal", "name": "t5", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        assert r.status_code == 201

    async def test_platform_quota_shared_across_members(self, client):
        await seed_platform_user()
        h1 = await _register_role(client, "pq1", "admin")
        h2 = await _register_role(client, "pq2", "admin")
        for i in range(5):
            r = await client.post("/api/access-tokens", headers=h1, json={
                "kind": "platform", "name": f"pt{i}", "ttlDays": 30,
                "scope": {"aliases": [], "authIds": []}})
            assert r.status_code == 201
        # 跨 member 竞争同一额度
        r = await client.post("/api/access-tokens", headers=h2, json={
            "kind": "platform", "name": "pt5", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "token_limit_reached"

    async def test_user_role_cannot_create_but_can_revoke(self, client):
        """user 角色:不能签发(403);可查看与吊销自己的(§2.3)。"""
        await seed_platform_user()
        h_member = await _register_role(client, "u_member", "admin")
        out = await _api_token(client, h_member, {
            "kind": "personal", "name": "give", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        # 把令牌挪给 user 角色用户(直插模拟:user 原本签不了)
        await _register(client, "plain_u")
        uid_plain = await _user_id("plain_u")
        async with db_module.SessionLocal() as s:
            tok = (await s.execute(sa.select(AccessToken).where(
                AccessToken.id == out["id"] if "id" in out else
                AccessToken.token_hash == at_svc.sha256_hex(out["token"]))
            )).scalar_one()
            tok.user_id = uid_plain
            await s.commit()
            tid = tok.id
        h_plain = await _register(client, "plain_u2")  # 另一个 user:404
        r = await client.delete(f"/api/access-tokens/{tid}",
                                headers=h_plain)
        assert r.status_code == 404
        # 属主(user 角色)可吊销
        login = await client.post("/api/auth/login", json={
            "username": "plain_u", "password": "pw123456"})
        h_own = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = await client.delete(f"/api/access-tokens/{tid}", headers=h_own)
        assert r.status_code == 200


# ── 生命周期:renew / regenerate / revoke / invalidate(§3.4)──────


class TestLifecycle:
    async def _mk(self, client, username):
        await seed_platform_user()
        h = await _register_role(client, username, "admin")
        out = await _api_token(client, h, {
            "kind": "personal", "name": "lc", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        tid = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]["id"]
        return h, tid, out["token"]

    async def test_renew_extends_expiry(self, client):
        h, tid, _ = await self._mk(client, "lc1")
        r = await client.post(f"/api/access-tokens/{tid}/renew",
                              headers=h, json={"ttlDays": 90})
        assert r.status_code == 200
        item = next(t for t in (await client.get(
            "/api/access-tokens", headers=h)).json()["items"]
            if t["id"] == tid)
        assert item["status"] == "active"

    async def test_renew_invalidated_409(self, client):
        h, tid, _ = await self._mk(client, "lc2")
        async with db_module.SessionLocal() as s:
            tok = await s.get(AccessToken, tid)
            tok.invalidated_at = at_svc.now_utc()
            tok.invalidated_reason = "password"
            await s.commit()
        r = await client.post(f"/api/access-tokens/{tid}/renew",
                              headers=h, json={"ttlDays": 90})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "regenerate_required"

    async def test_regenerate_new_plaintext_old_401(self, client):
        h, tid, old_plain = await self._mk(client, "lc3")
        r = await client.post(f"/api/access-tokens/{tid}/regenerate",
                              headers=h)
        assert r.status_code == 200
        new_plain = r.json()["token"]
        assert new_plain != old_plain
        r = await client.get("/api/executions", headers=_gtk(old_plain))
        assert r.status_code == 401
        r = await client.get("/api/executions", headers=_gtk(new_plain))
        assert r.status_code == 200

    async def test_regenerate_clears_invalidated(self, client):
        h, tid, _ = await self._mk(client, "lc4")
        async with db_module.SessionLocal() as s:
            tok = await s.get(AccessToken, tid)
            tok.invalidated_at = at_svc.now_utc()
            tok.invalidated_reason = "admin"
            await s.commit()
        r = await client.post(f"/api/access-tokens/{tid}/regenerate",
                              headers=h)
        assert r.status_code == 200
        item = next(t for t in (await client.get(
            "/api/access-tokens", headers=h)).json()["items"]
            if t["id"] == tid)
        assert item["status"] == "active"
        assert item["invalidatedReason"] is None

    async def test_revoke_terminal_idempotent(self, client):
        h, tid, plain = await self._mk(client, "lc5")
        r = await client.delete(f"/api/access-tokens/{tid}", headers=h)
        assert r.status_code == 200
        assert r.json()["revoked"] is True
        # 再吊销幂等 200
        r = await client.delete(f"/api/access-tokens/{tid}", headers=h)
        assert r.status_code == 200
        # 写操作 409;明文 401
        r = await client.post(f"/api/access-tokens/{tid}/renew",
                              headers=h, json={"ttlDays": 30})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "token_revoked"
        r = await client.get("/api/executions", headers=_gtk(plain))
        assert r.status_code == 401

    async def test_admin_force_invalidate_with_note(self, client):
        await seed_platform_user()
        h = await _register_role(client, "fi_member", "admin")
        await _api_token(client, h, {
            "kind": "personal", "name": "fi", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        tid = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]["id"]
        # 首个注册者是 admin(空库);造 admin 头
        h_admin = await _register(client, "fi_admin0") \
            if False else await _admin_headers(client)
        r = await client.post(f"/api/access-tokens/{tid}/invalidate",
                              headers=h_admin,
                              json={"note": "疑似在 CI 日志中泄露"})
        assert r.status_code == 200
        item = next(t for t in (await client.get(
            "/api/access-tokens", headers=h)).json()["items"]
            if t["id"] == tid)
        assert item["status"] == "invalidated"
        assert item["invalidatedReason"] == "admin"
        # 属主收到带处置说明的通知
        from app.models.permission import Notification
        async with db_module.SessionLocal() as s:
            note = (await s.execute(sa.select(Notification).where(
                Notification.title.contains("fi")))).scalars().first()
        assert note is not None and "CI 日志" in (note.body or "")

    async def test_admin_all_view_and_filters(self, client):
        await seed_platform_user()
        h = await _register_role(client, "av1", "admin")
        h2 = await _register_role(client, "av2", "admin")
        await _api_token(client, h, {
            "kind": "personal", "name": "mine", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        await _api_token(client, h2, {
            "kind": "platform", "name": "pt", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        h_admin = await _admin_headers(client)
        r = await client.get("/api/access-tokens?all=1", headers=h_admin)
        assert r.status_code == 200
        items = r.json()["items"]
        assert all("ownerName" in i for i in items)
        # member 不能用 all
        r = await client.get("/api/access-tokens?all=1", headers=h)
        assert r.status_code == 403

    async def test_admin_owner_name_filter(self, client):
        """2026-11-05 修复轮评审 P3-4/P3-3:ownerName 按用户名/昵称模糊
        (不区分大小写);输入里的 % / _ 按字面匹配,不当 LIKE 通配符
        (未转义时 '%'/'_' 会命中全部属主)。"""
        ha = await _register_role(client, "ownalpha", "admin")
        hb = await _register_role(client, "ownbeta", "admin")
        async with db_module.SessionLocal() as s:
            await s.execute(sa.update(User).where(
                User.username == "ownalpha").values(display_name="Alice Liddell"))
            await s.execute(sa.update(User).where(
                User.username == "ownbeta").values(display_name="50%_off"))
            await s.commit()
        for h, name in ((ha, "tok-a"), (hb, "tok-b")):
            await _api_token(client, h, {
                "kind": "personal", "name": name, "ttlDays": 30,
                "scope": {"aliases": [], "authIds": []}})
        h_admin = await _admin_headers(client)

        async def names(q: str) -> list[str]:
            r = await client.get("/api/access-tokens", headers=h_admin,
                                 params={"all": "1", "kind": "all", "ownerName": q})
            assert r.status_code == 200, r.text
            return sorted(i["name"] for i in r.json()["items"])

        assert await names("alpha") == ["tok-a"]        # 用户名
        assert await names("LIDDELL") == ["tok-a"]      # 昵称,不分大小写
        assert await names("%") == ["tok-b"]            # 字面 %
        assert await names("_") == ["tok-b"]            # 字面 _
        assert await names("nobody") == []

    async def test_platform_credentials_ref_counts(self, client):
        """2026-11-05 修复轮评审 P3-4:平台凭证列表「被引用」列(P2-3
        _cred_usage)—— refTokens = 范围含该凭证的令牌数;refTasks = 这些
        令牌直连的非模板、未删除任务数。同凭证多令牌按令牌累加。"""
        from .inbound_fixtures import mk_task_pair
        from app.models.integration_task import IntegrationTask
        from datetime import datetime, timezone

        await seed_platform_user()
        cred_a = await _add_credential("__platform__", "cred-a")
        cred_b = await _add_credential("__platform__", "cred-b")
        cred_c = await _add_credential("__platform__", "cred-c")   # 无引用
        h = await _register_role(client, "refcnt", "admin")
        t1 = await _api_token(client, h, {
            "kind": "platform", "name": "t1", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": [cred_a]}})
        t2 = await _api_token(client, h, {
            "kind": "platform", "name": "t2", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": [cred_a, cred_b]}})
        await mk_task_pair(name="live-1", token_id=t1["id"], identity_mode="platform")
        gone, _, _ = await mk_task_pair(
            name="gone-1", token_id=t1["id"], identity_mode="platform")
        await mk_task_pair(name="live-2", token_id=t2["id"], identity_mode="platform")
        async with db_module.SessionLocal() as s:
            await s.execute(sa.update(IntegrationTask).where(
                IntegrationTask.id == gone).values(
                removed_at=datetime.now(timezone.utc)))
            await s.commit()

        r = await client.get("/api/integration/platform-credentials",
                             headers=await _admin_headers(client))
        assert r.status_code == 200, r.text
        refs = {i["id"]: (i["refTokens"], i["refTasks"]) for i in r.json()["items"]}
        assert refs[cred_a] == (2, 2)   # t1(1 活 + 1 软删不计)+ t2(1)
        assert refs[cred_b] == (1, 1)
        assert refs[cred_c] == (0, 0)


async def _admin_headers(client: AsyncClient) -> dict:
    """直插 admin(mk_user 口令 = x;首注 admin 规则不可依赖 —— 各测试
    注册顺序不同)。"""
    from .inbound_fixtures import mk_user
    await mk_user("root_admin", role="super_admin")
    r = await client.post("/api/auth/login", json={
        "username": "root_admin", "password": "x"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── 范围(§3.2 / §3.3 缺项分类 / D4 空维度)──────────────────────


class TestScopeApi:
    async def test_scope_put_and_dry_run(self, client):
        await seed_platform_user()
        await seed_alias("fin-test")
        await seed_alias("logi-test")
        h = await _register_role(client, "sc1", "admin")
        out = await _api_token(client, h, {
            "kind": "personal", "name": "sc", "ttlDays": 30,
            "scope": {"aliases": ["fin-test"], "authIds": []}})
        tid = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]["id"]
        # dryRun:返回影响面,不落库
        r = await client.put(f"/api/access-tokens/{tid}/scope",
                             params={"dryRun": "1"}, headers=h,
                             json={"aliases": [], "authIds": []})
        assert r.status_code == 200
        assert "unsatisfied" in r.json()
        item = next(t for t in (await client.get(
            "/api/access-tokens", headers=h)).json()["items"]
            if t["id"] == tid)
        assert item["scopeCounts"]["aliases"] == 1
        # 正式替换:空维度合法(D4)
        r = await client.put(f"/api/access-tokens/{tid}/scope", headers=h,
                             json={"aliases": [], "authIds": []})
        assert r.status_code == 200
        item = next(t for t in (await client.get(
            "/api/access-tokens", headers=h)).json()["items"]
            if t["id"] == tid)
        assert item["scopeCounts"] == {"aliases": 0, "auths": 0}

    async def test_scope_unknown_objects_422(self, client):
        await seed_platform_user()
        h = await _register_role(client, "sc2", "admin")
        out = await _api_token(client, h, {
            "kind": "personal", "name": "sc2", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        tid = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]["id"]
        r = await client.put(f"/api/access-tokens/{tid}/scope", headers=h,
                             json={"aliases": ["no-such"], "authIds": []})
        assert r.status_code == 422

    async def test_platform_scope_candidates_only_alias(self, client):
        """平台令牌范围候选:平台凭证池只列别名(§5.1/D5)。"""
        await seed_platform_user()
        h = await _register_role(client, "sc3", "admin")
        r = await client.get(
            "/api/access-tokens/scope-candidates?kind=platform", headers=h)
        assert r.status_code == 200
        assert all(set(a.keys()) == {"id", "alias"}
                   for a in r.json()["auths"])


class TestRunScope:
    """POST /api/runs 的令牌范围闸(§3.1 ⑤,缺项分类)。"""

    async def test_scope_denied_403_with_classification(self, client):
        await seed_platform_user()
        await seed_alias("fin-test", base_url="https://fin.local")
        await seed_alias("wms-test", base_url="https://wms.local")
        h = await _register_role(client, "rs1", "admin")
        # 场景引用 fin-test(经别名解析)+ authored 直连 svc-direct
        draft = _draft("sc-rs1", steps=[GET_STEP])
        draft["definition"]["config"]["services"] = {"svc": ""}
        await client.post("/api/scenarios", headers=h, json=draft)
        await _api_token(client, h, {
            "kind": "personal", "name": "rs", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})   # 空范围
        tok = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]
        # 场景步骤 service=svc,未配置别名 → 引擎地址缺口,不在范围判定
        # (③层未命中);构造命中:把别名直接当 service 键
        draft2 = _draft("sc-rs2", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="fin-test"))])
        await client.post("/api/scenarios", headers=h, json=draft2)
        _, plain = await mk_token(
            user_id=await _user_id("rs1"),
            scope_aliases=["wms-test"])       # 范围里有 wms,没有 fin
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rs2"})
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert detail["code"] == "resource_not_allowed"
        missing = detail["missing"]
        assert missing == [{"kind": "alias", "name": "fin-test",
                            "deleted": False}]   # 对象存在 = 未授权

    async def test_scope_deleted_object_classification(self, client):
        await seed_platform_user()
        await seed_alias("gone-test", base_url="https://gone.local")
        h = await _register_role(client, "rs2", "admin")
        draft = _draft("sc-rs3", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="gone-test"))])
        await client.post("/api/scenarios", headers=h, json=draft)
        _, plain = await mk_token(user_id=await _user_id("rs2"),
                                  scope_aliases=["gone-test"])
        # 对象删除后范围行级联消失 → 缺项分类为「已删除」
        from app.models.service_alias import ServiceAlias as _SA
        async with db_module.SessionLocal() as s:
            await s.delete(await s.get(_SA, "gone-test"))
            await s.commit()
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rs3"})
        assert r.status_code == 403
        assert r.json()["detail"]["missing"] == [
            {"kind": "alias", "name": "gone-test", "deleted": True}]

    async def test_scope_ok_passes_and_audited(self, client, monkeypatch):
        await seed_platform_user()
        await seed_alias("ok-test", base_url="https://ok.local")
        h = await _register_role(client, "rs3", "admin")
        draft = _draft("sc-rs4", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="ok-test"))])
        await client.post("/api/scenarios", headers=h, json=draft)
        tid, plain = await mk_token(user_id=await _user_id("rs3"),
                                    scope_aliases=["ok-test"])
        from app.services import run_dispatcher as rd
        cap: list[int] = []

        async def _fake_fanout(*, db_factory, execution_id, **kw):
            cap.append(execution_id)
            await rd.transition_with_retry(
                db_factory, execution_id, rd.STATUS_DONE)

        monkeypatch.setattr(rd, "_fanout", _fake_fanout)
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rs4"})
        assert r.status_code == 201, r.text
        await _wait(lambda: len(cap) == 1)
        await _exec_done(r.json()["executionId"])
        # inbound.run 审计:资源列 = access_token/tid
        rows = await _recent_audit(tid)
        assert any(x.action == "inbound.run" for x in rows)
        # 执行 config_json 追溯块(§7.1)
        from app.models.execution import Execution
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, r.json()["executionId"])
            assert ex.token_id == tid
            cfg = ex.config_json
            assert cfg["token"] == {"id": tid, "name": "t", "kind": "personal"}
            assert cfg["resolvedServices"]["ok-test"]["source"] == "alias"

    async def test_out_of_scope_direct_recorded_not_blocked(self, client,
                                                            monkeypatch):
        """D15:直连地址(①②层)只记录不拦截 —— outOfScope 标记。"""
        await seed_platform_user()
        h = await _register_role(client, "rs4", "admin")
        draft = _draft("sc-rs5", steps=[GET_STEP])
        draft["definition"]["config"]["services"] = {"svc": "https://direct.local"}
        await client.post("/api/scenarios", headers=h, json=draft)
        _, plain = await mk_token(user_id=await _user_id("rs4"))
        from app.services import run_dispatcher as rd

        async def _fake_fanout(*, db_factory, execution_id, **kw):
            await rd.transition_with_retry(
                db_factory, execution_id, rd.STATUS_DONE)

        monkeypatch.setattr(rd, "_fanout", _fake_fanout)
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rs5"})
        assert r.status_code == 201, r.text
        await _exec_done(r.json()["executionId"])
        from app.models.execution import Execution
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, r.json()["executionId"])
            oos = ex.config_json.get("outOfScope")
            assert any(t["service"] == "svc" and t["source"] == "authored"
                       for t in oos["targets"])

    async def test_setup_teardown_auth_refs_in_scope(self, client,
                                                     monkeypatch):
        """§3.2:config.setup/teardown 条目的 ${auth.*} 计入凭证集。"""
        await seed_platform_user()
        h = await _register_role(client, "rs5", "admin")
        cred_id = await _add_credential("rs5", alias="setup-cred")
        draft = _draft("sc-rs6", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="free-svc"))])
        draft["definition"]["config"]["services"] = {
            "free-svc": "https://direct.local"}
        draft["definition"]["config"]["setup"] = [
            {"key": "k", "kind": "assign",
             "params": {"value": "${auth.setup-cred.password}"}}]
        await client.post("/api/scenarios", headers=h, json=draft)
        # 范围不含该凭证 → 403 resource_not_allowed(kind=auth)
        _, plain = await mk_token(user_id=await _user_id("rs5"))
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rs6"})
        assert r.status_code == 403
        assert {"kind": "auth", "name": "setup-cred",
                "deleted": False} in r.json()["detail"]["missing"]
        # 纳入范围后放行
        _, plain2 = await mk_token(user_id=await _user_id("rs5"),
                                   scope_auths=[cred_id])
        from app.services import run_dispatcher as rd

        async def _fake_fanout(*, db_factory, execution_id, **kw):
            await rd.transition_with_retry(
                db_factory, execution_id, rd.STATUS_DONE)

        monkeypatch.setattr(rd, "_fanout", _fake_fanout)
        r = await client.post("/api/runs", headers=_gtk(plain2), json={
            "scenarioId": "sc-rs6"})
        assert r.status_code == 201, r.text
        await _exec_done(r.json()["executionId"])


class TestPrecheck:
    async def test_precheck_token_scope(self, client):
        await seed_platform_user()
        await seed_alias("pc-test", base_url="https://pc.local")
        h = await _register_role(client, "pc1", "admin")
        draft = _draft("sc-pc1", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="pc-test"))])
        await client.post("/api/scenarios", headers=h, json=draft)
        # 建一个方案(POST /scenarios/{id}/run-schemes)
        r = await client.post("/api/scenarios/sc-pc1/run-schemes", headers=h,
                              json={"name": "base", "payload": {}})
        assert r.status_code == 201, r.text
        scheme_id = r.json().get("schemeId") or r.json().get("id")
        tid, plain = await mk_token(user_id=await _user_id("pc1"))
        # 令牌路径自动以当前令牌预检
        r = await client.post("/api/run/precheck", headers=_gtk(plain), json=[
            {"scenarioId": "sc-pc1", "schemeId": scheme_id}])
        assert r.status_code == 200, r.text
        item = r.json()[0]
        assert item["scopeMissing"] == [
            {"kind": "alias", "name": "pc-test", "deleted": False}]
        # JWT 传 tokenId 预检自己可管理的令牌
        r = await client.post(
            f"/api/run/precheck?tokenId={tid}", headers=h, json=[
                {"scenarioId": "sc-pc1", "schemeId": scheme_id}])
        assert r.status_code == 200
        assert r.json()[0]["scopeMissing"]


# ── 场景前提:平台只认公共场景(§3.1 ④/D9,取消 v3 别名属主豁免)──


class TestPlatformPremise:
    async def test_platform_private_scenario_403(self, client):
        await seed_platform_user()
        h = await _register_role(client, "pp1", "admin")
        await client.post("/api/scenarios", headers=h,
                          json=_draft("sc-pp1", steps=[GET_STEP]))
        _, plain = await mk_token(kind="platform", name="ppt")
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-pp1"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "platform_scope_denied"

    async def test_platform_public_scenario_readonly_gate(self, client):
        await seed_platform_user()
        h = await _register_role(client, "pp2", "admin")
        await client.post("/api/scenarios", headers=h,
                          json=_draft("sc-pp2", steps=[POST_STEP]))
        from .inbound_fixtures import publish_scenario
        await publish_scenario("sc-pp2")
        _, plain = await mk_token(kind="platform", name="ppt2")
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-pp2"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "not_read_only"

    async def test_jwt_platform_task_private_422(self, client):
        """JWT 创建平台任务:user 403;私有场景 422(§5.2)。"""
        await seed_platform_user()
        h_user = await _register_role(client, "pp_user", "user")
        await client.post("/api/scenarios", headers=h_user,
                          json=_draft("sc-pp3", steps=[GET_STEP]))
        r = await client.post("/api/integration/tasks", headers=h_user, json={
            "name": "t", "scenarioId": "sc-pp3", "identityMode": "platform",
            "triggerCron": "0 2 * * *"})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "capability_forbidden"
        h_member = await _register_role(client, "pp3", "admin")
        r = await client.post("/api/integration/tasks", headers=h_member, json={
            "name": "t", "scenarioId": "sc-pp3", "identityMode": "platform",
            "triggerCron": "0 2 * * *"})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "platform_scope_denied"


# ── 接口面收口(§2.2:graph / cancel 隔离 / 平台执行可见性 / 最近调用)──


class TestInterfaceFace:
    async def test_token_with_graph_422(self, client):
        """D20:令牌请求带 graph 一律 422(graph 为 JWT 专属)。"""
        await seed_platform_user()
        h = await _register_role(client, "if1", "admin")
        _, plain = await mk_token(user_id=await _user_id("if1"))
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "graph": {"mode": "aggregate",
                      "units": [{"ref": "a", "scenarioId": "sc-x"}]}})
        assert r.status_code == 422
        detail = r.json()["detail"]
        assert detail["code"] == "inbound_field_not_allowed"
        assert "graph" in detail["message"]

    async def test_cancel_isolated_by_token(self, client):
        """D25:令牌只能取消本令牌发起的执行;他人令牌 cancel 404。"""
        from .inbound_fixtures import mk_execution
        await seed_platform_user()
        h = await _register_role(client, "if2", "admin")
        tid_a, plain_a = await mk_token(user_id=await _user_id("if2"))
        _, plain_b = await mk_token(user_id=await _user_id("if2"),
                                    name="t-b")
        ex_id = await mk_execution(token_id=tid_a, status="running")
        # B 令牌看不到也取消不了 A 的执行
        r = await client.post(f"/api/executions/{ex_id}/cancel",
                              headers=_gtk(plain_b))
        assert r.status_code == 404
        # A 令牌取消自己的执行
        r = await client.post(f"/api/executions/{ex_id}/cancel",
                              headers=_gtk(plain_a))
        assert r.status_code == 200, r.text

    async def test_platform_execution_visibility_member_plus(self, client):
        """§5.2:执行属主为系统用户(平台令牌发起)时 member+ 可见,user 404。"""
        from .inbound_fixtures import mk_execution
        await seed_platform_user()
        ptid, _ = await mk_token(kind="platform", name="pv")
        ex_id = await mk_execution(token_id=ptid, status="running")
        h_member = await _register_role(client, "if3", "admin")
        r = await client.get(f"/api/executions/{ex_id}", headers=h_member)
        assert r.status_code == 200
        h_user = await _register_role(client, "if4", "user")
        r = await client.get(f"/api/executions/{ex_id}", headers=h_user)
        assert r.status_code == 404

    async def test_recent_calls_success_denied_and_revoked(self, client,
                                                           monkeypatch):
        """§7.2 最近调用:成功与被拒同列;吊销后的被拒归到该令牌;
        hash 未命中不出现在任何令牌下。"""
        await seed_platform_user()
        await seed_alias("rc-test", base_url="https://rc.local")
        h = await _register_role(client, "if5", "admin")
        draft = _draft("sc-rc1", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="rc-test"))])
        await client.post("/api/scenarios", headers=h, json=draft)
        tid, plain = await mk_token(user_id=await _user_id("if5"),
                                    scope_aliases=["rc-test"])
        # ① 成功调用一次
        from app.services import run_dispatcher as rd

        async def _fake_fanout(*, db_factory, execution_id, **kw):
            await rd.transition_with_retry(
                db_factory, execution_id, rd.STATUS_DONE)

        monkeypatch.setattr(rd, "_fanout", _fake_fanout)
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rc1"})
        assert r.status_code == 201, r.text
        await _exec_done(r.json()["executionId"])
        # ② 被拒一次(范围外场景)
        draft2 = _draft("sc-rc2", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="no-such-alias"))])
        await client.post("/api/scenarios", headers=h, json=draft2)
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rc2"})
        assert r.status_code == 403
        # ③ 吊销后再被拒一次(401,hash 命中已吊销仍归档到该令牌)
        async with db_module.SessionLocal() as s:
            tok = await s.get(AccessToken, tid)
            tok.revoked_at = at_svc.now_utc()
            await s.commit()
        r = await client.post("/api/runs", headers=_gtk(plain), json={
            "scenarioId": "sc-rc1"})
        assert r.status_code == 401
        # ④ hash 未命中(随机明文)—— 不归任何令牌
        r = await client.get("/api/executions", headers=_gtk("gtk_nope"))
        assert r.status_code == 401
        # 详情:三条都在(倒序:吊销后拒绝 → 超范围拒绝 → 成功)
        r = await client.get(f"/api/access-tokens/{tid}", headers=h)
        assert r.status_code == 200, r.text
        calls = r.json()["recentCalls"]
        assert len(calls) >= 3
        kinds = [(c["denied"], c.get("reason")) for c in calls[:3]]
        assert kinds[0] == (True, "token_invalid")   # 吊销后拒绝(最新)
        assert kinds[1][0] is True                   # 超范围拒绝
        assert kinds[2][0] is False                  # 成功调用
        # 无关令牌(if5b 用户的另一张)不含这些记录
        h_other = await _register_role(client, "if6", "admin")
        _, plain_other = await mk_token(
            user_id=await _user_id("if6"), name="other")
        r = await client.get("/api/access-tokens", headers=h_other)
        other_id = r.json()["items"][0]["id"]
        r = await client.get(f"/api/access-tokens/{other_id}",
                             headers=h_other)
        assert r.json()["recentCalls"] == []


# ── 范围对象生命周期(§4.1:改名级联)与明文规格(§4.1)────────────────


class TestScopeObjects:
    async def test_alias_rename_cascades_scope(self, client):
        """§4.1:别名改名级联到范围行(ON UPDATE CASCADE),授权随名走。"""
        await seed_platform_user()
        await seed_alias("ren-a", base_url="https://ren.local")
        h = await _register_role(client, "so1", "admin")
        tid, _ = await mk_token(user_id=await _user_id("so1"),
                                scope_aliases=["ren-a"])
        from app.models.service_alias import ServiceAlias as _SA
        async with db_module.SessionLocal() as s:
            row = await s.get(_SA, "ren-a")
            row.alias_name = "ren-b"
            await s.commit()
        r = await client.get(f"/api/access-tokens/{tid}", headers=h)
        assert r.status_code == 200
        assert r.json()["scope"]["aliases"] == ["ren-b"]

    async def test_plaintext_and_hint_shape(self, client):
        """§4.1:明文 = gtk_ + 43 字符 urlsafe;hint = 随机部分前4…后4。"""
        await seed_platform_user()
        h = await _register_role(client, "so2", "admin")
        out = await _api_token(client, h, {
            "kind": "personal", "name": "shape", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        token = out["token"]
        assert token.startswith("gtk_")
        assert len(token) == len("gtk_") + 43   # secrets.token_urlsafe(32)
        item = (await client.get("/api/access-tokens", headers=h)
                ).json()["items"][0]
        rand = token[len("gtk_"):]
        assert item["tokenHint"] == f"{rand[:4]}…{rand[-4:]}"


# ── 注册/保存面范围闸(§5.4 状态码约定:注册与保存 422)──────────────


class TestRegisterScopeGate:
    async def test_create_out_of_scope_422_then_in_scope_201(self, client):
        """令牌注册超范围场景 → 422 resource_not_allowed;范围补齐 → 201。"""
        await seed_platform_user()
        await seed_alias("rg-out", base_url="https://out.local")
        h = await _register_role(client, "rg1", "admin")
        draft = _draft("sc-rg1", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="rg-out"))])
        await client.post("/api/scenarios", headers=h, json=draft)
        # 空范围令牌注册 → 422(缺项「未授权」)
        _, plain = await mk_token(user_id=await _user_id("rg1"))
        r = await client.post("/api/integration/tasks", headers=_gtk(plain),
                              json={"name": "t", "scenarioId": "sc-rg1",
                                    "identityMode": "personal",
                                    "triggerCron": "0 3 * * *"})
        assert r.status_code == 422, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "resource_not_allowed"
        assert detail["missing"] == [{"kind": "alias", "name": "rg-out",
                                      "deleted": False}]
        # 范围补齐 → 201;JWT 注册不受令牌范围约束
        _, plain2 = await mk_token(user_id=await _user_id("rg1"),
                                   scope_aliases=["rg-out"])
        r = await client.post("/api/integration/tasks", headers=_gtk(plain2),
                              json={"name": "t2", "scenarioId": "sc-rg1",
                                    "identityMode": "personal",
                                    "triggerCron": "0 3 * * *"})
        assert r.status_code == 201, r.text
        r = await client.post("/api/integration/tasks", headers=h,
                              json={"name": "t3", "scenarioId": "sc-rg1",
                                    "identityMode": "personal",
                                    "triggerCron": "0 3 * * *"})
        assert r.status_code == 201, r.text

    async def test_patch_scheme_out_of_scope_422(self, client):
        """令牌 PATCH 换超范围方案 → 422(按将生效配方核对,§5.4 保存面)。"""
        await seed_platform_user()
        await seed_alias("rg-in", base_url="https://in.local")
        h = await _register_role(client, "rg2", "admin")
        await _add_credential("rg2", alias="auth-in")
        await _add_credential("rg2", alias="auth-out")
        draft = _draft("sc-rg2", steps=[dict(GET_STEP, call=dict(
            GET_STEP["call"], service="rg-in"))])
        await client.post("/api/scenarios", headers=h, json=draft)
        # 方案 A:绑定范围内凭证;方案 B:绑定范围外凭证
        # (body 是 RunScheme 平铺形状,serviceBindings 在顶层)
        r = await client.post("/api/scenarios/sc-rg2/run-schemes", headers=h,
                              json={"name": "ok", "serviceBindings": {
                                  "rg-in": {"authAlias": "auth-in"}}})
        assert r.status_code == 201, r.text
        scheme_ok = r.json().get("schemeId") or r.json().get("id")
        r = await client.post("/api/scenarios/sc-rg2/run-schemes", headers=h,
                              json={"name": "wide", "serviceBindings": {
                                  "rg-in": {"authAlias": "auth-out"}}})
        assert r.status_code == 201, r.text
        scheme_wide = r.json().get("schemeId") or r.json().get("id")
        # 令牌范围:别名 rg-in + 凭证 auth-in(不含 auth-out)
        uid = await _user_id("rg2")
        async with db_module.SessionLocal() as s:
            auth_in = (await s.execute(sa.select(AuthSession.id).where(
                AuthSession.owner_id == uid,
                AuthSession.alias == "auth-in"))).scalar_one()
        _, plain = await mk_token(user_id=uid, scope_aliases=["rg-in"],
                                  scope_auths=[auth_in])
        r = await client.post("/api/integration/tasks", headers=_gtk(plain),
                              json={"name": "t", "scenarioId": "sc-rg2",
                                    "identityMode": "personal",
                                    "schemeId": scheme_ok,
                                    "triggerCron": "0 3 * * *"})
        assert r.status_code == 201, r.text
        task_id = r.json()["id"]
        # 换到超范围方案 → 422(缺项 = 凭证 auth-out 未授权)
        r = await client.patch(f"/api/integration/tasks/{task_id}",
                               headers=_gtk(plain),
                               json={"schemeId": scheme_wide})
        assert r.status_code == 422, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "resource_not_allowed"
        assert {"kind": "auth", "name": "auth-out",
                "deleted": False} in detail["missing"]
        # 换回范围内方案 → 200
        r = await client.patch(f"/api/integration/tasks/{task_id}",
                               headers=_gtk(plain),
                               json={"schemeId": scheme_ok})
        assert r.status_code == 200, r.text
