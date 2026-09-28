"""core/scenario_runner.py

ScenarioRunner 驱动整个 Scenario，StepRunner 构造状态机并调用 run()。

StepRunner 不再感知状态流转的细节，那是状态机自己的事。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from gimbal.context.manager import ContextManager
from gimbal.context.scenario import ScenarioContext
from gimbal.context.step import StepStatus
from gimbal.context.suite import SuiteContext
from gimbal.context.views import StepContextAdapter
from gimbal.schema.scenario import Scenario
from gimbal.schema.step import Step
from gimbal.statemachine.engine import StepStateMachine, StepRunResult
from gimbal.strategy.dispatcher import StrategyDispatcher

from gimbal.log import get_logger
logger = get_logger(__name__)


# ── RuntimeControl ────────────────────────────────────────────────────────────
#
# Scenario 级的运行时控制参数（不入配置、不入 schema、不入 RuntimeControl
# 之外的 dataclass）。是 stage 1 最小子集中的"最小"：只允许按 step index
# 提前跳出 for 循环。其它控制（条件分支、循环某个 step 等）仍走插件层。
#
# 设计原则：
#   - 纯 dataclass，无 IO、无副作用：可在任意场景构造
#   - Step index 语义：0-based，对应 resolved_steps 列表位置
#   - halt_at 是"执行到该 index 后停止"语义，与 Python range(stop) 一致
#   - halt_reason 是给人看的，会写进 step_results 末尾的 marker，便于复盘
#   - 与 ScenarioRunResult.halted/halt_reason 字段对齐，reporter 据此渲染

@dataclass
class RuntimeControl:
    """Scenario 级运行时控制（残留 #4 裁定：只承载运行期控制）。

    四字段全部是运行期语义（halt/区间/调试挂起）；静态执行参数
    （n_runs/retry/parallel/fail_fast）在 PlanPolicy/UnitPolicy（schema/plan.py），
    不入本类。新增字段前先问：它随"这次执行"变 → 这里；随"用例定义"变 → schema。
    
    Attributes:
        halt_at:       0-based step index；执行到该 index 后停止。
                       None 表示不主动停止（仅依赖现有 timeout/cancel/failure 路径）。
        halt_reason:   halt 触发原因，写入标记 step 的 error 字段，便于日志/UI 区分。
                       默认 "user-requested"；CLI 通过 --step-to/--breakpoint 触发时使用默认；
                       编程式调用（如插件通过 EventBus 探测外部信号）应自定义 reason。
        step_from:     0-based；跳过 [0, step_from) 的 step（v2.1 批次 E 生效；
                       被跳过步骤所需输入由 inputs/--var 提供）。
        debug_mode:    调试档位（引擎让步）：挂起等待不计 scenario 超时。
        cancel_event:  协作取消事件（threading.Event）。调度器 attempt 超时
                       弃跑时置位——step 循环与 STEP_FAILED 重试点检测到
                       即停,防止被弃线程与重试并发重复发请求。
    """
    halt_at: Optional[int] = None
    halt_reason: str = "user-requested"
    step_from: Optional[int] = None
    debug_mode: bool = False
    cancel_event: Any = None


# ── ScenarioRunResult ─────────────────────────────────────────────────────────

@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str
    step_results: list[StepRunResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    # 当 status == "halted" 时为 True；reporter 据此渲染 "⏸ HALTED" 而非 "✗ FAILED"。
    # 通过 RuntimeControl.halt_at 触发；用户主动中止与业务失败可明确区分。
    halted: bool = False
    # 触发 halt 的具体原因（来自 RuntimeControl.halt_reason），便于审计。
    # 仅在 halted=True 时有值。
    halt_reason: Optional[str] = None
    # 单元输出（v2.1 批次 C）：scenario 作用域提升变量的快照
    # （extract scope=SCENARIO 的目标等），调度器据此喂下游单元。
    outputs: dict = field(default_factory=dict)
    # 三种乘法（v2.1 批次 D）：
    # run_index = n_runs 中的第几次（1-based；n_runs=1 恒为 1）
    run_index: int = 1
    # 每次 n_runs run 的简况 [{run, status, passed, retries}]；由调度器聚合写入
    attempts: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """便捷属性：status == 'passed' 时为 True。"""
        return self.status == "passed"

    @property
    def duration_ms(self) -> float:
        """便捷属性：以毫秒为单位计算 Scenario 的总耗时（started_at 与 ended_at 之差）。"""
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds() * 1000
        return 0.0


# ── StepRunner ────────────────────────────────────────────────────────────────

class StepRunner:
    """构造 StepStateMachine 并触发执行。

    职责：
      1. 创建 StepContext（在 scenario_ctx 下派生）
      2. 构造 StepStateMachine（注入执行所需的全部依赖）
      3. 调用 sm.run()，拿到结果
      4. finalize StepContext

    step_schema 在进入 StepRunner 之前已由 ScenarioPreprocessor 完成模板展开，
    这里不再做任何解析工作。
    """

    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
        service_base_url: str = "",
        hook_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        services: Optional[dict] = None,
        protocol_registry: Optional[Any] = None,
        auth_registry: Optional[Any] = None,
    ) -> None:
        """初始化 StepRunner，保存 strategy dispatcher、ctx_manager、service_base_url/services、可选的 hook_registry/event_bus/protocol_registry/auth_registry。"""
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._service_base_url = service_base_url
        # D7 per-step 查表:api.service → 场景声明 URL;空 dict 回落 base_url
        self._services = services or {}
        self._hooks = hook_registry
        self._bus = event_bus
        # 协议注册表（多协议分派）；None 时状态机兜底默认表（仅 http）
        self._protocols = protocol_registry
        # 认证注册表（v2.1 批次 D：auth_expired 单飞刷新通道）
        self._auth_registry = auth_registry
        logger.debug("[StepRunner] 初始化: service_base_url={} services={}",
                     service_base_url, sorted(self._services))

    def run(
        self,
        step_schema: Step,
        scenario_ctx: ScenarioContext,
        step_index: int,
    ) -> StepRunResult:
        """执行单个 Step：创建 StepContext、构造状态机、运行并 finalize。

        入参:
            step_schema: 已由预处理器展开的 Step 数据对象。
            scenario_ctx: 当前 Scenario 上下文。
            step_index:   当前 step 在 scenario 中的序号（用于生成 step_id）。
        返回:
            状态机产出的 StepRunResult。
        """
        step_id = f"step-{step_index:03d}"
        logger.debug("[StepRunner] 开始执行 Step: step_id={} scenario_id={}",
                     step_id, scenario_ctx.scenario_id)

        # 1. 创建 StepContext
        step_ctx = self._ctx_manager.derive_step_context(
            scenario_ctx,
            step_id=step_id,
            step_name=step_id,
            strategy_kind="multi",
            strategy_spec=step_schema.model_dump(),
            resolved_vars={},
            description=getattr(step_schema, "description", None),
        )
        logger.debug("[StepRunner] StepContext 创建完成: step_id={}", step_id)

        # 2. 构造状态机，注入全部执行依赖
        #    step_schema 已由预处理器展开，直接使用
        sm = StepStateMachine(
            step_id=step_id,
            step_schema=step_schema,
            dispatcher=self._dispatcher,
            view=StepContextAdapter(step_ctx),
            service_base_url=self._service_base_url,
            hook_registry=self._hooks,
            event_bus=self._bus,
            services=self._services,
            protocol_registry=self._protocols,
            auth_registry=self._auth_registry,
        )
        logger.debug("[StepRunner] StepStateMachine 构造完成: step_id={}", step_id)

        # 3. 状态机自驱动运行
        result = sm.run()
        logger.debug("[StepRunner] Step 执行完成: step_id={} status={} duration_ms={:.2f}",
                     step_id, result.status, result.duration_ms)

        # 4. finalize StepContext
        step_status = StepStatus(result.status) \
            if result.status in StepStatus._value2member_map_ \
            else StepStatus.ERROR
        self._ctx_manager.finalize_step(step_ctx, step_status)
        logger.debug("[StepRunner] StepContext finalized: step_id={} status={}",
                     step_id, step_status)

        return result


# ── abort 来源识别（P1-9）─────────────────────────────────────────────────────
# 状态机对 STEP_BEFORE 决策 abort（debugger 主动中止）的 step 结果 error
# 固定以 "[step.before] aborted" 开头（statemachine/engine.py）。scenario_runner
# 据此识别 abort 来源的失败：跳过 STEP_FAILED 决策询问，run 直接终止——
# abort 语义是框架级中止，不再触发二次裁决/二次暂停。

_STEP_BEFORE_ABORTED_PREFIX = "[step.before] aborted"


def _abort_originated(result: StepRunResult) -> bool:
    """step 失败是否来自 STEP_BEFORE 决策 abort（如 debugger 会话中止）。"""
    err = getattr(result, "error", None)
    return isinstance(err, str) and err.startswith(_STEP_BEFORE_ABORTED_PREFIX)


# ── ScenarioRunner ────────────────────────────────────────────────────────────

class _NullView:
    """无上下文时的分派视图兜底（LifecycleEntry 执行用）。"""

    def write_scratch(self, key, value) -> None:
        pass

    def read_scratch(self, key, default=None):
        return default

    def get_scratch_dict(self):
        return {}

    def read_variable(self, key, **kw):
        return None

    def record_assertion(self, result) -> None:
        pass


class ScenarioRunner:
    """驱动整个 Scenario 的执行。

    职责：
      - 在 suite_ctx 下派生 ScenarioContext
      - 调用 ScenarioPreprocessor 完成认证 + 模板展开
      - 按序调用 StepRunner 执行每个已展开的 step
      - 汇总结果，finalize ScenarioContext
      - 触发 SCENARIO_START / SCENARIO_END 事件
    """

    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
        hook_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        auth_registry: Optional[Any] = None,
        protocol_registry: Optional[Any] = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._hooks = hook_registry
        self._bus = event_bus
        self._auth_registry = auth_registry
        self._protocols = protocol_registry
        logger.debug("[ScenarioRunner] 初始化完成")

    def run(
        self,
        scenario_schema: Scenario,
        suite_ctx: SuiteContext,
        runtime_control: Optional[RuntimeControl] = None,
    ) -> ScenarioRunResult:
        """驱动整个 Scenario 的执行：派生上下文、预处理、按序跑 step、汇总结果、finalize。

        入参:
            scenario_schema:  已校验的 Scenario 数据对象。
            suite_ctx:        上层 Suite 上下文。
            runtime_control:  可选运行时控制（阶段 1 最小子集：按 step index 提前跳出
                              for 循环）。None 时退化为现有行为（仅 timeout/cancel/failure 中断）。
        返回:
            ScenarioRunResult（包含 status、step_results、started_at、ended_at；
                              当触发 halt 时 halted=True 且 halt_reason 写入）。
        副作用:
            向 ctx_manager 注册 scenario/step 上下文；向 event_bus 发布 SCENARIO_START/END。
        """
        started_at = datetime.now(timezone.utc)
        sid = scenario_schema.scenarioId
        logger.info(
            "[ScenarioRunner] 开始执行 Scenario: scenario_id={} scenario_name={} step_count={}",
            sid, scenario_schema.meta.name, len(scenario_schema.steps),
        )

        # 1. 派生 ScenarioContext
        scenario_ctx = self._ctx_manager.derive_scenario_context(
            suite_ctx,
            scenario_id=sid,
            scenario_name=scenario_schema.meta.name,
            description=scenario_schema.meta.description,
        )
        logger.debug("[ScenarioRunner] ScenarioContext 创建完成: scenario_id={}", sid)

        # 2. 预处理：认证 + 模板展开 + 提取 base_url
        #    认证结果写入 self._auth_registry（运行期容器）
        from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor

        preprocessor = ScenarioPreprocessor(
            scenario_schema=scenario_schema,
            bootstrap_config=scenario_ctx.config,
            auth_registry=self._auth_registry,
        )
        resolved_steps, base_url, services = preprocessor.run()
        logger.debug(
            "[ScenarioRunner] 预处理完成: resolved_steps={} base_url={}",
            len(resolved_steps), base_url,
        )

        # 2.6 setup 括号（上轮评审 #9：LifecycleEntry 执行落地）——
        # 顺序执行；任一失败 → 场景 error 且不进入 steps（suite before 同语义）
        setup_failed: "StepRunResult | None" = None
        if scenario_schema.config.setup:
            setup_res = self._run_lifecycle_entries(
                scenario_schema.config.setup, scenario_ctx, label="setup")
            if setup_res is not None:   # 失败条目
                setup_failed = setup_res
                logger.error(
                    "[ScenarioRunner] setup 失败，跳过 steps: scenario_id={} kind={}",
                    sid, "见 step_results")

        # 3. 触发 SCENARIO_START 事件
        #    step_count 用"实际会执行的 step 数"（不含不可执行条目），
        #    reporter 拿到的数字与最终执行结果一致。
        executable_count = sum(
            1 for s in resolved_steps if getattr(s, "call", None) is not None
        )
        # 唯一发布者（评审 #5）：suite_id/run_id 随事件带全
        self._emit_scenario_start(scenario_schema, sid, executable_count,
                                  suite_id=suite_ctx.suite_id,
                                  run_id=suite_ctx.run_id)

        # 4. 逐步执行（使用已展开的 resolved_steps）
        step_runner = StepRunner(
            dispatcher=self._dispatcher,
            ctx_manager=self._ctx_manager,
            service_base_url=base_url,
            hook_registry=self._hooks,
            event_bus=self._bus,
            services=services,
            protocol_registry=self._protocols,
            auth_registry=self._auth_registry,
        )

        step_results: list[StepRunResult] = []
        if setup_failed is not None:
            step_results.append(setup_failed)
        overall_status = "error" if setup_failed is not None else "passed"
        # 阶段 1 最小子集：runtime-controlled halt 信号
        halted = False
        halt_reason_out: Optional[str] = None

        # 修复 B3：scenario_timeout 强制执行
        # 实际是 cooperative timeout：每个 step 前检查 elapsed time
        cfg_timeout = getattr(scenario_ctx, "_timeout_seconds", None)
        if cfg_timeout is None:
            bs_cfg = scenario_ctx.config
            cfg_timeout = getattr(bs_cfg, "scenario_timeout", None)
        # 上轮评审 #9：scenario.config.timePolicy 消费——TimeoutPolicy.seconds
        # 为场景级超时（覆盖全局默认;RecordPolicy 维持计时记录语义）
        tp = getattr(scenario_schema.config, "timePolicy", None)
        if tp is not None and getattr(tp, "kind", "") == "timeout":
            cfg_timeout = int(tp.seconds)

        # 修复 B8：cancel flag 检查（移出循环，每 step 多次 sys.modules 查找）
        try:
            from gimbal.cli.main import is_cancelled
        except ImportError:
            is_cancelled = lambda: False  # noqa: E731 单元测试场景 cli.main 不可用

        total_steps = len(resolved_steps)

        def _append_marker(*, kind: str, next_idx: int, error: str, error_phase: str, status: str = "error") -> None:
            """Append a synthetic StepRunResult for scenario-level interrupts.

            用 `__scenario_<kind>__` 作为保留 step_id 前缀，避免与真实 step 的
            编号（如 step-002-API-1）冲突；next_idx 写进 error 消息便于定位。

            Args:
                kind:        标记种类（timeout/cancelled/halted/...），最终落到 step_id。
                next_idx:    触发中断时尚未执行的 step 索引，便于定位。
                error:       写入 StepRunResult.error 的描述。
                error_phase: 写入 StepRunResult.error_phase（区分 timeout/cancelled/halted）。
                status:      写入 StepRunResult.status；halted 分支使用 "halted" 与业务失败区分。
            """
            step_results.append(StepRunResult(
                step_id=f"__scenario_{kind}__",
                status=status,
                error=f"{error} (next_step_index={next_idx}/{total_steps})",
                error_phase=error_phase,
                duration_ms=0.0,
            ))

        for idx, step_union in enumerate([] if setup_failed else resolved_steps):
            # 协作取消（attempt 超时弃跑）：被弃线程在 step 边界自行终止,
            # 不再发后续 step 请求（防与重试并发重复下单）
            if (runtime_control is not None
                    and runtime_control.cancel_event is not None
                    and runtime_control.cancel_event.is_set()):
                logger.warning(
                    "[ScenarioRunner] 检测到取消信号（attempt 超时弃跑），停止后续 step: scenario_id={}",
                    sid)
                _append_marker(
                    kind="cancelled",
                    next_idx=idx,
                    error="cancelled: attempt timeout (cooperative)",
                    error_phase="cancelled",
                )
                overall_status = "error"
                break
            # 阶段 1 最小子集：runtime-controlled halt 检查（在 timeout/cancel 之前）
            # halt_at 语义类似 range(stop)：执行到该 idx 后停止；与现有逻辑正交。
            if runtime_control is not None and runtime_control.halt_at is not None and idx >= runtime_control.halt_at:
                logger.warning(
                    "[ScenarioRunner] Runtime halt 触发: scenario_id={} current_idx={} halt_at={} reason={!r}, "
                    "停止后续 step（不影响已执行结果）",
                    sid, idx, runtime_control.halt_at, runtime_control.halt_reason,
                )
                halted = True
                halt_reason_out = runtime_control.halt_reason
                overall_status = "halted"
                _append_marker(
                    kind="halted",
                    next_idx=idx,
                    error=f"halted: {runtime_control.halt_reason}",
                    error_phase="halted",
                    status="halted",
                )
                break
            # v2.1 批次 E：step_from —— 区间外（idx < step_from）的 step 跳过
            if runtime_control is not None and runtime_control.step_from is not None                     and idx < runtime_control.step_from:
                logger.debug("[ScenarioRunner] step[{}] < step_from={}，跳过",
                             idx, runtime_control.step_from)
                continue

            # 修复 B3：检查 scenario timeout（debug_mode 豁免：挂起等待不计超时）
            if cfg_timeout is not None and not (
                runtime_control is not None and runtime_control.debug_mode
            ):
                elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                if elapsed > cfg_timeout:
                    logger.warning(
                        "[ScenarioRunner] Scenario 超时: scenario_id={} elapsed={:.1f}s limit={}s, "
                        "停止后续 step",
                        sid, elapsed, cfg_timeout,
                    )
                    overall_status = "error"
                    _append_marker(
                        kind="timeout",
                        next_idx=idx,
                        error=f"scenario timeout after {elapsed:.1f}s (limit={cfg_timeout}s)",
                        error_phase="timeout",
                    )
                    break
            # 修复 B8：检查 cancel flag
            if is_cancelled():
                logger.warning("[ScenarioRunner] 检测到 cancel signal，停止后续 step")
                _append_marker(
                    kind="cancelled",
                    next_idx=idx,
                    error="cancelled by user (SIGINT)",
                    error_phase="cancelled",
                )
                overall_status = "error"
                break

            if getattr(step_union, "call", None) is None:
                logger.warning("[ScenarioRunner] step[{}] 缺少 call 声明，跳过", idx)
                continue

            logger.debug(
                "[ScenarioRunner] 开始执行第 {}/{} 个 Step: scenario_id={}",
                idx + 1, len(resolved_steps), sid,
            )
            result = step_runner.run(step_union, scenario_ctx, idx)

            if not result.passed and not _abort_originated(result):
                # 拦截决策点 STEP_FAILED（批次 E）：CONTINUE（记失败中断，默认）/
                # RETRY（整步重跑，人工=human 标 repaired）/ SKIP（跳过本步继续）/
                # ABORT（中断）
                # P1-9：STEP_BEFORE 决策 abort 来源的失败跳过本决策点——
                # abort 语义 = run 直接终止，不再触发 step.failed 二次询问
                from gimbal.core.decisions import ask_decision
                from gimbal.core.hooks import HookPoint
                decision = ask_decision(self._hooks, HookPoint.STEP_FAILED, {
                    "step_id": result.step_id,
                    "result": result,
                    "ctx": scenario_ctx,
                })
                # P1-10：retry 循环（带上限）——重跑仍失败则再次询问（再次
                # 暂停），直至通过 / continue / skip / abort / 上限耗尽。
                # 上限防线：交互会话持续回 retry 不得无限循环（挂死 run）
                _MAX_STEP_RETRIES = 8
                _retries = 0
                while decision.action == "retry":
                    if (runtime_control is not None
                            and runtime_control.cancel_event is not None
                            and runtime_control.cancel_event.is_set()):
                        logger.warning(
                            "[ScenarioRunner] retry 前检测到取消（attempt 超时弃跑）: step_id={}",
                            result.step_id)
                        break
                    if _retries >= _MAX_STEP_RETRIES:
                        logger.error(
                            "[ScenarioRunner] STEP_FAILED retry 达上限 {}：按最终失败收口 step_id={}",
                            _MAX_STEP_RETRIES, result.step_id)
                        break
                    _retries += 1
                    logger.info(
                        "[ScenarioRunner] STEP_FAILED 决策 retry：整步重跑 step_id={}（source={} {}/{}）",
                        result.step_id, decision.source, _retries, _MAX_STEP_RETRIES,
                    )
                    rerun = step_runner.run(step_union, scenario_ctx, idx)
                    result = rerun
                    if rerun.passed:
                        if decision.is_human:
                            rerun.repaired = True   # 人工修复标记（extract→promote 幂等覆盖）
                        break
                    if _abort_originated(rerun):
                        # P1-9：abort 来源的失败不再二次询问
                        break
                    # 重跑仍失败 → 循环再次询问（debugger 再次暂停等命令）
                    decision = ask_decision(self._hooks, HookPoint.STEP_FAILED, {
                        "step_id": rerun.step_id,
                        "result": rerun,
                        "ctx": scenario_ctx,
                    })
                if decision.action == "skip":
                    logger.info(
                        "[ScenarioRunner] STEP_FAILED 决策 skip：跳过 step_id={}，继续后续 step",
                        result.step_id,
                    )
                    result = StepRunResult(
                        step_id=result.step_id, status="skipped",
                        error=f"skipped by decision: {decision.note or 'step.failed'}",
                        duration_ms=0.0,
                    )

            step_results.append(result)
            logger.info(
                "[ScenarioRunner] Step 完成: step_id={} status={} duration_ms={:.2f} ({}/{})",
                result.step_id, result.status, result.duration_ms,
                idx + 1, len(resolved_steps),
            )

            if result.status == "skipped":
                continue          # 决策 skip：不中断场景，继续后续 step
            if not result.passed:
                # continue / abort / retry 后仍失败：现有语义（失败中断）
                overall_status = result.status
                logger.warning(
                    "[ScenarioRunner] Scenario 中断: step_id={} 失败，后续 step 不再执行",
                    result.step_id,
                )
                break

        # 4.5 收集单元输出（finalize 前快照；调度器喂下游用）
        try:
            outputs = dict(scenario_ctx.channels.variables_snapshot())
        except Exception:  # noqa: BLE001
            outputs = {}

        # 4.7 teardown 括号（评审 #9）：必达逆序执行——失败不改变主判定,
        # 记录为 teardown 留痕（suite after 同语义;主状态 error/pass 不受影响）
        if scenario_schema.config.teardown:
            for entry in reversed(scenario_schema.config.teardown):
                res = self._run_lifecycle_entries([entry], scenario_ctx,
                                                  label="teardown")
                if res is not None:
                    step_results.append(res)
                    logger.warning(
                        "[ScenarioRunner] teardown 条目失败(不改变主判定): kind={}",
                        getattr(entry, "kind", "?"))

        # 5. finalize ScenarioContext
        self._ctx_manager.finalize_scenario(scenario_ctx, overall_status)
        logger.debug(
            "[ScenarioRunner] ScenarioContext finalized: scenario_id={} status={}",
            sid, overall_status,
        )

        # 6. 触发 SCENARIO_END 事件（携带 Scenario.meta，让 reporter 可展示 tags/author/priority）
        self._emit_scenario_end(scenario_schema, sid, overall_status, len(resolved_steps),
                                suite_id=suite_ctx.suite_id,
                                run_id=suite_ctx.run_id)

        return ScenarioRunResult(
            scenario_id=sid,
            status=overall_status,
            step_results=step_results,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            halted=halted,
            halt_reason=halt_reason_out,
            outputs=outputs,
        )

    # ── 埋点辅助 ──
    def _run_lifecycle_entries(self, entries, scenario_ctx, *, label: str):
        """顺序执行 LifecycleEntry 列表（上轮评审 #9）。

        条目经 params 合成 duck-type 策略 spec（kind/name/enabled/onFailure）
        交 dispatcher 分派；需要 step 上下文视图——为每个条目开一个轻量
        StepContext（step_id = {label}:{kind}:{key}）。
        返回：全部通过 → None；首个失败条目的 StepRunResult 留痕。
        """
        from datetime import datetime, timezone
        from gimbal.schema.strategy import FailurePolicy
        for entry in entries:
            step_id = f"{label}:{entry.kind}:{entry.key or '-'}"
            try:
                step_ctx = self._ctx_manager.derive_step_context(
                    scenario_ctx, step_id=step_id,
                    step_name=step_id, strategy_kind=entry.kind,
                    strategy_spec=dict(entry.params or {}),
                )
            except Exception:  # noqa: BLE001 — 上下文设施缺失时退化为无 ctx 分派
                step_ctx = None
            spec = type("_LifecycleSpec", (), {
                "kind": entry.kind, "name": step_id, "phase": None, "order": 0,
                "enabled": True, "onFailure": FailurePolicy.ABORT, "tags": [],
                **dict(entry.params or {}),
            })()
            result = self._dispatcher.dispatch(spec, step_ctx.view if step_ctx else _NullView())
            if step_ctx is not None:
                from gimbal.statemachine.states import StepStatus
                try:
                    self._ctx_manager.finalize_step(
                        step_ctx,
                        StepStatus.PASSED if result.passed else StepStatus.FAILED)
                except Exception:  # noqa: BLE001
                    pass
            if result.failed:
                return StepRunResult(
                    step_id=step_id, status="failed",
                    error=f"{label} entry failed: {result.message}",
                    duration_ms=result.duration_ms or 0.0,
                )
        return None

    def _emit_scenario_start(self, scenario: Scenario, sid: str, step_count: int,
                             *, suite_id: str = "", run_id: "str | None" = None) -> None:
        """向 event_bus 发布 ScenarioStartEvent（唯一发布者,字段带全）。

        入参:
            scenario:   Scenario 数据对象。
            sid:        scenario 唯一 ID。
            step_count: 实际会执行的 step 数（不含不可执行条目）。
            suite_id:   所属 suite（套）标识。
            run_id:     本次 run 标识。
        副作用:
            发布事件，失败仅记 debug 日志。
        """
        if self._bus is None:
            return
        try:
            from gimbal.events.types import ScenarioStartEvent
            self._bus.publish(ScenarioStartEvent(
                scenario_id=sid,
                scenario_name=scenario.meta.name,
                step_count=step_count,
                suite_id=suite_id,
                run_id=run_id,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[ScenarioRunner] emit SCENARIO_START failed")

    def _emit_scenario_end(
        self,
        scenario: "Scenario",
        sid: str,
        status: str,
        step_count: int,
        *,
        suite_id: str = "",
        run_id: "str | None" = None,
    ) -> None:
        """向 event_bus 发布 ScenarioEndEvent（携带 scenario.meta 拍平后的 dict）。

        入参:
            scenario:   Scenario 数据对象。
            sid:        scenario 唯一 ID。
            status:     最终状态（passed/failed/error/skipped）。
            step_count: 已执行 step 数。
        副作用:
            发布事件，失败仅记 debug 日志。
        """
        if self._bus is None:
            return
        try:
            from gimbal.events.types import ScenarioEndEvent
            # 把 Scenario.meta 拍平成 dict（tags/author/priority/version/...），
            # 让订阅方拿到的是 plain dict 而不是 Pydantic 模型，避免序列化耦合。
            meta_dump: dict = {}
            try:
                if scenario.meta is not None:
                    meta_dump = scenario.meta.model_dump(mode="json")
            except Exception:  # noqa: BLE001
                logger.debug("[ScenarioRunner] scenario.meta.model_dump 失败，使用空 dict")
            self._bus.publish(ScenarioEndEvent(
                scenario_id=sid,
                status=status,
                step_count=step_count,
                meta=meta_dump,
                suite_id=suite_id,
                run_id=run_id,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[ScenarioRunner] emit SCENARIO_END failed")
