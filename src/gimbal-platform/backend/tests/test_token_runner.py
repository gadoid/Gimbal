"""定时任务令牌复核(§3.3 #1–#6)、恢复入口、自动恢复、解绑(D26)。

直接驱动 ``integration_runner.run_instance``?不 —— 走与生产同一入口:
手动触发端点的占用 CAS 语义重;这里用 ``run_instance(instance_id,
lease=now)`` 直调(测试直调路径,lease 跳过判定),暂停断言落库面。
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models.access_token import AccessToken
from app.models.integration_task import IntegrationTask
from app.models.user import User
from app.services import access_token as at_svc
from app.services import integration_runner as ir

from .helpers import wait_until as _wait
from .inbound_fixtures import mk_task_pair, mk_token, seed_platform_user


async def _pause_reason(inst_id: int) -> str:
    async with db_module.SessionLocal() as s:
        inst = await s.get(IntegrationTask, inst_id)
        return f"{inst.paused_reason}" if inst.paused_reason else ""


async def _result_of(inst_id: int):
    async with db_module.SessionLocal() as s:
        inst = await s.get(IntegrationTask, inst_id)
        return inst.run_status, (inst.last_error or "")


class TestPreRunChecks:
    async def _run(self, inst_id):
        # lease = 认领时写入的 running_since(测试直调路径:取行上现值)
        from app.core.timeutil import ensure_aware
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            lease = ensure_aware(inst.running_since) \
                if inst.running_since else None
        return await ir.run_instance(inst_id, lease=lease)

    async def _scenario(self, scenario_id="sc-w", visibility="public"):
        from app.models.composer_scenario import ComposerScenario
        async with db_module.SessionLocal() as s:
            row = ComposerScenario(
                scenario_id=scenario_id,
                owner_id=1, visibility=visibility,
                payload={"definition": {"steps": [], "config": {},
                                        "meta": {"name": scenario_id}}})
            s.add(row)
            await s.commit()
            return row.scenario_id

    async def test_token_revoked_pauses(self, client):
        await seed_platform_user()
        await self._scenario()
        uid_owner = await _uid("tr_owner")
        tid, _ = await mk_token(user_id=uid_owner)
        tpl_id, inst_id, _ = await mk_task_pair(token_id=tid,
                                                owner_id=uid_owner)
        async with db_module.SessionLocal() as s:
            tok = await s.get(AccessToken, tid)
            tok.revoked_at = at_svc.now_utc()
            await s.commit()
        await self._run(inst_id)
        assert await _pause_reason(inst_id) == "token_revoked"

    async def test_token_invalidated_pauses(self, client):
        await seed_platform_user()
        await self._scenario()
        uid = await _uid("ti_owner")
        tid, _ = await mk_token(user_id=uid)
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            tok = await s.get(AccessToken, tid)
            tok.invalidated_at = at_svc.now_utc()
            tok.invalidated_reason = "password"
            await s.commit()
        await self._run(inst_id)
        assert await _pause_reason(inst_id) == "token_invalidated"

    async def test_token_expired_pauses(self, client):
        await seed_platform_user()
        await self._scenario()
        uid = await _uid("te_owner")
        tid, _ = await mk_token(user_id=uid, days=-1)
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        await self._run(inst_id)
        assert await _pause_reason(inst_id) == "token_expired"

    async def test_owner_role_demoted_no_longer_pauses(self, client):
        """authz W5:「属主角色低于 admin」暂停原因不再产生 —— user 角色
        属主的个人令牌任务照常进入执行链(不再 auth 暂停;0036 已把
        存量该原因实例恢复)。"""
        await seed_platform_user()
        await self._scenario()
        uid = await _uid("to_owner", role="admin")
        tid, _ = await mk_token(user_id=uid)
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            u = await s.get(User, uid)
            u.role = "user"
            await s.commit()
        await self._run(inst_id)
        assert await _pause_reason(inst_id) != "token_owner_ineligible"

    async def test_owner_deactivated_pauses(self, client):
        await seed_platform_user()
        await self._scenario()
        uid = await _uid("td_owner")
        tid, _ = await mk_token(user_id=uid)
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            u = await s.get(User, uid)
            u.is_active = False
            await s.commit()
        await self._run(inst_id)
        assert await _pause_reason(inst_id) == "token_invalidated"

    async def test_platform_private_scenario_pauses_scope_denied(self, client):
        """#5 作用于全部平台模式任务(JWT 创建亦然)。"""
        await seed_platform_user()
        await self._scenario("sc-priv", visibility="private")
        async with db_module.SessionLocal() as s:
            pid = (await s.execute(sa.select(User.id).where(
                User.is_system == True))).scalar()  # noqa: E712
        tpl = IntegrationTask(name="jp", owner_id=pid,
                              identity_mode="platform",
                              scenario_id="sc-priv")
        async with db_module.SessionLocal() as s:
            s.add(tpl)
            await s.flush()
            inst = IntegrationTask(name="jp", owner_id=pid,
                                   template_id=tpl.id, holder_id=pid)
            s.add(inst)
            await s.commit()
            iid = inst.id
        await self._run(iid)
        assert await _pause_reason(iid) == "scope_denied"

    async def test_scope_exceeded_pauses_resource_not_allowed(self, client):
        """#6:超范围暂停;订阅者实例不受注册令牌影响(D19)。"""
        await seed_platform_user()
        from .test_access_tokens import GET_STEP
        scen_payload = {"definition": {
            "meta": {"name": "sc-sx"},
            "config": {},
            "steps": [dict(GET_STEP, call=dict(GET_STEP["call"],
                                               service="sx-alias"))]}}
        from app.models.composer_scenario import ComposerScenario
        from app.models.service_alias import ServiceAlias
        async with db_module.SessionLocal() as s:
            s.add(ServiceAlias(alias_name="sx-alias", base_service="pay",
                               kind="external", base_url="https://sx.local"))
            s.add(ComposerScenario(scenario_id="sc-sx",
                                   owner_id=1, visibility="public",
                                   payload=scen_payload))
            await s.commit()
        uid = await _uid("sx_owner")
        tid, _ = await mk_token(user_id=uid)      # 空范围
        tpl_id, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid,
                                                name="sx")
        # 场景 id 对齐(sc-w → sc-sx)
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            tpl.scenario_id = "sc-sx"
            await s.commit()
        await self._run(inst_id)
        reason = await _pause_reason(inst_id)
        assert reason == "resource_not_allowed"
        _, err = await _result_of(inst_id)
        assert "sx-alias" in err


