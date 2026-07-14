"""gimbal/generator/registry.py

生成器注册表：kind → 函数的映射。
"""
from __future__ import annotations

from typing import Callable, Any


class GeneratorRegistry:
    """生成器注册表。"""

    def __init__(self) -> None:
        self._funcs: dict[str, Callable[..., Any]] = {}

    def register(self, kind: str, func: Callable[..., Any]) -> None:
        """注册一个生成函数。"""
        if kind in self._funcs:
            raise ValueError(f"generator '{kind}' already registered")
        self._funcs[kind] = func

    def get(self, kind: str) -> Callable[..., Any] | None:
        """按 kind 取函数；未注册返回 None。"""
        return self._funcs.get(kind)

    def kinds(self) -> list[str]:
        """返回所有已注册 kind 列表（插入顺序）。"""
        return list(self._funcs.keys())


def build_default_registry() -> GeneratorRegistry:
    """构造注册了 9 个内置函数的注册表（含 random_decorated / time_offset）。"""
    from gimbal.generator import functions
    r = GeneratorRegistry()
    r.register("uuid",              functions.uuid)
    r.register("random_str",        functions.random_str)
    r.register("random_int",        functions.random_int)
    r.register("random_decimal",    functions.random_decimal)
    r.register("timestamp",         functions.timestamp)
    r.register("now",               functions.now)
    r.register("seq",               functions.seq)
    r.register("random_decorated",  functions.random_decorated_str)
    r.register("time_offset",       functions.time_offset)
    return r
