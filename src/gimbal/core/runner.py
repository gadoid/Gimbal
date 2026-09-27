"""core/runner.py

职责分离：

    initial_ctx = bootstrap(cli_ctx)      # 配置合并 + 基础设施初始化
    engine      = Engine(initial_ctx)     # 持有初始化上下文，等待执行请求
    result      = engine.run(scenario)    # 此时才创建 framework/suite 层级 context

bootstrap：
    - 调用 ConfigLoader 完成多来源配置合并 → BootstrapConfig
    - 配置日志系统
    - 初始化基础设施（EventBus / Archive / ContextManager / Dispatcher）
    - 产出 Configuration（不可变，安全传递）

Engine.run()：
    - 接收 Scenario 或 Suite 数据对象
    - 用 Configuration 中的 ctx_manager 创建本次执行的层级 context
        （FrameworkContext → SuiteContext，生命周期属于"一次执行"）
    - 分发到 ScenarioRunner 执行
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from gimbal.schema.scenario import Scenario
from gimbal.context.manager import ContextManager,FrameworkContext

from .bootstrap import Configuration


from gimbal.log import get_logger
logger = get_logger(__name__)


# ── RunResult ─────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    exit_code: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    # 阶段 1 最小子集：被 runtime halt 触发的 scenario 数。
    # 与 failed/error 区分（halted 算作"未通过"但有独立标记，便于 reporter 渲染）。
    halted: int = 0
    # v2.1 批次 C：上游失败导致下游未执行的单元数（编排判定状态之一）。
    blocked: int = 0
    # v2.1 批次 E：人工修复（debugger retry 后通过）的步骤数——不计正常通过率。
    repaired: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)



# ── Engine ────────────────────────────────────────────────────────────────────

class Engine:
    """执行引擎。

    __init__ 只存引用，不做任何 I/O 或状态初始化。
    所有执行相关的状态都在 run() 内部创建，保证每次 run() 相互独立。
    """

    def __init__(self, configuration: Configuration) -> None:
        """初始化 Engine，仅保存引用，不做任何 I/O 或状态初始化。

        入参:
            configuration: 由 bootstrap() 产出的不可变配置。
        """
        self._ictx = configuration
        # 最近一次 run() 产出的 ReportArtifact 列表（CLI 用来打印）
        self._artifacts: list = []
        logger.debug("[Engine] Engine 初始化完成")

    @property
    def artifacts(self) -> list:
        """最近一次 run() 产出的 ReportArtifact 列表。

        仅在 Engine.run() 完成后非空。
        """
        return list(self._artifacts)

    def run(self, target: Any, runtime_control: Any = None) -> RunResult:
        """执行入口。

        在此方法内创建本次执行的层级 context：
            1. FrameworkContext  —— 全量配置写入，run_id 在此生成
            2. SuiteContext      —— 单 scenario 执行时用 __default__ 占位
        然后分发到 ScenarioRunner。

        入参:
            target:           要执行的 Scenario 或 Suite 数据对象。
            runtime_control:  可选 RuntimeControl（阶段 1 最小子集）。透传给 ScenarioRunner，
                              允许 CLI/调用方按 step index 提前跳出 for 循环。
        """
        ictx = self._ictx

        # 1. 创建 FrameworkContext（每次 run 独立的 run_id）
        framework_ctx = ictx.ctx_manager.create_framework_context(
            run_id=str(uuid.uuid4()),
            cfg= ictx,
        )
        logger.info("[Engine] 执行开始: run_id={} env={} mode={} target={}",
                    framework_ctx.run_id, framework_ctx.config.env, framework_ctx.mode, type(target).__name__)

        # 2. 触发 RUN_START 事件
        self._emit_run_start(framework_ctx)

        # 2.5 启动所有 reporter（订阅事件 + 准备资源）
        reporter_runtime = ictx.reporter_runtime
        if reporter_runtime is not None:
            try:
                reporter_runtime.begin_all(
                    framework_ctx=framework_ctx,
                    reporter_names=list(ictx.cfg.reporters or ("console",)),
                    report_dir=ictx.cfg.report_dir,
                    plugin_configs=dict(ictx.cfg.plugin_configs or {}),
                )
            except Exception:  # noqa: BLE001
                logger.exception("[Engine] reporter_runtime.begin_all 失败（已隔离）")

        # 3. 执行：编译为 Plan → 单路径执行（v2.1 批次 B；scenario=隐式 aggregate）
        try:
            from gimbal.compiler.pipeline import compile_target, CompileError
            plan = compile_target(target)
            result = self._run_plan(plan, framework_ctx, runtime_control=runtime_control)
        except CompileError as e:
            logger.error("[Engine] 编译失败: {}", e)
            result = RunResult(exit_code=2, error=1)
        except Exception as e:  # noqa: BLE001
            logger.exception("[Engine] 执行异常: {}", e)
            result = RunResult(exit_code=2, error=1)

        # 4. 触发 RUN_END 事件
        self._emit_run_end(framework_ctx, result)

        # 5. 终结所有 reporter，产出 ReportArtifact 列表（仅写入 metadata，artifact 本身由 reporter 落盘）
        self._artifacts: list = []
        if reporter_runtime is not None:
            try:
                self._artifacts = reporter_runtime.finalize_all(result)
            except Exception:  # noqa: BLE001
                logger.exception("[Engine] reporter_runtime.finalize_all 失败（已隔离）")
        return result

    def _emit_run_start(self, framework_ctx: FrameworkContext) -> None:
        """向 event_bus 发布 RunStartEvent 事件。

        入参:
            framework_ctx: 本次 run 的 framework 上下文。
        副作用:
            发布事件，失败仅记 debug 日志，不影响主流程。
        """
        bus = self._ictx.event_bus
        if bus is None:
            return
        try:
            from gimbal.events.types import RunStartEvent
            bus.publish(RunStartEvent(
                run_id=framework_ctx.run_id,
                env=framework_ctx.config.env,
                mode=framework_ctx.mode,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[Engine] emit RUN_START failed")

    def _emit_run_end(self, framework_ctx: FrameworkContext, result: RunResult) -> None:
        """向 event_bus 发布 RunEndEvent 事件（带统计信息）。

        入参:
            framework_ctx: 本次 run 的 framework 上下文。
            result:        本次 run 的 RunResult 结果。
        副作用:
            发布事件，失败仅记 debug 日志。
        """
        bus = self._ictx.event_bus
        if bus is None:
            return
        try:
            from gimbal.events.types import RunEndEvent
            bus.publish(RunEndEvent(
                run_id=framework_ctx.run_id,
                total=result.total,
                passed=result.passed,
                failed=result.failed,
                error=result.error,
                skipped=result.skipped,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[Engine] emit RUN_END failed")

    # ── 内部分发 ─────────────────────────────────────────────────────────────

    def _run_plan(
        self,
        plan: Any,
        framework_ctx: FrameworkContext,
        runtime_control: Any = None,
    ) -> RunResult:
        """执行一个 Plan（唯一执行路径，v2.1 批次 B）。

        单元执行 = ScenarioRunner（生效副本 + inputs 注入）；调度 =
        PlanScheduler（before → units → after；串行/并行 + fail-fast）。
        结果映射保持两套历史口径：隐式 Plan（单场景）沿用单场景计数口径，
        聚合 Plan 沿用 Suite 计数口径 —— 对账与报告零回归。

        入参:
            plan:            compile_target 产出的 Plan。
            framework_ctx:   本次 run 的 framework 上下文。
            runtime_control: 可选 RuntimeControl（透传给每个单元）。
        """
        from gimbal.core.scenario_runner import ScenarioRunner
        from gimbal.scheduler.plan import PlanScheduler

        logger.info(
            "[Engine] 开始执行 Plan: suite_id={} mode={} units={} parallel={} implicit={}",
            plan.suite_id, plan.mode, len(plan.units), plan.policy.parallel, plan.implicit,
        )

        suite_ctx = framework_ctx.ctx_manager.derive_suite_context(
            framework_ctx,
            suite_id=plan.suite_id,
            suite_name=plan.suite_name,
            tags=[],
            plugins={},
        )
        logger.debug("[Engine] SuiteContext 创建完成: suite_id={}", suite_ctx.suite_id)

        runner = ScenarioRunner(
            framework_ctx.dispatcher,
            framework_ctx.ctx_manager,
            hook_registry=self._ictx.hook_registry,
            event_bus=self._ictx.event_bus,
            auth_registry=self._ictx.auth_registry,
            protocol_registry=self._ictx.protocols,
        )

        def _run_unit(unit, inputs):
            scenario = unit.scenario
            if inputs:
                # 统一输入注入原语：inputs 注入为 scenario vars（生效副本，不改源）；
                # inputs 由调度器解析（字面量 ∪ 连线值）
                merged = {**(scenario.config.vars or {}), **inputs}
                scenario = scenario.model_copy(update={
                    "config": scenario.config.model_copy(update={"vars": merged}),
                })
            logger.debug("[Engine] 开始执行单元: unit_id={}", unit.id)
            return runner.run(scenario, suite_ctx, runtime_control=runtime_control)

        fail_fast = framework_ctx.config.fail_fast
        if plan.policy.fail_fast is not None:
            fail_fast = plan.policy.fail_fast

        # P0-5：总线透传调度器——after 缺失输入注入 None 时发 debug.* 事件留痕
        sched = PlanScheduler(event_bus=self._ictx.event_bus)
        outcome = sched.run(plan, _run_unit, fail_fast=fail_fast)

        # ── 判定：按计划清单对账（blocked / cancelled 由 outcome 呈现）──
        if plan.implicit:
            return self._assemble_implicit(plan, outcome.results)
        return self._assemble_aggregate(plan, outcome)

    # ── 判定（两套历史口径，零回归）────────────────────────────

    @staticmethod
    def _detail_row(result: Any) -> dict[str, Any]:
        """ScenarioRunResult → details 行（历史形状）。"""
        return {
            "scenario_id": result.scenario_id,
            "status":      result.status,
            "duration_ms": result.duration_ms,
            "halted":      result.halted,
            "halt_reason": result.halt_reason,
            "steps": [
                {
                    "step_id":     s.step_id,
                    "status":      s.status,
                    "duration_ms": s.duration_ms,
                    "error":       s.error,
                    "error_phase": s.error_phase,
                    **({"repaired": True} if getattr(s, "repaired", False) else {}),
                }
                for s in result.step_results
            ],
        }

    def _assemble_implicit(self, plan: Any, results: dict) -> RunResult:
        """单场景历史计数口径：非通过一律计 failed（含 error 状态）。"""
        unit = plan.units[0]
        result = results.get(unit.id)
        if result is None or isinstance(result, Exception):
            logger.error("[Engine] 隐式 Plan 单元未产出结果: unit_id={}", unit.id)
            return RunResult(exit_code=1, total=1, failed=1)
        logger.info(
            "[Engine] Scenario 执行完成: scenario_id={} status={} duration_ms={:.2f} halted={}",
            result.scenario_id, result.status, result.duration_ms, result.halted,
        )
        repaired = sum(
            1 for s in getattr(result, "step_results", []) or []
            if getattr(s, "repaired", False)
        )
        return RunResult(
            exit_code=0 if result.passed else 1,
            total=len(getattr(result, "attempts", None) or [1]),
            passed=1 if result.passed else 0,
            failed=0 if result.passed else 1,
            halted=1 if result.halted else 0,
            repaired=repaired,
            details=[self._detail_row(result)],
        )

    def _assemble_aggregate(self, plan: Any, outcome: Any) -> RunResult:
        """Suite/Graph 计数口径：halted/passed/error/failed/blocked 分立；details 按提交序。

        v2.1 review P0-4：before/after 括号行与主体行统一组装——各占一行计入
        total；before 失败计 failed 且主体已被调度器置 blocked（各占一行计入
        total）；after 失败计 failed（必达执行，不影响其他行）。
        exit_code = 0 iff failed == error == halted == blocked == 0。
        """
        results = outcome.results
        total = passed = failed = error = halted = blocked = 0
        details: list[dict[str, Any]] = []

        # 括号单元行（P0-4：计入 total 与 exit_code；bracket 字段标识）
        for bracket, units in (("before", plan.before), ("after", plan.after)):
            for unit in units:
                result = results.get(unit.id)
                if isinstance(result, Exception):
                    total += 1
                    error += 1
                elif result is not None:
                    total += len(getattr(result, "attempts", None) or [1])
                    if result.halted:
                        halted += 1
                    elif result.passed:
                        passed += 1
                    elif result.status == "error":
                        error += 1
                    else:
                        failed += 1
                # result 为 None：理论不可达（括号必达执行）→ 仅占位行，不计入
                details.append(self._bracket_row(bracket, unit, result))

        for idx, unit in enumerate(plan.units):
            status = outcome.status_of(unit.id)
            if status == "blocked":
                # P0-4：blocked 行计入 total（before 失败阻断 / 依赖级联各占一行）
                total += 1
                blocked += 1
                details.append({
                    "scenario_id": unit.id,
                    "status": "blocked",
                    "duration_ms": 0.0,
                    "halted": False,
                    "halt_reason": "upstream failed",
                    "steps": [],
                })
                continue
            if status == "cancelled" or (result := results.get(unit.id)) is None:
                # fail-fast 取消 / 中断后未执行的单元：不计数，只留占位
                details.append({
                    "scenario_id": unit.id,
                    "status": "cancelled",
                    "duration_ms": 0.0,
                    "halted": False,
                    "halt_reason": "cancelled by fail-fast",
                    "steps": [],
                })
                continue
            # 计划清单对账：n_runs>1 时每次 run 计一次（attempts 聚合）
            total += len(getattr(result, "attempts", None) or [1])
            if isinstance(result, Exception):
                # 调度层兜底捕获的异常（runner 内部已隔离大部分，这里双保险）
                error += 1
                details.append({
                    "scenario_id": unit.id,
                    "status": "error",
                    "duration_ms": 0.0,
                    "halted": False,
                    "halt_reason": None,
                    "steps": [],
                    "error": str(result),
                })
                continue
            if result.halted:
                # 阶段 1：halted 单独计，不并入 failed/error；reporter 据此渲染。
                halted += 1
            elif result.passed:
                passed += 1
            elif result.status == "error":
                error += 1
            else:
                failed += 1
            details.append(self._detail_row(result))
            logger.info(
                "[Engine] Scenario 完成: scenario_id={} status={} duration_ms={:.2f} ({}/{}) halted={}",
                result.scenario_id, result.status, result.duration_ms,
                idx + 1, len(plan.units), result.halted,
            )
        cancelled = sum(1 for d in details if d["status"] == "cancelled")
        if cancelled:
            logger.warning("[Engine] fail_fast：{} 个单元被取消未执行", cancelled)
        if blocked:
            logger.warning("[Engine] {} 个单元因上游失败被 blocked", blocked)

        # P0-4：exit_code = 0 iff failed == error == halted == blocked == 0
        # （括号行失败计入 failed；halted 同为"未通过"口径）
        exit_code = 0 if (failed + error + halted + blocked) == 0 else 1
        logger.info(
            "[Engine] Suite 执行完成: suite_id={} mode={} parallel={} total={} passed={} failed={} error={} halted={} blocked={} exit_code={}",
            plan.suite_id, plan.mode, plan.policy.parallel > 1, total, passed, failed,
            error, halted, blocked, exit_code,
        )
        repaired = sum(
            1 for r in results.values()
            if not isinstance(r, Exception)
            for s in getattr(r, "step_results", []) or []
            if getattr(s, "repaired", False)
        )
        return RunResult(
            exit_code=exit_code,
            total=total, passed=passed,
            failed=failed, error=error, halted=halted, blocked=blocked,
            repaired=repaired,
            details=details,
        )

    @staticmethod
    def _bracket_row(bracket: str, unit: Any, result: Any) -> dict[str, Any]:
        """before/after 括号单元的 details 行（P0-4：计数已并入 _assemble_aggregate 统一组装）。"""
        if result is None or isinstance(result, Exception):
            return {
                "scenario_id": unit.id,
                "status": "error" if isinstance(result, Exception) else "skipped",
                "duration_ms": 0.0,
                "halted": False,
                "halt_reason": None,
                "steps": [],
                "bracket": bracket,
                "error": str(result) if isinstance(result, Exception) else None,
            }
        row = Engine._detail_row(result)
        row["bracket"] = bracket
        return row

