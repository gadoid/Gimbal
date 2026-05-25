from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING
from .utils import _evaluate
from gimbal.utils.jsonpath import is_jsonpath, get as jget
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

logger = logging.getLogger(__name__)


class AssertionExecutor(StrategyExecutor):
    """对 context 中的字段执行断言。"""

    kind = "assertion"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        from gimbal.schema.strategy import Assertion, AssertOperator
        from gimbal.context.base import ContextLayer
        from gimbal.context.step import AssertionResult

        assert isinstance(spec, Assertion)
        try:
            logger.info("[AssertionExecutor] 执行断言: target=%s operator=%s expected=%s",
                        spec.target, spec.operator, spec.expected)
            # from pprint import pprint
            # pprint(view.content)
            # 读取被断言的目标值
            _HTTP_EXCHANGE_KEYS = {
                "response_status", "response_body",
                "response_headers", "request_body"
            }
            logger.info(f"spec.target: {spec.target}")
            if spec.target in _HTTP_EXCHANGE_KEYS:
               # actual = view.read_http_exchange(spec.target)[spec.target]
                actual = view.read_http_exchange()[spec.target]
            elif is_jsonpath(spec.target):
                # $.data.code 这类路径，从 response_body 里提取
                exchange = view.read_http_exchange()
                raw_body = exchange.get("response_body") if exchange else None
                actual = jget(raw_body, spec.target)
            else:
                # 普通 key，从 Scenario channels 读（Extract 提升上来的业务字段）
                actual = view.read_variable(spec.target, from_layer=ContextLayer.SCENARIO)

            logger.info("[AssertionExecutor] 读取实际值: target=%s actual=%s", spec.target, actual)

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
            if passed:
                logger.info("[AssertionExecutor] 断言通过: %s %s %s -> actual=%s",
                           actual, spec.operator.value if hasattr(spec.operator, 'value') else spec.operator, spec.expected, actual)
            else:
                logger.warning("[AssertionExecutor] 断言失败: %s %s %s -> actual=%s",
                             actual, spec.operator.value if hasattr(spec.operator, 'value') else spec.operator, spec.expected, actual)

            return StrategyResult(
                status=status,
                message=human_msg,
            )
        except Exception as exc:
            logger.exception("[AssertionExecutor] 断言异常: target=%s", spec.target)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
