"""core/registry.py — 泛型扩展注册表（v2 §1，批次 C）。

统一的是**身份、参数声明、查找、描述导出**；各扩展点的调用接口各自独立
（"统一机制、不统一接口"）。四张表：
  - strategy：kind → (params 模型, executor) —— 由 dispatcher 侧装配
  - protocol：protocol → (call 字段模型, adapter)
  - mode：mode → (suite 声明参数, desugar 函数)
  - plugin：插件（声明订阅的事件与拦截点）

批次 C 先承载 mode 表（新代码最干净）；strategy/protocol 表在批次 F
收敛时把 StrategyDispatcher/ProtocolRegistry 的注册面切到本类。
``ext list --json`` = 四张表 describe() 之和。
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Generic, Optional, TypeVar

from pydantic import BaseModel

from gimbal.log import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class Registry(Generic[T]):
    """名字 → (参数模型, 实现对象) 的注册表；线程安全。"""

    def __init__(self, table: str) -> None:
        self._table = table
        self._items: dict[str, tuple[Optional[type[BaseModel]], T]] = {}
        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        impl: T,
        params: Optional[type[BaseModel]] = None,
    ) -> T:
        """注册一个扩展；同名后注册覆盖（升级语义）。返回 impl（装饰器友好）。"""
        if not name:
            raise ValueError(f"{self._table} 注册名不可为空")
        with self._lock:
            self._items[name] = (params, impl)
        logger.debug("[Registry:{}] registered: {} ({})", self._table, name,
                     type(impl).__name__)
        return impl

    def get(self, name: str) -> tuple[Optional[type[BaseModel]], T]:
        """按名取 (参数模型, 实现对象)；未知名字抛 KeyError（调用方转 CompileError）。"""
        with self._lock:
            if name not in self._items:
                raise KeyError(
                    f"{self._table} 表中未注册: {name!r}（已注册: {sorted(self._items)}）"
                )
            return self._items[name]

    def params_of(self, name: str) -> Optional[type[BaseModel]]:
        """按名取参数模型；未注册或该条目无模型返回 None。"""
        with self._lock:
            item = self._items.get(name)
            return item[0] if item is not None else None

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._items

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._items)

    def describe(self) -> list[dict[str, Any]]:
        """导出 name + 参数 JSON Schema（ext list --json 的口径）。"""
        out: list[dict[str, Any]] = []
        with self._lock:
            for name in sorted(self._items):
                params, _impl = self._items[name]
                out.append({
                    "table": self._table,
                    "name": name,
                    "params_schema": (
                        params.model_json_schema() if params is not None else None
                    ),
                })
        return out
