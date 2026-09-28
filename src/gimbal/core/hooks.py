"""core/hooks.py

框架级 Hook 系统。

与 Event 的区别：
    Event   → 通知型（fire-and-forget），订阅者无法中断主流程
    Hook    → 介入型（interposable），订阅者可：
                 1. 读取/修改 payload（mutate in place）
                 2. 抛 STOP 异常中断主流程
                 3. 返回新对象替换 payload

设计原则：
    1. 主流程经 ask_decision（core/decisions.py）询问拦截点；
    2. 同一 HookPoint 下多个 handler 按 priority 升序执行；
    3. 任一 handler 抛 Stop 异常 → 立即终止后续 handler 与主流程；
    4. handler 异常被吞掉并记录，避免单个插件拖垮整个流程；
    5. plugin_name 用于热卸载（unregister_plugin）。
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── Hook Point 枚举 ─────────────────────────────────────────────

class HookPoint(str, Enum):
    """拦截埋点（S-3 二分后只保留拦截点；观察一律走事件总线）。

    新增拦截点：在此处加一个枚举值，主流程经 ``ask_decision`` 询问；
    观察（run/scenario/step 生命周期、http 收发）对应事件
    run.start / scenario.start / step.start / http.request / http.response …
    —— 订阅事件，不注册 hook。

    拦截点（v2 §拦截表；S-3 起 STRATEGY_AFTER 观察位退役）：
      STEP_BEFORE       step 进入 BEFORE_REQUEST 前     CONTINUE/SKIP/ABORT(+write)
      STRATEGY_BEFORE   单条策略执行前                  CONTINUE/SKIP
      CALL_BEFORE_SEND  render 之后、send 之前          CONTINUE(+patch)/ABORT
      CALL_AFTER_RECV   send 之后、AFTER_REQUEST 前     CONTINUE/RETRY/ABORT
      STEP_FAILED       step 失败后(ScenarioRunner 层)  CONTINUE/RETRY/SKIP/ABORT
      FRAMEWORK_INIT / FRAMEWORK_TEARDOWN  框架生命周期(bootstrap;无事件对位)
    """
    FRAMEWORK_INIT = "framework.init"
    FRAMEWORK_TEARDOWN = "framework.teardown"
    STEP_FAILED = "step.failed"
    CALL_BEFORE_SEND = "call.before_send"   # payload: {protocol, step_id, spec, request, ctx}
    CALL_AFTER_RECV = "call.after_recv"     # payload: {protocol, step_id, spec, result, ctx}
    STEP_BEFORE = "step.before"             # payload: {step_id, step_schema, ctx}
    STRATEGY_BEFORE = "strategy.before"     # payload: {strategy_name, phase, ctx}


# S-3：HookSignal.STOP 异常通道退役 —— handler 直接 **return Decision(...)**；
# 未返回（None）= continue。观察型 handler 请订阅事件总线（events.bus）。


# ── Hook 记录 ────────────────────────────────────────────────

@dataclass
class Hook:
    """一条 hook 注册记录。"""
    hook_id: str
    point: HookPoint
    handler: Callable[[Any], Any]
    priority: int = 100                        # 数字越小越先执行
    plugin_name: Optional[str] = None
    description: str = ""


# S-3：HookResult 退役 —— trigger 返回 ``list[Decision]``（core.decisions），
# 首个非 continue 决策即生效（decisions.effective）。handler 异常记录后继续。
# ── Hook Registry ────────────────────────────────────────────────

class HookRegistry:
    """Hook 注册表。

    线程安全：register/sort 与 trigger 并发时共享 _hooks 列表，锁内只做
    handler 快照，**执行在锁外**（debugger 阻塞等待会话输入时不再持锁，
    并行下其它线程可继续注册）。
    """

    def __init__(self) -> None:
        """初始化一个空的 hook 注册表（_hooks 列表 + RLock）。"""
        self._hooks: list[Hook] = []
        self._lock = threading.RLock()

    # ── 注册 ──
    def register(
        self,
        point: "HookPoint | str",
        handler: Callable[[Any], Any],
        *,
        priority: int = 100,
        plugin_name: Optional[str] = None,
        description: str = "",
    ) -> str:
        """注册一个 hook。返回 hook_id（用于注销）。

        point 接受 HookPoint 枚举或字符串（"http.before_send"）。
        """
        # 字符串 → HookPoint（更宽容的 API，与 PluginContext.register_hook 一致）
        if isinstance(point, str):
            point = HookPoint(point)
        h = Hook(
            hook_id=str(uuid.uuid4()),
            point=point,
            handler=handler,
            priority=priority,
            plugin_name=plugin_name,
            description=description,
        )
        with self._lock:
            self._hooks.append(h)
            # 按 (point, priority) 排序，point 同组内 priority 升序
            self._hooks.sort(key=lambda x: (x.point.value, x.priority))
        logger.debug(
            "[HookRegistry] Registered: point=%s priority=%d plugin=%s",
            point.value, priority, plugin_name,
        )
        return h.hook_id

    def unregister(self, hook_id: str) -> bool:
        """按 hook_id 注销单个 hook。返回是否成功（True = 找到并删除）。"""
        with self._lock:
            for i, h in enumerate(self._hooks):
                if h.hook_id == hook_id:
                    self._hooks.pop(i)
                    logger.debug("[HookRegistry] Unregistered: id=%s", hook_id)
                    return True
            return False

    def unregister_plugin(self, plugin_name: str) -> int:
        """按插件名批量注销其注册的所有 hook。返回被移除的数量。"""
        with self._lock:
            before = len(self._hooks)
            self._hooks = [h for h in self._hooks if h.plugin_name != plugin_name]
            removed = before - len(self._hooks)
        if removed:
            logger.info("[HookRegistry] Plugin hooks removed: plugin=%s removed=%d", plugin_name, removed)
        return removed

    def list_hooks(
        self,
        point: Optional[HookPoint] = None,
        plugin_name: Optional[str] = None,
    ) -> list[Hook]:
        """按 point 和/或 plugin_name 过滤查询已注册的 hook 列表。

        入参:
            point:       可选，按埋点点过滤。
            plugin_name: 可选，按注册插件名过滤。
        返回:
            匹配条件的 Hook 列表（拷贝，原列表不受影响）。
        """
        out = self._hooks
        if point:
            out = [h for h in out if h.point == point]
        if plugin_name:
            out = [h for h in out if h.plugin_name == plugin_name]
        return list(out)

    # ── 触发 ──
    def trigger(self, point: "HookPoint | str", payload: Any) -> "list[Any]":
        """触发拦截点，返回全部 handler 产出的 Decision 列表（S-3）。

        - handler **return Decision(...)** 即产出决策；None / 其它返回值 = continue；
        - **短路语义（上轮评审 #8 成文）**：任一 handler 返回 Decision 即停止
          后续 handler——先到者裁决（与旧 STOP break 一致；abort 后 debugger
          等后续拦截者不再执行）；
        - 锁内只做 handler 快照，**执行在锁外**（debugger 阻塞等待输入时
          不再持锁，其它线程可继续 register）；
        - handler 异常记录后继续执行后续 handler。
        """
        if isinstance(point, str):
            point = HookPoint(point)
        with self._lock:
            hooks = [h for h in self._hooks if h.point == point]
        if not hooks:
            return []
        logger.debug("[HookRegistry] Trigger %s: %d handler(s)", point.value, len(hooks))
        decisions: list[Any] = []
        for h in hooks:
            try:
                ret = h.handler(payload)
                if ret is not None:
                    decisions.append(ret)
                    break   # 短路:首个返回 Decision 的 handler 即裁决
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "[HookRegistry] Handler error: point=%s plugin=%s handler=%s",
                    point.value, h.plugin_name, getattr(h.handler, "__name__", repr(h.handler)),
                )
        return decisions

    def clear(self) -> None:
        """清空所有已注册的 hook（用于 shutdown 兜底清理）。"""
        with self._lock:
            self._hooks.clear()
