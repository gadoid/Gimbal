"""集成线 v2 / I1:prepare / extracting 阶段 hard_failed 必须落
error_phase + _error(对齐 verifying 的写法,engine.py)。

修复前:两个 handler 直接进 TEARDOWN 不设 _error/_error_phase,
`core/runner.py:_error_kind_of` 首行 `not error → none`,这类
「被检系统结构变了」的失败在集成侧永远归类不了(应为 contract);
STEP_FAILED 事件文案也只有 `final_state=failed`。

修复后:`error_phase = preparing / extracting`、
`_error = "[phase] <首条失败策略 message>"`,`_error_kind_of`
判为 logic(集成分类函数 §2.2 规则 4 据此归 run=contract)。
"""
from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.strategy.executor_base import PhaseResult, StrategyResult, StrategyStatus
from gimbal.statemachine.engine import StepStateMachine, StepState
from gimbal.core.runner import Engine


def _failed_phase(phase: str, message: str) -> PhaseResult:
    return PhaseResult(
        phase=phase,
        results=[StrategyResult(
            status=StrategyStatus.FAILED,
            strategy_id=f"{phase}_fail",
            message=message,
        )],
    )


def _sm(phase_result: PhaseResult) -> MagicMock:
    sm = MagicMock(spec=StepStateMachine)
    sm._error = None
    sm._error_phase = None
    sm._error_kind = ""
    sm._phase_results = []
    sm._step_id = "step-pe"
    sm._run_phase = MagicMock(return_value=phase_result)
    return sm


# ── prepare ────────────────────────────────────────────────────────

def test_prepare_hard_failed_sets_error_and_phase():
    sm = _sm(_failed_phase("before_request", "$.cfg.token 提取失败: 路径不存在"))
    nxt = StepStateMachine._handle_prepare(sm)
    assert nxt is StepState.TEARDOWN
    assert sm._error_phase == "preparing"
    assert sm._error == "[preparing] $.cfg.token 提取失败: 路径不存在"


def test_prepare_hard_failed_fallback_message():
    sm = _sm(PhaseResult(phase="before_request", results=[
        StrategyResult(status=StrategyStatus.FAILED, message="")]))
    StepStateMachine._handle_prepare(sm)
    assert sm._error_phase == "preparing"
    assert sm._error == "[preparing] strategy failed"


def test_prepare_passed_leaves_error_unset():
    ok = PhaseResult(phase="before_request", results=[
        StrategyResult(status=StrategyStatus.PASSED, message="")])
    sm = _sm(ok)
    nxt = StepStateMachine._handle_prepare(sm)
    assert nxt is StepState.INVOKING
    assert sm._error is None and sm._error_phase is None


# ── extracting ─────────────────────────────────────────────────────

def test_extracting_hard_failed_sets_error_and_phase():
    sm = _sm(_failed_phase("after_request", "$.data.list 提取失败: 结构不符"))
    nxt = StepStateMachine._handle_extracting(sm)
    assert nxt is StepState.TEARDOWN
    assert sm._error_phase == "extracting"
    assert sm._error == "[extracting] $.data.list 提取失败: 结构不符"


def test_extracting_hard_failed_fallback_message():
    sm = _sm(PhaseResult(phase="after_request", results=[
        StrategyResult(status=StrategyStatus.FAILED, message="")]))
    StepStateMachine._handle_extracting(sm)
    assert sm._error_phase == "extracting"
    assert sm._error == "[extracting] strategy failed"


def test_extracting_passed_leaves_error_unset():
    ok = PhaseResult(phase="after_request", results=[
        StrategyResult(status=StrategyStatus.PASSED, message="")])
    sm = _sm(ok)
    nxt = StepStateMachine._handle_extracting(sm)
    assert nxt is StepState.VERIFYING
    assert sm._error is None and sm._error_phase is None


# ── 分类联动(none → logic,集成 §2.2 规则 4 的前置) ────────────────

def _kind(error, phase):
    step = MagicMock()
    step.error = error
    step.error_phase = phase
    step.error_kind = ""
    step.status = "failed"
    return Engine._error_kind_of(step)


def test_error_kind_now_logic_not_none():
    """修复前 error 为空 → none;修复后有 error/phase → logic
    (集成分类函数规则 4:preparing/extracting → run=contract)。"""
    assert _kind("[preparing] $.cfg.token 提取失败", "preparing") == "logic"
    assert _kind("[extracting] $.data.list 提取失败", "extracting") == "logic"
