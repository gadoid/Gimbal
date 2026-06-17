from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from .utils import _evaluate
from gimbal.utils.jsonpath import is_jsonpath, get as jget
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

from gimbal.log import get_logger
logger = get_logger(__name__)


class AssertionExecutor(StrategyExecutor):
    kind = "assertion"

    def execute(self, spec, view) -> StrategyResult:
        """执行断言策略：解析 spec.target 的实际值，用 spec.operator 与 spec.expected 比较，结果记入 view 并返回 StrategyResult。"""
        try:
            logger.info(
                "[AssertionExecutor] 执行断言: target={} operator={} expected={}",
                spec.target, spec.operator, spec.expected
            )

            # 统一从 scratch 用 JSONPath 取值
            # target 可以是 "$.response_status" 或 "$.response_body.code"
            scratch = view.get_scratch_dict()

            if is_jsonpath(spec.target):
                actual = jget(scratch, spec.target)
            else:
                # 普通 key，直接从 scratch 取
                actual = scratch.get(spec.target)
                # 取不到再从上层 channels 找
                if actual is None:
                    from gimbal.context.base import ContextLayer
                    actual = view.read_variable(
                        spec.target,
                        from_layer=ContextLayer.SCENARIO
                    )

            logger.info(
                "[AssertionExecutor] 实际值: target={} actual={}",
                spec.target, actual
            )

            passed, msg = _evaluate(spec.operator, actual, spec.expected)
            human_msg = spec.message or msg

            from gimbal.context.step import AssertionResult
            view.record_assertion(AssertionResult(
                name=spec.name or spec.target,
                passed=passed,
                expected=spec.expected,
                actual=actual,
                message=human_msg,
            ))

            status = StrategyStatus.PASSED if passed else StrategyStatus.FAILED
            if passed:
                logger.info("[AssertionExecutor] 断言通过: {}", human_msg)
            else:
                logger.warning("[AssertionExecutor] 断言失败: {}", human_msg)

            return StrategyResult(status=status, message=human_msg)

        except Exception as exc:
            logger.exception("[AssertionExecutor] 断言异常: target={}", spec.target)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
