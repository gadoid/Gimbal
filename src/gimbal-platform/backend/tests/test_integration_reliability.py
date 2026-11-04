"""S3 + S2 修复(修复方案 2026-11-01 §6/§7):执行与投递可靠性。

S3:租约回收逐行独立会话 —— 单行异常/回滚不波及同批;
S2:投递三段式 —— 短事务领取(投递租约)+ 令牌分组并发发送 + 逐行
回写;慢接收端不队头阻塞,同令牌组内按 id 串行(v4 领取键 token_id)。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core import db as db_module
from app.models.integration_task import IntegrationTask
from app.models.webhook_delivery import WebhookDelivery
from app.services import integration_runner as ir
from app.services import webhook_outbox as wo

from .inbound_fixtures import (
    mk_pending, mk_task_pair as _mk_pair, mk_token,
    seed_alias as _seed_alias, seed_platform_user as _seed_platform_user,
)


class TestS3RecoverStuck:
    async def test_second_row_survives_first_row_failure(
            self, client, monkeypatch):
        """同批两行:第一行收口中途抛异常(模拟 rollback)→ 第二行照常
        回收。旧实现共用会话时第一行的异常/回滚会波及第二行。"""
        await _seed_platform_user()
        await _seed_alias()
        old = datetime.now(timezone.utc) - timedelta(
            seconds=ir.RUN_LEASE_SECONDS + 60)
        ids = []
        for name in ("s3-a", "s3-b"):
            tpl_id, inst_id, _owner = await _mk_pair(name=name)
            async with db_module.SessionLocal() as s:
                inst = await s.get(IntegrationTask, inst_id)
                inst.running_since = old
                await s.commit()
            ids.append(inst_id)
        calls = {"n": 0}
        orig = ir._finish

        async def _flaky(db, inst, tpl, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("db blip")
            return await orig(db, inst, tpl, *a, **kw)

        monkeypatch.setattr(ir, "_finish", _flaky)
        async with db_module.SessionLocal() as db:
            n = await ir._recover_stuck(db)
        assert n == 1                     # 只有第二行成功
        async with db_module.SessionLocal() as s:
            first = await s.get(IntegrationTask, ids[0])
            second = await s.get(IntegrationTask, ids[1])
            assert first.state == "running"   # 第一行保持原状(独立事务)
            assert second.state == "idle"     # 第二行照常回收
            assert second.run_status == "timeout"

    async def test_template_removed_row_commits_independently(self, client):
        await _seed_platform_user()
        old = datetime.now(timezone.utc) - timedelta(
            seconds=ir.RUN_LEASE_SECONDS + 60)
        tpl_id, inst_id, _owner = await _mk_pair(name="s3-c")
        async with db_module.SessionLocal() as s:
            tpl = await s.get(IntegrationTask, tpl_id)
            tpl.removed_at = datetime.now(timezone.utc)
            inst = await s.get(IntegrationTask, inst_id)
            inst.running_since = old
            await s.commit()
        async with db_module.SessionLocal() as db:
            n = await ir._recover_stuck(db)
        assert n == 1
        async with db_module.SessionLocal() as s:
            inst = await s.get(IntegrationTask, inst_id)
            assert inst.state == "idle"
            assert inst.run_status == "timeout"


# ── S2:投递三段式 ────────────────────────────────────────────────


class _Resp:
    def __init__(self, code):
        self.status_code = code


class _SlowClient:
    """按 URL 延迟的替身:slow 主机挂起,快主机即时返回。"""

    events: "list[tuple[str, float]]" = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, *, content=None, headers=None):
        import time as _t
        if "slow" in url:
            await asyncio.sleep(2.0)
        _SlowClient.events.append((url, _t.monotonic()))
        return _Resp(200)


class TestS2DeliveryLoop:
    async def test_slow_alias_does_not_block_others(
            self, client, monkeypatch):
        """令牌 A 的接收端挂起 2s,令牌 B 的投递不受阻(并发)。"""
        from app.services import access_token as at_mod
        monkeypatch.setattr(at_mod, "host_is_private", lambda h: False)
        slow_tid, _ = await mk_token(kind="platform", name="slow",
                                      callback_url="https://slow.example/cb",
                                      callback_secret="s")
        fast_tid, _ = await mk_token(kind="platform", name="fast",
                                      callback_url="https://fast.example/cb",
                                      callback_secret="s")
        await mk_pending(token_id=slow_tid,
                          url="https://slow.example/cb")
        await mk_pending(token_id=fast_tid,
                          url="https://fast.example/cb")
        _SlowClient.events.clear()
        monkeypatch.setattr(wo.httpx, "AsyncClient", _SlowClient)
        t0 = asyncio.get_event_loop().time()
        n = await wo.delivery_once()
        assert n == 2
        fast_done = [t for u, t in _SlowClient.events if "fast" in u][0]
        assert fast_done - t0 < 1.5       # 未被慢组拖住

    async def test_same_alias_serial_by_id(self, client, monkeypatch):
        """同一令牌的两行按 id 顺序发送。"""
        from app.services import access_token as at_mod
        monkeypatch.setattr(at_mod, "host_is_private", lambda h: False)
        tid, _ = await mk_token(kind="platform", name="serial",
                                callback_url="https://cb.example.local/1",
                                callback_secret="s")
        first = await mk_pending(token_id=tid,
                                  url="https://cb.example.local/1")
        second = await mk_pending(token_id=tid,
                                   url="https://cb.example.local/2")
        _SlowClient.events.clear()
        monkeypatch.setattr(wo.httpx, "AsyncClient", _SlowClient)
        await wo.delivery_once()
        urls = [u for u, _ in _SlowClient.events]
        assert urls == ["https://cb.example.local/1",
                        "https://cb.example.local/2"]
        assert first < second

    async def test_delivery_lease_reclaim_after_crash(
            self, client, monkeypatch):
        """发送中进程退出(不回写)→ 投递租约到期后被重新领取。"""
        tok_tid, _ = await mk_token(kind="platform", name="lease")
        row_id = await mk_pending(token_id=tok_tid)
        # 只领取、发送阶段整体失败(模拟崩溃:进程在 writeback 前退出)
        jobs = await wo._claim(db_module.SessionLocal)
        assert len(jobs) == 1
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            assert row.status == "pending"       # 仍是 pending
            assert row.attempts == 0             # 未计数
            lease_until = row.next_retry_at
            assert lease_until is not None
        # 租约内不重领
        assert await wo._claim(db_module.SessionLocal) == []
        # 租约到期 → 重新领取
        async with db_module.SessionLocal() as s:
            row = await s.get(WebhookDelivery, row_id)
            row.next_retry_at = datetime.now(timezone.utc) - timedelta(
                seconds=1)
            await s.commit()
        assert len(await wo._claim(db_module.SessionLocal)) == 1

    async def test_concurrent_claim_sends_once(self, client, monkeypatch):
        from app.services import access_token as at_mod
        monkeypatch.setattr(at_mod, "host_is_private", lambda h: False)
        once_tid, _ = await mk_token(kind="platform", name="once",
                                      callback_secret="s")
        await mk_pending(token_id=once_tid)
        calls = {"n": 0}

        class _Count:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, *, content=None, headers=None):
                calls["n"] += 1
                return _Resp(200)

        monkeypatch.setattr(wo.httpx, "AsyncClient", _Count)
        await asyncio.gather(wo.delivery_once(), wo.delivery_once())
        assert calls["n"] == 1