async def _uid(username: str, *, role: str = "admin") -> int:
    from .inbound_fixtures import mk_user
    return await mk_user(username, role=role)


class TestResumeAndRevive:
    async def test_resume_allow_list_and_409s(self, client):
        """§3.3 恢复入口:token_revoked 409 提示解绑;expired/invalidated
        409 提示续期或重新生成;resource_not_allowed / owner_ineligible
        / scope_denied 放行。"""
        from .test_access_tokens import _register_role
        await seed_platform_user()
        h = await _register_role(client, "rv_m", "admin")
        uid = await _uid("rv_owner")
        tid, _ = await mk_token(user_id=uid)
        tpl_id, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        # 以属主身份操作(订阅面)
        login = await client.post("/api/auth/login", json={
            "username": "rv_owner", "password": "x"})
        h_owner = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def _set(reason: str):
            async with db_module.SessionLocal() as s:
                inst = await s.get(IntegrationTask, inst_id)
                inst.state = "paused"
                inst.paused_reason = reason
                await s.commit()

        for reason, expect in (
                ("token_revoked", 409),
                ("token_expired", 409),
                ("token_invalidated", 409),
                ("manual", 200),
        ):
            await _set(reason)
            r = await client.post(
                f"/api/integration/tasks/{tpl_id}/subscription/resume",
                headers=h_owner)
            assert r.status_code == expect, (reason, r.text)
            if expect == 409:
                assert r.json()["detail"]["code"] == "resume_not_allowed"

    async def test_regenerate_auto_revives(self, client):
        """重新生成 → token_invalidated/token_expired 暂停自动恢复。"""
        from .test_access_tokens import _api_token, _register_role
        await seed_platform_user()
        h = await _register_role(client, "gr_m", "admin")
        out = await _api_token(client, h, {
            "kind": "personal", "name": "gr", "ttlDays": 30,
            "scope": {"aliases": [], "authIds": []}})
        tid = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]["id"]
        async with db_module.SessionLocal() as s:
            uid = (await s.execute(sa.select(User.id).where(
                User.username == "gr_m"))).scalar_one()
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.state = "paused"
            inst.paused_reason = "token_expired"
            await s.commit()
        r = await client.post(f"/api/access-tokens/{tid}/regenerate",
                              headers=h)
        assert r.status_code == 200
        # revive 在端点内同步完成(§3.3 自动恢复,复活钩子同一机制)
        assert await _state_of(inst_id) == "idle"

    async def test_renew_revives_expired_instance(self, client):
        """续期 → token_expired 暂停自动恢复(§3.4)。"""
        from .test_access_tokens import _api_token, _register_role
        await seed_platform_user()
        h = await _register_role(client, "rn_m", "admin")
        await _api_token(client, h, {
            "kind": "personal", "name": "rn", "ttlDays": 1,
            "scope": {"aliases": [], "authIds": []}})
        tid = (await client.get("/api/access-tokens", headers=h)
               ).json()["items"][0]["id"]
        async with db_module.SessionLocal() as s:
            uid = (await s.execute(sa.select(User.id).where(
                User.username == "rn_m"))).scalar_one()
        _, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.state = "paused"
            inst.paused_reason = "token_expired"
            await s.commit()
        r = await client.post(f"/api/access-tokens/{tid}/renew",
                              headers=h, json={"ttlDays": 30})
        assert r.status_code == 200
        assert await _state_of(inst_id) == "idle"


