"""protocols/base.py — 协议适配器抽象（v2 §3，v2.1 批次 A 契约）。

协议适配器 = "一种可注册进执行器的调用协议"的全部实现，契约三点：

  1. ``build_spec(call, pctx)``：**render** —— 把 step.call 的开放字段
     识别/校验并合成"渲染后的请求描述"（spec；URL 路由等协议细节在此完成）；
  2. ``send(spec, view) -> CallResult``：**send** —— 真实传输，返回统一
     证据形状 CallResult；传输失败抛 ProtocolTransportError（任何**送达**的
     响应——含 4xx/5xx——都是成功的调用，判定交给断言）；
  3. ``redact(request) -> dict``：证据脱敏（默认实现按敏感键名匹配）。

``execute()`` 是**模板方法，子类不再覆写**（v2 运行时口径）::

    build_spec(状态机已调) → CALL_BEFORE_SEND(中立钩子，可原地补丁)
    → 请求侧旧键 scratch → send → redact 复核
    → scratch 双写（``call`` 键 + 响应侧旧键）→ StrategyResult
    → after_send 扩展点（http 在此触发其命名空间钩子/事件）
    → CALL_AFTER_RECV + CallExchangeEvent

render 与 send 分开，是为了让 CALL_BEFORE_SEND 拦截（调试改待发请求）
有干净落点（v2 §3）。状态机（statemachine/engine.py `_do_call`）只做：
识别 protocol → build_spec → dispatcher 注册表分发，不含任何协议细节。

双读期声明（v2.1 批次 A-F）：scratch 同时保留旧键（response_* 等），
批次 F 回收；HTTP 命名空间钩子/事件留在 http 适配器内部不动的契约
（认证原生注入已替代 auth_headers 插件，批次 F-2b 完成）。

凭证并入协议（v2 ``login``）：批次 D 前置设计时落地；CallResult 预留
``auth_expired`` 字段。
"""
from __future__ import annotations

import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from gimbal.protocols.result import CallResult, redact_mapping
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

if TYPE_CHECKING:
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.call import Call

from gimbal.log import get_logger

logger = get_logger(__name__)

_MISSING = object()


@dataclass
class ProtocolCallContext:
    """build_spec 阶段的只读输入（状态机合成，随 spec 内嵌传递给 send）。

    为什么放进 ctx 再嵌进 spec：execute(spec, view) 的签名来自
    StrategyExecutor（dispatcher 统一分发），埋点设施（hooks/bus/step_id）
    只能经 spec 携带 —— spec 本就是每次调用现合成的，天然是载体。
    """

    call: "Call"                       # 归一化后的协议中立调用（开放字段）
    step_id: str = ""
    services: dict = field(default_factory=dict)   # scenario.config.services 查表
    service_base_url: str = ""                     # 兼容回落 base_url
    # step.request.body 的默认值（HTTP 语义：scratch request_body 未被
    # Assign 改写时的兜底请求体；其它协议自行解释）
    request_body: Any = None
    hook_registry: Any = None                      # 协议层钩子（可 None）
    event_bus: Any = None                          # 协议层事件（可 None）
    auth_registry: Any = None                      # 认证注册表（auth_expired 刷新；批次 D）


