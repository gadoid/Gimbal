"""横向件补全轮(2026-10-20):审计/通知/时间线对既有功能的覆盖回填。

- 审计:平台凭证增删(admin-only 特权写)、admin 越属主的场景/套件
  删除与可见性变更、adaptation.batch.apply 死键退役;
- 通知:场景删除通知引用者(与 suite 删除/用户处置同口径)、
  integration/share_ref_* 类型进词表与开关、凭证复活钩子补恢复通知、
  resource_handoff 带 payload.sender_name(悬浮标签数据源);
- 时间线:场景域 created/import/deleted/published/unpublished、
  share 撤销/退订、suite 域事件并入查询面(此前只写不读)、
  集成边沿事件(subscribed/unsubscribed/paused/resumed)第四源。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.activity_event import ActivityEvent
from app.models.composer_scenario import ComposerScenario
from app.models.integration_task import IntegrationTask
from app.models.permission import AuditLog, Notification
from app.models.user import User
from tests.helpers import (
    login_user, make_draft, register_and_login,
)
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)


async def _seed_platform_user() -> None:
    from app.core.security import hash_password
    async with db_module.SessionLocal() as db:
        exists = (await db.execute(select(User).where(
            User.is_system == True))).scalar()  # noqa: E712
        if exists is None:
            db.add(User(username="__platform__", display_name="平台系统",
                        password_hash=hash_password("x"), is_system=True))
            await db.commit()


async def _audit_rows(action: str) -> list[AuditLog]:
    async with db_module.SessionLocal() as db:
        return list((await db.execute(select(AuditLog).where(
            AuditLog.action == action).order_by(
            AuditLog.id.desc()))).scalars().all())


async def _activity_rows(actor_id: int, kind: str) -> list[ActivityEvent]:
    async with db_module.SessionLocal() as db:
        return list((await db.execute(select(ActivityEvent).where(
            ActivityEvent.actor_id == actor_id,
            ActivityEvent.kind == kind))).scalars().all())


async def _notifications(user_id: int, type_: str) -> list[Notification]:
    async with db_module.SessionLocal() as db:
        return list((await db.execute(select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == type_))).scalars().all())


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as db:
        return (await db.execute(select(User.id).where(
            User.username == username))).scalar_one()


async def _mk_scenario(client, h, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft(sid))
    assert r.status_code in (200, 201), r.text


# ── 审计:平台凭证(admin-only 特权写)──────────────────────────────

class TestAuditPlatformCredentials:
    async def test_create_and_delete_audited(self, client):
        await _seed_platform_user()
        await register_and_login(client, "hz_first", "hz_firstpass123")
        h = await register_and_login(client, "hz_admin", "hz_adminpass123")
        async with db_module.SessionLocal() as db:
            u = (await db.execute(select(User).where(
                User.username == "hz_admin"))).scalar()
            u.role = "admin"
            await db.commit()
        r = await client.post("/api/integration/platform-credentials",
                              headers=h, json={
                                  "alias": "hz-bot", "url": "https://x",
                                  "username": "bot", "password": "s3cret"})
        assert r.status_code == 201, r.text
        rows = await _audit_rows("integration.credential.write")
        assert len(rows) == 1 and rows[0].detail["fn"] == "create"
        assert rows[0].resource_type == "integration_credential"
        cred_id = r.json()["id"]
        r = await client.delete(
            f"/api/integration/platform-credentials/{cred_id}", headers=h)
        assert r.status_code == 200, r.text
        rows = await _audit_rows("integration.credential.write")
        assert len(rows) == 2 and rows[0].detail["fn"] == "delete"
        # 删除后审计仍可读(resource_name 折叠在 detail)
        assert rows[0].detail.get("resource_name") == "hz-bot"


# ── 审计:admin 越属主的删除/可见性变更 ────────────────────────────

class TestAuditAdminCrossOwner:
    async def test_scenario_visibility_and_delete(self, client):
        await register_and_login(client, "ax_admin", "ax_adminpass123")
        h_owner = await register_and_login(client, "ax_owner", "ax_ownerpass123")
        owner_id = await _uid("ax_owner")
        await _mk_scenario(client, h_owner, "sc-ax-1")
        # 属主自发布/自下架:不入审计(只记越属主那一半),事件落本人轴
        r = await client.post("/api/scenarios/sc-ax-1/publish",
                              headers=h_owner)
        assert r.status_code == 200, r.text
        # 重复发布 = 状态未变:不刷事件
        r = await client.post("/api/scenarios/sc-ax-1/publish",
                              headers=h_owner)
        assert r.status_code == 200, r.text
        assert len(await _activity_rows(owner_id, "scenario.published")) == 1
        assert not await _audit_rows("scenario.admin_publish")
        r = await client.post("/api/scenarios/sc-ax-1/unpublish",
                              headers=h_owner)
        assert r.status_code == 200, r.text

        # admin 越属主:发布/下架/删除三条审计 + 事件落受影响人轴
        async with db_module.SessionLocal() as db:
            u = (await db.execute(select(User).where(
                User.username == "ax_admin"))).scalar()
            u.role = "admin"
            await db.commit()
        h_admin = await login_user(client, "ax_admin", "ax_adminpass123")
        r = await client.post("/api/scenarios/sc-ax-1/publish",
                              headers=h_admin)
        assert r.status_code == 200, r.text
        r = await client.post("/api/scenarios/sc-ax-1/unpublish",
                              headers=h_admin)
        assert r.status_code == 200, r.text
        r = await client.delete("/api/scenarios/sc-ax-1", headers=h_admin)
        assert r.status_code == 204, r.text
        assert len(await _audit_rows("scenario.admin_publish")) == 1
        assert len(await _audit_rows("scenario.admin_unpublish")) == 1
        assert len(await _audit_rows("scenario.admin_delete")) == 1
        # 时间线:自发布 + admin 发布各一条 published(同理 unpublished),
        # admin 那两条 detail.by 记操作者;deleted 仅 admin 一条
        for kind in ("scenario.published", "scenario.unpublished"):
            rows = await _activity_rows(owner_id, kind)
            assert len(rows) == 2, kind
            assert sum(1 for x in rows if x.detail.get("by")) == 1, kind
        rows = await _activity_rows(owner_id, "scenario.deleted")
        assert len(rows) == 1
        assert rows[0].detail.get("by") == "ax_admin"

    async def test_suite_publish_delete_audited(self, client):
        await register_and_login(client, "as_admin", "as_adminpass123")
        h_owner = await register_and_login(client, "as_owner", "as_ownerpass123")
        owner_id = await _uid("as_owner")
        await _mk_scenario(client, h_owner, "sc-as-1")
        r = await client.post("/api/suites", headers=h_owner,
                              json={"name": "as-suite", "description": ""})
        assert r.status_code == 201, r.text
        suite_id = r.json()["suiteId"]
        r = await client.post(f"/api/suites/{suite_id}/members", headers=h_owner,
                              json={"scenarioIds": ["sc-as-1"],
                                    "publishUnpublished": True})
        assert r.status_code == 200, r.text
        async with db_module.SessionLocal() as db:
            u = (await db.execute(select(User).where(
                User.username == "as_admin"))).scalar()
            u.role = "admin"
            await db.commit()
        h_admin = await login_user(client, "as_admin", "as_adminpass123")
        r = await client.post(f"/api/suites/{suite_id}/publish", headers=h_admin)
        assert r.status_code == 200, r.text
        # 级联公开成员场景:scenario.published(via=suite_publish)落属主轴
        rows = await _activity_rows(owner_id, "scenario.published")
        assert len(rows) == 1 and rows[0].detail.get("via") == "suite_publish"
        r = await client.delete(f"/api/suites/{suite_id}", headers=h_admin)
        assert r.status_code == 204, r.text
        assert len(await _audit_rows("suite.admin_publish")) == 1
        assert len(await _audit_rows("suite.admin_delete")) == 1


# ── 通知:场景删除通知引用者(N1)───────────────────────────────────

class TestScenarioDeleteNotifiesReferrers:
    async def test_delete_notifies_grantee_and_records_event(self, client):
        await register_and_login(client, "nd_admin", "nd_adminpass123")
        h_owner = await register_and_login(client, "nd_owner", "nd_ownerpass123")
        owner_id = await _uid("nd_owner")
        h_grantee = await register_and_login(client, "nd_grantee",
                                             "nd_granteepass123")
        grantee_id = await _uid("nd_grantee")
        await _mk_scenario(client, h_owner, "sc-nd-1")
        r = await client.post("/api/scenarios/sc-nd-1/publish",
                              headers=h_owner)
        assert r.status_code == 200, r.text
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-nd-1",
            "granteeUserId": grantee_id, "mode": "ref"})
        assert r.status_code == 201, r.text
        r = await client.delete("/api/scenarios/sc-nd-1", headers=h_owner)
        assert r.status_code == 204, r.text
        notes = await _notifications(grantee_id, "share_ref_resource_deleted")
        assert len(notes) == 1
        assert notes[0].title.startswith("引用失效")
        # 时间线:删除事件落属主轴
        assert len(await _activity_rows(owner_id, "scenario.deleted")) == 1


# ── 通知:类型词表 + 开关(N2)+ handoff payload(N4)────────────────

class TestNotificationTypesSync:
    async def test_emitted_types_in_registry_and_prefs(self, client):
        from app.services.notifications import NOTIFICATION_TYPES
        for t in ("integration", "share_ref_received", "share_ref_revoked",
                  "share_ref_resource_deleted", "share_ref_owner_changed",
                  "scenario.version_change"):
            assert t in NOTIFICATION_TYPES, t
        h = await register_and_login(client, "nt_user", "nt_userpass123")
        # PrefsIn 现在收得下这些类型(此前 Literal 外 → 422)
        r = await client.put("/api/notifications/preferences", headers=h,
                             json={"off": ["integration",
                                           "share_ref_received"]})
        assert r.status_code == 200, r.text
        assert set(r.json()["off"]) == {"integration", "share_ref_received"}

    async def test_handoff_notification_carries_sender_name(self, client):
        await register_and_login(client, "hp_admin", "hp_adminpass123")
        h_owner = await register_and_login(client, "hp_owner", "hp_ownerpass123")
        owner_id = await _uid("hp_owner")
        h_grantee = await register_and_login(client, "hp_grantee",
                                             "hp_granteepass123")
        grantee_id = await _uid("hp_grantee")
        await _mk_scenario(client, h_owner, "sc-hp-1")
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-hp-1",
            "granteeUserId": grantee_id, "mode": "copy"})
        assert r.status_code == 201, r.text
        notes = await _notifications(grantee_id, "resource_handoff")
        assert len(notes) == 1
        # 悬浮标签数据源(handoff-unread 读 payload.sender_name)
        assert (notes[0].payload or {}).get("sender_name")
        assert owner_id  # noqa: B018


# ── 时间线:share 撤销/退订 + suite 源开放(T1/T3)─────────────────

class TestShareAndSuiteTimeline:
    async def test_unsubscribe_and_revoke_events(self, client):
        await register_and_login(client, "sr_admin", "sr_adminpass123")
        h_owner = await register_and_login(client, "sr_owner", "sr_ownerpass123")
        owner_id = await _uid("sr_owner")
        h_grantee = await register_and_login(client, "sr_grantee",
                                             "sr_granteepass123")
        grantee_id = await _uid("sr_grantee")
        await _mk_scenario(client, h_owner, "sc-sr-1")
        await client.post("/api/scenarios/sc-sr-1/publish", headers=h_owner)
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-sr-1",
            "granteeUserId": grantee_id, "mode": "ref"})
        share_id = r.json()["id"]
        # 退订:被分享人轴一条
        r = await client.delete(f"/api/shares/{share_id}", headers=h_grantee)
        assert r.status_code == 204, r.text
        assert len(await _activity_rows(
            grantee_id, "scenario.share_ref_unsubscribed")) == 1
        # 再建一次,走撤销:撤销者 + 被分享人双事件
        r = await client.post("/api/shares", headers=h_owner, json={
            "resourceType": "scenario", "resourceId": "sc-sr-1",
            "granteeUserId": grantee_id, "mode": "ref"})
        share_id = r.json()["id"]
        r = await client.delete(f"/api/shares/{share_id}", headers=h_owner)
        assert r.status_code == 204, r.text
        assert len(await _activity_rows(
            owner_id, "scenario.share_ref_revoked")) == 1
        rows = await _activity_rows(grantee_id, "scenario.share_ref_revoked")
        assert len(rows) == 1 and rows[0].detail.get("by")

    async def test_suite_created_published_deleted_in_activity(self, client):
        await register_and_login(client, "st_admin", "st_adminpass123")
        h = await register_and_login(client, "st_owner", "st_ownerpass123")
        uid = await _uid("st_owner")
        r = await client.post("/api/suites", headers=h,
                              json={"name": "st-suite", "description": ""})
        suite_id = r.json()["suiteId"]
        assert len(await _activity_rows(uid, "suite.created")) == 1
        r = await client.get("/api/activity", headers=h)
        suite_events = [e for e in r.json()["events"] if e["kind"] == "suite"]
        assert any(e["action"] == "suite.created" and e["suiteId"] == suite_id
                   for e in suite_events)
        assert r.json()["sources"]["suites"] is True
        r = await client.delete(f"/api/suites/{suite_id}", headers=h)
        assert r.status_code == 204, r.text
        assert len(await _activity_rows(uid, "suite.deleted")) == 1

    async def test_scenario_created_event(self, client):
        await register_and_login(client, "sc_admin", "sc_adminpass123")
        h = await register_and_login(client, "sc_owner", "sc_ownerpass123")
        uid = await _uid("sc_owner")
        await _mk_scenario(client, h, "sc-sc-1")
        rows = await _activity_rows(uid, "scenario.created")
        assert len(rows) == 1
        assert rows[0].detail["source"] == "manual"


# ── 时间线+通知:集成边沿事件与复活钩子(T2/N3)────────────────────

class TestIntegrationTimeline:
    async def test_revive_hook_records_event_and_notifies(self, client):
        from app.services import integration_runner
        await register_and_login(client, "iv_admin", "iv_adminpass123")
        await register_and_login(client, "iv_holder", "iv_holderpass123")
        holder_id = await _uid("iv_holder")
        async with db_module.SessionLocal() as db:
            tpl = IntegrationTask(
                name="iv-task", owner_id=holder_id,
                identity_mode="personal", target_type="scenario",
                scenario_id="sc-iv-1", trigger_cron="*/5 * * * *",
                result_policy="latest", visibility="public",
                card_template="status")
            db.add(tpl)
            await db.flush()
            db.add(IntegrationTask(
                name=tpl.name, owner_id=tpl.owner_id,
                template_id=tpl.id, holder_id=holder_id, enabled=True,
                state="paused", paused_reason="auth_failed"))
            await db.commit()
            tpl_id = tpl.id
        revived = await integration_runner.revive_paused_instances(holder_id)
        assert revived == 1
        rows = await _activity_rows(holder_id, "integration.resumed")
        assert len(rows) == 1 and rows[0].resource_id == str(tpl_id)
        assert rows[0].detail["via"] == "credential_revive"
        notes = await _notifications(holder_id, "integration")
        assert len(notes) == 1 and "自动恢复" in notes[0].title

    async def test_subscription_lifecycle_events(self, client, plate_mock):
        from tests.test_integration_consent_fixes import (
            ANCHORED_STEPS, FULLS, _subscribe, _task_body,
        )
        plate_mock.fulls.update(FULLS)
        await _seed_platform_user()
        await register_and_login(client, "il_first", "il_firstpass123")
        h_owner = await register_and_login(client, "il_owner",
                                           "il_ownerpass123")
        h_sub = await register_and_login(client, "il_sub", "il_subpass123")
        sub_id = await _uid("il_sub")
        r = await client.post(
            "/api/scenarios", headers=h_owner,
            json=make_draft("sc-il-1", steps=ANCHORED_STEPS,
                            plate={"jira": "1.0#1"},
                            system=["jira"]))
        assert r.status_code in (200, 201), r.text
        r = await client.post("/api/integration/tasks", headers=h_owner,
                              json=_task_body("sc-il-1", name="il-fn",
                                              visibility="public"))
        assert r.status_code in (200, 201), r.text
        tid = r.json()["id"]
        r = await _subscribe(client, h_sub, tid)
        assert r.status_code == 200, r.text
        assert len(await _activity_rows(sub_id, "integration.subscribed")) == 1
        r = await client.post(f"/api/integration/tasks/{tid}/subscription/pause",
                              headers=h_sub)
        assert r.status_code == 200, r.text
        assert len(await _activity_rows(sub_id, "integration.paused")) == 1
        r = await client.post(
            f"/api/integration/tasks/{tid}/subscription/resume", headers=h_sub)
        assert r.status_code == 200, r.text
        assert len(await _activity_rows(sub_id, "integration.resumed")) == 1
        r = await client.delete(
            f"/api/integration/tasks/{tid}/subscription", headers=h_sub)
        assert r.status_code == 204, r.text
        assert len(await _activity_rows(sub_id, "integration.unsubscribed")) == 1
        # 第四源:GET /activity 里能看到集成事件
        r = await client.get("/api/activity", headers=h_sub)
        assert r.json()["sources"]["integrations"] is True
        ints = [e for e in r.json()["events"] if e["kind"] == "integration"]
        assert any(e["action"] == "integration.subscribed" for e in ints)


# ── 审计:死键退役(A3)─────────────────────────────────────────────

class TestAuditDeadKeyRetired:
    def test_adaptation_batch_apply_removed_from_registry(self):
        from app.services.audit import AUDIT_ACTIONS
        assert "adaptation.batch.apply" not in AUDIT_ACTIONS
        for a in ("integration.credential.write", "scenario.admin_delete",
                  "scenario.admin_publish", "scenario.admin_unpublish",
                  "suite.admin_delete", "suite.admin_publish"):
            assert a in AUDIT_ACTIONS, a
