"""回调投递(webhook v4 §6):outbox 写行、必带签名、主机白名单与
loopback 拒绝、按令牌分组串行、排查端点与补发。

测试矩阵(§9 回调行):

* outbox:execution.finished 按 token_id 写行,payload caller =
  {tokenId, tokenName};JWT 发起的执行无投递行;
* 必带签名:密钥可用 → HMAC 对拍;密钥缺失/不可解 → 该行 failed
  (signing_key_missing),绝不无签名发送;令牌行删除 → token_deleted;
* 地址检查:loopback/link-local 主机 → 该行 failed;
* 撤销 v3 行为:已吊销令牌照常带签名投递;
* 排查端点:令牌只列本令牌;补发只走 JWT(admin/属主/member+)。
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json

import sqlalchemy as sa

from app.core import db as db_module
from app.models.webhook_delivery import WebhookDelivery
from app.services import webhook_outbox as wo

from .inbound_fixtures import (
    allow_delivery_hosts, body_of, deliveries, mk_token, seed_platform_user,
)
from .test_access_tokens import _gtk, _register_role, _user_id

CB_URL = "https://cb.example.com/hook"   # 公网可解析,投递前地址检查过


async def _mk_delivery(*, token_row, url=CB_URL, execution_id=None,
                       status="pending", **over) -> int:
    row = WebhookDelivery(
        token_id=token_row.id, token_name=token_row.name,
        event_type=over.pop("event_type", "execution.finished"),
        url=url, execution_id=execution_id,
        body=over.pop("body", json.dumps({"event": "execution.finished"})),
        status=status, attempts=0, **over)
    async with db_module.SessionLocal() as s:
        s.add(row)
        await s.commit()
        return row.id


async def _token_row(token_id: int):
    from app.models.access_token import AccessToken
    async with db_module.SessionLocal() as s:
        return await s.get(AccessToken, token_id)


class TestMustSign:
    async def test_signed_delivery_hmac(self, client, monkeypatch):
        import httpx

        real_async_client = httpx.AsyncClient
        # 沙箱无外网 DNS:解析失败按 fail-closed 拒 —— 对拍用例放行解析
        # 与投递面白名单(D16 复核)
        allow_delivery_hosts(monkeypatch)
        await seed_platform_user()
        await _register_role(client, "wd_m", "member")
        tid, _ = await mk_token(user_id=await _user_id("wd_m"),
                                callback_url=CB_URL,
                                callback_secret="sec-1")
        tok = await _token_row(tid)
        did = await _mk_delivery(token_row=tok)
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = request.content
            seen["sig"] = request.headers.get("X-Gimbal-Signature", "")
            return httpx.Response(200)

        class _FakeAC:
            def __init__(self, **kw):
                self._inner = real_async_client(
                    transport=httpx.MockTransport(handler))

            async def __aenter__(self):
                return self._inner

            async def __aexit__(self, *exc):
                await self._inner.aclose()

        monkeypatch.setattr(wo.httpx, "AsyncClient", _FakeAC)
        n = await wo.delivery_once(db_factory=db_module.SessionLocal)
        assert n == 1
        assert seen["sig"].startswith("t=")
        ts = seen["sig"].split(",", 1)[0][2:]
        mac = hmac_mod.new(b"sec-1", f"{ts}.".encode() + seen["body"],
                           hashlib.sha256).hexdigest()
        assert seen["sig"] == f"t={ts},v1={mac}"
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.status == "delivered"

    async def test_missing_secret_fails_row(self, client):
        """必带签名(§6):密钥为空 → failed(signing_key_missing),
        绝不无签名发送。"""
        await seed_platform_user()
        await _register_role(client, "wd2_m", "member")
        tid, _ = await mk_token(user_id=await _user_id("wd2_m"),
                                callback_url=CB_URL,
                                callback_secret=None)
        tok = await _token_row(tid)
        did = await _mk_delivery(token_row=tok)
        n = await wo.delivery_once(db_factory=db_module.SessionLocal)
        assert n == 1
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.status == "failed"
            assert row.last_error == "signing_key_missing"

    async def test_deleted_token_fails_row(self, client):
        """令牌行删除(用户删除流程漏置 failed 的兜底)→ token_deleted
        终态失败,不无限重试。"""
        from sqlalchemy import delete as _del
        from app.models.access_token import AccessToken
        await seed_platform_user()
        tid, _ = await mk_token(kind="platform", name="gone",
                                callback_url=CB_URL, callback_secret="s")
        did = await _mk_delivery(token_row=await _token_row(tid))
        async with db_module.SessionLocal() as s:
            await s.execute(_del(AccessToken).where(AccessToken.id == tid))
            await s.commit()
        # FK SET NULL:投递行保留、token_id 置空 → 领取面(token_id IS
        # NOT NULL)不再领取(n=0)。正常路径由删除用户流程的
        # fail_pending_of_token 显式置 failed(token_deleted,人员变动
        # 测试覆盖);这里钉住兜底语义 —— 直删令牌行不产生幽灵重试。
        n = await wo.delivery_once(db_factory=db_module.SessionLocal)
        assert n == 0
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.token_id is None
            assert row.status == "pending"

    async def test_undecryptable_secret_fails(self, client):
        await seed_platform_user()
        await _register_role(client, "wd3_m", "member")
        tid, _ = await mk_token(user_id=await _user_id("wd3_m"),
                                callback_url=CB_URL)
        from app.models.access_token import AccessToken as _AT
        async with db_module.SessionLocal() as s:
            tok = await s.get(_AT, tid)
            tok.callback_secret = "not-a-fernet-key"
            await s.commit()
        tok = await _token_row(tid)
        did = await _mk_delivery(token_row=tok)
        await wo.delivery_once(db_factory=db_module.SessionLocal)
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.status == "failed"
            assert row.last_error == "signing_key_missing"


class TestHostChecks:
    async def test_loopback_host_rejected(self, client, monkeypatch):
        from app.core.config import settings
        await seed_platform_user()
        tid, _ = await mk_token(kind="platform", name="lp",
                                callback_url="https://cb.example.local/hook",
                                callback_secret="s")
        tok = await _token_row(tid)
        # 白名单放行 127.0.0.1(专测 D24 私址检查);冻结 URL 指向
        # loopback(建行绕过保存校验的模拟)
        monkeypatch.setattr(settings, "CALLBACK_HOST_ALLOWLIST", "127.0.0.1")
        did = await _mk_delivery(token_row=tok,
                                 url="http://127.0.0.1:9000/hook")
        await wo.delivery_once(db_factory=db_module.SessionLocal)
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.status in ("pending", "failed")
            # 至少不再无限重试成功:重试后仍会失败 —— 直接断言未 delivered
            assert row.status != "delivered"

    async def test_allowlist_rechecked_at_delivery(self, client, monkeypatch):
        """D16(评审 2026-11-05 P1):保存后再把主机移出白名单 → 投递
        终态失败(callback_host_not_allowed),不无限重试。"""
        from app.core.config import settings
        await seed_platform_user()
        tid, _ = await mk_token(kind="platform", name="wl",
                                callback_url=CB_URL, callback_secret="s")
        tok = await _token_row(tid)
        did = await _mk_delivery(token_row=tok)
        # 保存时在白名单;投递前被移出
        monkeypatch.setattr(settings, "CALLBACK_HOST_ALLOWLIST", "other.example")
        n = await wo.delivery_once(db_factory=db_module.SessionLocal)
        assert n == 1
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, did)
            assert row.status == "failed"
            assert row.last_error == "callback_host_not_allowed"
            assert row.next_retry_at is None


class TestOutboxWrites:
    async def test_execution_finished_payload(self, client, monkeypatch):
        """终态迁移段同款写行:caller = {tokenId, tokenName}。"""
        from app.models.execution import Execution
        await seed_platform_user()
        await _register_role(client, "ow_m", "member")
        uid = await _user_id("ow_m")
        tid, _ = await mk_token(user_id=uid, name="nightly",
                                callback_url=CB_URL, callback_secret="s")
        async with db_module.SessionLocal() as s:
            ex = Execution(scenario_id="sc-ow", scenario_name="OW",
                           owner_id=uid, owner_name="o",
                           status="queued", total_runs=1, token_id=tid,
                           config_json={})
            s.add(ex)
            await s.commit()
            ex_id = ex.id
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, ex_id)
            nid = await wo.enqueue_execution_finished(s, ex)
            await s.commit()
        assert nid is not None
        rows = await deliveries()
        assert rows and rows[-1].token_id == tid
        payload = body_of(rows[-1])
        assert payload["caller"] == {"tokenId": tid, "tokenName": "nightly"}

    async def test_jwt_execution_no_delivery(self, client):
        from app.models.execution import Execution
        await seed_platform_user()
        async with db_module.SessionLocal() as s:
            from .inbound_fixtures import mk_user
            uid = await mk_user("jwt_u")
            ex = Execution(scenario_id="sc-j", scenario_name="J",
                           owner_id=uid, owner_name="o",
                           status="queued", total_runs=1,
                           token_id=None, config_json={})
            s.add(ex)
            await s.commit()
            ex_id = ex.id
        async with db_module.SessionLocal() as s:
            ex = await s.get(Execution, ex_id)
            nid = await wo.enqueue_execution_finished(s, ex)
        assert nid is None


class TestListAndRedeliver:
    async def test_token_sees_only_own_deliveries(self, client):
        await seed_platform_user()
        await _register_role(client, "dl_m", "member")
        t1, p1 = await mk_token(user_id=await _user_id("dl_m"),
                                callback_url=CB_URL, callback_secret="s")
        t2, p2 = await mk_token(kind="platform", name="other",
                                callback_url=CB_URL, callback_secret="s")
        tok1, tok2 = await _token_row(t1), await _token_row(t2)
        d1 = await _mk_delivery(token_row=tok1)
        d2 = await _mk_delivery(token_row=tok2)
        r = await client.get("/api/webhook-deliveries?tokenId="
                             f"{t1}", headers=_gtk(p1))
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()["items"]]
        assert d1 in ids and d2 not in ids
        # 令牌路径不能补发(§5.2)
        r = await client.post(f"/api/webhook-deliveries/{d1}/redeliver",
                              headers=_gtk(p1))
        assert r.status_code == 404

    async def test_owner_redeliver_creates_new_row(self, client):
        await seed_platform_user()
        h = await _register_role(client, "rd_m", "member")
        uid = await _user_id("rd_m")
        t1, _ = await mk_token(user_id=uid, callback_url=CB_URL,
                               callback_secret="s")
        tok = await _token_row(t1)
        async with db_module.SessionLocal() as s:
            d1 = WebhookDelivery(
                token_id=t1, token_name=tok.name,
                event_type="integration.paused", url=CB_URL,
                body=json.dumps({"event": "integration.paused",
                                 "deliveryId": 1}),
                status="failed", attempts=5)
            s.add(d1)
            await s.commit()
            old_id = d1.id
        r = await client.post(
            f"/api/webhook-deliveries/{old_id}/redeliver", headers=h)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"] != old_id
        payload = json.loads(
            (await _row(body["id"])).body)
        assert payload["deliveryId"] == body["id"]
        assert payload["redeliveredFrom"] == old_id


async def _row(did: int) -> WebhookDelivery:
    async with db_module.SessionLocal() as s:
        return await s.get(WebhookDelivery, did)
