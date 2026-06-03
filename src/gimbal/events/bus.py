"""events/bus.py
增强版事件总线：支持 filter / priority / sync|async|batch 三种模式 / 插件热卸载。
"""
from __future__ import annotations
import threading
import time
import uuid
from typing import Any, Callable, Optional

from .subscription import (
    EventFilter, EventHandler, Subscription, SubscriptionMode
)
from gimbal.log import get_logger
logger = get_logger(__name__)


class InMemoryEventBus:
    """进程内事件总线。

    特性：
      - filter: event_type / event_type_pattern / run_id / step_id / scenario_id / custom
      - priority: 数字越小越先调用
      - mode: SYNC（同步） / ASYNC（异步线程） / BATCH（攒批）
      - 插件热卸载：unsubscribe_plugin 一次清理
    """

    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []
        self._batch_queue: list[tuple[Subscription, Any]] = []
        self._batch_size = 100
        self._batch_interval = 1.0
        self._running = False
        self._batch_thread: Optional[threading.Thread] = None
        self._async_pool: list[threading.Thread] = []
        logger.debug("[EventBus] InMemoryEventBus initialized")

    # ── 订阅 ──────────────────────────────────────
    def subscribe(
        self,
        handler: EventHandler,
        *,
        event_type: Optional[str] = None,
        event_type_pattern: Optional[str] = None,
        run_id: Optional[str] = None,
        step_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        custom: Optional[dict] = None,
        mode: SubscriptionMode = SubscriptionMode.SYNC,
        plugin_name: Optional[str] = None,
        priority: int = 100,
    ) -> str:
        flt = EventFilter(
            event_type=event_type,
            event_type_pattern=event_type_pattern,
            run_id=run_id,
            step_id=step_id,
            scenario_id=scenario_id,
            custom=custom or {},
        )
        sub = Subscription(
            subscription_id=str(uuid.uuid4()),
            event_filter=flt,
            handler=handler,
            mode=mode,
            plugin_name=plugin_name,
            priority=priority,
        )
        self._subscriptions.append(sub)
        self._subscriptions.sort(key=lambda s: s.priority)
        logger.debug(
            "[EventBus] Subscribed: id={} type={} pattern={} mode={} plugin={}",
            sub.subscription_id, event_type, event_type_pattern, mode, plugin_name,
        )
        return sub.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        for i, sub in enumerate(self._subscriptions):
            if sub.subscription_id == subscription_id:
                self._subscriptions.pop(i)
                return True
        return False

    def unsubscribe_plugin(self, plugin_name: str) -> int:
        before = len(self._subscriptions)
        self._subscriptions = [
            s for s in self._subscriptions if s.plugin_name != plugin_name
        ]
        removed = before - len(self._subscriptions)
        if removed:
            logger.debug("[EventBus] Plugin unsubscribed: plugin={} removed={}", plugin_name, removed)
        return removed

    def list_subscriptions(self, plugin_name: Optional[str] = None) -> list[Subscription]:
        if plugin_name:
            return [s for s in self._subscriptions if s.plugin_name == plugin_name]
        return list(self._subscriptions)

    # ── 发布 ──────────────────────────────────────
    def publish(self, event: Any) -> None:
        et = getattr(event, "event_type", type(event).__name__)
        logger.debug("[EventBus] Publishing: {} (subs={})", et, len(self._subscriptions))
        for sub in self._subscriptions:
            if not sub.event_filter.matches(event):
                continue
            if sub.mode == SubscriptionMode.SYNC:
                self._safe_call(sub, event)
            elif sub.mode == SubscriptionMode.ASYNC:
                self._dispatch_async(sub, event)
            elif sub.mode == SubscriptionMode.BATCH:
                self._batch_queue.append((sub, event))
                if len(self._batch_queue) >= self._batch_size:
                    self._flush_batch()

    def _safe_call(self, sub: Subscription, event: Any) -> None:
        try:
            sub.handler(event)
        except Exception:
            logger.exception(
                "[EventBus] Handler error: sub_id={} event={} handler={}",
                sub.subscription_id, type(event).__name__,
                getattr(sub.handler, "__name__", repr(sub.handler)),
            )

    def _dispatch_async(self, sub: Subscription, event: Any) -> None:
        t = threading.Thread(target=self._safe_call, args=(sub, event), daemon=True)
        t.start()
        self._async_pool.append(t)

    def _flush_batch(self) -> None:
        if not self._batch_queue:
            return
        queue, self._batch_queue = self._batch_queue, []
        for sub, event in queue:
            self._safe_call(sub, event)

    def start_batch_loop(self) -> None:
        if self._running:
            return
        self._running = True

        def loop():
            while self._running:
                time.sleep(self._batch_interval)
                self._flush_batch()
        self._batch_thread = threading.Thread(target=loop, daemon=True)
        self._batch_thread.start()
        logger.debug("[EventBus] Batch loop started: interval={}s", self._batch_interval)

    def stop(self) -> None:
        self._running = False
        self._flush_batch()
        logger.debug("[EventBus] Stopped")
