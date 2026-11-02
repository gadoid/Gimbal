"""回调 P2(webhook 设计 v3 §5):outbox 同事务写行、投递循环(签名/
退避/上限)、单 case outputs、通知跳过系统用户、保留期与排查端点。

测试矩阵(设计 §9):

* outbox:终态回滚则无投递行;JWT 发起的执行无投递行;迟到的集成
  结果无投递行;canceled 经 transition_execution 真实迁移 → 发
  status=canceled(D11);
* 投递:HMAC 对拍;重试 body 字节与 deliveryId 不变;2xx 成功;非
  2xx 退避;上限置 failed;不跟随重定向;并发领取同一行只发一次;
* outputs:单 case 有 outputs 且已脱敏;多行为 null;
* D12:仅注册方实例回调,订阅者实例不回。
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac as hmac_mod
import json
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.core.security import fernet_encrypt, hash_password
from app.models import Execution, Notification, User
from app.models.integration_task import IntegrationTask
from app.models.service_alias import ServiceAlias
from app.models.webhook_delivery import WebhookDelivery
from app.services import integration_runner as ir
from app.services import run_dispatcher as rd
from app.services import webhook_outbox as wo
from app.services.run_dispatcher import STATUS_CANCELED, STATUS_DONE

# ── 种子助手 ─────────────────────────────────────────────────────


async def _seed_platform_user() -> int:
    async with db_module.SessionLocal() as db:
        uid = (await db.execute(
            sa.select(User.id).where(User.is_system == True)  # noqa: E712
        )).scalar()
        if uid is None:
            u = User(username="__platform__", display_name="平台系统",
                     password_hash=hash_password("x"), is_system=True)
            db.add(u)
            await db.commit()
            uid = u.id
    return uid


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


async def _mk_execution(*, caller="agent-sys", grant_id=None,
                        status="running", total=1, owner_id=None,
                        config_json=None, **over) -> int:
    async with db_module.SessionLocal() as s:
        if owner_id is None:
            owner_id = await _seed_platform_user()
        cfg = config_json if config_json is not None else {}
        ex = Execution(scenario_id="sc-w", scenario_name="W",
                       owner_id=owner_id, owner_name="o", status=status,
                       total_runs=total,
                       passed=total if status == STATUS_DONE else 0,
                       caller_alias_name=caller, grant_id=grant_id,
                       config_json=cfg, **over)
        s.add(ex)
        await s.commit()
        return ex.id


async def _mk_task_pair(*, identity_mode="personal", caller="agent-sys",
                        grant_id=None, holder_id=None) -> tuple[int, int]:
    """(tpl_id, inst_id) 直插;holder 缺省 = 模板 owner(注册方自己)。"""
    async with db_module.SessionLocal() as s:
        owner = (await s.execute(
            sa.select(User.id).where(User.is_system == False)  # noqa: E712
        )).scalar()
        if owner is None:
            u = User(username="w_owner", display_name="o",
                     password_hash=hash_password("x"))
            s.add(u)
            await s.commit()
            owner = u.id
        tpl = IntegrationTask(
            name="w-task", owner_id=owner, identity_mode=identity_mode,
            scenario_id="sc-w", trigger_cron="*/5 * * * *",
            caller_alias_name=caller, grant_id=grant_id)
        s.add(tpl)
        await s.flush()
        inst = IntegrationTask(
            name="w-task", owner_id=owner, template_id=tpl.id,
            holder_id=holder_id if holder_id is not None else owner,
            state="running",
            running_since=datetime.now(timezone.utc),
        )
        s.add(inst)
        await s.commit()
        return tpl.id, inst.id


async def _deliveries() -> "list[WebhookDelivery]":
    async with db_module.SessionLocal() as s:
        return list((await s.execute(
            sa.select(WebhookDelivery).order_by(WebhookDelivery.id))
        ).scalars().all())


# ── outbox 写入点(执行域)───────────────────────────────────────


class TestOutboxExecution:
    async def test_moved_writes_row_and_wakes(self, client, monkeypatch):
        await _seed_alias()
        ex_id = await _mk_execution(
            status="running", total=1, client_ref="agent-task-9",
            callback_path_override="/ov")
        woken = []
        monkeypatch.setattr(wo, "wake", lambda: woken.append(1))
        res = await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        assert res is rd.TransitionResult.MOVED
        rows = await _deliveries()
        assert len(rows) == 1
        r = rows[0]
        assert r.event_type == "execution.finished"
        assert r.url == "https://cb.example.local/ov"  # 覆盖路径优先
        assert r.status == "pending"
        body = json.loads(r.body)
        assert body["deliveryId"] == r.id       # 去重键 = 行 id
        assert body["executionId"] == ex_id
        assert body["clientRef"] == "agent-task-9"
        assert body["status"] == "done"
        assert body["identityMode"] == "platform"
        assert body["outputs"] is None          # 无 outputs 面
        assert woken == [1]

    async def test_grant_execution_identity_personal(self, client):
        await _seed_alias()
        ex_id = await _mk_execution(status="running", grant_id=555)
        await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        body = json.loads((await _deliveries())[0].body)
        assert body["identityMode"] == "personal"

    async def test_jwt_execution_no_row(self, client):
        await _seed_alias()
        ex_id = await _mk_execution(caller=None)
        await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        assert await _deliveries() == []

    async def test_canceled_path_writes_row(self, client):
        """D11:取消路径经 transition_execution 真实迁移 → 也发回调。"""
        await _seed_alias()
        ex_id = await _mk_execution(status="running")
        await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_CANCELED)
        rows = await _deliveries()
        assert len(rows) == 1
        assert json.loads(rows[0].body)["status"] == "canceled"

    async def test_already_terminal_no_row(self, client):
        await _seed_alias()
        ex_id = await _mk_execution(status=STATUS_DONE)
        res = await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_CANCELED)
        assert res is rd.TransitionResult.ALREADY_TERMINAL
        assert await _deliveries() == []

    async def test_outbox_failure_rolls_back_terminal(self, client,
                                                      monkeypatch):
        """同事务语义:写行失败 → 终态也不落库(两者都不出现)。"""
        await _seed_alias()
        ex_id = await _mk_execution(status="running")

        async def _boom(db, ex):
            raise RuntimeError("outbox down")

        monkeypatch.setattr(
            "app.services.webhook_outbox.enqueue_execution_finished", _boom)
        res = await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        assert res is rd.TransitionResult.FAILED
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, ex_id)
            assert ex.status == "running"     # 终态未落
        assert await _deliveries() == []

    async def test_callback_disabled_no_row(self, client):
        await _seed_alias("agent-off", callback_enabled=False)
        ex_id = await _mk_execution(caller="agent-off")
        await rd.transition_execution(
            db_module.SessionLocal, ex_id, STATUS_DONE)
        assert await _deliveries() == []


# ── outbox 写入点(集成域)───────────────────────────────────────


class TestOutboxIntegration:
    async def test_finish_registrant_writes_run_finished(self, client):
        await _seed_alias()
        tpl_id, inst_id = await _mk_task_pair()
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, inst_id)
            res = await ir._finish(
                db, inst, tpl, "ok", "", check_status="pass",
                outputs={"status": "SETTLED"}, duration_ms=2310,
                lease=inst.running_since)
            assert res["status"] == "passed"
        rows = await _deliveries()
        assert len(rows) == 1
        body = json.loads(rows[0].body)
        assert body["event"] == "integration.run_finished"
        assert body["taskId"] == tpl_id
        assert body["instanceId"] == inst_id
        assert body["runStatus"] == "ok"
        assert body["checkStatus"] == "pass"
        assert body["outputs"] == {"status": "SETTLED"}
        assert body["durationMs"] == 2310

    async def test_finish_pause_branch_writes_paused(self, client):
        await _seed_alias()
        tpl_id, inst_id = await _mk_task_pair()
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, inst_id)
            await ir._finish(
                db, inst, tpl, "auth", "认证失败",
                pause_reason="auth_failed",
                lease=inst.running_since)
        rows = await _deliveries()
        assert len(rows) == 1
        body = json.loads(rows[0].body)
        assert body["event"] == "integration.paused"
        assert body["reason"] == "auth_failed"

    async def test_subscriber_instance_never_callbacks(self, client):
        """D12:订阅者实例(holder ≠ owner)不写投递行。"""
        await _seed_alias()
        tpl_id, inst_id = await _mk_task_pair()
        # 订阅人(holder ≠ 模板 owner):另建实例挂同一模板
        async with db_module.SessionLocal() as s:
            other = User(username="w_sub", display_name="s",
                         password_hash=hash_password("x"))
            s.add(other)
            await s.commit()
            sub_id = other.id
            sub = IntegrationTask(
                name="w-task", owner_id=other.id, template_id=tpl_id,
                holder_id=sub_id, state="running",
                running_since=datetime.now(timezone.utc))
            s.add(sub)
            await s.commit()
            sub_inst_id = sub.id
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, sub_inst_id)
            await ir._finish(
                db, inst, tpl, "ok", "", check_status="pass",
                lease=inst.running_since)
        assert await _deliveries() == []

    async def test_late_result_no_row(self, client):
        """迟到结果(租约不匹配)丢弃 → 无投递行(P0-3.1 + §5.1)。"""
        await _seed_alias()
        tpl_id, inst_id = await _mk_task_pair()
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, inst_id)
            await ir._finish(
                db, inst, tpl, "ok", "", check_status="pass",
                lease=datetime.now(timezone.utc)
                + timedelta(seconds=999))      # 不匹配的旧租约
        assert await _deliveries() == []

    async def test_consent_pause_writes_paused(self, client):
        await _seed_alias()
        tpl_id, inst_id = await _mk_task_pair()
        async with db_module.SessionLocal() as db:
            tpl = await db.get(IntegrationTask, tpl_id)
            inst = await db.get(IntegrationTask, inst_id)
            await ir._pause_consent_changed(
                db, inst, tpl, paused_reason="template_changed",
                message="模板内容已变更", lease=inst.running_since)
        rows = await _deliveries()
        assert len(rows) == 1
        body = json.loads(rows[0].body)
        assert body["event"] == "integration.paused"
        assert body["reason"] == "template_changed"


# ── 投递循环 ─────────────────────────────────────────────────────


class _Resp:
    def __init__(self, code):
        self.status_code = code


class _FakeClient:
    """httpx.AsyncClient 替身:记录调用,返回可编程状态码。"""

    calls: "list[dict]" = []
    next_code: "list[int]" = [200]
    last_kwargs: dict = {}

    def __init__(self, *a, **kw):
        _FakeClient.last_kwargs = kw

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, *, content=None, headers=None):
        _FakeClient.calls.append({
            "url": url, "content": content, "headers": dict(headers or {})})
        return _Resp(_FakeClient.next_code.pop(0))


async def _mk_pending(**over) -> int:
    row = WebhookDelivery(
        alias_name=over.get("alias_name", "agent-sys"),
        event_type=over.get("event_type", "execution.finished"),
        url=over.get("url", "https://cb.example.local/gimbal/callback"),
        body=over.get("body", '{"event":"execution.finished"}'),
        status="pending", attempts=over.get("attempts", 0))
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()
        return row.id


class TestDeliveryLoop:
    async def test_hmac_verify_and_headers(self, client, monkeypatch):
        """HMAC 对拍(§5.3):t/v1 与 hashlib 独立计算一致;头齐备。"""
        await _seed_alias()
        await _mk_pending()
        _FakeClient.calls.clear()
        monkeypatch.setattr(wo.httpx, "AsyncClient", _FakeClient)
        n = await wo.delivery_once()
        assert n == 1
        assert len(_FakeClient.calls) == 1
        call = _FakeClient.calls[0]
        h = call["headers"]
        assert h["X-Gimbal-Event"] == "execution.finished"
        assert h["X-Gimbal-Delivery"].isdigit()
        ts = int(h["X-Gimbal-Timestamp"])
        body = call["content"].decode("utf-8")
        sig = h["X-Gimbal-Signature"]
        expect = "t={},v1={}".format(ts, hmac_mod.new(
            b"cb-secret-1", f"{ts}.{body}".encode(),
            hashlib.sha256).hexdigest())
        assert sig == expect
        # 不跟随重定向(§5.2)
        assert _FakeClient.last_kwargs.get("follow_redirects") is False

    async def test_retry_same_bytes_same_delivery(self, client,
                                                  monkeypatch):
        await _seed_alias()
        row_id = await _mk_pending()
        _FakeClient.calls.clear()
        _FakeClient.next_code = [500, 200]
        monkeypatch.setattr(wo.httpx, "AsyncClient", _FakeClient)
        await wo.delivery_once()
        # 非 2xx → 退避,attempts=1
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            assert row.status == "pending"
            assert row.attempts == 1
            assert row.last_error == "HTTP 500"
            assert row.next_retry_at is not None
        # 未到退避时间 → 不再领
        assert await wo.delivery_once() == 0
        # 时间拨到到期 → 重试成功;body 字节与 deliveryId 不变
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            row.next_retry_at = (datetime.now(timezone.utc)
                                 - timedelta(seconds=1))
            await s.commit()
        await wo.delivery_once()
        assert len(_FakeClient.calls) == 2
        assert _FakeClient.calls[0]["content"] == \
            _FakeClient.calls[1]["content"]
        assert _FakeClient.calls[0]["headers"]["X-Gimbal-Delivery"] == \
            _FakeClient.calls[1]["headers"]["X-Gimbal-Delivery"]
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            assert row.status == "delivered"
            assert row.delivered_at is not None

    async def test_attempts_exhausted_marks_failed(self, client,
                                                   monkeypatch):
        await _seed_alias()
        from app.core.config import settings
        row_id = await _mk_pending(attempts=settings.WEBHOOK_MAX_ATTEMPTS
                                   - 1)
        _FakeClient.calls.clear()
        _FakeClient.next_code = [500]
        monkeypatch.setattr(wo.httpx, "AsyncClient", _FakeClient)
        await wo.delivery_once()
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            assert row.status == "failed"
            assert row.next_retry_at is None

    async def test_bad_scheme_immediate_fail(self, client):
        await _seed_alias()
        row_id = await _mk_pending(url="ftp://cb.example.local/x")
        await wo.delivery_once()
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            # 首次失败即退避;上限内不会 failed(除非 attempts 已满)
            assert row.status == "pending"
            assert "bad url" in (row.last_error or "")

    async def test_concurrent_claim_sends_once(self, client, monkeypatch):
        await _seed_alias()
        await _mk_pending()
        _FakeClient.calls.clear()
        _FakeClient.next_code = [200, 200]
        monkeypatch.setattr(wo.httpx, "AsyncClient", _FakeClient)
        await asyncio.gather(wo.delivery_once(), wo.delivery_once())
        assert len(_FakeClient.calls) == 1   # SKIP LOCKED:同一行只发一次


class TestBackoff:
    def test_sequence_from_settings(self):
        # 默认 30,120,480,1800;尝试次数封顶到尾
        assert wo.backoff_seconds(1) == 30
        assert wo.backoff_seconds(2) == 120
        assert wo.backoff_seconds(3) == 480
        assert wo.backoff_seconds(4) == 1800
        assert wo.backoff_seconds(9) == 1800


# ── 单 case outputs(D10)─────────────────────────────────────────


class TestSingleCaseOutputs:
    async def test_outputs_written_and_scrubbed(self, client):
        from app.services.run_dispatcher import _store_single_case_outputs
        ex_id = await _mk_execution(
            status="running", total=1, config_json={"runId": "r1"})
        await _store_single_case_outputs(db_module.SessionLocal, ex_id, {
            "status": "SETTLED", "nextToken": "NT-1",
            "auth_token": "should-be-redacted"})
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, ex_id)
            out = ex.config_json["outputs"]
            assert out["status"] == "SETTLED"
            assert out["nextToken"] == "NT-1"   # 游标键豁免
            assert out["auth_token"] == "***"   # 脱敏

    async def test_single_case_payload_carries_outputs(self, client):
        """total_runs=1 且有 outputs → 回调 payload 携带;多行 → null。"""
        await _seed_alias()
        ex1 = await _mk_execution(
            status="running", total=1,
            config_json={"outputs": {"status": "OK"}})
        await rd.transition_execution(db_module.SessionLocal, ex1,
                                      STATUS_DONE)
        ex2 = await _mk_execution(
            status="running", total=3, config_json={})
        await rd.transition_execution(db_module.SessionLocal, ex2,
                                      STATUS_DONE)
        rows = await _deliveries()
        bodies = {json.loads(r.body)["executionId"]: json.loads(r.body)
                  for r in rows}
        assert bodies[ex1]["outputs"] == {"status": "OK"}
        assert bodies[ex2]["outputs"] is None


# ── 通知跳过系统用户(§5.6/D8)────────────────────────────────────


class TestNotifySkipsSystemUser:
    async def test_no_notification_for_platform_owner(self, client):
        await _seed_alias()
        sys_uid = await _seed_platform_user()
        ex_id = await _mk_execution(
            status="running", owner_id=sys_uid)
        await rd.transition_execution(db_module.SessionLocal, ex_id,
                                      STATUS_DONE)
        async with db_module.SessionLocal() as s:
            n = (await s.execute(sa.select(sa.func.count()).select_from(
                Notification))).scalar_one()
        assert n == 0

    async def test_real_user_still_notified(self, client):
        async with db_module.SessionLocal() as s:
            u = User(username="w_human", display_name="h",
                     password_hash=hash_password("x"))
            s.add(u)
            await s.commit()
            uid = u.id
        ex_id = await _mk_execution(status="running", owner_id=uid,
                                    caller=None)
        await rd.transition_execution(db_module.SessionLocal, ex_id,
                                      STATUS_DONE)
        async with db_module.SessionLocal() as s:
            n = (await s.execute(sa.select(sa.func.count()).select_from(
                Notification))).scalar_one()
        assert n == 1


# ── 保留期(§5.2)与排查端点(P2-6)───────────────────────────────


async def _client_login(client: AsyncClient, username: str) -> dict:
    await client.post("/api/auth/register", json={
        "username": username, "password": "pw123456",
        "display_name": username})
    r = await client.post("/api/auth/login", json={
        "username": username, "password": "pw123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestRetentionAndEndpoint:
    async def test_cleanup_retention_windows(self, client):
        from app.core.config import settings
        async with db_module.SessionLocal() as s:
            old_ok = WebhookDelivery(
                alias_name="agent-sys", event_type="e", url="https://x/y",
                body="{}", status="delivered",
                created_at=datetime.now(timezone.utc) - timedelta(
                    days=settings.WEBHOOK_RETENTION_DELIVERED_DAYS + 5))
            fresh_ok = WebhookDelivery(
                alias_name="agent-sys", event_type="e", url="https://x/y",
                body="{}", status="delivered",
                created_at=datetime.now(timezone.utc) - timedelta(days=1))
            old_fail = WebhookDelivery(
                alias_name="agent-sys", event_type="e", url="https://x/y",
                body="{}", status="failed",
                created_at=datetime.now(timezone.utc) - timedelta(
                    days=settings.WEBHOOK_RETENTION_FAILED_DAYS + 5))
            fresh_fail = WebhookDelivery(
                alias_name="agent-sys", event_type="e", url="https://x/y",
                body="{}", status="failed",
                created_at=datetime.now(timezone.utc) - timedelta(days=1))
            s.add_all([old_ok, fresh_ok, old_fail, fresh_fail])
            await s.commit()
        d, f = await wo.cleanup_retention(db_module.SessionLocal)
        assert (d, f) == (1, 1)
        async with db_module.SessionLocal() as s:
            assert (await s.execute(
                sa.select(sa.func.count()).select_from(
                    WebhookDelivery))).scalar_one() == 2

    async def test_deliveries_endpoint_visibility(self, client):
        await _seed_alias()
        h = await _client_login(client, "w_owner9")
        ex_id = await _mk_execution(status=STATUS_DONE)
        # 直接手写一行投递(端点只读;写行语义已由 outbox 族覆盖)
        async with db_module.SessionLocal() as s:
            s.add(WebhookDelivery(
                alias_name="agent-sys", event_type="execution.finished",
                execution_id=ex_id,
                url="https://cb.example.local/gimbal/callback",
                body="{}", status="delivered", attempts=1))
            await s.commit()
        # 别名属主(agent-sys 归 w_owner9)按 executionId 可查
        async with db_module.SessionLocal() as s:
            alias = await s.get(ServiceAlias, "agent-sys")
            alias.owner_user_id = (await s.execute(
                sa.select(User.id).where(
                    User.username == "w_owner9"))).scalar_one()
            await s.commit()
        r = await client.get(
            f"/api/webhook-deliveries?executionId={ex_id}", headers=h)
        assert r.status_code == 200, r.text
        assert len(r.json()["items"]) == 1
        assert r.json()["items"][0]["eventType"] == "execution.finished"
        # 陌生人 → 404
        h2 = await _client_login(client, "w_stranger9")
        r = await client.get(
            f"/api/webhook-deliveries?executionId={ex_id}", headers=h2)
        assert r.status_code == 404
        # 无过滤参数 → 422
        r = await client.get("/api/webhook-deliveries", headers=h)
        assert r.status_code == 422


class TestRedeliver:
    """人工补发(收尾评审 2026-11-02 G5):新建一行 pending、原行留历史;
    body 的 deliveryId 跟着换成新 id(按 body 去重的接收端也能收到)并附
    redeliveredFrom;别名属主 / admin 可点,入站凭证与陌生人 404;pending
    行 409。"""

    @staticmethod
    async def _failed_row(**over) -> int:
        async with db_module.SessionLocal() as s:
            row = WebhookDelivery(
                alias_name="agent-sys", event_type="execution.finished",
                execution_id=over.get("execution_id"),
                url="https://cb.example.local/gimbal/callback",
                body=json.dumps({"event": "execution.finished",
                                 "deliveryId": 0, "executionId": 7}),
                status=over.get("status", "failed"), attempts=5,
                last_error="HTTP 503")
            s.add(row)
            await s.commit()
            return row.id

    async def test_alias_owner_redelivers_as_new_row(self, client):
        await _seed_platform_user()          # 先于注册:避免首个注册者成 admin
        await _seed_alias()
        h = await _client_login(client, "rd_owner")
        async with db_module.SessionLocal() as s:
            alias = await s.get(ServiceAlias, "agent-sys")
            alias.owner_user_id = (await s.execute(
                sa.select(User.id).where(
                    User.username == "rd_owner"))).scalar_one()
            await s.commit()
        old_id = await self._failed_row()
        r = await client.post(f"/api/webhook-deliveries/{old_id}/redeliver",
                              headers=h)
        assert r.status_code == 201, r.text
        out = r.json()
        assert out["redeliveredFrom"] == old_id
        assert out["id"] != old_id
        assert out["status"] == "pending" and out["attempts"] == 0
        assert out["url"].endswith("/gimbal/callback")
        async with db_module.SessionLocal() as s:
            old = await s.get(WebhookDelivery, old_id)
            new = await s.get(WebhookDelivery, out["id"])
            assert (old.status, old.attempts, old.last_error) == ("failed", 5, "HTTP 503")
            assert new.alias_name == old.alias_name
            assert new.next_retry_at is None and new.last_error is None
            # body 跟着换 id:deliveryId = 新行 id、附 redeliveredFrom,其余字段不变;
            # 原行 body 不动
            new_body, old_body = json.loads(new.body), json.loads(old.body)
            assert new_body["deliveryId"] == out["id"]
            assert new_body["redeliveredFrom"] == old_id
            assert {k: v for k, v in new_body.items()
                    if k not in ("deliveryId", "redeliveredFrom")} == {
                "event": "execution.finished", "executionId": 7}
            assert old_body["deliveryId"] == 0
            # 全量评估 2026-11-02 #8:人工补发入审计(resource = 别名)
            from app.models.permission import AuditLog
            logs = (await s.execute(sa.select(AuditLog).where(
                AuditLog.action == "webhook.redeliver"))).scalars().all()
            assert len(logs) == 1
            assert logs[0].resource_id == "agent-sys"
            assert logs[0].detail["delivery"] == old_id
            assert logs[0].detail["new_delivery"] == out["id"]
        # 新行可被投递循环领取(领取后推进租约、仍 pending)
        jobs = await wo._claim(db_module.SessionLocal)
        assert [j.id for j in jobs] == [out["id"]]
        # pending 行再补发 → 409
        r = await client.post(f"/api/webhook-deliveries/{out['id']}/redeliver",
                              headers=h)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "already_pending"

    async def test_visibility_and_admin(self, client):
        from app.models.inbound_identity import InboundCredential
        from app.services.inbound_identity import (
            generate_credential_token, sha256_hex)

        await _seed_platform_user()
        await _seed_alias()
        admin = await _client_login(client, "rd_admin")
        async with db_module.SessionLocal() as s:
            u = (await s.execute(sa.select(User).where(
                User.username == "rd_admin"))).scalar_one()
            u.role = "admin"
            tok = generate_credential_token()
            s.add(InboundCredential(alias_name="agent-sys", name="t",
                                    token_hash=sha256_hex(tok)))
            await s.commit()
        stranger = await _client_login(client, "rd_stranger")
        row_id = await self._failed_row(status="delivered")
        r = await client.post(f"/api/webhook-deliveries/{row_id}/redeliver",
                              headers=stranger)
        assert r.status_code == 404
        r = await client.post(f"/api/webhook-deliveries/{row_id}/redeliver",
                              headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 404           # 入站凭证不开放补发
        r = await client.post("/api/webhook-deliveries/999999/redeliver",
                              headers=admin)
        assert r.status_code == 404
        r = await client.post(f"/api/webhook-deliveries/{row_id}/redeliver",
                              headers=admin)
        assert r.status_code == 201, r.text    # admin 可补发已投递行

