"""入站/回调修复复核(2026-11-01)回归 —— 复核报告 §2 / §3.1 / §3.2。

* §2 grant 重新绑定:grant 到期 → 暂停 grant_revoked(「启动」409 指向
  PATCH 重绑)→ 调用方带**新 grant** PATCH → grant_id 更新、实例回
  idle、时间线 integration.resumed(via=grant_rebind)、下次运行通过;
  他人 grant → 403 grant_issuer_mismatch;平台模式任务带 grant → 422
  identity_mode_mismatch;不带 grant 的同别名 PATCH 不动 grant_id
  (维持 M2 别名级管理权)。
* §3.1 暂停通知按 pause_reason 分立:grant_revoked / scope_denied 不再
  冒充「凭证失效…自动恢复」;scope_denied 场景修复后可由「启动」恢复;
  auth_failed / missing_credential 维持原文案(复活钩子真会恢复它们)。
* §3.2 outbox 边角:flush 后序列化失败不留空体行;租约按组内位置递增;
  回写前校验行仍 pending(多实例预留)。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.core import db as db_module
from app.models.activity_event import ActivityEvent
from app.models.inbound_identity import InboundGrant
from app.models.integration_task import IntegrationTask
from app.models.permission import Notification
from app.models.service_alias import ServiceAlias
from app.models.webhook_delivery import WebhookDelivery
from app.services import integration_runner as ir
from app.services import webhook_outbox as wo
from app.services.inbound_identity import generate_grant_token, sha256_hex

from .helpers import make_draft as _draft
from .inbound_fixtures import (
    deliveries, mk_pending,
    publish_scenario as _publish,
    seed_alias as _seed_alias, seed_platform_user as _seed_platform_user,
)
from .test_inbound_identity import (
    GET_STEP, _gic, _mk_credential, _own_alias, _register, _user_id,
)

AUTH_STEP = {"kind": "step", "id": "s1", "call": {
    "protocol": "http", "service": "svc", "method": "GET", "path": "/x",
    "headers": {"Authorization": "${auth.gitlab.token}"}},
    "request": {"kind": "request", "body": {}}, "strategy": []}


# ── 助手 ──────────────────────────────────────────────────────────


async def _mk_grant_row(alias: str, user_id: int) -> "tuple[str, int]":
    """直插 grant 行,返回 (明文 token, 行 id)。"""
    token = generate_grant_token()
    async with db_module.SessionLocal() as s:
        row = InboundGrant(
            alias_name=alias, user_id=user_id, token_hash=sha256_hex(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        s.add(row)
        await s.commit()
        return token, row.id


async def _expire_grant(grant_id: int) -> None:
    async with db_module.SessionLocal() as s:
        row = await s.get(InboundGrant, grant_id)
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await s.commit()


async def _disown_alias(alias: str) -> None:
    """别名转团队共享(无属主)→ 平台模式只剩公共场景可用。"""
    async with db_module.SessionLocal() as s:
        row = await s.get(ServiceAlias, alias)
        row.owner_user_id = None
        await s.commit()


async def _register_personal_task(client, h, username: str, scenario_id: str,
                                  name: str) -> "tuple[int, int, str, int]":
    """入站个人模式注册(签发人 = username)。返回 (tid, inst_id, gic
    token, grant 行 id)。"""
    uid = await _user_id(username)
    await client.post("/api/scenarios", headers=h, json=_draft(
        scenario_id, steps=[GET_STEP]))
    token = await _mk_credential()
    grant, gid = await _mk_grant_row("agent-sys", uid)
    r = await client.post(
        "/api/integration/tasks", headers=_gic(token, grant),
        json={"name": name, "scenarioId": scenario_id,
              "identityMode": "personal"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    return tid, await _inst_id_of(tid), token, gid


async def _inst_id_of(tid: int) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(IntegrationTask.id).where(
            IntegrationTask.template_id == tid))).scalar_one()


async def _row(row_id: int) -> IntegrationTask:
    async with db_module.SessionLocal() as s:
        return await s.get(IntegrationTask, row_id)


async def _last_integration_notification(user_id: int) -> Notification:
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(
            sa.select(Notification).where(
                Notification.user_id == user_id,
                Notification.type == "integration")
            .order_by(Notification.id))).scalars().all()
        assert rows, "期望有集成通知"
        return rows[-1]


def _stub_run_ok(monkeypatch, scenario_id: str) -> None:
    """让 run_instance 过闸后真正跑完:plate convert 透传 + 通道回
    passed + 物化原样(与 test_integration 手动执行用例同桩)。"""
    from app.services import plate_client as pc

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}
    monkeypatch.setattr(pc, "convert", _fake_convert)

    class _FakeResult:
        launch_status = "ok"
        exit_code = 0
        error = ""
        details = [{"scenario_id": scenario_id, "outputs": {"k": "v"}}]

    class _FakeChannels:
        async def run_case(self, case_path):
            return _FakeResult()

        async def reap_idle(self):
            return 0

    monkeypatch.setattr(ir, "channels", _FakeChannels())
    monkeypatch.setattr(ir, "materialize_run_copy",
                        lambda converted, **kw: dict(converted))


# ── §2 grant 重新绑定 ──────────────────────────────────────────────


class TestGrantRebind:
    async def test_expired_grant_rebind_restores_and_next_run_passes(
            self, client, monkeypatch):
        """到期 → 暂停 grant_revoked(启动 409)→ 新 grant PATCH →
        grant_id 更新 + 实例回 idle + 时间线 → 下次运行通过。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_issuer")
        tid, iid, token, gid_old = await _register_personal_task(
            client, h, "hb_issuer", "sc-hb-1", "hb1")
        await _expire_grant(gid_old)
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.state == "paused"
        assert inst.paused_reason == "grant_revoked"
        assert "PATCH" in inst.last_error          # 文案指向重绑路径
        # 「启动」不解 grant_revoked:409 且指向 PATCH 重绑
        r = await client.post(
            f"/api/integration/tasks/{tid}/subscription/resume", headers=h)
        assert r.status_code == 409, r.text
        assert "resume_not_allowed" in r.text and "PATCH" in r.text
        # 签发人重新签发 → 调用方带新 grant PATCH(顺带改 clientRef)
        uid = await _user_id("hb_issuer")
        grant_new, gid_new = await _mk_grant_row("agent-sys", uid)
        r = await client.patch(
            f"/api/integration/tasks/{tid}", headers=_gic(token, grant_new),
            json={"clientRef": "after-rebind"})
        assert r.status_code == 200, r.text
        tpl = await _row(tid)
        assert tpl.grant_id == gid_new
        assert tpl.client_ref == "after-rebind"
        inst = await _row(iid)
        assert inst.state == "idle"
        assert inst.paused_reason == ""
        assert inst.next_run_at is not None
        async with db_module.SessionLocal() as s:
            evs = (await s.execute(sa.select(ActivityEvent).where(
                ActivityEvent.kind == "integration.resumed",
                ActivityEvent.resource_id == str(tid)))).scalars().all()
            assert evs and evs[-1].detail.get("via") == "grant_rebind"
        # 下次运行:新 grant 过重校验,真正跑完
        _stub_run_ok(monkeypatch, "sc-hb-1")
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.state == "idle"
        assert inst.paused_reason == ""
        assert inst.run_status == "ok"

    async def test_rebind_is_idempotent_when_not_paused(self, client):
        """实例未暂停时带 grant PATCH 只换 grant_id,不动状态、不写
        恢复时间线。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_idem")
        tid, iid, token, gid_old = await _register_personal_task(
            client, h, "hb_idem", "sc-hb-idem", "hbi")
        uid = await _user_id("hb_idem")
        grant_new, gid_new = await _mk_grant_row("agent-sys", uid)
        r = await client.patch(
            f"/api/integration/tasks/{tid}", headers=_gic(token, grant_new),
            json={})
        assert r.status_code == 200, r.text
        assert (await _row(tid)).grant_id == gid_new
        inst = await _row(iid)
        assert inst.state == "idle"
        async with db_module.SessionLocal() as s:
            n = (await s.execute(sa.select(sa.func.count()).select_from(
                ActivityEvent).where(
                ActivityEvent.kind == "integration.resumed",
                ActivityEvent.resource_id == str(tid)))).scalar_one()
            assert n == 0

    async def test_rebind_with_other_issuers_grant_403(self, client):
        """他人签发的 grant 不能接管任务:403,grant_id / 字段均不变。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_issuer2")
        await _register(client, "hb_other2")
        tid, _iid, token, gid_old = await _register_personal_task(
            client, h, "hb_issuer2", "sc-hb-2", "hb2")
        other_uid = await _user_id("hb_other2")
        grant_other, _ = await _mk_grant_row("agent-sys", other_uid)
        r = await client.patch(
            f"/api/integration/tasks/{tid}", headers=_gic(token, grant_other),
            json={"clientRef": "hijack"})
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "grant_issuer_mismatch"
        tpl = await _row(tid)
        assert tpl.grant_id == gid_old
        assert tpl.client_ref != "hijack"

    async def test_platform_task_with_grant_422(self, client):
        """平台模式任务不绑定 grant:带 grant 的 PATCH 身份不符 → 422
        (与创建闸同码)。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_p3")
        await _own_alias("agent-sys", "hb_p3")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-hb-3", steps=[GET_STEP]))
        token = await _mk_credential()
        r = await client.post(
            "/api/integration/tasks", headers=_gic(token),
            json={"name": "hb3", "scenarioId": "sc-hb-3",
                  "identityMode": "platform"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        grant, _ = await _mk_grant_row("agent-sys", await _user_id("hb_p3"))
        r = await client.patch(
            f"/api/integration/tasks/{tid}", headers=_gic(token, grant),
            json={"clientRef": "x"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "identity_mode_mismatch"
        assert (await _row(tid)).client_ref != "x"

    async def test_same_alias_patch_without_grant_keeps_grant_id(
            self, client):
        """M2 别名级管理权不变:同别名不带 grant 的 PATCH 仍能改字段,
        但 grant_id 不动(没有重绑语义)。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_p4")
        tid, _iid, token, gid_old = await _register_personal_task(
            client, h, "hb_p4", "sc-hb-4", "hb4")
        r = await client.patch(
            f"/api/integration/tasks/{tid}", headers=_gic(token),
            json={"clientRef": "platform-call"})
        assert r.status_code == 200, r.text
        tpl = await _row(tid)
        assert tpl.grant_id == gid_old
        assert tpl.client_ref == "platform-call"


