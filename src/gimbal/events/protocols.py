"""events/protocols.py

定义事件总线与钩子注册表的抽象接口（Protocol）。

目的：
    - core/plugin.py 中的 PluginContext 不应直接持有具体实现类
      （InMemoryEventBus / HookRegistry），而应依赖这些 Protocol。
    - 未来替换为分布式实现（Redis / Kafka / gRPC 等）时，PluginContext
      及其所有下游用户无需任何修改。

设计原则：
    - Protocol 而非 ABC：保持鸭子类型风格，运行时不需要显式注册。
    - 只声明 PluginContext 实际调用的最小子集，避免泄露实现细节。
    - 与 bus.py / hooks.py 的具体类保持方法签名一致。
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class EventBusProtocol(Protocol):
    """事件总线协议。

    PluginContext 实际使用的方法子集：
        - subscribe:   注册事件订阅
        - unsubscribe: 取消单个订阅
        - publish:     发布事件
    """

    def subscribe(
        self,
        handler: Callable[[Any], None],
        *,
        event_type: Optional[str] = None,
        event_type_pattern: Optional[str] = None,
        run_id: Optional[str] = None,
        step_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        custom: Optional[dict] = None,
        mode: Any = ...,
        plugin_name: Optional[str] = None,
        priority: int = 100,
    ) -> str:
        """注册一个事件订阅，返回 subscription_id。"""
        ...

    def unsubscribe(self, subscription_id: str) -> bool:
        """按 id 取消订阅。返回是否成功。"""
        ...

    def publish(self, event: Any) -> None:
        """发布事件。"""
        ...


@runtime_checkable
class HookRegistryProtocol(Protocol):
    """钩子注册表协议。

    PluginContext 实际使用的方法子集：
        - register:    注册钩子
        - unregister:  按 id 注销钩子
    """

    def register(
        self,
        point: Any,  # HookPoint | str
        handler: Callable[[Any], Any],
        *,
        priority: int = 100,
        plugin_name: Optional[str] = None,
        description: str = "",
    ) -> str:
        """注册一个 hook，返回 hook_id。"""
        ...

    def unregister(self, hook_id: str) -> bool:
        """按 id 注销钩子。返回是否成功。"""
        ...
