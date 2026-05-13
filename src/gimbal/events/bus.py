"""events/bus.py  —  内存事件总线（开发/测试用，生产可替换为异步实现）。"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)

EventHandler = Callable[[Any], None]


class InMemoryEventBus:
    """同步内存事件总线。

    publish 后同步调用所有订阅者。
    生产环境可替换为基于 asyncio / Redis / Kafka 的实现，接口不变。
    """

    def __init__(self) -> None:
        # event_type → list of handlers
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        event_type = getattr(event, "event_type", type(event).__name__)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus handler error for event_type=%s", event_type)

        # 通配订阅 "*" 接收所有事件
        for handler in self._handlers.get("*", []):
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus wildcard handler error")