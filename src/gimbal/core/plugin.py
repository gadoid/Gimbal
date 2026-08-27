"""core/plugin.py

插件抽象基类 + 插件上下文。

设计：
    Plugin 是所有插件的抽象基类。它本身不知道 EventBus / HookRegistry 的存在，
    这些由 PluginContext 在 activate() 时注入。

    插件通过"注册回调"参与框架，而非直接调用框架代码：
        plugin.register_event(PluginActivatedEvent, handler)
        plugin.register_hook(HookPoint.HTTP_BEFORE_SEND, handler)
        plugin.register_strategy(StrategyImpl)

    框架在 activate() 时把回调挂到对应的 Registry / Dispatcher。

生命周期：
    DISCOVERED → LOADED → ACTIVATED → DEACTIVATED
            ↘ FAILED（任意阶段出错）

子类的可选覆写点：
    on_load()      — 加载时（如解析 manifest、读取资源），可抛异常
    on_activate()  — 激活时（注册订阅/hook/strategy），可抛异常
    on_deactivate()— 卸载时（清理资源、关闭连接），不应抛异常
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .hooks import HookPoint
from gimbal.events.protocols import EventBusProtocol, HookRegistryProtocol
from gimbal.events.types import FrameworkEvent

logger = logging.getLogger(__name__)


# ── 插件状态 ────────────────────────────────────────────────

class PluginState(str, Enum):
    """插件生命周期状态。"""
    DISCOVERED = "discovered"        # 找到 manifest
    LOADED = "loaded"                # 类已 import，实例已创建
    ACTIVATING = "activating"        # 正在注册回调
    ACTIVATED = "activated"          # 激活完成
    DEACTIVATING = "deactivating"
    DEACTIVATED = "deactivated"
    FAILED = "failed"                # 任意阶段失败


# ── 插件清单（从 manifest 解析） ────────────────────────────────

@dataclass
class PluginManifest:
    """从 plugin.yaml / plugin.toml 解析出的清单。

    必需字段：name, version, entry_point
    """
    name: str
    version: str
    entry_point: str                  # 形如 "my_plugin.plugin:MyPlugin"
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)        # 其它插件名
    gimbal_version: str = ""          # 兼容的 gimbal 版本（语义化）
    capabilities: list[str] = field(default_factory=list)        # 声明的能力（auth/reporter/...）
    config_schema: dict[str, Any] = field(default_factory=dict)  # 用户配置 schema
    default_config: dict[str, Any] = field(default_factory=dict) # 用户配置默认值


# ── 插件上下文（activate 时由框架注入） ─────────────────────────────

@dataclass
class PluginContext:
    """插件在 activate() 时获得的运行时句柄集合。

    通过 Protocol 持有基础设施引用：
        - event_bus:        EventBusProtocol（可替换为分布式实现）
        - hook_registry:    HookRegistryProtocol（可替换为远程注册表）
        - plugin_registry:  通用插件注册表（避开循环 import）

    插件代码可以照常调用 subscribe/publish/register 等方法，
    底层是 InMemoryEventBus / HookRegistry 或是它们的远端替代，对插件透明。
    """
    plugin_name: str
    config: dict[str, Any]                                 # 用户配置（与 default_config 合并后）
    event_bus: EventBusProtocol
    hook_registry: HookRegistryProtocol
    plugin_registry: Any = None                            # 通用插件注册表（避开循环 import）
    auth_registry: Any = None                              # 运行时认证会话注册表

    # 计数器：仅用于 activate 日志打印"本插件注册了几个 event/hook"。
    # 实际的清理走 name-based 路径（event_bus.unsubscribe_plugin(name) /
    # hook_registry.unregister_plugin(name)），不需要记 id。
    # 旧实现用 list 存 id 但从未被消费过，是死代码。Issue ② 已清理。
    event_count: int = 0
    hook_count: int = 0

    def register_event(
        self,
        event_type: str,
        handler: Callable[[Any], None],
        *,
        priority: int = 100,
        mode: Any = None,  # SubscriptionMode
    ) -> str:
        """注册事件订阅。"""
        # 避免在基类里 import SubscriptionMode（可能造成循环），由调用方传
        from gimbal.events.subscription import SubscriptionMode
        m = mode or SubscriptionMode.SYNC
        sid = self.event_bus.subscribe(
            handler,
            event_type=event_type,
            mode=m,
            priority=priority,
            plugin_name=self.plugin_name,
        )
        self.event_count += 1
        return sid

    def register_hook(
        self,
        point: "HookPoint | str",
        handler: Callable[[Any], Any],
        *,
        priority: int = 100,
        description: str = "",
    ) -> str:
        """注册 hook。point 接受 HookPoint 枚举或字符串。"""
        # 字符串 → HookPoint
        if isinstance(point, str):
            point = HookPoint(point)
        hid = self.hook_registry.register(
            point,
            handler,
            priority=priority,
            plugin_name=self.plugin_name,
            description=description,
        )
        self.hook_count += 1
        return hid

    def emit(self, event: FrameworkEvent) -> None:
        """发布事件（插件也可以发事件给其它订阅者）。"""
        self.event_bus.publish(event)


# ── 插件抽象基类 ────────────────────────────────────────────────

class Plugin(ABC):
    """所有插件的抽象基类。

    子类必须：
        1. 在类属性里声明 manifest（PluginManifest 实例）
        2. 覆写 on_activate(ctx)（必须）
        3. 可选覆写 on_load()、on_deactivate()

    框架的 PluginLoader 会：
        1. import entry_point 拿到类
        2. 实例化 → 调 on_load()
        3. 创建 PluginContext → 调 on_activate(ctx)
        4. 卸载时调 on_deactivate() → 清理 event/hook 注册
    """

    # 子类必须定义
    manifest: PluginManifest  # type: ignore[assignment]

    def __init__(self) -> None:
        self.state: PluginState = PluginState.DISCOVERED
        self.ctx: Optional[PluginContext] = None
        self.error: Optional[str] = None

    # ── 框架调用的入口（一般不覆写） ──
    def load(self) -> None:
        """加载：仅做轻量初始化（解析参数、打开资源）。"""
        if self.state != PluginState.DISCOVERED:
            return
        try:
            self.on_load()
            self.state = PluginState.LOADED
            logger.info("[Plugin:%s] loaded (v%s)", self.manifest.name, self.manifest.version)
        except Exception as e:  # noqa: BLE001
            self.state = PluginState.FAILED
            self.error = str(e)
            logger.exception("[Plugin:%s] load failed: %s", self.manifest.name, e)
            raise

    def activate(self, ctx: PluginContext) -> None:
        """激活：注册事件/hook/strategy 等。"""
        if self.state not in (PluginState.LOADED, PluginState.ACTIVATED):
            raise RuntimeError(f"[Plugin:{self.manifest.name}] cannot activate from state={self.state}")
        self.ctx = ctx
        self.state = PluginState.ACTIVATING
        try:
            self.on_activate(ctx)
            self.state = PluginState.ACTIVATED
            logger.info(
                "[Plugin:%s] activated (events=%d hooks=%d)",
                self.manifest.name,
                ctx.event_count,
                ctx.hook_count,
            )
        except Exception as e:  # noqa: BLE001
            self.state = PluginState.FAILED
            self.error = str(e)
            logger.exception("[Plugin:%s] activate failed: %s", self.manifest.name, e)
            # 触发 PluginFailedEvent
            from gimbal.events.types import PluginFailedEvent
            ctx.emit(PluginFailedEvent(
                plugin_name=self.manifest.name,
                error=str(e),
                stage="activate",
            ))
            raise

    def deactivate(self) -> None:
        """卸载：先调 on_deactivate()，再由框架清理其 event/hook 注册。"""
        if self.state != PluginState.ACTIVATED:
            return
        self.state = PluginState.DEACTIVATING
        try:
            self.on_deactivate()
        except Exception as e:  # noqa: BLE001
            logger.exception("[Plugin:%s] on_deactivate raised: %s", self.manifest.name, e)
        finally:
            # 框架会负责清理：event_bus.unsubscribe_plugin(name) + hook_registry.unregister_plugin(name)
            # 走 name-based 路径，无需 id 列表（PluginContext 内只记 event_count/hook_count 供日志）
            self.state = PluginState.DEACTIVATED
            logger.info("[Plugin:%s] deactivated", self.manifest.name)

    # ── 子类覆写点 ──
    def on_load(self) -> None:
        """可选：加载阶段（解析 manifest 之外的资源）。"""
        pass

    @abstractmethod
    def on_activate(self, ctx: PluginContext) -> None:
        """必须：注册事件/hook/strategy 等。"""
        raise NotImplementedError

    def on_deactivate(self) -> None:
        """可选：清理资源。"""
        pass

    # ── 工具方法 ──
    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Plugin {self.manifest.name} v{self.manifest.version} state={self.state.value}>"
