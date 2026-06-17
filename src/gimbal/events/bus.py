"""events/bus.py
增强版事件总线：支持 filter / priority / sync|async|batch 三种模式 / 插件热卸载。
"""
from __future__ import annotations
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from .subscription import (
    EventFilter, EventHandler, Subscription, SubscriptionMode
)
from gimbal.log import get_logger
logger = get_logger(__name__)


# 修复 #8：ASYNC 模式使用固定大小的线程池，避免无限创建线程
_ASYNC_POOL_MAX_WORKERS = 8


class InMemoryEventBus:
    """进程内事件总线。

    特性：
      - filter: event_type / event_type_pattern / run_id / step_id / scenario_id / custom
      - priority: 数字越小越先调用
      - mode: SYNC（同步） / ASYNC（异步线程） / BATCH（攒批）
      - 插件热卸载：unsubscribe_plugin 一次清理
    """

    def __init__(self) -> None:
        """初始化事件总线：创建订阅列表、批量队列参数以及用于 ASYNC 模式的固定大小线程池（_ASYNC_POOL_MAX_WORKERS=8）。无入参；副作用为初始化内部数据结构并创建 ThreadPoolExecutor。"""
        self._subscriptions: list[Subscription] = []
        self._batch_queue: list[tuple[Subscription, Any]] = []
        self._batch_size = 100
        self._batch_interval = 1.0
        self._running = False
        self._batch_thread: Optional[threading.Thread] = None
        # 修复 #8：用 ThreadPoolExecutor 替代裸线程列表
        self._async_executor: Optional[ThreadPoolExecutor] = ThreadPoolExecutor(
            max_workers=_ASYNC_POOL_MAX_WORKERS,
            thread_name_prefix="gimbal-eventbus-async",
        )
        logger.debug("[EventBus] InMemoryEventBus initialized")

    # ── 订阅 ──────────────────────────────────────
    def subscribe(
        self,
        handler: EventHandler,
        event_type: Optional[str] = None,
        *,
        filter: Optional[EventFilter] = None,
        mode: SubscriptionMode = SubscriptionMode.SYNC,
        plugin_name: Optional[str] = None,
        priority: int = 100,
    ) -> str:
        """订阅事件。

        三种调用风格（从最简到最强）：

        1. 极简（80% 用法）：只关心事件类型
            bus.subscribe(handler, "step.start")

        2. 显式 EventFilter（中等复杂度：正则 / run_id / step_id 过滤）
            bus.subscribe(handler, filter=EventFilter(
                event_type="step.*", step_id="step-000"))

        3. event_type 与 filter 叠加（罕见：filter 是基础，event_type 覆盖）
            bus.subscribe(handler, "step.start", filter=EventFilter(step_id="x"))
            # 最终 filter: event_type="step.start" + step_id="x"

        参数：
            handler:     事件处理函数
            event_type:  事件类型字符串（覆盖 filter.event_type）
            filter:      复杂过滤（正则 / run_id / step_id / scenario_id / custom）
            mode:        SYNC / ASYNC / BATCH
            plugin_name: 订阅者名（用于热卸载）
            priority:    数字越小越先调用
        """
        # 合并 event_type 和 filter：event_type 优先
        if event_type is not None:
            if filter is None:
                filter = EventFilter(event_type=event_type)
            else:
                # 复制 filter 并覆盖 event_type（避免修改入参）
                filter = filter.model_copy(update={"event_type": event_type})
        elif filter is None:
            # 都不给：订阅所有事件
            filter = EventFilter()

        sub = Subscription(
            subscription_id=str(uuid.uuid4()),
            event_filter=filter,
            handler=handler,
            mode=mode,
            plugin_name=plugin_name,
            priority=priority,
        )
        self._subscriptions.append(sub)
        self._subscriptions.sort(key=lambda s: s.priority)
        logger.debug(
            "[EventBus] Subscribed: id={} type={} mode={} plugin={}",
            sub.subscription_id, filter.event_type, mode, plugin_name,
        )
        return sub.subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """按 subscription_id 取消单条订阅。参数 subscription_id 为要移除的订阅唯一标识；返回 True 表示找到并移除，False 表示未找到。"""
        for i, sub in enumerate(self._subscriptions):
            if sub.subscription_id == subscription_id:
                self._subscriptions.pop(i)
                return True
        return False

    def unsubscribe_plugin(self, plugin_name: str) -> int:
        """按插件名批量取消其名下所有订阅（用于插件热卸载）。参数 plugin_name 为插件名；返回被移除的订阅数量。"""
        before = len(self._subscriptions)
        self._subscriptions = [
            s for s in self._subscriptions if s.plugin_name != plugin_name
        ]
        removed = before - len(self._subscriptions)
        if removed:
            logger.debug("[EventBus] Plugin unsubscribed: plugin={} removed={}", plugin_name, removed)
        return removed

    def list_subscriptions(self, plugin_name: Optional[str] = None) -> list[Subscription]:
        """列出当前所有订阅或按 plugin_name 过滤后的订阅快照。参数 plugin_name 可选，传入时仅返回该插件的订阅；返回 Subscription 列表（拷贝）。"""
        if plugin_name:
            return [s for s in self._subscriptions if s.plugin_name == plugin_name]
        return list(self._subscriptions)

    # ── 发布 ──────────────────────────────────────
    def publish(self, event: Any) -> None:
        """发布一个事件到总线，按订阅的 mode 派发（SYNC 同步调用、ASYNC 提交到线程池、BATCH 入队并在达到 batch_size 时刷新）。参数 event 为任意带 event_type 属性的对象；无返回值；副作用为触发匹配的 handler 或写入批量队列。"""
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
        """安全地调用 sub.handler(event)，handler 抛出的任何异常都会被 logger.exception 记录但不会向上传播，保证单个订阅出错不影响其他订阅。参数 sub 为目标订阅记录，event 为要分发的事件对象；无返回值。"""
        try:
            sub.handler(event)
        except Exception:
            logger.exception(
                "[EventBus] Handler error: sub_id={} event={} handler={}",
                sub.subscription_id, type(event).__name__,
                getattr(sub.handler, "__name__", repr(sub.handler)),
            )

    def _dispatch_async(self, sub: Subscription, event: Any) -> None:
        """将订阅 (sub, event) 提交到 _async_executor 线程池异步执行；若总线已 stop（executor 为 None）则回退为同步调用以避免事件丢失。参数 sub 为订阅记录，event 为事件对象；无返回值。"""
        # 修复 #8：用 ThreadPoolExecutor 提交，线程由池管理不再泄漏
        if self._async_executor is not None:
            self._async_executor.submit(self._safe_call, sub, event)
        else:
            # bus 已 stop，fallback 到同步执行避免丢失事件
            self._safe_call(sub, event)

    def _flush_batch(self) -> None:
        """将当前 _batch_queue 中的所有 (sub, event) 取出并逐个通过 _safe_call 同步派发，然后清空队列。空队列时直接返回；无入参；无返回值；副作用为消费批量队列。"""
        if not self._batch_queue:
            return
        queue, self._batch_queue = self._batch_queue, []
        for sub, event in queue:
            self._safe_call(sub, event)

    def start_batch_loop(self) -> None:
        """启动后台批处理循环线程：每 _batch_interval 秒调用一次 _flush_batch()。若已运行则直接返回；无入参；无返回值；副作用为启动一个守护线程。"""
        if self._running:
            return
        self._running = True

        def loop():
            """批处理循环线程主体：循环 _running 为 True 时每隔 _batch_interval 秒调用 _flush_batch()，无入参无返回值。"""
            while self._running:
                time.sleep(self._batch_interval)
                self._flush_batch()
        self._batch_thread = threading.Thread(target=loop, daemon=True)
        self._batch_thread.start()
        logger.debug("[EventBus] Batch loop started: interval={}s", self._batch_interval)

    def stop(self) -> None:
        """关闭事件总线：停止批处理循环、刷新剩余批量事件、关闭 ASYNC 线程池并等待 pending 任务完成。无入参；无返回值；幂等，调用后再次 _dispatch_async 会回退到同步。"""
        self._running = False
        self._flush_batch()
        # 修复 #8：关闭 ThreadPoolExecutor，确保 pending 任务完成
        if self._async_executor is not None:
            self._async_executor.shutdown(wait=True)
            self._async_executor = None
        logger.debug("[EventBus] Stopped")
