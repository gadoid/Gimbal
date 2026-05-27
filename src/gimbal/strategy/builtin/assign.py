from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

from gimbal.log import get_logger
logger = get_logger(__name__)

class AssignExecutor(StrategyExecutor):
    """将字面量或 context 变量赋值到指定路径。

    source 可以是：
      - 字面量（str/int/bool/dict）
      - 模板字符串 "${varname}" -> 从 context 中读取
    """

    kind = "assign"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        from gimbal.schema.strategy import Assign

        assert isinstance(spec, Assign)

        try:
            logger.debug("[AssignExecutor] 执行赋值: target={} source={} scope={}",
                        spec.target, spec.source, spec.scope)

            # 解析 source：是模板还是字面量
            value = _resolve_source_value(spec.source, view, spec.scope)

            if value is None:
                if spec.default is not None:
                    value = spec.default
                    logger.debug("[AssignExecutor] 使用默认值: target={} default={}", spec.target, value)
                elif spec.required:
                    logger.warning("[AssignExecutor] 赋值失败: target={} source={} is required but resolved to None",
                                  spec.target, spec.source)
                    return StrategyResult(
                        status=StrategyStatus.FAILED,
                        message=f"Assign: source {spec.source!r} resolved to None, field required",
                    )

            # 写入 context（target 在 request body 里的路径留给模板引擎处理）
            from gimbal.context.base import ContextLayer
            target_layer = _scope_to_layer(spec.scope)
            view.promote_variable(spec.target, value, to=target_layer)

            logger.info("[AssignExecutor] 赋值成功: {}=%r (layer={})", spec.target, value, target_layer.value)

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Assigned {spec.target}={value!r}",
                extracted={spec.target: value},
            )
        except Exception as exc:
            logger.exception("[AssignExecutor] 赋值异常: target={}", spec.target)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
