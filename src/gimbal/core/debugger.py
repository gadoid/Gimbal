"""core/debugger.py — debugger 插件（v2 §调试，v2.1 批次 E）。

调试是一个插件，挂拦截点（STEP_BEFORE / CALL_BEFORE_SEND / STEP_FAILED；
STRATEGY_BEFORE 复用 dispatcher 现有 STOP→SKIP）；引擎的三个让步：
执行 Decision、调试档位挂起超时豁免（RuntimeControl.debug_mode）、
强制 parallel=1（CLI 装载时钳制）。

- 启用：仅当 Plan 为单单元且 n_runs=1（CLI --debug 校验）。
- 暂停策略 pause: none | on_failure（缺省）| every_step。
- 断点地址：``<step>[:before | call_before | <策略名>]``（策略名断点挂
  STRATEGY_BEFORE，批次 E v1 支持 before/call_before 两类）。
- 会话通道抽象 DebugSession：CLI 终端（回车继续 / q 退出 / r 读最近调用）
  与 server 命令端点（QueueSession）两种实现；测试用 ScriptedSession。
- 命令与结果记 ``debug.*`` 事件（paused / command / resumed）。
- 等待超时按 abort（QueueSession 可配；CLI 会话不设限）。
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Optional, Protocol

from gimbal.core.hooks import HookPoint, HookRegistry, HookSignal
from gimbal.core.decisions import Decision
from gimbal.log import get_logger

logger = get_logger(__name__)


class DebugSession(Protocol):
    """调试会话通道：展示（send）与收命令（recv，阻塞）。"""

    def send(self, text: str) -> None: ...

    def recv(self, timeout: Optional[float] = None) -> Optional[str]: ...


class CliSession:
    """终端极简会话（v1 口径）：回车=continue/下一步、q=abort、r=read。"""

    def send(self, text: str) -> None:
        print(text, flush=True)

    def recv(self, timeout: Optional[float] = None) -> Optional[str]:
        try:
            return input("(debug) 回车=继续 q=退出 r=查看 > ").strip() or "continue"
        except EOFError:
            return "abort"


class ScriptedSession:
    """测试用预编程序列会话：按序返回命令；耗尽后返回 'continue'。"""

    def __init__(self, commands: list[str]) -> None:
        self._commands = list(commands)
        self.log: list[str] = []

    def send(self, text: str) -> None:
        self.log.append(text)

    def recv(self, timeout: Optional[float] = None) -> Optional[str]:
        if not self._commands:
            return "continue"
        return self._commands.pop(0).strip() or "continue"


class QueueSession:
    """server 会话：命令经队列注入（POST /runs/{id}/debug），输出可取回。"""

    def __init__(self, timeout: float = 300.0) -> None:
        self._inbox: "queue.Queue[str]" = queue.Queue()
        self.output: list[str] = []
        self.timeout = timeout

    def send(self, text: str) -> None:
        self.output.append(text)

    def submit(self, command: str) -> None:
        self._inbox.put(command)

    def recv(self, timeout: Optional[float] = None) -> Optional[str]:
        try:
            return self._inbox.get(timeout=timeout if timeout is not None else self.timeout)
        except queue.Empty:
            return None

    def drain_output(self) -> list[str]:
        out, self.output = self.output, []
        return out


class DebuggerPlugin:
    """调试器（编程式装载：CLI --debug / server 请求体 debug 段）。

    不走 plugin.yaml 发现；activate 时把 handler 注册进 HookRegistry
    （plugin_name="debugger"），deactivate 清理。
    """

    NAME = "debugger"

    def __init__(
        self,
        *,
        pause: str = "on_failure",
        breakpoints: Optional[list[str]] = None,
        session: Optional[DebugSession] = None,
        event_bus: Any = None,
        wait_timeout: Optional[float] = None,
    ) -> None:
        if pause not in ("none", "on_failure", "every_step"):
            raise ValueError(f"未知 pause 策略: {pause!r}")
        self.pause = pause
        self.breakpoints = set(breakpoints or [])
        self.session: DebugSession = session or CliSession()
        self.event_bus = event_bus
        self.wait_timeout = wait_timeout
        self.hook_ids: list[str] = []
        self.paused_count = 0

    # ── 装载 / 卸载 ─────────────────────────────────────────

    def activate(self, hook_registry: HookRegistry) -> None:
        self.hook_ids = [
            hook_registry.register(
                HookPoint.STEP_BEFORE, self._on_step_before,
                plugin_name=self.NAME, description="debugger: step 前暂停/断点",
            ),
            hook_registry.register(
                HookPoint.CALL_BEFORE_SEND, self._on_call_before,
                plugin_name=self.NAME, description="debugger: 调用前断点/补丁",
            ),
            hook_registry.register(
                HookPoint.STEP_FAILED, self._on_step_failed,
                plugin_name=self.NAME, description="debugger: 失败时暂停（retry/skip）",
            ),
        ]
        logger.info("[debugger] 已装载: pause={} breakpoints={}", self.pause, sorted(self.breakpoints))

    def deactivate(self, hook_registry: HookRegistry) -> None:
        for hid in self.hook_ids:
            hook_registry.unregister(hid)
        self.hook_ids = []

    # ── 拦截 handler ─────────────────────────────────────────

    def _on_step_before(self, payload: dict) -> None:
        step_id = payload.get("step_id", "?")
        hit = self.pause == "every_step" or f"{step_id}:before" in self.breakpoints \
            or step_id in self.breakpoints
        if not hit:
            return None
        cmd, note = self._pause("step.before", step_id, payload)
        if cmd == "abort":
            raise HookSignal.STOP(Decision(action="abort", source="human", note=note))
        return None   # continue

    def _on_call_before(self, payload: dict) -> None:
        step_id = payload.get("step_id", "?")
        if f"{step_id}:call_before" not in self.breakpoints:
            return None
        cmd, note = self._pause("call.before", step_id, payload)
        if cmd == "abort":
            raise HookSignal.STOP(Decision(action="abort", source="human", note=note))
        return None

    def _on_step_failed(self, payload: dict) -> None:
        if self.pause not in ("on_failure", "every_step"):
            return None
        step_id = getattr(payload.get("result"), "step_id", "?")
        cmd, note = self._pause("step.failed", step_id, payload)
        if cmd in ("retry", "skip", "abort"):
            raise HookSignal.STOP(Decision(action=cmd, source="human", note=note))
        return None   # continue（记失败）

    # ── 暂停与命令循环 ───────────────────────────────────────

    def _pause(self, point: str, step_id: str, payload: dict) -> tuple[str, str]:
        """阻塞等一条命令；超时按 abort。返回 (命令, 附注)。"""
        self.paused_count += 1
        result = getattr(payload.get("result"), "error", None)
        head = f"[debug 暂停] {point} step={step_id}"
        if result:
            head += f" error={str(result)[:120]}"
        self.session.send(head)
        self._emit_event("paused", {"point": point, "step_id": step_id})

        cmd = self.session.recv(timeout=self.wait_timeout)
        if cmd is None:
            self.session.send("[debug] 等待超时，按 abort 处理")
            return "abort", "debug wait timeout"

        cmd = cmd.strip() or "continue"
        if cmd in ("r", "read"):
            call = self._latest_call(payload)
            self.session.send(f"[read] 最近调用证据: {call}")
            self._emit_event("command", {"point": point, "step_id": step_id, "cmd": "read"})
            # read 后继续等下一条
            return self._pause(point, step_id, payload)
        if cmd not in ("continue", "step", "c", "\n", "q", "quit", "abort",
                       "retry", "skip"):
            self.session.send(f"[debug] 未知命令 {cmd!r}（continue/step/q/r"
                              + ("/retry/skip" if point == "step.failed" else "")
                              + "）")
            self._emit_event("command", {"point": point, "step_id": step_id, "cmd": cmd, "unknown": True})
            return self._pause(point, step_id, payload)

        normalized = {"c": "continue", "step": "continue", "\n": "continue",
                      "q": "abort", "quit": "abort"}[cmd] if cmd in ("c", "step", "\n", "q", "quit") else cmd
        self._emit_event("command", {"point": point, "step_id": step_id, "cmd": normalized})
        self._emit_event("resumed", {"point": point, "step_id": step_id,
                                       "decision": normalized})
        return normalized, f"debugger:{normalized}"

    @staticmethod
    def _latest_call(payload: dict) -> Any:
        view = payload.get("ctx")
        getter = getattr(view, "read_scratch", None)
        if callable(getter):
            return getter("call")
        return None

    def _emit_event(self, kind: str, data: dict) -> None:
        if self.event_bus is None:
            return
        try:
            from gimbal.events.types import DebugSessionEvent
            self.event_bus.publish(DebugSessionEvent(
                kind=kind,
                point=data.get("point", ""),
                step_id=data.get("step_id", ""),
                decision=data.get("decision", ""),
                data=data,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[debugger] 事件发布失败（忽略）")
