from __future__ import annotations
 
import traceback
from typing import Any, TYPE_CHECKING
 
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
 
if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase

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
            # 1. 取出要解析的原始数据
            raw = view.read_variable(
                _source_to_var_key(spec.source),
                from_layer=_scope_to_layer(spec.scope),
            )
 
            # 2. 解析表达式
            value = _jsonpath_simple(raw, spec.expression)
 
            if value is None:
                if spec.default is not None:
                    value = spec.default
                elif spec.required:
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
 
            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Extracted {spec.target}={value!r}",
                extracted={spec.target: value},
            )
        except Exception as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )