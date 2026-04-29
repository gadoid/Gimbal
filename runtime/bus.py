"""EventBus - 事件总线"""
from typing import Callable
from runtime.events import Event, EventType


class EventBus:
    """事件总线，用于发布/订阅事件"""

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: Event):
        """发布事件"""
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                handler(event)
