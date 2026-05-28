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
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional

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
    body: dict = field(default_factory=dict)
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

    @property
    def passed(self) -> bool:
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
    ) -> None:
        self._step_id = step_id
        self._step_schema = step_schema
        self._dispatcher = dispatcher
        self._view = view
        self._service_base_url = service_base_url
        self._on_transition = on_transition

        self._state: StepState = StepState.PENDING
        self._phase_results: list[PhaseResult] = []
        self._error: Optional[str] = None

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
        return self._state

    @property
    def phase_results(self) -> list[PhaseResult]:
        return list(self._phase_results)

    def run(self) -> StepRunResult:
        """驱动状态机运行直到终态，返回执行结果。"""
        t_start = datetime.utcnow()
        logger.info("[SM {}] 状态机开始执行", self._step_id)

        try:
            # 初始化 scratch.request_body（可能被 Assign 等策略修改）
            request_body = getattr(self._step_schema.request, "body", None) or {}
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

        duration_ms = (datetime.utcnow() - t_start).total_seconds() * 1000
        logger.info("[SM {}] 状态机执行完成: final_state={} duration_ms={:.2f}",
                    self._step_id, self._state.value, duration_ms)

        return StepRunResult(
            step_id=self._step_id,
            status=self._state.value,
            phase_results=self._phase_results,
            error=self._error,
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

        if pr.all_passed:
            logger.info("[SM {}] VERIFYING 阶段全部通过，进入 PASSED", self._step_id)
            return StepState.PASSED
        else:
            logger.warning("[SM {}] VERIFYING 阶段存在失败，进入 FAILED", self._step_id)
            return StepState.FAILED

    def _handle_teardown(self) -> StepState:
        """执行清理策略，决定最终终态。"""
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 TEARDOWN 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.TEARDOWN)
        self._phase_results.append(pr)

        # 前序阶段是否有失败
        had_failure = any(
            p.any_failed
            for p in self._phase_results[:-1]  # 排除刚加入的 teardown 结果
        )

        if had_failure or pr.any_failed:
            logger.warning("[SM {}] TEARDOWN 阶段完成，存在前置失败，进入 FAILED", self._step_id)
            return StepState.FAILED
        logger.info("[SM {}] TEARDOWN 阶段完成，进入 PASSED", self._step_id)
        return StepState.PASSED

    # ── 内部辅助 ──────────────────────────────────────────────────────────────

    def _run_phase(self, phase: str) -> PhaseResult:
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

        service_url = self._service_base_url or f"http://{api.service}"
        request = self._step_schema.request
        body = getattr(request, "body", {}) or {}

        # request_body 已由 run() 初始化到 scratch，BEFORE_REQUEST 阶段的 Assign 可能已修改它
        # 不再重复写入，避免覆盖 Assign 的修改

        call_spec = _CallSpec(
            method=api.method,
            url=f"{service_url.rstrip('/')}{api.path}",
            headers=api.headers or {},
            body=body,
            timeout=api.timeout,
        )
        logger.info("[SM {}] HTTP 请求: method={} url={} timeout={:.1f}s",
                    self._step_id, api.method, call_spec.url, api.timeout)
        result = self._dispatcher.dispatch(call_spec, self._view)
        logger.info("[SM {}] HTTP 响应: status={} duration_ms={:.2f}",
                    self._step_id, result.status, result.duration_ms)
        return result

    def _advance(self, to: StepState, *, reason: str = "") -> None:
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
        try:
            self._advance(to, reason=reason)
            return True
        except (InvalidTransitionError, AlreadyTerminalError):
            return False