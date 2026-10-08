from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from .utils import _evaluate
from gimbal.protocols.result import is_sensitive_path, redact_value
from gimbal.utils.jsonpath import is_jsonpath, get as jget
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

from gimbal.log import get_logger
logger = get_logger(__name__)


class AssertionExecutor(StrategyExecutor):
    kind = "assertion"

    def execute(self, spec, view) -> StrategyResult:
        """执行断言策略：解析 spec.target 的实际值，用 spec.operator 与 spec.expected 比较，结果记入 view 并返回 StrategyResult。"""
        try:
            # P0-3b：target 命中敏感键（token/cookie/... 与证据脱敏同表）时，
            # actual/expected 只以脱敏形态进断言记录（outcome.assertions →
            # 归档）与日志；**判定仍用 scratch 原值**（P0-3 语义不变）
            sensitive = is_sensitive_path(spec.target)

            logger.info(
                "[AssertionExecutor] 执行断言: target={} operator={} expected={}",
                spec.target, spec.operator,
                redact_value(spec.expected) if sensitive else spec.expected
            )

            # 统一从 scratch 用 JSONPath 取值
            # target 是 scratch 路径:协议归一树 $.call.response.status /
            # $.call.response.body.code(v2.1 批次 F 终态——旧伪路径
            # $.response_status/$.response_body.* 已退役,取值恒 None;
            # 存量经 scripts/migrate_legacy_case.py 迁移)
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
                spec.target, redact_value(actual) if sensitive else actual
            )

            passed, msg = _evaluate(spec.operator, actual, spec.expected)
            if sensitive:
                # 消息同样只携带脱敏形态；PASS/FAIL 前缀仍来自原值判定，
                # 失败时可看出"值不一致"而不泄露原值
                masked = redact_value(actual)
                msg = (
                    f"PASS: {masked} {spec.operator.value} {masked}" if passed
                    else f"FAIL: expected {masked} {spec.operator.value} {masked}"
                )
            human_msg = spec.message or msg

            from gimbal.context.step import AssertionResult
            view.record_assertion(AssertionResult(
                name=spec.name or spec.target,
                passed=passed,
                expected=redact_value(spec.expected) if sensitive else spec.expected,
                actual=redact_value(actual) if sensitive else actual,
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
