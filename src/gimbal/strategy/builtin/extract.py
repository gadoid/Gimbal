from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from gimbal.strategy.builtin.utils import _scope_to_layer
from gimbal.utils.jsonpath import get as jget

if TYPE_CHECKING:
    from gimbal.context.views import StepContextAdapter
    from gimbal.schema.strategy import Extract

from gimbal.log import get_logger
logger = get_logger(__name__)


class ExtractExecutor(StrategyExecutor):
    kind = "extract"

    def execute(self, spec: "Extract", view: "StepContextAdapter") -> StrategyResult:
        try:
            logger.debug(
                "[ExtractExecutor] 执行提取: expression={} target={} scope={}",
                spec.expression, spec.target, spec.scope
            )

            # 1. 从 scratch 用 JSONPath 取值
            scratch = view.get_scratch_dict()
            value = jget(scratch, spec.expression)

            logger.debug(
                "[ExtractExecutor] JSONPath 结果: expression={} value={}",
                spec.expression, value
            )

            # 2. 处理空值
            if value is None:
                if spec.default is not None:
                    value = spec.default
                    logger.debug(
                        "[ExtractExecutor] 使用默认值: target={} default={}",
                        spec.target, value
                    )
                elif spec.required:
                    return StrategyResult(
                        status=StrategyStatus.FAILED,
                        message=(
                            f"Extract: expression {spec.expression!r} "
                            f"returned None, required=True"
                        ),
                    )

            # 3. 根据 scope 决定写入目标
            from gimbal.schema.strategy import Scope
            if spec.scope == Scope.STEP:
                view.write_scratch(spec.target, value)
                logger.info(
                    "[ExtractExecutor] 写入 scratch: {}={!r}",
                    spec.target, value
                )
            else:
                target_layer = _scope_to_layer(spec.scope)
                view.promote_variable(spec.target, value, to=target_layer)
                logger.info(
                    "[ExtractExecutor] 提升变量: {}={!r} layer={}",
                    spec.target, value, target_layer.value
                )

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Extracted {spec.target}={value!r}",
                extracted={spec.target: value},
            )

        except Exception as exc:
            logger.exception(
                "[ExtractExecutor] 提取异常: expression={}", spec.expression
            )
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
