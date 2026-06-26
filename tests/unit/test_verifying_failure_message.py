"""Regression tests: verifying 阶段失败时，message 应到达 StepFailedEvent 与 StepRunResult。

修复前：
  - _handle_verifying 失败分支不写 self._error，导致 StepFailedEvent.error 为空。
  - runner.py 转换 RunResult.details 时丢 error 字段。

修复后：
  - self._error = f"[verifying] {failed_strategy.message}" 写入。
  - details.steps[j] 含 error / error_phase 字段。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from unittest.mock import MagicMock

from gimbal.strategy.executor_base import PhaseResult, StrategyResult, StrategyStatus
from gimbal.statemachine.engine import StepStateMachine


print("=" * 60)
print("VERIFYING FAILURE MESSAGE PROPAGATION TEST")
print("=" * 60)


def _make_failed_phase_result(message: str) -> PhaseResult:
    """构造一个 hard_failed 的 verifying PhaseResult（含一条 FAILED 策略）。"""
    failed = StrategyResult(
        status=StrategyStatus.FAILED,
        strategy_id="assert_status_eq",
        message=message,
    )
    return PhaseResult(phase="verifying", results=[failed])


def test_verifying_failure_sets_error_on_step_state_machine():
    """verifying 阶段失败时，StepStateMachine.run() 返回的 StepRunResult.error 非空且包含 message。"""
    sm = MagicMock(spec=StepStateMachine)
    sm._error = None
    sm._error_phase = None
    sm._phase_results = []
    sm._step_id = "step-x"
    sm._has_phase = MagicMock(return_value=False)

    sm._run_phase = MagicMock(
        return_value=_make_failed_phase_result("FAIL: expected 5 eq 6")
    )

    StepStateMachine._handle_verifying(sm)

    assert sm._error_phase == "verifying"
    assert sm._error == "[verifying] FAIL: expected 5 eq 6"
    print(" [1] verifying 失败 self._error 含 message: OK")


def test_verifying_failure_falls_back_when_no_message():
    """边界：失败策略无 message 时，回退到固定文案，不崩溃。"""
    sm = MagicMock(spec=StepStateMachine)
    sm._error = None
    sm._error_phase = None
    sm._phase_results = []
    sm._step_id = "step-y"
    sm._has_phase = MagicMock(return_value=False)

    sm._run_phase = MagicMock(
        return_value=PhaseResult(
            phase="verifying",
            results=[StrategyResult(status=StrategyStatus.FAILED, message="")],
        )
    )

    StepStateMachine._handle_verifying(sm)

    assert sm._error_phase == "verifying"
    assert sm._error == "[verifying] assertion failed"
    print(" [2] verifying 失败无 message 时回退: OK")


def test_verifying_failure_handles_empty_results():
    """边界：PhaseResult 没有任何结果时，不崩溃（hard_failed 为 False 走 PASSED 分支）。"""
    sm = MagicMock(spec=StepStateMachine)
    sm._error = None
    sm._error_phase = None
    sm._phase_results = []
    sm._step_id = "step-z"
    sm._has_phase = MagicMock(return_value=False)

    sm._run_phase = MagicMock(
        return_value=PhaseResult(phase="verifying", results=[])
    )

    StepStateMachine._handle_verifying(sm)

    # 空 results 时 hard_failed=False，应进入 PASSED 分支，self._error 不应被设置
    assert sm._error is None
    assert sm._error_phase is None
    print(" [3] verifying 空 results 走 PASSED 分支: OK")