# ── §3.1 暂停通知文案 ──────────────────────────────────────────────


class TestPauseNotificationText:
    async def test_grant_revoked_text_points_to_rebind(self, client):
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_n1")
        _tid, iid, _token, gid = await _register_personal_task(
            client, h, "hb_n1", "sc-hb-n1", "hbn1")
        await _expire_grant(gid)
        await ir.run_instance(iid)
        assert (await _row(iid)).paused_reason == "grant_revoked"
        n = await _last_integration_notification(await _user_id("hb_n1"))
        assert "授权已失效" in n.title
        assert "凭证失效" not in n.title
        assert "重新绑定" in n.body and "PATCH" in n.body
        assert "自动恢复" not in n.body

    async def test_scope_denied_text_and_resume_by_start(
            self, client, monkeypatch):
        """scope_denied:文案说场景范围而非凭证;场景公开后 admin
        「启动」恢复(此前 409 无路可走),再跑不再暂停。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_admin")      # 首个注册 = admin
        await _own_alias("agent-sys", "hb_admin")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-hb-6", steps=[GET_STEP]))
        token = await _mk_credential()
        r = await client.post(
            "/api/integration/tasks", headers=_gic(token),
            json={"name": "hb6", "scenarioId": "sc-hb-6",
                  "identityMode": "platform"})
        assert r.status_code == 201, r.text
        tid = r.json()["id"]
        iid = await _inst_id_of(tid)
        # 别名转团队共享 → 私有场景出范围
        await _disown_alias("agent-sys")
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.paused_reason == "scope_denied"
        assert "启动" in inst.last_error
        n = await _last_integration_notification(await _user_id("hb_admin"))
        assert "场景已不在平台模式允许范围" in n.title
        assert "凭证" not in n.title
        assert "启动" in n.body
        assert "自动恢复" not in n.body
        # 场景公开 → 「启动」解暂停
        await _publish("sc-hb-6")
        r = await client.post(
            f"/api/integration/tasks/{tid}/subscription/resume", headers=h)
        assert r.status_code == 200, r.text
        inst = await _row(iid)
        assert inst.state == "idle"
        assert inst.paused_reason == ""
        _stub_run_ok(monkeypatch, "sc-hb-6")
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.state == "idle"
        assert inst.run_status == "ok"

    async def test_missing_credential_text_unchanged(self, client):
        """默认分支钉住:缺凭证仍是「凭证失效…自动恢复」(复活钩子
        确实会恢复 auth_failed / missing_credential)。"""
        await _seed_platform_user()
        h = await _register(client, "hb_n3")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-hb-n3", steps=[AUTH_STEP]))
        r = await client.post(
            "/api/integration/tasks", headers=h,
            json={"name": "hbn3", "scenarioId": "sc-hb-n3",
                  "identityMode": "personal", "triggerCron": "0 * * * *"})
        assert r.status_code == 201, r.text
        iid = await _inst_id_of(r.json()["id"])
        await ir.run_instance(iid)
        assert (await _row(iid)).paused_reason == "missing_credential"
        n = await _last_integration_notification(await _user_id("hb_n3"))
        assert "凭证失效" in n.title
        assert "自动恢复" in n.body


# ── §3.2 outbox 边角 ───────────────────────────────────────────────


class TestOutboxEdges:
    async def test_post_flush_serialize_failure_leaves_no_row(
            self, client, monkeypatch):
        """S4:flush 后最终序列化失败 → 行撤出会话,_guarded 吞掉后
        随后的 commit 不会落下 body='' 的投递行。"""
        real = json

        class _FlakyJson:
            calls = 0

            def dumps(self, *a, **k):
                self.calls += 1
                if self.calls == 2:        # 第 1 次 = 插入前试序列化
                    raise ValueError("boom after flush")
                return real.dumps(*a, **k)

            def __getattr__(self, name):
                return getattr(real, name)

        monkeypatch.setattr(wo, "json", _FlakyJson())
        async with db_module.SessionLocal() as s:
            rid = await wo._guarded(
                "t", wo._add_delivery, s, alias_name="agent-sys",
                event_type="execution.finished",
                url="https://cb.example.local/x", payload={"a": 1})
            assert rid is None
            await s.commit()
        assert await deliveries() == []

    async def test_claim_lease_grows_with_group_position(self, client):
        """S2:同别名组内第 k 行租约 = k × 基数;其他别名各自从 1 起。"""
        a1 = await mk_pending(alias_name="agent-sys")
        a2 = await mk_pending(alias_name="agent-sys")
        a3 = await mk_pending(alias_name="agent-sys")
        b1 = await mk_pending(alias_name="other-sys")
        jobs = await wo._claim(db_module.SessionLocal)
        assert {j.id for j in jobs} == {a1, a2, a3, b1}
        base = timedelta(seconds=wo._delivery_lease_seconds())
        rows = {r.id: r for r in await deliveries()}
        assert rows[a2].next_retry_at - rows[a1].next_retry_at == base
        assert rows[a3].next_retry_at - rows[a2].next_retry_at == base
        assert rows[b1].next_retry_at == rows[a1].next_retry_at
        for r in rows.values():
            assert r.status == "pending"

    async def test_writeback_skips_row_no_longer_pending(self, client):
        """S2:回写前校验行仍 pending —— 已被另一实例投递的行不被改成
        failed、不再计次。"""
        rid = await mk_pending()
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, rid)
            row.status = "delivered"
            row.attempts = 1
            row.delivered_at = datetime.now(timezone.utc)
            await s.commit()
        job = wo._Job(id=rid, alias_name="agent-sys",
                      event_type="execution.finished",
                      url="https://cb.example.local/x", body="{}")
        await wo._writeback(db_module.SessionLocal, job, False, "late fail")
        row = (await deliveries())[0]
        assert row.status == "delivered"
        assert row.attempts == 1
        assert row.last_error is None


# ── 全量评估 2026-11-02 #6:别名开关 vs 凭证吊销 ───────────────────────


async def _set_inbound(alias: str, enabled: bool) -> None:
    async with db_module.SessionLocal() as s:
        row = await s.get(ServiceAlias, alias)
        row.inbound_enabled = enabled
        await s.commit()


class TestInboundSwitchVsCredentialRevoke:
    async def test_disable_inbound_pauses_task_and_restart_after_reenable(
            self, client, monkeypatch):
        """关「允许入站调用」→ 下次运行前暂停 inbound_disabled(回调 +
        时间线);重新开启后「启动」恢复 → 下次运行通过。"""
        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_sw")
        tid, iid, _token, _gid = await _register_personal_task(
            client, h, "hb_sw", "sc-hb-sw", "hbsw")
        await _set_inbound("agent-sys", False)
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.state == "paused"
        assert inst.paused_reason == "inbound_disabled"
        assert "允许入站调用" in inst.last_error
        paused = [d for d in await deliveries()
                  if d.event_type == "integration.paused"]
        assert paused and '"inbound_disabled"' in paused[-1].body
        # 重新开启 + 「启动」(白名单内,200)→ idle → 真正跑完
        await _set_inbound("agent-sys", True)
        r = await client.post(
            f"/api/integration/tasks/{tid}/subscription/resume", headers=h)
        assert r.status_code == 200, r.text
        assert (await _row(iid)).state == "idle"
        _stub_run_ok(monkeypatch, "sc-hb-sw")
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.state == "idle" and inst.run_status == "ok"

    async def test_revoking_credential_does_not_touch_tasks(
            self, client, monkeypatch):
        """吊销别名下全部 gic_:已注册任务照常运行(信任单元是别名)。"""
        from app.models.inbound_identity import InboundCredential

        await _seed_platform_user()
        await _seed_alias()
        h = await _register(client, "hb_rv")
        _tid, iid, _token, _gid = await _register_personal_task(
            client, h, "hb_rv", "sc-hb-rv", "hbrv")
        async with db_module.SessionLocal() as s:
            await s.execute(sa.update(InboundCredential).values(
                revoked_at=datetime.now(timezone.utc)))
            await s.commit()
        _stub_run_ok(monkeypatch, "sc-hb-rv")
        await ir.run_instance(iid)
        inst = await _row(iid)
        assert inst.state == "idle" and inst.run_status == "ok"