class ProtocolTransportError(Exception):
    """传输失败（连接/超时/被钩子拦截等"调用没有送达结果"的情形）。

    message 直接进 StrategyResult.message（http 的历史文案
    "Request timeout: ..." / "Request error: ..." 等由适配器翻译后抛出）；
    traceback_str 进 StrategyResult.error。
    """

    def __init__(self, message: str, *, traceback_str: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.traceback_str = traceback_str


class ProtocolExecutor(StrategyExecutor):
    """协议适配器基类（render/send 契约）。

    子类必须声明类属性 ``protocol`` 并实现 build_spec / send；
    可选覆写 redact（默认按敏感键名脱敏）与 after_send（送达后的协议
    命名空间扩展点，http 用于触发 HTTP_BEFORE/AFTER 与事件）。
    """

    protocol: str = ""

    def __init__(self) -> None:
        if not self.protocol:
            raise ValueError(
                f"{type(self).__name__} 必须声明非空类属性 protocol（协议注册表分派键）"
            )

    @property
    def kind(self) -> str:  # type: ignore[override]
        """dispatcher 注册键；http 覆写为 '_call' 保持历史兼容，其余为 '_call:{protocol}'。"""
        return f"_call:{self.protocol}"

    # ── 子类实现的契约点 ──────────────────────────────────────

    @abstractmethod
    def build_spec(self, call: "Call", pctx: ProtocolCallContext) -> Any:
        """render：把 step.call 的开放字段合成该协议的传输 spec。

        spec 需要 duck-type StrategyBase（kind/name/enabled/onFailure 等由
        dispatch 插装读取），并内嵌 pctx 供 send 使用。路由失败可直接返回
        StrategyResult（状态机采纳，不进 dispatch）。
        """
        raise NotImplementedError

    @abstractmethod
    def send(self, spec: Any, view: "StrategyContextView") -> CallResult:
        """send：执行真实传输，返回统一证据 CallResult。

        传输失败（连接/超时/被协议钩子拦截）抛 ProtocolTransportError；
        送达的响应无论业务状态如何都正常返回（判定交给断言）。
        """
        raise NotImplementedError

    def redact(self, request: dict) -> dict:
        """证据脱敏：默认按敏感键名匹配（authorization/cookie/token/...）。"""
        return redact_mapping(request)

    def refresh_auth(self, pctx: Optional[ProtocolCallContext]) -> bool:
        """凭证过期时的单飞刷新钩子（默认无刷新动作）。

        返回 True 表示已尝试刷新、值得重发一次（http 实现：按 call.user
        标签经 AuthRegistry 单飞重跑 AuthManager.get_auth；重发时
        _inject_auth_headers 用新 token 重新签名注入）。
        """
        return False

    def after_send(self, spec: Any, view: "StrategyContextView",
                   call_result: CallResult, result: StrategyResult) -> None:
        """送达后的协议命名空间扩展点（默认无操作）。

        http 适配器在此发送 http.response 事件；
        认证头在 send 内部原生注入（call.user → token/timestamp）。
        """
        return None

    # ── 模板方法（子类不再覆写）───────────────────────────────

    def execute(self, spec, view) -> StrategyResult:
        """调用模板：中立拦截 → 请求侧 scratch → send → 双写 → 结果 → 送达后扩展。"""
        pctx = getattr(spec, "pctx", None)
        step_id = getattr(pctx, "step_id", "") or ""

        # 中立拦截点 CALL_BEFORE_SEND（批次 E 升级为 Decision 通道）：
        # - payload.request 是 spec 可变字段的视图，拦截者原地改写即补丁；
        # - 或返回 Decision(patch={...})：标量覆盖（method/url/timeout）、
        #   headers 合并、body 覆盖；
        # - Decision(abort) → 不发请求（兼容旧 STOP 字符串拦截者）。
        from gimbal.core.decisions import Decision, ask_decision
        decision = ask_decision(
            getattr(pctx, "hook_registry", None), "CALL_BEFORE_SEND", {
                "protocol": self.protocol,
                "step_id": step_id,
                "spec": spec,
                "request": self._spec_request_view(spec),
                "ctx": view,
            })
        if decision.action == "abort":
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=self.kind,
                message=f"{self.protocol} call blocked by hook"
                        + (f": {decision.note}" if decision.note else ""),
            )
        if decision.patch:
            self._apply_patch(spec, decision.patch)

        t0 = time.monotonic()
        try:
            call_result = self.send(spec, view)
            if getattr(call_result, "auth_expired", False):
                # 凭证过期 → 单飞刷新 → 重发一次（v2 §调用与协议）
                if self.refresh_auth(pctx):
                    logger.info("[Protocol] auth_expired：已刷新凭证，重发一次: step_id={}",
                                getattr(pctx, "step_id", "?"))
                    call_result = self.send(spec, view)
        except ProtocolTransportError as exc:
            logger.warning(
                "[Protocol {}] 传输失败: step_id={} protocol={} message={}",
                step_id, step_id, self.protocol, exc.message,
            )
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=self.kind,
                message=exc.message,
                error=exc.traceback_str,
            )
        if not call_result.elapsed_ms:
            call_result.elapsed_ms = (time.monotonic() - t0) * 1000

        # 脱敏复核 + scratch 写统一证据形状（v2.1 批次 F：旧 scratch 键退役，
        # `call` 是唯一证据键；下游一律经 $.call.request/response 导航）
        call_result.request = self.redact(call_result.request or {})
        evidence = call_result.to_scratch()
        view.write_scratch("call", evidence)

        message = self._summary(call_result)
        result = StrategyResult(
            status=StrategyStatus.PASSED,
            strategy_id=self.kind,
            message=message,
            extracted={"call": evidence},
        )

        # 协议命名空间扩展点（http：http.response 事件）
        self.after_send(spec, view, call_result, result)

        # 中立钩子 CALL_AFTER_RECV + 事件信封（携带脱敏 CallResult）
        self._fire_hook(pctx, "CALL_AFTER_RECV", {
            "protocol": self.protocol,
            "step_id": step_id,
            "spec": spec,
            "result": result,
            "ctx": view,
        })
        self._emit_call_exchange(pctx, call_result, result)
        return result

    # ── 模板辅助 ─────────────────────────────────────────────

    @staticmethod
    def _apply_patch(spec: Any, patch: dict) -> None:
        """应用 CALL_BEFORE 补丁：标量覆盖、headers 合并、body 覆盖。"""
        for key in ("method", "url", "timeout"):
            if key in patch:
                setattr(spec, key, patch[key])
        if isinstance(patch.get("headers"), dict):
            spec.headers.update(patch["headers"])
        if "body" in patch:
            spec.body = patch["body"]
        logger.debug("[Protocol] CALL_BEFORE patch 已应用: keys={}", sorted(patch))

    @staticmethod
    def _spec_request_view(spec: Any) -> dict:
        """spec 的请求侧可变字段视图（同对象引用，原地改写即补丁）。"""
        view: dict = {}
        for attr in ("method", "url", "headers", "body", "timeout"):
            val = getattr(spec, attr, _MISSING)
            if val is not _MISSING:
                view[attr] = val
        return view

    def _summary(self, cr: CallResult) -> str:
        """StrategyResult 摘要：http 形态复现历史文案 "HTTP GET url -> 200"。"""
        method = (cr.request or {}).get("method", "")
        url = (cr.request or {}).get("url", "")
        if method or url:
            return f"{self.protocol.upper()} {method} {url} -> {cr.status}"
        return f"{self.protocol} call -> {cr.status}"

    @staticmethod
    def _fire_hook(pctx: Optional[ProtocolCallContext], point_name: str, payload: dict) -> bool:
        """触发中立钩子；返回 True 继续，False 表示被 STOP 中断。"""
        if pctx is None or pctx.hook_registry is None:
            return True
        try:
            from gimbal.core.hooks import HookPoint
            try:
                point = HookPoint[point_name]
            except KeyError:
                point = HookPoint(point_name)
        except (ValueError, ImportError):
            return True
        return not pctx.hook_registry.trigger(point, payload).stopped

    @staticmethod
    def _emit_call_exchange(pctx: Optional[ProtocolCallContext],
                            call_result: CallResult, result: StrategyResult) -> None:
        """发布 CallExchangeEvent（中立证据信封，携带脱敏后的 CallResult）。"""
        if pctx is None or pctx.event_bus is None:
            return
        try:
            from gimbal.events.types import CallExchangeEvent
            pctx.event_bus.publish(CallExchangeEvent(
                step_id=pctx.step_id,
                protocol=call_result.protocol,
                status=result.status.value if hasattr(result.status, "value") else str(result.status),
                message=(result.message or "")[:200],
                duration_ms=float(call_result.elapsed_ms or 0.0),
                evidence_keys=sorted((result.extracted or {}).keys()),
                result=call_result.to_evidence(),
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[Protocol {}] emit CALL_EXCHANGE failed", getattr(pctx, "step_id", "?"))
