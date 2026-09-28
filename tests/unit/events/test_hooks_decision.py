"""S-3:hook 决策通道 — 锁外执行 / Decision 收集 / effective 聚合。"""
import threading
import time

from gimbal.core.decisions import Decision, effective
from gimbal.core.hooks import HookPoint, HookRegistry


def test_trigger_runs_handlers_outside_lock():
    """handler 阻塞时,另一线程可继续 register(不持锁)。"""
    reg = HookRegistry()
    reg.register(HookPoint.STEP_BEFORE, lambda p: time.sleep(0.4))
    t = threading.Thread(target=reg.trigger, args=(HookPoint.STEP_BEFORE, {}))
    t.start()
    time.sleep(0.1)   # 让 trigger 进入 handler
    hid = reg.register(HookPoint.STEP_BEFORE, lambda p: None)   # 必须不阻塞
    reg.unregister(hid)
    t.join(timeout=5)
    assert not t.is_alive()


def test_trigger_collects_decisions_in_registration_order():
    reg = HookRegistry()
    reg.register(HookPoint.STEP_BEFORE, lambda p: Decision(action="skip"), priority=10)
    reg.register(HookPoint.STEP_BEFORE, lambda p: Decision(action="abort"), priority=20)
    ds = reg.trigger(HookPoint.STEP_BEFORE, {})
    assert [d.action for d in ds] == ["skip", "abort"]
    assert effective(ds).action == "skip"


def test_effective_continues_with_payload():
    """continue+载荷(write/patch)不被聚合丢弃——debugger write/patch 依赖。"""
    d = effective([Decision(action="continue", write={"orderId": "O-9"})])
    assert d.action == "continue" and d.write == {"orderId": "O-9"}


def test_handler_exception_does_not_break_others():
    reg = HookRegistry()
    reg.register(HookPoint.STEP_BEFORE, lambda p: 1 / 0, priority=10)
    reg.register(HookPoint.STEP_BEFORE, lambda p: Decision(action="skip"), priority=20)
    ds = reg.trigger(HookPoint.STEP_BEFORE, {})
    assert [d.action for d in ds] == ["skip"]
