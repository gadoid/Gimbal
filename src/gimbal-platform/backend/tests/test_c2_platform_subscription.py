"""authz C2:平台模板转订阅制 + platform 系统静态令牌认证(dev-plan §十一)。

① 静态令牌认证(自举系统 platform,consolidated §3.3):auth 会话免
   登录 URL —— 令牌本体直接以 bearer 施加,不走登录流程;/test 对
   静态方式不做拨测。入站面 gtk_ 个人令牌 bearer 直连(无令牌 401)。
② 指纹闸覆盖平台模板(0038 改写后的形态:owner=__platform__ 的公共
   personal 模板):订阅 → 模板被改 → paused/template_changed →
   重新确认恢复;存量订阅实例迁移后照跑(钉 0038 的 visibility=
   'public' 双条件改写 —— 只改 identity_mode 的话闸内
   visibility != public → made_private 会暂停全部订阅,评审 R1)。
③ 平台模板维护口径:__platform__ 持有、Admin+(ops.write)维护;恒
   公共;维护面不外溢到他人的个人公共模板。
"""
from __future__ import annotations

from httpx import AsyncClient

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.user import User
from app.services import integration_runner as ir
from tests.helpers import make_draft, register_and_login
from tests.test_integration_consent_fixes import ANCHORED_STEPS, FULLS, _subscribe
from tests.test_scenario_composer_plate_integration import (  # noqa: F401 — 模块级导入即 fixture 注册
    PlateMock, plate_mock,
)


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

        await ir.run_instance(inst.id)
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


# ── ③ 平台模板维护口径(__platform__ 持有、Admin+ 维护)────────────
class TestPlatformTemplateMaintenance:
    async def test_admin_maintains_user_cannot(
            self, client: AsyncClient, plate_mock: PlateMock):
        """Admin+(ops.write)可改/删平台模板;普通用户 403;canManage
        随之下发。平台模板恒公共:转私有 409。"""
        from tests.helpers import role_headers

        tid, _ = await _mk_platform_template(client, plate_mock,
                                             sid="sc-c2m")
        h_user = await role_headers(client, "c2_mu", role="user")
        h_adm = await role_headers(client, "c2_ma", role="admin")

        r = await client.get(f"/api/integration/tasks/{tid}", headers=h_user)
        assert r.status_code == 200 and r.json()["canManage"] is False
        r = await client.get(f"/api/integration/tasks/{tid}", headers=h_adm)
        assert r.status_code == 200 and r.json()["canManage"] is True

        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_user,
                               json={"triggerCron": "*/10 * * * *"})
        assert r.status_code == 403, r.text
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_adm,
                               json={"triggerCron": "*/10 * * * *"})
        assert r.status_code == 200, r.text
        assert r.json()["triggerCron"] == "*/10 * * * *"

        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_adm, json={"visibility": "private"})
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "platform_template_public"

        r = await client.post("/api/integration/cards", headers=h_adm,
                              json={"ids": [f"fn:{tid}"]})
        assert r.json()["items"][0]["canManage"] is True

        r = await client.delete(f"/api/integration/tasks/{tid}",
                                headers=h_user)
        assert r.status_code == 403, r.text
        r = await client.delete(f"/api/integration/tasks/{tid}",
                                headers=h_adm)
        assert r.status_code == 200, r.text

    async def test_admin_cannot_manage_personal_public_template(
            self, client: AsyncClient):
        """维护面只覆盖 __platform__ 持有的模板 —— 他人的个人公共模板
        Admin+ 无改动权(对象级规则不因角色越属主)。"""
        from tests.helpers import role_headers

        h_own = await register_and_login(client, "c2_po")
        r = await client.post("/api/scenarios", headers=h_own,
                              json=make_draft("sc-c2p"))
        assert r.status_code in (200, 201), r.text
        async with db_module.SessionLocal() as s:
            tpl = IntegrationTask(
                name="c2-personal-tpl", owner_id=await _uid("c2_po"),
                visibility="public", identity_mode="personal",
                scenario_id="sc-c2p", trigger_cron="*/5 * * * *",
                result_policy="latest", card_template="status")
            s.add(tpl)
            await s.commit()
            tid = tpl.id
        h_adm = await role_headers(client, "c2_pa", role="admin")
        r = await client.patch(f"/api/integration/tasks/{tid}",
                               headers=h_adm, json={"name": "x"})
        assert r.status_code == 403, r.text


# ── ④ 订阅执行:持有人 ≠ 场景属主 → 数据集敏感列不进执行 ──────────────
async def test_subscriber_run_strips_dataset_sensitive_columns(
        client: AsyncClient, plate_mock: PlateMock, monkeypatch):
    """原件不剥(authz W6 修订)后,订阅执行由运行面兜底:选中行的敏感
    列剥离后才合成;指纹仍按原行算(同一模板全订阅者同一指纹)。"""
    from sqlalchemy import select as sa_select

    from app.models.composer_run_scheme import ComposerRunScheme
    from app.services import run_prepare

    plate_mock.fulls.update(FULLS)
    h_own = await register_and_login(client, "c2_dso")
    draft = make_draft("sc-c2ds", steps=ANCHORED_STEPS,
                       plate={"jira": "1.0#1"}, system=["jira"])
    draft["definition"]["config"]["vars"] = {"amount": 1, "password": ""}
    r = await client.post("/api/scenarios", headers=h_own, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/scenarios/sc-c2ds/data-sets", headers=h_own,
                          json={"name": "ds", "rows": [
                              {"amount": 3, "password": "pw-secret"}]})
    ds_id = r.json()["datasetId"]
    async with db_module.SessionLocal() as s:
        sch = (await s.execute(sa_select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-c2ds"))).scalars().first()
        sch.payload = {**(sch.payload or {}), "dataSetIds": [ds_id]}
        await s.commit()
    from tests.inbound_fixtures import publish_scenario

    await publish_scenario("sc-c2ds")
    async with db_module.SessionLocal() as s:
        tpl = IntegrationTask(
            name="c2-ds-tpl", owner_id=await _uid("c2_dso"),
            visibility="public", identity_mode="personal",
            scenario_id="sc-c2ds", target_system="jira",
            trigger_cron="*/5 * * * *", result_policy="latest",
            card_template="status")
        s.add(tpl)
        await s.commit()
        tid = tpl.id

    h_sub = await register_and_login(client, "c2_dss")
    r = await _subscribe(client, h_sub, tid)
    assert r.status_code in (200, 201), r.text
    inst = await _inst(tid, await _uid("c2_dss"))

    seen: list[dict] = []
    orig = run_prepare.compose_scenario

    def _spy(payload, row, *a, **kw):
        seen.append(dict(row))
        return orig(payload, row, *a, **kw)

    monkeypatch.setattr(run_prepare, "compose_scenario", _spy)
    await ir.run_instance(inst.id)
    inst = await _inst(tid, await _uid("c2_dss"))
    assert inst.paused_reason != "template_changed"   # 指纹未漂移
    assert seen, "未走到合成"
    assert seen[-1].get("amount") == 3
    assert "password" not in seen[-1]
