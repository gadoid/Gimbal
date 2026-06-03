"""events package - 事件系统公共 API。"""
from .bus import InMemoryEventBus
from .protocols import EventBusProtocol, HookRegistryProtocol
from .subscription import EventFilter, EventHandler, Subscription, SubscriptionMode
from .types import (
    EventType,                            # 枚举（与 HookPoint 对称）
    FrameworkEvent,
    FrameworkInitEvent, FrameworkTeardownEvent,
    RunStartEvent, RunEndEvent,
    SuiteStartEvent, SuiteEndEvent,
    ScenarioStartEvent, ScenarioEndEvent,
    StepStartEvent, StepEndEvent, StepFailedEvent,
    HttpRequestEvent, HttpResponseEvent,
    ContextPromotionEvent,
    PluginActivatedEvent, PluginFailedEvent, PluginDeactivatedEvent,
)

__all__ = [
    "InMemoryEventBus",
    "EventBusProtocol", "HookRegistryProtocol",
    "EventFilter", "EventHandler", "Subscription", "SubscriptionMode",
    "EventType",
    "FrameworkEvent",
    "FrameworkInitEvent", "FrameworkTeardownEvent",
    "RunStartEvent", "RunEndEvent",
    "SuiteStartEvent", "SuiteEndEvent",
    "ScenarioStartEvent", "ScenarioEndEvent",
    "StepStartEvent", "StepEndEvent", "StepFailedEvent",
    "HttpRequestEvent", "HttpResponseEvent",
    "ContextPromotionEvent",
    "PluginActivatedEvent", "PluginFailedEvent", "PluginDeactivatedEvent",
]