class TestUnbind:
    async def _paused_then_unbind_then_resume(self, client, *, reason: str):
        """P0 回归主链(评审 2026-11-05):吊销/到期暂停 → 解绑 → 手动
        启动。解绑须按 §3.6 实例暂停规则把 token_* 改 manual —— 此前
        解绑只处理未暂停实例,token_* 原样保留,恢复接口 409 提示
        「先解绑」,解绑后仍 409,死循环。"""
        from .test_access_tokens import _register_role
        await seed_platform_user()
        await _register_role(client, "ub2_m", "admin")
        uid = await _uid("ub2_owner")
        tid, _ = await mk_token(user_id=uid)
        tpl_id, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.state = "paused"
            inst.paused_reason = reason
            await s.commit()
        login = await client.post("/api/auth/login", json={
            "username": "ub2_owner", "password": "x"})
        h_owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = await client.patch(f"/api/integration/tasks/{tpl_id}",
                               headers=h_owner, json={"tokenId": None})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            assert tpl.token_id is None
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.paused_reason == "manual"
        # 解绑后可手动启动(死循环修复的判据)
        r2 = await client.post(
            f"/api/integration/tasks/{tpl_id}/subscription/resume",
            headers=h_owner)
        assert r2.status_code == 200, r2.text
        assert await _state_of(inst_id) == "idle"

    async def test_revoked_then_unbind_then_resume(self, client):
        """吊销 → 解绑 → 启动。"""
        await self._paused_then_unbind_then_resume(
            client, reason="token_revoked")

    async def test_expired_then_unbind_then_resume(self, client):
        """到期 → 解绑 → 启动(token_id 已空无法重生,同 P0)。"""
        await self._paused_then_unbind_then_resume(
            client, reason="token_expired")

    async def test_scope_denied_pause_survives_unbind(self, client):
        """§3.6:其余暂停原因(scope_denied)解绑后原样保留,不被
        manual 覆盖掉真实成因。"""
        await seed_platform_user()
        uid = await _uid("ub3_owner")
        tid, _ = await mk_token(user_id=uid)
        tpl_id, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            inst.state = "paused"
            inst.paused_reason = "scope_denied"
            await s.commit()
        login = await client.post("/api/auth/login", json={
            "username": "ub3_owner", "password": "x"})
        h_owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = await client.patch(f"/api/integration/tasks/{tpl_id}",
                               headers=h_owner, json={"tokenId": None})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.paused_reason == "scope_denied"

    async def test_jwt_unbind_d26(self, client):
        """JWT 管理者 PATCH {tokenId: null}:token_id 置空、manual 暂停、
        停回调;令牌路径不能解绑。"""
        from .test_access_tokens import _register_role
        await seed_platform_user()
        h = await _register_role(client, "ub_m", "admin")
        uid = await _uid("ub_owner")
        tid, plain = await mk_token(user_id=uid)
        tpl_id, inst_id, _ = await mk_task_pair(token_id=tid, owner_id=uid)
        # 属主 JWT 解绑(个人任务属主)
        login = await client.post("/api/auth/login", json={
            "username": "ub_owner", "password": "x"})
        h_owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = await client.patch(f"/api/integration/tasks/{tpl_id}",
                               headers=h_owner, json={"tokenId": None})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            assert tpl.token_id is None
            assert tpl.callback_path_override is None
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.paused_reason == "manual"
        # 令牌路径解绑 → 403
        tid2, plain2 = await mk_token(user_id=uid)
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            tpl.token_id = tid2
            tpl.removed_at = None
            await s.commit()
        r = await client.patch(f"/api/integration/tasks/{tpl_id}",
                               headers={"Authorization": f"Bearer {plain2}"},
                               json={"tokenId": None})
        assert r.status_code == 403
        # 绑定值非 null → 422
        r = await client.patch(f"/api/integration/tasks/{tpl_id}",
                               headers=h_owner, json={"tokenId": 123})
        assert r.status_code == 422

    async def test_unbind_pauses_owner_instance_not_min_id(self, client):
        """解绑目标实例显式定位(评审 2026-11-05 P2):个人模板存在
        id 更小的订阅者实例时,解绑暂停必须仍落属主(注册方)实例 ——
        旧实现取「该模板 id 最小的实例」,正确只是靠创建顺序。"""
        await seed_platform_user()
        uid = await _uid("ub5_owner")
        sub_id = await _uid("ub5_sub", role="user")
        tid, _ = await mk_token(user_id=uid)
        async with db_module.SessionLocal() as s:
            tpl = IntegrationTask(name="w-sub", owner_id=uid,
                                  identity_mode="personal",
                                  scenario_id="sc-w", token_id=tid)
            s.add(tpl)
            await s.flush()
            # 订阅者实例先建(id 更小)—— 旧实现会错拿到它
            sub = IntegrationTask(name="w-sub", owner_id=uid,
                                  template_id=tpl.id, holder_id=sub_id,
                                  state="idle")
            s.add(sub)
            await s.flush()
            own = IntegrationTask(name="w-sub", owner_id=uid,
                                  template_id=tpl.id, holder_id=uid,
                                  state="idle")
            s.add(own)
            await s.commit()
            tpl_id, sub_iid, own_iid = tpl.id, sub.id, own.id
        assert sub_iid < own_iid
        login = await client.post("/api/auth/login", json={
            "username": "ub5_owner", "password": "x"})
        h_owner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        r = await client.patch(f"/api/integration/tasks/{tpl_id}",
                               headers=h_owner, json={"tokenId": None})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as s:
            own_inst = await s.get(IntegrationTask, own_iid)
            assert own_inst.state == "paused"
            assert own_inst.paused_reason == "manual"
            # 订阅者实例不受解绑影响(订阅者自己的凭证与令牌无关)
            sub_inst = await s.get(IntegrationTask, sub_iid)
            assert sub_inst.state == "idle"
            assert not sub_inst.paused_reason


async def _state_of(inst_id: int) -> str:
    async with db_module.SessionLocal() as s:
        inst = await s.get(IntegrationTask, inst_id)
        return inst.state if inst else ""
