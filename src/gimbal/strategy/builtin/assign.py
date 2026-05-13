from __future__ import annotations
 
import traceback
from typing import Any, TYPE_CHECKING
 
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

class AssignExecutor(StrategyExecutor):
    """将字面量或 context 变量赋值到指定路径。
 
    source 可以是：
      - 字面量（str/int/bool/dict）
      - 模板字符串 "${varname}" → 从 context 中读取
    """
 
    kind = "assign"
 
    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
        from gimbal.schema.strategy import Assign
 
        assert isinstance(spec, Assign)
 
        try:
            # 解析 source：是模板还是字面量
            value = _resolve_source_value(spec.source, view, spec.scope)
 
            if value is None:
                if spec.default is not None:
                    value = spec.default
                elif spec.required:
                    return StrategyResult(
                        status=StrategyStatus.FAILED,
                        message=f"Assign: source {spec.source!r} resolved to None, field required",
                    )
 
            # 写入 context（target 在 request body 里的路径留给模板引擎处理）
            from gimbal.context.base import ContextLayer
            target_layer = _scope_to_layer(spec.scope)
            view.promote_variable(spec.target, value, to=target_layer)
 
            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"Assigned {spec.target}={value!r}",
                extracted={spec.target: value},
            )
        except Exception as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )