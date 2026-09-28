"""断言求值 —— 把 YAML 里写的断言真正跑在真实响应上。

编排器不评估断言就报 "passed" 是自欺：数出来的只是「发了几次请求」，
不是「响应符不符合预期」。这个模块让 passed/failed 有证据。

求值对象是引擎的 scratch 形状 `{"call": {"response": {status, body}}}`，
与 YAML 里 `$.call.response.body.*` 的路径一一对应 —— 用例将来交给引擎
执行时，断言语义不变。
"""

from __future__ import annotations

import re
from typing import Any

MISSING = object()

_SEG = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def resolve(node: Any, path: str) -> Any:
    """按 `$.a.b[0].c` 取值；任一段不存在返回 MISSING。"""
    if not path.startswith("$"):
        raise ValueError(f"断言路径必须以 $ 开头: {path!r}")
    cur = node
    for m in _SEG.finditer(path[1:]):
        key, idx = m.group(1), m.group(2)
        if key is not None:
            if not isinstance(cur, dict) or key not in cur:
                return MISSING
            cur = cur[key]
        else:
            i = int(idx)
            if not isinstance(cur, (list, tuple)) or i >= len(cur):
                return MISSING
            cur = cur[i]
    return cur


def _truthy_len(value: Any) -> int | None:
    if isinstance(value, (str, list, tuple, dict)):
        return len(value)
    return None


def evaluate(node: Any, spec: dict) -> bool:
    """求值单条断言。路径缺失一律判 False（不抛），让失败可归因到断言本身。"""
    op = spec["operator"]
    actual = resolve(node, spec["target"])
    expected = spec.get("expected")

    if op == "exists":
        return actual is not MISSING
    if op == "empty":
        return actual is MISSING or actual is None or _truthy_len(actual) == 0
    if op == "length_eq":
        n = _truthy_len(actual)
        return n is not None and n == expected

    if actual is MISSING:
        return False

    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op in ("gt", "gte", "lt", "lte"):
        try:
            return {
                "gt": actual > expected,
                "gte": actual >= expected,
                "lt": actual < expected,
                "lte": actual <= expected,
            }[op]
        except TypeError:
            return False
    if op == "in":
        return actual in (expected or [])
    if op == "not_in":
        return actual not in (expected or [])
    if op == "contains":
        try:
            return expected in actual
        except TypeError:
            return False
    if op == "not_contains":
        try:
            return expected not in actual
        except TypeError:
            return True
    raise ValueError(f"未知 operator: {op!r}")
