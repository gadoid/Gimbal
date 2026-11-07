"""authz C2:平台模板转订阅制 + platform 系统静态令牌认证(dev-plan §十一)。

① 静态令牌认证(自举系统 platform,consolidated §3.3):auth 会话免
   登录 URL —— 令牌本体直接以 bearer 施加,不走登录流程;/test 对
   静态方式不做拨测。入站面 gtk_ 个人令牌 bearer 直连(无令牌 401)。
② 指纹闸覆盖平台模板(0038 改写后的形态:owner=__platform__ 的公共
   personal 模板):订阅 → 模板被改 → paused/template_changed →
   重新确认恢复;存量订阅实例迁移后照跑(钉 0038 的 visibility=
   'public' 双条件改写 —— 只改 identity_mode 的话闸内
   visibility != public → made_private 会暂停全部订阅,评审 R1)。
"""
from __future__ import annotations

from httpx import AsyncClient

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.user import User
from app.services import integration_runner as ir
from tests.helpers import make_draft, register_and_login
from tests.test_integration_consent_fixes import (
    ANCHORED_STEPS, FULLS, _subscribe, _task_body,
)
from tests.test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


async def _uid(username: str) -> int:
    from sqlalchemy import select as sa_select

    async with db_module.SessionLocal() as s:
        return (await s.execute(sa_select(User.id).where(
            User.username == username))).scalars().one()


async def _inst(tpl_id: int, holder: int) -> IntegrationTask | None:
    from sqlalchemy import select as sa_select

    async with db_module.SessionLocal() as s:
        return (await s.execute(sa_select(IntegrationTask).where(
            IntegrationTask.template_id == tpl_id,
            IntegrationTask.holder_id == holder))).scalar()


# ── ① 静态令牌认证 ────────────────────────────────────────────────
class TestStaticTokenAuth:
    async def test_auth_session_without_login_url(self, client: AsyncClient):
        """静态令牌方式:url 免填(区别于登录式),令牌本体直接施加。"""
        h = await register_and_login(client, "c2_st")
        r = await client.post("/api/auths", headers=h, json={
            "alias": "platform", "username": "me",
            "password": "gtk_static_token", "tokenType": "Bearer"})
        assert r.status_code in (200, 201), r.text
        assert r.json()["url"] == ""

        # /test 不做登录拨测(无登录流程)
        aid = r.json()["id"]
        r = await client.post(f"/api/auths/{aid}/test", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        assert "无登录" in r.json()["message"]

        # 执行链照常解析(令牌本体 = password 值)
        from app.services.run_prepare import resolve_exec_auths

        out = await resolve_exec_auths(
            db_module.SessionLocal, await _uid("c2_st"), ["platform"])
        assert out and out[0].password == "gtk_static_token"

    async def test_inbound_bearer_personal_token_no_login(
            self, client: AsyncClient):
        """入站面:gtk_ 个人令牌 bearer 直连;无令牌 401(不走登录)。"""
        from tests.inbound_fixtures import mk_token

        await register_and_login(client, "c2_ib")
        _, plain = await mk_token(user_id=await _uid("c2_ib"))
        r = await client.get(
            "/api/executions", headers={"Authorization": f"Bearer {plain}"})
        assert r.status_code == 200, r.text
        r = await client.get("/api/executions")
        assert r.status_code in (401, 403), r.text


# ── ② 平台模板订阅指纹闸 ─────────────────────────────────────────
async def _mk_platform_template(client: AsyncClient, plate_mock: PlateMock,
                                *, sid: str = "sc-c2") -> tuple[int, dict]:
    """公共场景 + owner=__platform__ 的公共 personal 模板(0038 形态)。"""
    from tests.inbound_fixtures import seed_platform_user

    plate_mock.fulls.update(FULLS)
    h_own = await register_and_login(client, "c2_own")
    r = await client.post("/api/scenarios", headers=h_own, json=make_draft(
        sid, steps=ANCHORED_STEPS, plate={"jira": "1.0#1"}, system=["jira"]))
    assert r.status_code in (200, 201), r.text
    from tests.inbound_fixtures import publish_scenario

    await publish_scenario(sid)

    plat_uid = await seed_platform_user()
    async with db_module.SessionLocal() as s:
        tpl = IntegrationTask(
            name="c2-platform-tpl", owner_id=plat_uid,
            visibility="public", identity_mode="personal",
            scenario_id=sid, target_system="jira",
            trigger_cron="*/5 * * * *", result_policy="latest",
            card_template="status")
        s.add(tpl)
        await s.commit()
        await s.refresh(tpl)
        return tpl.id, {"owner_h": h_own}


class TestPlatformTemplateSubscription:
    async def test_template_change_pauses_and_reconfirm_revives(
            self, client: AsyncClient, plate_mock: PlateMock):
        """订阅平台模板 → 属主改场景 → 实例暂停 template_changed →
        重新确认(新指纹)恢复执行。"""
        tid, ctx = await _mk_platform_template(client, plate_mock)
        h_sub = await register_and_login(client, "c2_sub")
        uid_sub = await _uid("c2_sub")

        r = await _subscribe(client, h_sub, tid)
        assert r.status_code in (200, 201), r.text
        inst = await _inst(tid, uid_sub)
        assert inst is not None and inst.consent_fingerprint

        # 模板被改:触发周期变更(指纹七要素之「周期」;Admin+ 维护
        # 平台模板的常规动作)
        async with db_module.SessionLocal() as s:
            tpl_row = await s.get(IntegrationTask, tid)
            tpl_row.trigger_cron = "*/10 * * * *"
            await s.commit()

        out = await ir.run_instance(inst.id)
        inst = await _inst(tid, uid_sub)
        assert inst.state == "paused"
        assert inst.paused_reason == "template_changed"

        # 重新确认(取新摘要指纹再订阅)→ 恢复
        r = await _subscribe(client, h_sub, tid)
        assert r.status_code in (200, 201), r.text
        inst = await _inst(tid, uid_sub)
        assert inst.state == "idle" and inst.paused_reason == ""

    async def test_legacy_instance_keeps_running_after_migration(
            self, client: AsyncClient, plate_mock: PlateMock):
        """R1 钉:0038 双条件改写(personal ∧ public)后,存量订阅实例
        照常执行 —— 不触发 made_private(那正是只改 identity_mode 的
        事故形态)。"""
        tid, _ = await _mk_platform_template(client, plate_mock,
                                             sid="sc-c2b")
        h_sub = await register_and_login(client, "c2_sub2")
        uid_sub = await _uid("c2_sub2")
        r = await _subscribe(client, h_sub, tid)
        assert r.status_code in (200, 201), r.text
        inst = await _inst(tid, uid_sub)

        await ir.run_instance(inst.id)
        inst = await _inst(tid, uid_sub)
        # 指纹一致 + 场景公共:不因可见性暂停(R1:visibility 改写钉)
        assert inst.paused_reason != "made_private"
        assert inst.paused_reason != "template_changed"
