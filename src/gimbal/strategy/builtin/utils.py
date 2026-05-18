from typing import Any
from gimbal.context.views import StrategyContextView

def _source_to_var_key(source) -> str:
    """将 ExtractSource 枚举映射到 context 变量名。"""
    from gimbal.schema.strategy import ExtractSource
    mapping = {
        ExtractSource.RESPONSE_BODY: "response_body",
        ExtractSource.RESPONSE_HEADER: "response_headers",
        ExtractSource.REQUEST_BODY: "request_body",
        ExtractSource.REQUEST_HEADER: "request_headers",
    }
    return mapping.get(source, str(source))
 
 
def _scope_to_layer(scope):
    """将 schema Scope 映射到 ContextLayer。"""
    from gimbal.schema.strategy import Scope
    from gimbal.context.base import ContextLayer
    mapping = {
        Scope.FRAMEWORK: ContextLayer.FRAMEWORK,
        Scope.SESSION: ContextLayer.SUITE,     # session ≈ suite
        Scope.SCENARIO: ContextLayer.SCENARIO,
        Scope.STEP: ContextLayer.SCENARIO,     # STEP 不允许自写，降级到 SCENARIO
        Scope.REQUEST: ContextLayer.SCENARIO,
    }
    return mapping.get(scope, ContextLayer.SCENARIO)
 
 
def _jsonpath_simple(data: Any, expression: str) -> Any:
    """极简 JSONPath 实现，支持 $.a.b.c 和 $.a[0].b 形式。
    生产环境建议替换为 jsonpath-ng。
    """
    if data is None:
        return None
 
    # 去掉前缀 $
    expr = expression.lstrip("$").lstrip(".")
    if not expr:
        return data
 
    parts = expr.split(".")
    current = data
    for part in parts:
        if current is None:
            return None
        # 处理数组下标 a[0]
        if "[" in part:
            name, idx_str = part.rstrip("]").split("[", 1)
            try:
                idx = int(idx_str)
            except ValueError:
                return None
            current = current.get(name) if isinstance(current, dict) else None
            if isinstance(current, list):
                current = current[idx] if 0 <= idx < len(current) else None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
 
 
def _resolve_source_value(source: Any, view: "StrategyContextView", scope) -> Any:
    """解析 Assign.source：模板变量或字面量。"""
    from gimbal.context.base import ContextLayer
 
    if isinstance(source, str) and source.startswith("${") and source.endswith("}"):
        var_name = source[2:-1].strip()
        layer = _scope_to_layer(scope)
        return view.read_variable(var_name, from_layer=layer)
    return source
 
 
def _evaluate(operator, actual: Any, expected: Any) -> tuple[bool, str]:
    """执行比较操作，返回 (是否通过, 描述信息)。"""
    from gimbal.schema.strategy import AssertOperator
 
    op = operator
    try:
        if op == AssertOperator.EQ:
            ok = actual == expected
        elif op == AssertOperator.NE:
            ok = actual != expected
        elif op == AssertOperator.GT:
            ok = actual > expected
        elif op == AssertOperator.GTE:
            ok = actual >= expected
        elif op == AssertOperator.LT:
            ok = actual < expected
        elif op == AssertOperator.LTE:
            ok = actual <= expected
        elif op == AssertOperator.IN:
            ok = actual in expected
        elif op == AssertOperator.NOT_IN:
            ok = actual not in expected
        elif op == AssertOperator.CONTAINS:
            ok = expected in actual
        elif op == AssertOperator.NOT_CONTAINS:
            ok = expected not in actual
        elif op == AssertOperator.EXISTS:
            ok = actual is not None
        elif op == AssertOperator.EMPTY:
            ok = not actual
        elif op == AssertOperator.LENGTH_EQ:
            ok = len(actual) == expected
        else:
            return False, f"Unknown operator: {op}"
 
        msg = (
            f"PASS: {actual!r} {op.value} {expected!r}"
            if ok
            else f"FAIL: expected {actual!r} {op.value} {expected!r}"
        )
        return ok, msg
    except Exception as exc:
        return False, f"Evaluation error: {exc}"