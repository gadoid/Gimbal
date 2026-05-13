from __future__ import annotations
 
import traceback
from typing import Any, TYPE_CHECKING
 
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

class AssertionExecutor(StrategyExecutor):
    """对 context 中的字段执行断言。"""
 
    kind = "assertion"
 
    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        from gimbal.schema.strategy import Assertion, AssertOperator
        from gimbal.context.base import ContextLayer
        from gimbal.context.step import AssertionResult
 
        assert isinstance(spec, Assertion)
 
        try:
            # 读取被断言的目标值
            actual = view.read_variable(
                spec.target,
                from_layer=ContextLayer.SCENARIO,
            )
 
            passed, msg = _evaluate(spec.operator, actual, spec.expected)
            human_msg = spec.message or msg
 
            # 记录断言结果到 context
            view.record_assertion(AssertionResult(
                name=spec.name or spec.target,
                passed=passed,
                expected=spec.expected,
                actual=actual,
                message=human_msg,
            ))
 
            status = StrategyStatus.PASSED if passed else StrategyStatus.FAILED
            return StrategyResult(
                status=status,
                message=human_msg,
            )
        except Exception as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )