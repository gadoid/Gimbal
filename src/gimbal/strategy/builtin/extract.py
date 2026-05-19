from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from gimbal.utils.jsonpath import (
    get as jget , get_all , set_value as jset ,
    resolve_template, is_template
)

if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase

logger = logging.getLogger(__name__)


class ExtractExecutor(StrategyExecutor):
    """从响应/请求中提取字段写入 context。

    支持简单的 JSONPath-like 表达式（$.field.sub）。
    完整 JSONPath 可替换为 jsonpath-ng 库。
    """

    kind = "extract"

    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        from gimbal.schema.strategy import Extract, ExtractSource

        assert isinstance(spec, Extract)

        try:
            logger.debug("[ExtractExecutor] 执行提取: target=%s source=%s expression=%s scope=%s",
                        spec.target, spec.source, spec.expression, spec.scope)

            # 1. 取出要解析的原始数据
            exchange = view.read_http_exchange(spec.target)
            if exchange is None:
                return StrategyResult(
                    status=StrategyStatus.ERROR,
                    message="ExtractExecutor: no http_exchange found, "
                            "Extract must run after CALLING phase",
                )

            source_key = _source_to_var_key(spec.source)
            raw = getattr(exchange, source_key, None)
            logger.debug("[ExtractExecutor] 读取源数据: source=%s raw_type=%s",
                        source_key, type(raw).__name__)

            # 2. 解析表达式
            value = jget(raw, spec.expression)
            logger.debug("[ExtractExecutor] JSONPath 解析结果: expression=%s value=%s", spec.expression, value)

            if value is None:
                if spec.default is not None:
                    value = spec.default
                    logger.debug("[ExtractExecutor] 使用默认值: target=%s default=%s", spec.target, value)
                elif spec.required:
                    logger.warning("[ExtractExecutor] 提取失败: expression=%s is required but returned None", spec.expression)
                    return StrategyResult(
                        status=StrategyStatus.FAILED,
                        message=f"Extract: expression {spec.expression!r} returned None, "
                                f"field is required",
                    )
                else:
                    value = spec.default

            # 3. 写入 context
            from gimbal.context.base import ContextLayer
            target_layer = _scope_to_layer(spec.scope)
            view.promote_variable(spec.target, value, to=target_layer)

            logger.info("[ExtractExecutor] 提取成功: %s=%r (layer=%s)", spec.target, value, target_layer.value)

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Extracted {spec.target}={value!r}",
                extracted={spec.target: value},
            )
        except Exception as exc:
            logger.exception("[ExtractExecutor] 提取异常: target=%s expression=%s", spec.target, spec.expression)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
