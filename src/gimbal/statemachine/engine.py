"""statemachine/engine.py

状态机是 Step 执行的主驱动。

设计原则：
  - 状态机持有执行所需的全部依赖（dispatcher、view、step schema）
  - 每个状态对应一个 handler，handler 执行完返回下一个状态
  - 状态机内部循环驱动，直到进入终态
  - 调用方只需要 sm.run()，不感知内部如何流转

协议中立化（2026-09-27）：
  - 状态机不再内置任何协议细节；INVOKING（历史名 CALLING）阶段的调用
    经 `_do_call` 三段式分派：识别 protocol（ProtocolRegistry）→
    build_spec（协议执行器合成传输描述）→ dispatcher 注册表分发。
  - HTTP 的 URL 拼装/路由与 HTTP 命名空间钩子/事件已迁入
    strategy/builtin/call.py 的 CallExecutor（http 协议执行器）。
  - 状态机只触发**中立层**钩子（CALL_BEFORE_SEND/AFTER_RECV，所有协议）
    与中立事件信封（CallExchangeEvent，E1 带 protocol 字段）。

流转表（中立名 / 历史别名，value 不变）：
  PENDING
    └─→ PREPARE                执行 Assign 等前置策略
          ├─→ INVOKING(CALLING)    策略全部通过
          └─→ TEARDOWN             hard-fail，跳过协议调用
    INVOKING(CALLING)           发出协议调用（ProtocolRegistry 分派）
          ├─→ EXTRACTING            调用成功
          └─→ TEARDOWN             调用失败
    EXTRACTING                执行 Extract 等后置策略
          ├─→ VERIFYING            策略全部通过
          └─→ TEARDOWN             hard-fail
    VERIFYING                   执行 Assertion
          ├─→ PASSED               无 teardown 且全部通过
          ├─→ FAILED               无 teardown 且有失败
          └─→ TEARDOWN             有 teardown 策略（无论结果）
    TEARDOWN                    执行清理策略
          ├─→ PASSED
          └─→ FAILED
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
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


# ── 历史兼容 re-export ────────────────────────────────────────────────────────
# _CallSpec 的实现本体已随 http 协议执行器迁至 strategy/builtin/call.py；
# 此处 re-export 维持 `from gimbal.statemachine.engine import _CallSpec` 可用。
from gimbal.strategy.builtin.call import _CallSpec  # noqa: F401  (兼容导入)

from gimbal.protocols.base import ProtocolCallContext
from gimbal.protocols.result import CallResult


@lru_cache(maxsize=1)
def _default_protocols():
    """兜底协议注册表（仅 http）：给 __new__ 直填字段构造 / 未注入注册表的状态机用。

    bootstrap 正常链路注入的是含插件协议的实例；本兜底与 ProtocolRegistry
    默认表内容一致（http 第一员）。
    """
    from gimbal.protocols.registry import build_default_protocol_registry
    return build_default_protocol_registry()


# ── 执行结果 ──────────────────────────────────────────────────────────────────

@dataclass
class StepRunResult:
    step_id: str
    status: str
    phase_results: list[PhaseResult] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    # 修复 #5：标记 step 失败的阶段（"calling"/"verifying"/"teardown"/None）
    # 方便 reporter 区分"调用失败"vs"断言失败"vs"清理失败"
    # （value 保持 "calling" 不变——报告/台账的历史口径）
    error_phase: Optional[str] = None
    # v2.1 批次 E：人工 retry（debugger 会话）后通过的标记——不计正常通过率
    repaired: bool = False

    @property
    def passed(self) -> bool:
        """返回 step 是否通过的布尔值：status == "passed"。"""
        return self.status == "passed"


# ── 状态机 ────────────────────────────────────────────────────────────────────

class StepStateMachine:
    """Step 执行状态机（协议中立）。

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
        protocol_registry: Optional[Any] = None,
        auth_registry: Optional[Any] = None,
    ) -> None:
        self._step_id = step_id
        self._step_schema = step_schema
        self._dispatcher = dispatcher
        self._view = view
        self._service_base_url = service_base_url
        # D7 per-step 路由:call.service → 声明 URL 查表;空/未命中回落 base_url
        self._services = services or {}
        self._on_transition = on_transition
        # 埋点设施：可选，不传则不触发（保持向后兼容）
        self._hooks = hook_registry
        self._bus = event_bus
        # 协议注册表：INVOKING 阶段按 step.call.protocol 分派；
        # None 时兜底默认表（仅 http，兼容直构造场景）
        self._protocols = protocol_registry
        # 认证注册表（批次 D：auth_expired 单飞刷新经 pctx 传给协议适配器）
        self._auth_registry = auth_registry

        self._state: StepState = StepState.PENDING
        self._phase_results: list[PhaseResult] = []
        self._error: Optional[str] = None
        self._error_phase: Optional[str] = None  # 修复 #5

        # handler 表：状态 → 处理函数，返回下一个状态
        # （键用中立名；历史别名是同一成员，查表互通）
        self._handlers: dict[StepState, Callable[[], StepState]] = {
            StepState.PREPARE:     self._handle_prepare,
            StepState.INVOKING:    self._handle_invoking,
            StepState.EXTRACTING:  self._handle_extracting,
            StepState.VERIFYING:   self._handle_verifying,
            StepState.TEARDOWN:    self._handle_teardown,
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

        try:
            # 拦截决策点 STEP_BEFORE（批次 E）：SKIP → 直接终态跳过；
            # ABORT → 框架级中止；continue → 正常流转
            from gimbal.core.decisions import ask_decision
            from gimbal.core.hooks import HookPoint
            pre = ask_decision(self._hooks, HookPoint.STEP_BEFORE, {
                "step_id": self._step_id,
                "step_schema": self._step_schema,
                "ctx": self._view,
            })
            if pre.action == "skip":
                logger.info("[SM {}] STEP_BEFORE 决策 skip，整步跳过", self._step_id)
                self._try_advance(StepState.SKIPPED, reason="step.before skip")
                duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
                return StepRunResult(
                    step_id=self._step_id, status=self._state.value,
                    duration_ms=duration_ms,
                )
            if pre.action == "abort":
                self._error = f"[step.before] aborted: {pre.note or 'by interceptor'}"
                self._try_advance(StepState.ERROR, reason="step.before abort")
                duration_ms = (datetime.now(timezone.utc) - t_start).total_seconds() * 1000
                self._emit_step_failed(self._error)
                return StepRunResult(
                    step_id=self._step_id, status=self._state.value,
                    error=self._error, duration_ms=duration_ms,
                )
            # P1-10：continue 决策携带 write（debugger write 命令）→
            # 注入 scratch 变量后继续——后续 Assign/调用/断言即见新值
            if pre.write:
                for key, value in pre.write.items():
                    self._view.write_scratch(key, value)
                logger.info("[SM {}] STEP_BEFORE write 注入 scratch: keys={}",
                            self._step_id, sorted(pre.write))

            # 初始化请求体 scratch（残留 #5：统一 $.call.request.body 子树，
            # 可能被 Assign 等策略修改）；body 可为 Dict/List —— 不用 `or {}`
            # 兜底，避免把 list body 静默改成 dict。
            request_body = getattr(getattr(self._step_schema, "request", None), "body", None)
            if request_body:
                self._view.write_scratch("$.call.request.body", request_body)

            # 从 PENDING 推进到第一个执行阶段
            self._advance(StepState.PREPARE, reason="start")

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

        # 埋点：STEP_FAILED 事件（step.start/end 由 ContextManager 投影发布）
        if self._state == StepState.FAILED or self._state == StepState.ERROR:
            self._emit_step_failed(self._error or f"final_state={self._state.value}")

        return StepRunResult(
            step_id=self._step_id,
            status=self._state.value,
            phase_results=self._phase_results,
            error=self._error,
            error_phase=self._error_phase,  # 修复 #5
            duration_ms=duration_ms,
        )

    # ── 各状态 handler ────────────────────────────────────────────────────────

    def _handle_prepare(self) -> StepState:
        """执行前置策略（Assign / SQL 注入等，协议无关）。"""
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 PREPARE 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.PREPARE)
        self._phase_results.append(pr)

        if pr.hard_failed:
            logger.warning("[SM {}] PREPARE 阶段 hard_failed，进入 TEARDOWN", self._step_id)
            return StepState.TEARDOWN   # 跳过协议调用，直接清理
        logger.debug("[SM {}] PREPARE 阶段完成 all_passed={}，进入 INVOKING", self._step_id, pr.all_passed)
        return StepState.INVOKING

    def _handle_invoking(self) -> StepState:
        """发出协议调用（ProtocolRegistry 分派），把结果写入 context。"""
        logger.info("[SM {}] 开始协议调用", self._step_id)
        result = self._do_call()
        self._phase_results.append(PhaseResult(phase="calling", results=[result]))

        if result.failed:
            # 修复 #5：标记错误阶段为 "calling"，错误信息包含原始 message
            # 避免 reporter 把调用失败错误归因到"断言失败"
            self._error_phase = "calling"
            self._error = f"[calling] {result.message or 'protocol call failed'}"
            logger.warning("[SM {}] 协议调用失败: status={} message={}，进入 TEARDOWN",
                          self._step_id, result.status, result.message)
            return StepState.TEARDOWN
        logger.info("[SM {}] 协议调用成功，进入 EXTRACTING", self._step_id)
        return StepState.EXTRACTING

    def _handle_extracting(self) -> StepState:
        """执行后置策略（Extract 提取字段等）。"""
        from gimbal.schema.strategy import StrategyPhase

        logger.debug("[SM {}] 进入 EXTRACTING 阶段", self._step_id)
        pr = self._run_phase(StrategyPhase.EXTRACTING)
        self._phase_results.append(pr)

        if pr.hard_failed:
            logger.warning("[SM {}] EXTRACTING 阶段 hard_failed，进入 TEARDOWN", self._step_id)
            return StepState.TEARDOWN
        logger.debug("[SM {}] EXTRACTING 阶段完成 all_passed={}，进入 VERIFYING", self._step_id, pr.all_passed)
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
          - 业务阶段（INVOKING/VERIFYING）失败 → 终态 FAILED
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

    def _do_call(self) -> StrategyResult:
        """协议调用三段式：识别 protocol → build_spec → 执行器模板直调（S-2）。

        1. 识别：step.call.protocol（归一化后恒有值）→ ProtocolRegistry.resolve；
        2. 合成：协议执行器把 call 开放字段合成为传输 spec（含路由），
           路由期失败直接返回 StrategyResult（不进 dispatch）；
        3. 直调：executor.execute 模板（计时/异常兜底/中立 CALL_BEFORE_SEND/
           AFTER_RECV 钩子均在模板内；S-2 起不经策略 dispatcher）。
        """
        call = getattr(self._step_schema, "call", None)
        if call is None:
            logger.error("[SM {}] step 缺少 call 声明，无法调用", self._step_id)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message="step has no call declaration",
            )

        # __new__ 直填字段构造的状态机没有 _protocols 属性，兜底默认表
        protocols = getattr(self, "_protocols", None) or _default_protocols()
        executor = protocols.resolve(call.protocol)
        if executor is None:
            logger.error(
                "[SM {}] 未注册的协议: protocol={!r}，已注册={}",
                self._step_id, call.protocol, protocols.protocols(),
            )
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=f"call:{call.protocol}",
                message=(
                    f"No protocol executor registered for protocol={call.protocol!r}; "
                    f"registered={protocols.protocols()}"
                ),
            )

        pctx = ProtocolCallContext(
            call=call,
            step_id=self._step_id,
            services=self._services,
            service_base_url=self._service_base_url,
            request_body=getattr(getattr(self._step_schema, "request", None), "body", None),
        )

        # 第一+二段：识别协议字段 → 合成 spec（路由失败在此返回）
        spec = executor.build_spec(call, pctx)
        if isinstance(spec, StrategyResult):
            return spec

        logger.info("[SM {}] 协议调用: protocol={} executor={} kind={}",
                    self._step_id, call.protocol, type(executor).__name__,
                    getattr(spec, "kind", "?"))

        # 第三段：ProtocolRegistry 直调执行器模板（S-2：不经策略 dispatcher）。
        # 模板内部完成：中立钩子 CALL_BEFORE_SEND（可补丁）→ send →
        # scratch 双写（call 键）→ CALL_AFTER_RECV + CallExchangeEvent；
        # 计时与异常兜底同在模板内；http 命名空间钩子/事件在适配器自己的
        # send/after_send 里（v2.1 批次 A 契约）。
        result = executor.execute(spec, self._view)
        logger.info("[SM {}] 协议调用返回: protocol={} status={} duration_ms={:.2f}",
                    self._step_id, call.protocol, result.status, result.duration_ms)
        return result

    # 历史名兼容：既有调用方/测试直接调 _do_http_call
    _do_http_call = _do_call

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

        point_name 可以是 HookPoint 枚举的名字（如 "CALL_BEFORE_SEND"），
        也可以是它的 value（如 "call.before_send"）。
        """
        if self._hooks is None:
            return True
        try:
            from gimbal.core.hooks import HookPoint
            # 优先按枚举名查（"CALL_BEFORE_SEND"），再按 value 查（"call.before_send"）
            try:
                point = HookPoint[point_name]
            except KeyError:
                point = HookPoint(point_name)
        except (ValueError, ImportError):
            return True
        from gimbal.core.decisions import effective
        return effective(self._hooks.trigger(point, payload)).action == "continue"

    # HTTP 事件兼容委托：职责在 http 协议适配器（CallExecutor._emit_http_*），
    # 历史直调方（tests/unit/test_defect_fixes.py #34）经此薄委托保持可用。
    def _emit_http_request(self, call_spec) -> None:
        self._delegate_http("request", call_spec, None)

    def _emit_http_response(self, call_spec, result: StrategyResult) -> None:
        # 历史口径：HTTP 状态/响应体取自 result.extracted（response_status/body）
        extracted = getattr(result, "extracted", None) or {}
        cr = CallResult(
            protocol="http",
            request={"method": getattr(call_spec, "method", ""),
                     "url": getattr(call_spec, "url", "")},
            response={
                "status": extracted.get("response_status"),
                "meta": {"headers": {}},
                "body": extracted.get("response_body"),
            },
            elapsed_ms=float(getattr(result, "duration_ms", 0.0) or 0.0),
        )
        self._delegate_http("response", call_spec, cr)

    # 生命周期事件唯一发布者（上轮评审 #5）：step.start/end 由 ContextManager
    # 投影发布（计数字段全）；状态机不再直发（避免双发与字段缺失）

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

    # ── 历史兼容（直调方：tests/unit/test_defect_fixes.py 等；批次 F 回收）──

    def _delegate_http(self, kind: str, call_spec, call_result) -> None:
        """HTTP 事件薄委托：职责在 http 适配器（CallExecutor._emit_http_*）。"""
        from gimbal.strategy.builtin.call import CallExecutor

        if self._bus is None:
            return

        class _BusPctx:
            step_id: str
            event_bus: Any

        p = _BusPctx()
        p.step_id = self._step_id
        p.event_bus = self._bus
        if kind == "request":
            CallExecutor._emit_http_request(
                p, getattr(call_spec, "method", ""), getattr(call_spec, "url", ""),
                getattr(call_spec, "headers", {}) or {},
                getattr(call_spec, "body", None),
            )
        else:
            CallExecutor._emit_http_response(p, call_result)

    # 残留 #1 收尾：历史方法名别名已删（状态中立名 = 处理器名）
