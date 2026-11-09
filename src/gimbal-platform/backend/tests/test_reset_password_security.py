"""authz W6:重置密码不再是接管通道(dev-plan W6 测试项①–⑤)。

管理员重置密码的三件套(方案 10.1):
* must_change_password=True → 只能改密门(CurrentUser 403
  password_change_required,白名单 /auth/me / /auth/refresh /
  /auth/change-password;评审 R4:拦了 me 前端永远到不了改密页);
* 本人个人令牌全部落库失效(REASON_PASSWORD)+ 注册方实例暂停;
* token_version + 1 → 旧 JWT access/refresh 整体失效。

临时密码仍一次性返回给管理员(R8 定死:当前无其他通道交给用户,
接受「能接管、做不到悄悄接管」—— 审计 + 通知 + 强制改密在)。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import role_headers


async def _reset(client: AsyncClient, target_username: str) -> dict:
    """super_admin 重置 target 密码,返回 {user_id, new_password, 旧材料}。"""
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.user import User

    h_root = await role_headers(client, "rp_root", role="super_admin")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa_select(User.id).where(
            User.username == target_username))).scalar_one()
    r = await client.post(f"/api/users/{uid}/reset-password", headers=h_root)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["user_id"] == uid and out["new_password"]
    return out


class TestResetPasswordSecurity:
    async def test_old_token_and_jwt_die_and_must_change_flow(
            self, client: AsyncClient):
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.user import User

        # 靶子:user 角色用户 + 一张个人令牌 + 一个活跃 JWT
        h_victim = await role_headers(client, "rp_victim", role="user")
        from tests.inbound_fixtures import mk_token

        async with db_module.SessionLocal() as s:
            vid = (await s.execute(sa_select(User.id).where(
                User.username == "rp_victim"))).scalar_one()
        _tid, plain = await mk_token(user_id=vid)

        # ── 重置(靶子材料已就位:旧令牌 + 旧 JWT)─────────────────
        out = await _reset(client, "rp_victim")

        # ① 旧个人令牌 → 401 token_invalidated
        r = await client.get(
            "/api/executions",
            headers={"Authorization": f"Bearer {plain}"})
        assert r.status_code == 401, r.text
        assert r.json()["detail"]["code"] == "token_invalidated"

        # ② 旧 JWT(重置前签发)→ 401 token_version_stale
        r = await client.get("/api/auth/me", headers=h_victim)
        assert r.status_code == 401, r.text
        assert r.json()["detail"]["code"] == "token_version_stale"

        # ③ 临时密码登录:me 200(带 must_change_password)/ refresh 200 /
        #    改密 200 / 其他接口 403 password_change_required
        r = await client.post("/api/auth/login", json={
            "username": "rp_victim", "password": out["new_password"]})
        assert r.status_code == 200, r.text
        h_tmp = {"Authorization": f"Bearer {r.json()['access_token']}"}
        refresh = r.json()["refresh_token"]

        r = await client.get("/api/auth/me", headers=h_tmp)
        assert r.status_code == 200, r.text
        assert r.json()["must_change_password"] is True

        r = await client.post("/api/auth/refresh",
                              json={"refresh_token": refresh})
        assert r.status_code == 200, r.text

        r = await client.get("/api/scenarios", headers=h_tmp)
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "password_change_required"

        r = await client.post("/api/auth/change-password", headers=h_tmp,
                              json={"old_password": out["new_password"],
                                    "new_password": "Fresh2026pass"})
        assert r.status_code == 200, r.text

        # ④ 改密成功:门解除 + must_change_password 复位(新会话)
        h_new = {"Authorization":
                 f"Bearer {r.json()['access_token']}"}
        r = await client.get("/api/scenarios", headers=h_new)
        assert r.status_code == 200, r.text
        r = await client.get("/api/auth/me", headers=h_new)
        assert r.json()["must_change_password"] is False

    async def test_reset_notifies_target_and_audits(self, client: AsyncClient):
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.permission import AuditLog, Notification
        from app.models.user import User

        await role_headers(client, "rp_n2", role="user")
        out = await _reset(client, "rp_n2")
        async with db_module.SessionLocal() as s:
            vid = (await s.execute(sa_select(User.id).where(
                User.username == "rp_n2"))).scalar_one()
            note = (await s.execute(sa_select(Notification).where(
                Notification.user_id == vid,
                Notification.title.contains("重置")))).scalars().first()
            assert note is not None
            # 明文密码绝不进通知/日志(接管通道闭合的另一半)
            assert out["new_password"] not in (note.body or "")
            audit = (await s.execute(sa_select(AuditLog).where(
                AuditLog.action == "user.reset_password"))).scalars().first()
            assert audit is not None

    async def test_non_admin_cannot_reset_others(self, client: AsyncClient):
        """越权重置他人 → 403(既有闸回归;重置三件套只对合法重置生效)。"""
        from sqlalchemy import select as sa_select

        from app.core import db as db_module
        from app.models.user import User

        await role_headers(client, "rp_n3a", role="user")
        await role_headers(client, "rp_n3b", role="user")
        async with db_module.SessionLocal() as s:
            bid = (await s.execute(sa_select(User.id).where(
                User.username == "rp_n3b"))).scalar_one()
        h_a = await role_headers(client, "rp_n3a", role="user")
        r = await client.post(f"/api/users/{bid}/reset-password", headers=h_a)
        assert r.status_code == 403, r.text
