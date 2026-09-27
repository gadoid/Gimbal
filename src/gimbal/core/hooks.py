"""core/hooks.py

框架级 Hook 系统。

与 Event 的区别：
    Event   → 通知型（fire-and-forget），订阅者无法中断主流程
    Hook    → 介入型（interposable），订阅者可：
                 1. 读取/修改 payload（mutate in place）
                 2. 抛 STOP 异常中断主流程
                 3. 返回新对象替换 payload

设计原则：
    1. 主流程通过 HookTriggerer.fire(point, payload) 调用；
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
    """框架所有可埋点的位置。

    新增埋点：在此处加一个枚举值，然后在主流程中调用
        fire(HookPoint.XXX, payload)
    即可，无需修改其它任何代码。
    """
    # 框架生命周期
    FRAMEWORK_INIT = "framework.init"
    FRAMEWORK_TEARDOWN = "framework.teardown"

    # Run 生命周期
    RUN_START = "run.start"
    RUN_END = "run.end"

    # Suite 生命周期
    SUITE_START = "suite.start"
    SUITE_END = "suite.end"

    # Scenario 生命周期
    SCENARIO_START = "scenario.start"
    SCENARIO_END = "scenario.end"

    # Step 生命周期
    STEP_START = "step.start"
    STEP_END = "step.end"
    STEP_FAILED = "step.failed"

    # v2.1 批次 F-2b：HTTP_BEFORE_SEND/AFTER_RECV 钩子已退役——
    # 认证注入原生进 http 适配器（call.user），观察走 http.request/http.response 事件；
    # 中立拦截点 CALL_BEFORE_SEND/CALL_AFTER_RECV（Decision 通道）保留。

    # 协议调用前后（中立层，所有协议，由状态机 _do_call 触发；2026-09-27 协议中立化）
    CALL_BEFORE_SEND = "call.before_send"   # payload: {protocol, step_id, spec, request, ctx}
    CALL_AFTER_RECV = "call.after_recv"     # payload: {protocol, step_id, spec, result, ctx}

    # 拦截决策点（v2 §拦截 hook，批次 E；经 Decision 通道返回决策）
    STEP_BEFORE = "step.before"             # payload: {step_id, step_schema, ctx}
    # STEP_FAILED（"step.failed"）已存在；批次 E 起在 ScenarioRunner 层
    # 作为拦截决策点（CONTINUE/RETRY/SKIP/ABORT）触发

    # Strategy 调用前后
    STRATEGY_BEFORE = "strategy.before"     # payload: {strategy_name, phase, ctx}
    STRATEGY_AFTER = "strategy.after"       # payload: {strategy_name, phase, result, ctx}


# ── Hook Signal：可 raise 的异常类 ──────────────────────────────

class HookSignal:
    """hook 系统中可被 handler 抛出的信号集合。

    用法：
        def my_handler(payload):
            if some_condition:
                raise HookSignal.STOP("rate limited")   # 中断主流程
            mutate(payload)
    """
    pass


class _StopException(Exception):
    """handler 抛出后中断主流程的信号。

    携带的 reason 可以是字符串（兼容旧拦截者）或 Decision
    （core/decisions.py，批次 E 拦截决策通道）。
    """


# 把 Stop 挂在 HookSignal 下，类型上是 Exception 的子类（可 raise）
HookSignal.STOP = _StopException   # type: ignore[attr-defined]


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


# ── Hook 触发结果 ────────────────────────────────────────────────

@dataclass
class HookResult:
    """fire() 的返回值。

    - stopped:        是否被某个 handler 抛 STOP 中断
    - stop_reason:    停止原因（handler 抛 STOP 时可附带的字符串）
    - stop_plugin:    抛出 STOP 的插件名（用于审计/上报）
    - modified:       是否有 handler 返回了非 None 值（即替换了 payload）
                      注：in-place 修改（如 dict["k"]=v）需 handler 显式
                      return payload 才能被识别为 modified
    - errors:         执行期间 handler 异常列表（仅记录，不抛出）
    """
    stopped: bool = False
    stop_reason: Any = ""     # str（旧拦截者）或 Decision（批次 E 决策通道）
    stop_plugin: Optional[str] = None
    modified: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)

    def __bool__(self) -> bool:        # 方便 if not triggerer.fire(...): return 这样的写法
        """支持 `if not result` 这种写法：未中断时为 True（继续主流程）。"""
        return not self.stopped


# ── Hook Registry ────────────────────────────────────────────────

class HookRegistry:
    """Hook 注册表。

    线程安全（2026-09-27 多线程分派）：register/sort 与 trigger 并发时
    共享 _hooks 列表，统一用 RLock 保护；trigger 内联执行 handler 也在锁内
    （干预型 hook 语义 = 串行裁决，并行 scenario 下天然按到达顺序生效）。
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
    def trigger(self, point: HookPoint, payload: Any) -> HookResult:
        """触发 point 的所有 hook。

        payload 约定：dict 或 dataclass（属性可被 handler 直接修改）。
        返回 HookResult，调用方根据 stopped 决定是否继续。
        """
        result = HookResult()
        with self._lock:
            hooks = [h for h in self._hooks if h.point == point]

            if not hooks:
                return result

            logger.debug("[HookRegistry] Trigger %s: %d handler(s)", point.value, len(hooks))

            for h in hooks:
                try:
                    ret = h.handler(payload)
                    if ret is not None and payload is not None:
                        # 如果 handler 返回了新对象，替换 payload
                        payload = ret
                        # 修复 #15：仅当 handler 实际返回新对象（替换 payload）时才标记 modified
                        # 之前是"任何 handler 跑过就 modified=True"，误导消费者
                        result.modified = True
                    # in-place 修改（如 dict["k"]=v）需 handler 显式 return payload 才被识别
                except _StopException as sig:
                    result.stopped = True
                    # reason 兼容 str 与 Decision（批次 E）
                    result.stop_reason = sig.args[0] if sig.args else ""
                    result.stop_plugin = h.plugin_name
                    logger.info(
                        "[HookRegistry] STOP signal at %s from plugin=%s reason=%s",
                        point.value, h.plugin_name, result.stop_reason,
                    )
                    break
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "[HookRegistry] Handler error: point=%s plugin=%s handler=%s",
                        point.value, h.plugin_name, getattr(h.handler, "__name__", repr(h.handler)),
                    )
                    result.errors.append({
                        "point": point.value,
                        "plugin": h.plugin_name,
                        "handler": getattr(h.handler, "__name__", repr(h.handler)),
                        "error": str(e),
                    })
                    # 继续执行其它 hook
        return result

    def clear(self) -> None:
        """清空所有已注册的 hook（用于 shutdown 兜底清理）。"""
        with self._lock:
            self._hooks.clear()


# ── HookTriggerer：给主流程用的便利触发器 ──────────────────────

class HookTriggerer:
    """轻量级 fire 包装。

    用法：
        triggerer = HookTriggerer(registry)
        payload = {"request": req, "ctx": ctx}
        result = triggerer.fire(HookPoint.CALL_BEFORE_SEND, payload)
        if not result:
            return  # 被某个 hook 拦截
        # payload 已被 hook 改写，直接用
        send(payload["request"])
    """

    def __init__(self, registry: HookRegistry) -> None:
        """初始化触发器，绑定到一个 HookRegistry 实例。"""
        self._registry = registry

    def fire(self, point: HookPoint, payload: Any) -> HookResult:
        """在绑定的 registry 上触发指定 point 的所有 hook。返回 HookResult。"""
        return self._registry.trigger(point, payload)
