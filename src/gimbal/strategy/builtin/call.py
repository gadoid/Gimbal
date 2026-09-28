"""strategy/builtin/call.py — HTTP 协议适配器（CallExecutor，v2.1 批次 A 契约）。

2026-09-27 协议中立化（批次 0）+ 批次 A render/send 契约化：
  - build_spec = render：URL 拼装 + service 路由（D7 per-step 查表）；
  - send = 传输：HTTP_BEFORE_SEND 钩子（http 命名空间，可原地改写 headers）
    → httpx 传输 → CallResult（统一证据形状）；
  - after_send：HTTP_AFTER_RECV 钩子 + HttpRequest/HttpResponse 事件；
  - execute 为基类模板方法（双写 scratch：``call`` 键 + 旧键），本类不再覆写。

v2.1 终态契约（批次 F-2b：auth_headers/response_body_extract 已退役，
批次 F 回收）：
  - kind 自残留清理 #2 起为 "call"（S-2 后仅为结果标签,无注册键语义）；
  - HTTP_BEFORE_SEND payload 的 headers 与实际请求 headers 是**同一对象**，
    钩子原地改写必须影响真实请求；被 STOP 中断 → 不发请求，ERROR 结果
    （文案 "HTTP request blocked by hook"）；
  - 事件形状 HttpRequestEvent/HttpResponseEvent 字段不变；
  - scratch 唯一证据键 = call（v2.1 F 终态）；
  - 本模块的 logger 不搬迁（测试按模块 patch warning）。
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from gimbal.protocols.base import (
    ProtocolCallContext, ProtocolExecutor, ProtocolTransportError,
)
from gimbal.protocols.result import CallResult
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus

from gimbal.log import get_logger
logger = get_logger(__name__)


@dataclass
class _CallSpec:
    """HTTP 调用描述（render 产物）。不属于 schema。

    S-2 起不经过策略 dispatcher：计时/异常兜底由 ProtocolExecutor.execute
    模板承担。kind = "call"（残留 #2 起的规范标签）。
    埋点设施（协议层钩子/事件/认证）经执行器 bind 注入；pctx 只承载逐调数据。
    """

    kind: str = "call"
    method: str = "GET"
    url: str = ""
    headers: dict = field(default_factory=dict)
    # body 与 schema/request.py:Request.body 保持一致：
    # Union[str, Dict[str, Any], List[Any]] —— str body（text/xml、text/plain）、
    # list body（批量请求等场景）都合法。
    body: Union[str, dict, list] = field(default_factory=dict)
    timeout: float = 30.0
    name: Optional[str] = "http_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)
    # 协议执行上下文（埋点设施 + 路由表），由状态机 _do_call 注入
    pctx: Optional[ProtocolCallContext] = None


class CallExecutor(ProtocolExecutor):
    """http 协议适配器：render（路由）+ send（httpx 传输）+ after_send（钩子/事件）。

    由状态机在 INVOKING 阶段经 ProtocolRegistry 分派，传入 build_spec 产物
    _CallSpec；执行模板（含 scratch 双写与统一证据）在 ProtocolExecutor 基类。
    """

    protocol = "http"
    # 结果标签（残留 #2：历史 "_call" 改 "call"）
    kind = "call"

    # ── render：识别协议字段 → 合成 spec ─────────────────────

    def build_spec(self, call, pctx: ProtocolCallContext) -> Any:
        """把 call{protocol:'http'} 的开放字段合成为 _CallSpec。

        路由规则（D7 + 修复 #6）：api.service 先查 scenario.config.services
        声明 dict，未命中回落兼容 base_url；两者皆空 → 显式失败，不造幽灵 URL。
        路由失败返回 StrategyResult（不进 dispatch），由状态机直接采纳。
        """
        service = getattr(call, "service", None)
        if not service:
            return self._routing_error(
                pctx,
                message="api is missing the 'service' field required for routing",
                strategy_id="call",
            )
        method = getattr(call, "method", "GET")
        path = getattr(call, "path", "/")
        headers = dict(getattr(call, "headers", None) or {})
        timeout = float(getattr(call, "timeout", 30) or 30)
        # 默认 body 来自 step.request.body（状态机经 pctx.request_body 传入；
        # scratch 中被 Assign 改写过的值在 send 阶段优先）
        body = pctx.request_body if pctx.request_body is not None else {}

        service_url = (pctx.services or {}).get(service) or pctx.service_base_url
        if not service_url:
            return self._routing_error(
                pctx,
                message=(
                    f"no service_base_url configured; api.service={service!r} "
                    "is a service key, not a URL. Configure scenario.config.services "
                    "or bootstrap.services with a real base URL."
                ),
                strategy_id="http_call",
                service=service,
            )
        return _CallSpec(
            method=method,
            url=f"{service_url.rstrip('/')}{path}",
            headers=headers,
            body=body,
            timeout=timeout,
            pctx=pctx,
        )

    @staticmethod
    def _routing_error(pctx: Optional[ProtocolCallContext], *, message: str,
                       strategy_id: str, service: Any = None) -> StrategyResult:
        logger.error(
            "[SM {}] 缺少 service_base_url: service={!r}，"
            "请在 scenario.config.services 或 bootstrap.services 中配置",
            getattr(pctx, "step_id", "?"), service, message,
        )
        return StrategyResult(
            status=StrategyStatus.ERROR,
            strategy_id=strategy_id,
            message=message,
        )

    # ── 协议侧认证握手（S-2：login 并入适配器）─────────────────

    def login(self, user: str, pctx: Optional[ProtocolCallContext] = None) -> dict:
        """http 握手：按标签取会话，签名 token/timestamp 头（S-2）。

        契约与退役插件 auth_headers 逐字节一致（特征化用例钉死）：
        token = md5(f"{session.token}{timestamp}").hexdigest()（32-hex，
        随会话 token 变化）；timestamp = str(int(epoch 秒))。
        无标签 / 会话缺失 / token 空 → 空 dict（调用方跳过注入，不阻断）。
        """
        registry = getattr(self, "_auth_registry", None)
        if not user or registry is None:
            return {}
        session = registry.get(str(user))
        token = getattr(session, "token", None)
        if not token:
            logger.warning("[CallExecutor] call.user={!r} 会话缺失或未登录，跳过认证头注入", user)
            return {}
        import hashlib
        import time as _time
        timestamp = int(_time.time())
        return {
            "token": hashlib.md5(f"{token}{timestamp}".encode("utf-8")).hexdigest(),
            "timestamp": str(timestamp),
        }

    def _inject_auth_headers(self, headers: dict, pctx) -> None:
        """按 ``call.user`` 标签注入 login() 签名头（http 语义）。"""
        user = getattr(getattr(pctx, "call", None), "user", None)
        if not user:
            return
        signed = self.login(str(user), pctx)
        if not signed:
            return
        headers.update(signed)
        logger.debug("[CallExecutor] 已注入认证头: user={} ts={}", user, signed.get("timestamp"))

    # ── send：传输 ────────────────────────────────────────────

    def send(self, spec, view) -> CallResult:
        """http 传输：原生认证注入（call.user）→ httpx → CallResult。

        传输失败抛 ProtocolTransportError（历史文案保持）。
        """
        method = spec.method
        url = spec.url
        headers = spec.headers
        timeout = spec.timeout
        pctx = getattr(spec, "pctx", None)

        # 原生认证注入（批次 F-2b；原 auth_headers 插件的 HTTP_BEFORE_SEND 钩子退役）
        self._inject_auth_headers(headers, pctx)

        # 请求体通道（残留 #5：$.call.request.body 子树）
        # 注意：用 `is None` 而非 `not ...` —— 空 dict / 空 list 是合法的 request body，
        # 不应被 falsy 判定重新覆盖。
        if view.read_scratch("$.call.request.body") is None:
            view.write_scratch("$.call.request.body", spec.body)
        # 从 scratch 读取实时渲染的请求体（可能被 Assign 等策略修改过）
        body = view.read_scratch("$.call.request.body")

        try:
            import httpx

            logger.info("[CallExecutor] HTTP 请求: {} {}", method, url)

            self._emit_http_request(pctx, method, url, headers, body)

            t_start = time.monotonic()
            with httpx.Client(timeout=timeout) as client:
                # body 形态分发（阶段 1：新增 str 形态支持）：
                #   GET/HEAD  → params=  （向后兼容：dict/list/str 都走 query string）
                #   str body  → content= （原始文本通道，Content-Type 由 api.headers 控制）
                #   dict/list  → json=    （Content-Type: application/json，httpx 兜底）
                # 互斥传递：httpx 接受同时传 json= 和 content= 但后者会覆盖前者，
                # 所以必须 if/elif/else 分发，不能传多个参数。
                method_upper = method.upper()
                if method_upper in ("GET", "HEAD"):
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=body,
                    )
                elif isinstance(body, str):
                    # str body：原始文本通道
                    # Content-Type 完全由调用方在 api.headers 显式声明；
                    # 若未声明，httpx 默认 text/plain，建议显式。
                    if not headers or "Content-Type" not in headers:
                        logger.warning(
                            "[CallExecutor] str body 但 headers 缺少 Content-Type，"
                            "httpx 将使用 text/plain 兜底；"
                            "建议在 api.headers 显式声明（如 text/xml、application/xml）"
                        )
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        content=body.encode("utf-8"),
                    )
                else:
                    # dict/list：JSON 通道
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=body,
                    )
            duration_ms = (time.monotonic() - t_start) * 1000

            logger.info(
                "[CallExecutor] HTTP 响应: {} {} -> {} ({:.1f}ms)",
                method, url, response.status_code, duration_ms
            )

            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text

            # 401 = 凭证过期信号（v2.1 批次 D）：响应照常返回（断言可判），
            # auth_expired=True 交由执行器模板走 单飞刷新→重发一次
            auth_expired = response.status_code == 401
            return CallResult.build(
                protocol=self.protocol,
                request={
                    "method": method,
                    "url": url,
                    "headers": headers,
                    "body": body,
                    "timeout": timeout,
                },
                status=response.status_code,
                body=resp_body,
                meta={"headers": dict(response.headers)},
                elapsed_ms=duration_ms,
                auth_expired=auth_expired,
            )

        except ProtocolTransportError:
            raise
        except Exception as exc:
            # httpx.TimeoutException / RequestError 与其它异常统一翻译为传输失败
            logger.exception("[CallExecutor] 异常: {} {}", method, url)
            tb = traceback.format_exc()
            try:
                import httpx as _httpx
                if isinstance(exc, _httpx.TimeoutException):
                    raise ProtocolTransportError(f"Request timeout: {exc}", traceback_str=tb) from exc
                if isinstance(exc, _httpx.RequestError):
                    raise ProtocolTransportError(f"Request error: {exc}", traceback_str=tb) from exc
            except ImportError:
                pass
            raise ProtocolTransportError(str(exc), traceback_str=tb) from exc

    # ── 凭证刷新（批次 D）：按 call.user 标签单飞重认证 ────────

    def refresh_auth(self, pctx) -> bool:
        user = getattr(getattr(pctx, "call", None), "user", None)
        registry = getattr(self, "_auth_registry", None)
        if not user or registry is None:
            return False

        def _do_refresh():
            from gimbal.auth.manager import AuthManager
            AuthManager(registry).get_auth(str(user))

        try:
            executed = registry.singleflight_refresh(str(user), _do_refresh)
            logger.info("[CallExecutor] 凭证刷新: user={} 单飞执行={}", user, executed)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("[CallExecutor] 凭证刷新失败（仍按原样重发一次）: {}", exc)
            return True

    # ── after_send：http 命名空间钩子/事件（送达后）────────────

    def after_send(self, spec, view, call_result: CallResult, result: StrategyResult) -> None:
        """送达后扩展点（批次 F-2b：HTTP_AFTER_RECV 钩子退役，只剩事件）。"""
        pctx = getattr(spec, "pctx", None)
        self._emit_http_response(pctx, call_result)

    # ── http 命名空间埋点（payload/事件形状不变）──────────────

    def _emit_http_request(self, pctx, method: str, url: str, headers: dict, body) -> None:
        """向 event_bus 发送 HttpRequestEvent 事件（method、url、request_body、request_headers 浅拷贝）。"""
        bus = getattr(self, "_bus", None)
        if bus is None:
            return
        try:
            from gimbal.events.types import HttpRequestEvent
            bus.publish(HttpRequestEvent(
                step_id=getattr(pctx, "step_id", ""),
                method=method,
                url=url,
                request_body=body,
                request_headers=dict(headers or {}),
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit HTTP_REQUEST failed", getattr(pctx, "step_id", "?"))

    def _emit_http_response(self, pctx, call_result: CallResult) -> None:
        """向 event_bus 发送 HttpResponseEvent 事件；数据取自 CallResult。"""
        bus = getattr(self, "_bus", None)
        if bus is None:
            return
        try:
            from gimbal.events.types import HttpResponseEvent
            raw_status = call_result.status
            try:
                status_code = int(raw_status) if raw_status is not None else 0
            except (ValueError, TypeError):
                status_code = 0
            bus.publish(HttpResponseEvent(
                step_id=getattr(pctx, "step_id", ""),
                method=call_result.request.get("method", ""),
                url=call_result.request.get("url", ""),
                status_code=status_code,
                duration_ms=float(call_result.elapsed_ms or 0.0),
                response_body=call_result.body,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit HTTP_RESPONSE failed", getattr(pctx, "step_id", "?"))
