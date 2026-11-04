"""人员变动(§3.6):改密两个选项与 tv、停用失效、系统用户保护、
删除用户的令牌与集成任务处置。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.user import User
from app.services import access_token as at_svc

from .helpers import make_draft as _draft
from .inbound_fixtures import mk_token, seed_platform_user
from .test_access_tokens import (
    GET_STEP, _gtk, _register, _register_role, _user_id,
)


class TestChangePassword:
    async def test_defaults_invalidate_tokens_and_logout_others(self, client):
        await seed_platform_user()
        h = await _register_role(client, "cp_m", "member")
        # 两套登录(JWT)+ 一张令牌
        other = await client.post("/api/auth/login", json={
            "username": "cp_m", "password": "pw123456"})
        _, plain = await mk_token(user_id=await _user_id("cp_m"))
        r = await client.post("/api/auth/change-password", headers=h, json={
            "old_password": "pw123456", "new_password": "newpw12345"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["access_token"]          # 返回新 JWT
        # 旧 JWT(tv 过期)→ 401
        r2 = await client.get("/api/executions", headers=h)
        assert r2.status_code == 401
        # 其他会话的旧 refresh 不能换新(§3.6:tv 比对)
        r3 = await client.post("/api/auth/refresh", json={
            "refresh_token": other.json()["refresh_token"]})
        assert r3.status_code == 401
        # 新 JWT 正常
        r4 = await client.get("/api/executions", headers={
            "Authorization": f"Bearer {body['access_token']}"})
        assert r4.status_code == 200
        # 个人令牌已失效
        r5 = await client.get("/api/executions", headers=_gtk(plain))
        assert r5.status_code == 401
        assert r5.json()["detail"]["code"] == "token_invalidated"

    async def test_opt_out_keeps_tokens_and_sessions(self, client):
        await seed_platform_user()
        h = await _register_role(client, "cp2_m", "member")
        other = await client.post("/api/auth/login", json={
            "username": "cp2_m", "password": "pw123456"})
        _, plain = await mk_token(user_id=await _user_id("cp2_m"))
        r = await client.post("/api/auth/change-password", headers=h, json={
            "old_password": "pw123456", "new_password": "newpw12345",
            "invalidateTokens": False, "logoutOthers": False})
        assert r.status_code == 200
        # 令牌仍可用
        r2 = await client.get("/api/executions", headers=_gtk(plain))
        assert r2.status_code == 200
        # 其他会话的 refresh 仍可换新(tv 未变)
        r3 = await client.post("/api/auth/refresh", json={
            "refresh_token": other.json()["refresh_token"]})
        assert r3.status_code == 200

    async def test_platform_tokens_unaffected(self, client):
        await seed_platform_user()
        h = await _register_role(client, "cp3_m", "member")
        _, plain = await mk_token(kind="platform", name="pt")
        r = await client.post("/api/auth/change-password", headers=h, json={
            "old_password": "pw123456", "new_password": "newpw12345"})
        assert r.status_code == 200
        r2 = await client.get("/api/executions", headers=_gtk(plain))
        assert r2.status_code == 200

    async def test_invalidated_token_tasks_pause_and_revive(self, client):
        """改密失效 → 注册方实例 token_invalidated 暂停;重新生成自动恢复。"""
        from .inbound_fixtures import mk_task_pair
        await seed_platform_user()
        h = await _register_role(client, "cp4_m", "member")
        uid = await _user_id("cp4_m")
        tid, _ = await mk_token(user_id=uid)
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        await client.post("/api/auth/change-password", headers=h, json={
            "old_password": "pw123456", "new_password": "newpw12345"})
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.paused_reason == "token_invalidated"
        # 重新登录(旧密码已换)+ 重新生成 → 自动恢复
        login = await client.post("/api/auth/login", json={
            "username": "cp4_m", "password": "newpw12345"})
        h2 = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = await client.post(f"/api/access-tokens/{tid}/regenerate",
                              headers=h2)
        assert r.status_code == 200
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "idle"


class TestDeactivation:
    async def test_deactivate_invalidates_tokens(self, client):
        """停用 → 个人令牌落库失效(deactivated);重新启用不恢复。"""
        from .test_access_tokens import _admin_headers
        await seed_platform_user()
        await _register(client, "first_admin")  # 首注 admin
        h = await _register_role(client, "da_m", "member")
        uid = await _user_id("da_m")
        tid, plain = await mk_token(user_id=uid)
        h_admin = await _admin_headers(client)
        r = await client.patch(f"/api/users/{uid}", headers=h_admin,
                               json={"is_active": False})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as s:
            tok = (await s.execute(sa.select(
                __import__("app.models.access_token", fromlist=["AccessToken"])
                .AccessToken).where(
                    __import__("app.models.access_token", fromlist=["AccessToken"])
                    .AccessToken.id == tid))).scalar_one()
            assert tok.invalidated_reason == "deactivated"
        r2 = await client.get("/api/executions", headers=_gtk(plain))
        assert r2.status_code == 401
        # 重新启用不恢复(需重新生成)
        await client.patch(f"/api/users/{uid}", headers=h_admin,
                           json={"is_active": True})
        r3 = await client.get("/api/executions", headers=_gtk(plain))
        assert r3.status_code == 401

    async def test_system_user_patch_delete_409(self, client):
        from .test_access_tokens import _admin_headers
        await seed_platform_user()
        h_admin = await _admin_headers(client)
        async with db_module.SessionLocal() as s:
            pid = (await s.execute(sa.select(User.id).where(
                User.is_system == True))).scalar()  # noqa: E712
        r = await client.patch(f"/api/users/{pid}", headers=h_admin,
                               json={"is_active": False})
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "system_user_protected"
        r = await client.delete(f"/api/users/{pid}", headers=h_admin)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "system_user_protected"


class TestDeleteUserDisposal:
    """§3.6 删除用户:集成任务三处置 + 实例暂停规则 + 令牌删除。

    P1 先确认修掉的现存缺陷:此前删除拥有模板/实例的用户违反外键。
    """

    async def _admin(self, client):
        from .test_access_tokens import _admin_headers
        return await _admin_headers(client)

    async def _seed_owner_with_task(self, username: str,
                                    identity_mode: str = "personal"):
        from .inbound_fixtures import mk_task_pair, mk_user
        await mk_user(username, role="member")
        uid = await _user_id(username)
        tid, _ = await mk_token(user_id=uid)
        tpl_id, inst_id, _ = await mk_task_pair(
            token_id=tid, owner_id=uid, identity_mode=identity_mode,
            name=f"{username}-task")
        return uid, tid, tpl_id, inst_id

    async def test_transfer_personal_task(self, client):
        await seed_platform_user()
        await _register(client, "df_a0")           # 首注(无关)
        h_admin = await self._admin(client)
        await _register_role(client, "df_transferee", "member")
        transfee_id = await _user_id("df_transferee")
        uid, tid, tpl_id, inst_id = await self._seed_owner_with_task(
            "df_owner1")
        # 个人模式场景直插(处置段按 owner 找场景)
        from app.models.composer_scenario import ComposerScenario
        async with db_module.SessionLocal() as s:
            s.add(ComposerScenario(
                scenario_id=f"sc-{uid}", owner_id=uid, visibility="private",
                payload={"definition": {"steps": [], "config": {},
                                        "meta": {"name": "x"}}}))
            await s.commit()
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            tpl.scenario_id = f"sc-{uid}"
            await s.commit()
        r = await client.request(
            "DELETE", f"/api/users/{uid}", headers=h_admin,
            json={"disposal": "transfer", "transfer_to": transfee_id})
        assert r.status_code == 204, r.text
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            assert tpl.owner_id == transfee_id
            assert tpl.token_id is None
            # 原属主注册方实例已删(受让人启动时自建)
            n = (await s.execute(sa.select(sa.func.count()).select_from(
                IntegrationTask).where(
                    IntegrationTask.template_id == tpl_id))).scalar_one()
            assert n == 0

    async def test_publicize_platform_task_paused_manual(self, client):
        await seed_platform_user()
        await _register(client, "df_a1")
        h_admin = await self._admin(client)
        uid, tid, tpl_id, inst_id = await self._seed_owner_with_task(
            "df_owner2", identity_mode="platform")
        from app.models.composer_scenario import ComposerScenario
        from app.models.user import User as _U
        async with db_module.SessionLocal() as s:
            pid = (await s.execute(sa.select(User.id).where(
                User.is_system == True))).scalar()  # noqa: E712
            s.add(ComposerScenario(
                scenario_id=f"sc2-{uid}", owner_id=uid, visibility="private",
                payload={"definition": {"steps": [], "config": {},
                                        "meta": {"name": "x"}}}))
            await s.commit()
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            tpl.scenario_id = f"sc2-{uid}"
            await s.commit()
        r = await client.request(
            "DELETE", f"/api/users/{uid}", headers=h_admin,
            json={"disposal": "publicize"})
        assert r.status_code == 204, r.text
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            assert tpl.owner_id == pid      # __platform__
            assert tpl.token_id is None
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "paused"
            assert inst.paused_reason == "manual"

    async def test_purge_deletes_tasks(self, client):
        await seed_platform_user()
        await _register(client, "df_a2")
        h_admin = await self._admin(client)
        uid, tid, tpl_id, inst_id = await self._seed_owner_with_task(
            "df_owner3")
        from app.models.composer_scenario import ComposerScenario
        async with db_module.SessionLocal() as s:
            s.add(ComposerScenario(
                scenario_id=f"sc3-{uid}", owner_id=uid, visibility="private",
                payload={"definition": {"steps": [], "config": {},
                                        "meta": {"name": "x"}}}))
            await s.commit()
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            tpl.scenario_id = f"sc3-{uid}"
            await s.commit()
        r = await client.request(
            "DELETE", f"/api/users/{uid}", headers=h_admin,
            json={"disposal": "purge"})
        assert r.status_code == 204, r.text
        async with db_module.SessionLocal() as s:
            assert await s.get(IntegrationTask, tpl_id) is None

    async def test_pending_deliveries_failed_on_delete(self, client):
        """删除用户:令牌删除前 pending 投递显式置 failed(token_deleted)。"""
        from .inbound_fixtures import mk_pending
        await seed_platform_user()
        await _register(client, "df_a3")
        h_admin = await self._admin(client)
        uid, tid, _, _ = await self._seed_owner_with_task("df_owner4")
        did = await mk_pending(token_id=tid)
        r = await client.request(
            "DELETE", f"/api/users/{uid}", headers=h_admin,
            json={"disposal": "purge"})
        assert r.status_code == 204, r.text
        from app.models.webhook_delivery import WebhookDelivery
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.status == "failed"
            assert row.last_error == "token_deleted"
