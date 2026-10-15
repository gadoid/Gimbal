"""集成通道池借还语义(整体评审 2026-10-15 #1)。

旧实现按 ``session is None`` 选槽:两槽预热后恒回落 ``slots[0]``,并发
两次挤进同一单 run server(引擎 409),异常分支再把另一次正在用的会话
关掉。本组用例用桩会话(忙时抛 409,模拟引擎单 run 约束)钉住:

1. 预热后并发 N(= 槽数)次:无 409,各槽都被用到;
2. 并发数 > 槽数:超出的等待归还,不挤占忙槽;
3. 一次会话层故障只关闭本槽,另一槽上的执行不受影响;
4. reap_idle 不回收借出中的槽。
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app.services import gimbal_server_session as gss
from app.services import integration_runner as ir


class _FakeSession:
    created = 0

    def __init__(self) -> None:
        _FakeSession.created += 1
        self.id = _FakeSession.created
        self.busy = False
        self.closed = False
        self.ran: list[str] = []
        self.fail_next = False

    async def start(self) -> None:
        return None

    async def run_case(self, case_path):
        if self.closed:
            raise RuntimeError(f"session{self.id}: closed")
        if self.busy:
            raise RuntimeError(f"session{self.id}: 409 one run at a time")
        self.busy = True
        try:
            await asyncio.sleep(0.05)
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError(f"session{self.id}: boom")
            if self.closed:
                raise RuntimeError(f"session{self.id}: killed mid-run")
            self.ran.append(str(case_path))
            return f"ok@{self.id}"
        finally:
            self.busy = False

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_sessions(monkeypatch):
    _FakeSession.created = 0
    monkeypatch.setattr(gss, "ServerSession", _FakeSession)
    return _FakeSession


async def test_warm_slots_concurrent_no_collision(fake_sessions):
    ch = ir.IntegrationChannels(size=2)
    # 预热:两槽都起会话(旧实现此后 session is None 永远找不到)
    assert sorted(await asyncio.gather(ch.run_case("a"), ch.run_case("b"))) \
        == ["ok@1", "ok@2"]
    results = await asyncio.gather(
        ch.run_case("c"), ch.run_case("d"), return_exceptions=True)
    assert all(isinstance(r, str) for r in results), results
    assert sorted(results) == ["ok@1", "ok@2"]      # 两槽各一次
    assert fake_sessions.created == 2                # 无多余冷启动
    assert all(s.session is not None and not s.busy for s in ch.slots)


async def test_overflow_waits_for_release(fake_sessions):
    ch = ir.IntegrationChannels(size=2)
    results = await asyncio.gather(
        *(ch.run_case(f"c{i}") for i in range(5)), return_exceptions=True)
    assert all(isinstance(r, str) for r in results), results
    assert fake_sessions.created == 2


async def test_session_failure_only_closes_own_slot(fake_sessions):
    ch = ir.IntegrationChannels(size=2)
    await asyncio.gather(ch.run_case("a"), ch.run_case("b"))
    s1, s2 = (s.session for s in ch.slots)
    s1.fail_next = True
    s2_ran_before = len(s2.ran)
    results = await asyncio.gather(
        ch.run_case("x"), ch.run_case("y"), return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    oks = [r for r in results if isinstance(r, str)]
    assert len(errors) == 1 and "boom" in str(errors[0])
    assert len(oks) == 1                     # 另一次不被误伤
    assert s1.closed and not s2.closed
    assert len(s2.ran) == s2_ran_before + 1
    # 故障槽下次借出时重新拉起
    assert await ch.run_case("z") in ("ok@2", "ok@3")


async def test_reap_idle_skips_busy_slot(fake_sessions, monkeypatch):
    ch = ir.IntegrationChannels(size=2)
    await ch.run_case("warm")
    slot = next(s for s in ch.slots if s.session is not None)
    # 借出并把 last_used 拨到很久以前:忙槽不得被回收
    acquired = await ch._acquire()
    assert acquired is slot
    slot.last_used = ir._now() - timedelta(
        seconds=ir.CHANNEL_IDLE_SECONDS + 60)
    assert await ch.reap_idle() == 0
    assert slot.session is not None and not slot.session.closed
    await ch._release(slot)
    slot.last_used = ir._now() - timedelta(
        seconds=ir.CHANNEL_IDLE_SECONDS + 60)
    assert await ch.reap_idle() == 1
    assert slot.session is None
