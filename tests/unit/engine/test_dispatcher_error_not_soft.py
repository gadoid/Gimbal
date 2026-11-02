"""ERROR 永远不是 soft(executor_base.StrategyResult 契约;全量评估 2026-11-02 #5)。

dispatcher 此前对 ``failed``(FAILED ∪ ERROR)一律按 onFailure 置 soft,
onFailure=CONTINUE/WARN 时执行器抛异常、策略 kind 未注册都会 hard_failed=False
→ 状态机各阶段只看 hard_failed,步骤被判 PASSED。本文件钉住三条对拍:
FAILED+CONTINUE 仍是 soft;ERROR(执行器抛异常)+CONTINUE 不 soft;
未注册 kind(ERROR)+CONTINUE 不 soft。
"""
from __future__ import annotations

from types import SimpleNamespace

from gimbal.schema import FailurePolicy
from gimbal.strategy.dispatcher import StrategyDispatcher
from gimbal.strategy.executor_base import (
    StrategyExecutor, StrategyResult, StrategyStatus,
)


class _FailingExecutor(StrategyExecutor):
    kind = "t.fail"

    def execute(self, spec, view) -> StrategyResult:
        return StrategyResult(status=StrategyStatus.FAILED, message="assert false")


class _RaisingExecutor(StrategyExecutor):
    kind = "t.raise"

    def execute(self, spec, view) -> StrategyResult:
        raise RuntimeError("boom")


def _spec(kind: str, policy: FailurePolicy) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, name=f"s-{kind}", enabled=True,
                           onFailure=policy)


def _dispatcher() -> StrategyDispatcher:
    d = StrategyDispatcher()
    d.register(_FailingExecutor())
    d.register(_RaisingExecutor())
    return d


def test_failed_with_continue_is_soft() -> None:
    r = _dispatcher().dispatch(_spec("t.fail", FailurePolicy.CONTINUE), view=None)
    assert r.status is StrategyStatus.FAILED
    assert r.soft is True and r.hard_failed is False


def test_failed_with_abort_is_hard() -> None:
    r = _dispatcher().dispatch(_spec("t.fail", FailurePolicy.ABORT), view=None)
    assert r.status is StrategyStatus.FAILED
    assert r.soft is False and r.hard_failed is True


def test_executor_exception_is_never_soft() -> None:
    for policy in (FailurePolicy.CONTINUE, FailurePolicy.WARN):
        r = _dispatcher().dispatch(_spec("t.raise", policy), view=None)
        assert r.status is StrategyStatus.ERROR
        assert r.soft is False, policy
        assert r.hard_failed is True, policy


def test_unregistered_kind_is_never_soft() -> None:
    r = _dispatcher().dispatch(_spec("t.typo", FailurePolicy.CONTINUE), view=None)
    assert r.status is StrategyStatus.ERROR
    assert "No executor registered" in r.message
    assert r.soft is False and r.hard_failed is True
