from typing import Any
from gimbal.context.views import StrategyContextView
from gimbal.log import get_logger
logger = get_logger(__name__)

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
    """极简 JSONPath 实现，支持 $.a.b.c 与 $.a[0].b 形式；查询不到返回 None。生产环境建议替换为 jsonpath-ng。"""
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
    """解析 Assign.source：
    - scope=STEP: 先从 scratch JSONPath 查询，查不到再去场景上下文
    - scope=SCENARIO: 直接从场景上下文查询
    - "$.jsonpath" -> 从 scratch 读取（如 "$.response_body.data.order_no"）
    - "${varname}" -> 从 context 读取（如 "${order_no}"）
    - 字面量 -> 直接返回
    """
    from gimbal.utils.jsonpath import get as jsonpath_get
    from gimbal.schema.strategy import Scope

    if not isinstance(source, str):
        return source

    # STEP scope: 先查 scratch，再提升到 scenario context 用同一 JSONPath 查询
    if scope == Scope.STEP:
        # JSONPath 格式：先从 scratch JSONPath 查询，查不到再提升到 scenario 用同一路径查询
        if source.startswith("$."):
            scratch = view.get_scratch_dict()
            value = jsonpath_get(scratch, source)
            if value is not None:
                logger.debug("[_resolve_source_value] STEP scope scratch hit: {} -> {}", source, value)
                return value
            # scratch 查不到，提升到 scenario 用同一 JSONPath 继续查询
            layer = _scope_to_layer(Scope.SCENARIO)
            ctx_value = view.read_variable(source, from_layer=layer)
            logger.debug("[_resolve_source_value] STEP scope scratch miss, promote to scenario with same path: {} -> {}", source, ctx_value)
            return ctx_value

        # 模板格式：先查 scratch，再查 context
        if source.startswith("${") and source.endswith("}"):
            var_name = source[2:-1].strip()
            # 先从 scratch 查找
            scratch = view.get_scratch_dict()
            if var_name in scratch:
                value = scratch[var_name]
                logger.debug("[_resolve_source_value] STEP scope scratch hit: {} -> {}", var_name, value)
                return value
            # 查不到再从 context
            layer = _scope_to_layer(Scope.SCENARIO)
            ctx_value = view.read_variable(var_name, from_layer=layer)
            logger.debug("[_resolve_source_value] STEP scope scratch miss, fallback to scenario: {} -> {}", var_name, ctx_value)
            return ctx_value

    # SCENARIO scope: 直接从场景上下文用同一 JSONPath 查询
    if scope == Scope.SCENARIO and source.startswith("$."):
        layer = _scope_to_layer(scope)
        ctx_value = view.read_variable(source, from_layer=layer)
        logger.debug("[_resolve_source_value] SCENARIO scope: {} -> {}", source, ctx_value)
        return ctx_value

    if source.startswith("${") and source.endswith("}"):
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
