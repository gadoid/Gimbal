"""statemachine/engine.py

状态机是 Step 执行的主驱动。

设计原则：
  - 状态机持有执行所需的全部依赖（dispatcher、view、step schema）
  - 每个状态对应一个 handler，handler 执行完返回下一个状态
  - 状态机内部循环驱动，直到进入终态
  - 调用方只需要 sm.run()，不感知内部如何流转

流转表：
  PENDING
    └─→ BEFORE_REQUEST   执行 Assign 等前置策略
          ├─→ CALLING        策略全部通过
          └─→ TEARDOWN       hard-fail，跳过 HTTP
    CALLING               发出 HTTP 请求
          ├─→ AFTER_REQUEST  请求成功
          └─→ TEARDOWN       请求失败
    AFTER_REQUEST         执行 Extract 等后置策略
          ├─→ VERIFYING      策略全部通过
          └─→ TEARDOWN       hard-fail
    VERIFYING             执行 Assertion
          ├─→ PASSED         无 teardown 且全部通过
          ├─→ FAILED         无 teardown 且有失败
          └─→ TEARDOWN       有 teardown 策略（无论结果）
    TEARDOWN              执行清理策略
          ├─→ PASSED
          └─→ FAILED
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Optional, Union, Dict, List

from gimbal.statemachine.states import StepState, VALID_TRANSITIONS
from gimbal.statemachine.exceptions import InvalidTransitionError, AlreadyTerminalError
from gimbal.strategy.executor_base import PhaseResult, StrategyResult, StrategyStatus

if TYPE_CHECKING:
    from gimbal.context.views import StepContextAdapter
    from gimbal.schema.step import Step
    from gimbal.schema.strategy import StrategyPhase
    from gimbal.strategy.dispatcher import StrategyDispatcher
    
from gimbal.log import get_logger
logger = get_logger(__name__)

TransitionHook = Callable[[StepState, StepState, str], None]


# ── 内部 _CallSpec ────────────────────────────────────────────────────────────

@dataclass
class _CallSpec:
    """HTTP 调用描述，由状态机在 CALLING 阶段合成。不属于 schema。"""
    kind: str = "_call"
    method: str = "GET"
    url: str = ""
    headers: dict = field(default_factory=dict)
    # body 与 schema/request.py:Request.body 保持一致：
    # Union[str, Dict[str, Any], List[Any]] —— str body（text/xml、text/plain）、
    # list body（批量请求等场景）都合法。
    body: Union[str, Dict[str, Any], List[Any]] = field(default_factory=dict)
    timeout: float = 30.0
    name: Optional[str] = "http_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)


# ── 执行结果 ──────────────────────────────────────────────────────────────────

@dataclass
class StepRunResult:
    step_id: str
    status: str
    phase_results: list[PhaseResult] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    # 修复 #5：标记 step 失败的阶段（"calling"/"verifying"/"teardown"/None）
    # 方便 reporter 区分"网络失败"vs"断言失败"vs"清理失败"
    error_phase: Optional[str] = None

    @property
    def passed(self) -> bool:
        """返回 step 是否通过的布尔值：status == "passed"。"""
        return self.status == "passed"


# ── 状态机 ────────────────────────────────────────────────────────────────────

class StepStateMachine:
    """Step 执行状态机。

    持有执行所需的全部上下文，自己驱动整个流程。

    用法::

        sm = StepStateMachine(
            step_id="step-001",
            step_schema=step,
            dispatcher=dispatcher,
            view=view,
            service_base_url="http://user-service",
            services={"user-service": "http://user-service"},
        )
        result = sm.run()
    """

    def __init__(
        self,
        *,
        step_id: str,
        step_schema: "Step",
        dispatcher: "StrategyDispatcher",
        view: "StepContextAdapter",
        service_base_url: str = "",
        on_transition: Optional[TransitionHook] = None,
        hook_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        services: Optional[dict[str, str]] = None,
    ) -> None:
        self._step_id = step_id
        self._step_schema = step_schema
        self._dispatcher = dispatcher
        self._view = view
        self._service_base_url = service_base_url
        # D7 per-step 路由:api.service → 声明 URL 查表;空/未命中回落 base_url
        self._services = services or {}
        self._on_transition = on_transition
        # 埋点设施：可选，不传则不触发（保持向后兼容）
        self._hooks = hook_registry
        self._bus = event_bus

        self._state: StepState = StepState.PENDING
        self._phase_results: list[PhaseResult] = []
        self._error: Optional[str] = None
        self._error_phase: Optional[str] = None  # 修复 #5

        # handler 表：状态 → 处理函数，返回下一个状态
        self._handlers: dict[StepState, Callable[[], StepState]] = {
            StepState.BEFORE_REQUEST: self._handle_before_request,
            StepState.CALLING:        self._handle_calling,
            StepState.AFTER_REQUEST:  self._handle_after_request,
            StepState.VERIFYING:      self._handle_verifying,
            StepState.TEARDOWN:       self._handle_teardown,
        }

        logger.debug("[SM {}] StepStateMachine 初始化完成", self._step_id)

    # ── 公开接口 ──────────────────────────────────────────────────────────────

    @property
    def state(self) -> StepState:
        """返回当前状态机所处的 StepState 枚举值。"""
        return self._state

    @property
    def phase_results(self) -> list[PhaseResult]:
        """返回当前累积的阶段执行结果列表的浅拷贝（PhaseResult 列表）。"""
        return list(self._phase_results)

    def run(self) -> StepRunResult:
        """驱动状态机运行直到终态，返回执行结果。"""
        t_start = datetime.now(timezone.utc)
        logger.info("[SM {}] 状态机开始执行", self._step_id)

        # 埋点：STEP_START 事件
        self._emit_step_start()

        try:
            # 初始化 scratch.request_body（可能被 Assign 等策略修改）
            # body 现在可以是 Dict 或 List —— 不要用 `or {}` 兜底成 dict，
            # 那样会把 list body 静默改成 dict。
            request_body = getattr(self._step_schema.request, "body", None)
            if request_body:
                self._view.write_scratch("request_body", request_body)

            # 从 PENDING 推进到第一个执行阶段
            self._advance(StepState.BEFORE_REQUEST, reason="start")

            # 内部循环：每次调用当前状态的 handler，handler 返回下一个状态
            while not self._state.is_terminal:
                handler = self._handlers.get(self._state)
                if handler is None:
                    # 防御：没有 handler 的非终态，直接 ERROR
                    logger.warning("[SM {}] 无 handler for state={}，进入 ERROR 状态", self._step_id, self._state.value)
                    self._advance(StepState.ERROR, reason=f"no handler for {self._state.value}")
                    break
                next_state = handler()
                self._advance(next_state, reason=f"{self._state.value} done")

        except Exception as exc:
            logger.exception("[SM {}] 状态机执行异常: {}", self._step_id, exc)
            self._error = traceback.format_exc()
            self._try_advance(StepState.ERROR, reason=str(exc))

        duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
        logger.info("[SM {}] 状态机执行完成: final_state={} duration_ms={:.2f}",
                    self._step_id, self._state.value, duration_ms)

        # 埋点：STEP_END / STEP_FAILED 事件
        if self._state == StepState.FAILED or self._state == StepState.ERROR:
            self._emit_step_failed(self._error or f"final_state={self._state.value}")
        else:
            self._emit_step_end(duration_ms)

        return StepRunResult(
            step_id=self._step_id,
            status=self._state.value,
            phase_results=self._phase_results,
            error=self._error,
            error_phase=self._error_phase,  # 修复 #5
            duration_ms=duration_ms,
        )

    # ── 各状态 handler ────────────────────────────────────────────────────────

    def _handle_before_request(self) -> StepState:
        """执行前置策略（Assign / SQL 注入等）。"""
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 BEFORE_REQUEST 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.BEFORE_REQUEST)
        self._phase_results.append(pr)

        if pr.hard_failed:
            logger.warning("[SM {}] BEFORE_REQUEST 阶段 hard_failed，进入 TEARDOWN", self._step_id)
            return StepState.TEARDOWN   # 跳过 HTTP，直接清理
        logger.debug("[SM {}] BEFORE_REQUEST 阶段完成 all_passed={}，进入 CALLING", self._step_id, pr.all_passed)
        return StepState.CALLING

    def _handle_calling(self) -> StepState:
        """发出 HTTP 请求，把响应写入 context。"""
        logger.info("[SM {}] 开始 HTTP 请求", self._step_id)
        result = self._do_http_call()
        self._phase_results.append(PhaseResult(phase="calling", results=[result]))

        if result.failed:
            # 修复 #5：标记错误阶段为 "calling"，错误信息包含原始 message
            # 避免 reporter 把 HTTP 失败错误归因到"断言失败"
            self._error_phase = "calling"
            self._error = f"[calling] {result.message or 'HTTP request failed'}"
            logger.warning("[SM {}] HTTP 请求失败: status={} message={}，进入 TEARDOWN",
                          self._step_id, result.status, result.message)
            return StepState.TEARDOWN
        logger.info("[SM {}] HTTP 请求成功，进入 AFTER_REQUEST", self._step_id)
        return StepState.AFTER_REQUEST

    def _handle_after_request(self) -> StepState:
        """执行后置策略（Extract 提取字段等）。"""
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 AFTER_REQUEST 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.AFTER_REQUEST)
        self._phase_results.append(pr)

        if pr.hard_failed:
            logger.warning("[SM {}] AFTER_REQUEST 阶段 hard_failed，进入 TEARDOWN", self._step_id)
            return StepState.TEARDOWN
        logger.debug("[SM {}] AFTER_REQUEST 阶段完成 all_passed={}，进入 VERIFYING", self._step_id, pr.all_passed)
        return StepState.VERIFYING

    def _handle_verifying(self) -> StepState:
        """执行断言策略。"""
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 VERIFYING 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.VERIFYING)
        self._phase_results.append(pr)

        # 有 teardown 策略则必须进入 TEARDOWN（无论断言结果）
        if self._has_phase(StrategyPhase.TEARDOWN):
            logger.debug("[SM {}] 检测到 TEARDOWN 策略，进入 TEARDOWN", self._step_id)
            return StepState.TEARDOWN

        # 修复 #9：使用 hard_failed 而非 all_passed，soft 失败不阻断
        if pr.hard_failed:
            failed_strategy = next((r for r in pr.results if r.failed), None)
            self._error_phase = "verifying"
            self._error = (
                f"[verifying] {failed_strategy.message}"
                if failed_strategy and failed_strategy.message
                else "[verifying] assertion failed"
            )
            logger.warning(
                "[SM {}] VERIFYING 阶段存在硬失败: message={}，进入 FAILED",
                self._step_id, self._error,
            )
            return StepState.FAILED
        logger.info(
            "[SM {}] VERIFYING 阶段通过 (soft_failures={})，进入 PASSED",
            self._step_id, pr.any_failed,
        )
        return StepState.PASSED

    def _handle_teardown(self) -> StepState:
        """执行清理策略，决定最终终态（修复 B6：teardown 失败不污染业务结果）。

        语义：
          - 业务阶段（CALLING/VERIFYING）失败 → 终态 FAILED
          - 业务阶段全通过 + teardown 阶段失败 → 终态仍 PASSED
            （teardown 失败只记录到 error_phase="teardown"，不污染业务结果）
          - 业务阶段全通过 + teardown 阶段通过 → PASSED
        """
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 TEARDOWN 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.TEARDOWN)
        self._phase_results.append(pr)

        # 前序阶段（不含 teardown）是否有硬失败
        had_hard_failure = any(
            p.hard_failed
            for p in self._phase_results[:-1]
        )

        if had_hard_failure:
            logger.warning("[SM {}] TEARDOWN 阶段完成，业务阶段有硬失败，进入 FAILED", self._step_id)
            return StepState.FAILED

        # 业务阶段全通过：teardown 失败不污染终态（B6 修复）
        if pr.hard_failed:
            self._error_phase = "teardown"
            self._error = f"[teardown] cleanup failed: {pr.results[0].message if pr.results else 'unknown'}"
            logger.warning(
                "[SM {}] TEARDOWN 阶段失败但业务通过，标记为 PASSED with teardown_failure",
                self._step_id,
            )
            return StepState.PASSED

        logger.info(
            "[SM {}] TEARDOWN 阶段完成，进入 PASSED (soft_failures={})",
            self._step_id, pr.any_failed,
        )
        return StepState.PASSED

    # ── 内部辅助 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _body_shape(body: Any) -> str:
        """把 body 形态压缩成一行可读字符串，供日志展示。

        阶段 1 引入 str body 后，单纯用 keys()/str 会丢失形态信息。
        这里给出形态 + 长度（str 用字符数、list 用元素数、dict 用 key 数），
        便于排查时一眼区分。
        """
        if isinstance(body, dict):
            return f"dict[{len(body)}]"
        if isinstance(body, list):
            return f"list[{len(body)}]"
        if isinstance(body, str):
            return f"str[{len(body)}]"
        return type(body).__name__

    def _run_phase(self, phase: str) -> PhaseResult:
        """通过 dispatcher 分发执行指定 phase 的所有策略，返回聚合的 PhaseResult（包含所有 StrategyResult）。"""
        logger.debug("[SM {}] 执行策略阶段: phase={}", self._step_id, phase)
        results = self._dispatcher.dispatch_phase(
            phase, self._step_schema.strategy, self._view
        )
        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if r.failed)
        logger.debug("[SM {}] 策略阶段完成: phase={} total={} passed={} failed={}",
                    self._step_id, phase, len(results), passed_count, failed_count)
        return PhaseResult(phase=phase, results=results)

    def _has_phase(self, phase: str) -> bool:
        """检查 step schema 的 strategy 列表中是否至少存在一条 phase 等于 phase 的策略，返回布尔值。"""
        return any(
            getattr(s, "phase", None) == phase
            for s in self._step_schema.strategy
        )

    def _do_http_call(self) -> StrategyResult:
        """合成 _CallSpec 交给 CallExecutor 执行。"""
       # from gimbal.context.base import ContextLayer

        api = self._step_schema.api
        if not hasattr(api, "service"):
            logger.error("[SM {}] API 是未解析的 Ref", self._step_id)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message="api is a ref that was not resolved before execution",
            )

        # D7 per-step 路由 + 修复 #6:先查场景声明 dict(api.service 是
        # config.services 的 key),未命中回落兼容 _service_base_url
        # (_pick_base_url 兼容路径);两者皆空 → 显式失败,不造幽灵 URL。
        service_url = self._services.get(api.service) or self._service_base_url
        if not service_url:
            logger.error(
                "[SM {}] 缺少 service_base_url: api.service={!r}，"
                "请在 scenario.config.services 或 bootstrap.services 中配置",
                self._step_id, api.service,
            )
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id="http_call",
                message=(
                    f"no service_base_url configured; api.service={api.service!r} "
                    "is a service key, not a URL. Configure scenario.config.services "
                    "or bootstrap.services with a real base URL."
                ),
            )
        request = self._step_schema.request
        # body 可以是 Dict 或 List —— 不要用 `or {}` 兜底成 dict，会把 list 静默改成 dict。
        original_body = getattr(request, "body", None)

        # 修复 B2：BEFORE_REQUEST 阶段的 Assign 写到 view.scratch.request_body，
        # 这里优先取 scratch 的值（被 Assign 修改后的），没有则用原 body
        scratch_body = self._view.read_scratch("request_body")
        if scratch_body is not None:
            body = scratch_body
        else:
            body = original_body

        call_spec = _CallSpec(
            method=api.method,
            url=f"{service_url.rstrip('/')}{api.path}",
            headers=api.headers or {},
            body=body,
            timeout=api.timeout,
        )
        logger.info("[SM {}] HTTP 请求: method={} url={} timeout={:.1f}s body_shape={}",
                    self._step_id, api.method, call_spec.url, api.timeout,
                    self._body_shape(body))

        # 埋点：HTTP_REQUEST 事件 + HTTP_BEFORE_SEND hook（可改写 call_spec）
        self._emit_http_request(call_spec)
        if not self._fire_hook("HTTP_BEFORE_SEND", {
            "method": call_spec.method,
            "url": call_spec.url,
            "headers": call_spec.headers,
            "body": call_spec.body,
            "timeout": call_spec.timeout,
            "step_id": self._step_id,
            "ctx": self._view,
        }):
            # hook 中断：返回错误结果
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message="HTTP request blocked by hook",
            )

        result = self._dispatcher.dispatch(call_spec, self._view)
        logger.info("[SM {}] HTTP 响应: status={} duration_ms={:.2f}",
                    self._step_id, result.status, result.duration_ms)

        # 埋点：HTTP_RESPONSE 事件 + HTTP_AFTER_RECV hook（可改写 result）
        self._emit_http_response(call_spec, result)
        self._fire_hook("HTTP_AFTER_RECV", {
            "method": call_spec.method,
            "url": call_spec.url,
            "status": result.status,
            "headers": getattr(result, "headers", {}),
            "body": getattr(result, "body", None),
            "duration_ms": getattr(result, "duration_ms", 0.0),
            "step_id": self._step_id,
            "ctx": self._view,
        })
        return result

    def _advance(self, to: StepState, *, reason: str = "") -> None:
        """从当前状态合法地转换到 to：校验在 VALID_TRANSITIONS 白名单内，触发 on_transition 回调（日志告警吞错），更新 self._state；非法抛 InvalidTransitionError。

        Args:
            to: 目标 StepState
            reason: 转换原因，仅用于日志与回调
        """
        allowed = VALID_TRANSITIONS.get(self._state, frozenset())
        if to not in allowed:
            raise InvalidTransitionError(self._state.value, to.value)
        if self._on_transition:
            try:
                self._on_transition(self._state, to, reason)
            except Exception:
                logger.warning(
                    "[SM {}] 状态转换回调异常: {} → {} ({})",
                    self._step_id, self._state.value, to.value, reason,
                )
        logger.debug("[SM {}] 状态转换: {} → {} ({})", self._step_id, self._state.value, to.value, reason)
        self._state = to

    def _try_advance(self, to: StepState, *, reason: str = "") -> bool:
        """包装 _advance：捕获 InvalidTransitionError / AlreadyTerminalError 时返回 False，成功推进返回 True。"""
        try:
            self._advance(to, reason=reason)
            return True
        except (InvalidTransitionError, AlreadyTerminalError):
            return False

    # ── 埋点辅助 ──────────────────────────────────────────────────────

    def _fire_hook(self, point_name: str, payload: dict) -> bool:
        """触发 hook。返回 True 表示继续，False 表示被 STOP 中断。

        point_name 可以是 HookPoint 枚举的名字（如 "HTTP_BEFORE_SEND"），
        也可以是它的 value（如 "http.before_send"）。
        """
        if self._hooks is None:
            return True
        try:
            from gimbal.core.hooks import HookPoint
            # 优先按枚举名查（"HTTP_BEFORE_SEND"），再按 value 查（"http.before_send"）
            try:
                point = HookPoint[point_name]
            except KeyError:
                point = HookPoint(point_name)
        except (ValueError, ImportError):
            return True
        result = self._hooks.trigger(point, payload)
        return not result.stopped

    def _emit_step_start(self) -> None:
        """向 event_bus 发送 StepStartEvent 事件（含 step_id / step_name / description）；无 bus 时静默 return，内部异常仅 debug 日志。"""
        if self._bus is None:
            return
        try:
            from gimbal.events.types import StepStartEvent
            self._bus.publish(StepStartEvent(
                step_id=self._step_id,
                step_name=getattr(self._step_schema, "name", "") or self._step_id,
                description=getattr(self._step_schema, "description", None),
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit STEP_START failed", self._step_id)

    def _emit_step_end(self, duration_ms: float) -> None:
        """向 event_bus 发送 StepEndEvent 事件（step_id、status、duration_ms）；无 bus 静默 return，内部异常仅 debug 日志。"""
        if self._bus is None:
            return
        try:
            from gimbal.events.types import StepEndEvent
            self._bus.publish(StepEndEvent(
                step_id=self._step_id,
                status=self._state.value,
                duration_ms=duration_ms,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit STEP_END failed", self._step_id)

    def _emit_step_failed(self, error: str) -> None:
        """向 event_bus 发送 StepFailedEvent 事件（error 截断 500 字符，phase 为当前 state）；无 bus 静默 return，内部异常仅 debug 日志。"""
        if self._bus is None:
            return
        try:
            from gimbal.events.types import StepFailedEvent
            self._bus.publish(StepFailedEvent(
                step_id=self._step_id,
                error=error[:500] if error else "",
                phase=self._state.value,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit STEP_FAILED failed", self._step_id)

    def _emit_http_request(self, call_spec: "_CallSpec") -> None:
        """向 event_bus 发送 HttpRequestEvent 事件（method、url、request_body、request_headers 浅拷贝）；无 bus 静默 return，内部异常仅 debug 日志。"""
        if self._bus is None:
            return
        try:
            from gimbal.events.types import HttpRequestEvent
            self._bus.publish(HttpRequestEvent(
                step_id=self._step_id,
                method=call_spec.method,
                url=call_spec.url,
                request_body=call_spec.body,
                request_headers=dict(call_spec.headers or {}),
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit HTTP_REQUEST failed", self._step_id)

    def _emit_http_response(self, call_spec: "_CallSpec", result: StrategyResult) -> None:
        """向 event_bus 发送 HttpResponseEvent 事件（method、url、status_code 非数字安全 fallback 0、duration_ms、response_body）；无 bus 静默 return，内部异常仅 debug 日志。"""
        if self._bus is None:
            return
        try:
            from gimbal.events.types import HttpResponseEvent
            # 防御：HTTP 失败时 result.status 是字符串（"timeout"/"RequestError"），
            # int() 会抛 ValueError 吞掉整个事件；只把能转 int 的状态码写事件
            raw_status = getattr(result, "status", None)
            try:
                status_code = int(raw_status) if raw_status is not None else 0
            except (ValueError, TypeError):
                status_code = 0
            self._bus.publish(HttpResponseEvent(
                step_id=self._step_id,
                method=call_spec.method,
                url=call_spec.url,
                status_code=status_code,
                duration_ms=float(getattr(result, "duration_ms", 0.0) or 0.0),
                response_body=getattr(result, "body", None),
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[SM {}] emit HTTP_RESPONSE failed", self._step_id)