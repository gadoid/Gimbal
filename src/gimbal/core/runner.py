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

from gimbal.schema.scenario import Scenario, Suite
from gimbal.context.manager import ContextManager,FrameworkContext

from .boostrap import Configuration


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
    details: list[dict[str, Any]] = field(default_factory=list)



# ── Engine ────────────────────────────────────────────────────────────────────

class Engine:
    """执行引擎。

    __init__ 只存引用，不做任何 I/O 或状态初始化。
    所有执行相关的状态都在 run() 内部创建，保证每次 run() 相互独立。
    """

    def __init__(self, configuration: Configuration) -> None:
        self._ictx = configuration
        logger.debug("[Engine] Engine 初始化完成，持有 Configuration 引用")

    def run(self, target: Scenario | Suite) -> RunResult:
        """执行入口。

        在此方法内创建本次执行的层级 context：
            1. FrameworkContext  —— 全量配置写入，run_id 在此生成
            2. SuiteContext      —— 单 scenario 执行时用 __default__ 占位
        然后分发到 ScenarioRunner。
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

        try:
            if isinstance(target, Scenario):
                result = self._run_scenario(target, framework_ctx)
            elif isinstance(target, Suite):
                result = self._run_suite(target, framework_ctx)
            else:
                logger.error("[Engine] 收到未展开的 Ref: {}", type(target).__name__)
                result = RunResult(exit_code=3, error=1)
        except Exception as e:  # noqa: BLE001
            logger.exception("[Engine] 执行异常: {}", e)
            result = RunResult(exit_code=2, error=1)

        # 3. 触发 RUN_END 事件
        self._emit_run_end(framework_ctx, result)
        return result

    def _emit_run_start(self, framework_ctx: FrameworkContext) -> None:
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
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[Engine] emit RUN_END failed")

    # ── 内部分发 ─────────────────────────────────────────────────────────────

    def _run_scenario(
        self,
        scenario: Scenario,
        framework_ctx: FrameworkContext,
    ) -> RunResult:
        from gimbal.core.scenario_runner import ScenarioRunner

        logger.info("[Engine] 开始执行 Scenario: scenario_id={}", scenario.scenarioId)

        # 2. 为单 scenario 执行创建默认 SuiteContext
        suite_ctx = framework_ctx.ctx_manager.derive_suite_context(
            framework_ctx,
            suite_id="__default__",
            suite_name="Default Suite",
            tags=[],
            plugins={},
        )
        logger.debug("[Engine] SuiteContext 创建完成: suite_id={}", suite_ctx.suite_id)

        result = ScenarioRunner(
            framework_ctx.dispatcher,
            framework_ctx.ctx_manager,
            hook_registry=self._ictx.hook_registry,
            event_bus=self._ictx.event_bus,
            auth_registry=self._ictx.auth_registry,
        ).run(
            scenario, suite_ctx
        )

        logger.info("[Engine] Scenario 执行完成: scenario_id={} status={} duration_ms={:.2f}",
                    scenario.scenarioId, result.status, result.duration_ms)

        return RunResult(
            exit_code=0 if result.passed else 1,
            total=1,
            passed=1 if result.passed else 0,
            failed=0 if result.passed else 1,
            details=[{
                "scenario_id": result.scenario_id,
                "status":      result.status,
                "duration_ms": result.duration_ms,
                "steps": [
                    {
                        "step_id":     s.step_id,
                        "status":      s.status,
                        "duration_ms": s.duration_ms,
                    }
                    for s in result.step_results
                ],
            }],
        )

    def _run_suite(
        self,
        suite: Suite,
        framework_ctx: FrameworkContext,
    ) -> RunResult:
        from gimbal.core.scenario_runner import ScenarioRunner

        suite_id = getattr(suite, "suiteId", "__suite__")
        suite_name = getattr(suite, "name", "Suite")
        logger.info("[Engine] 开始执行 Suite: suite_id={} suite_name={} scenario_count={}",
                     suite_id, suite_name, len(suite.suite))

        # 2. Suite 执行时用 Suite 自身信息创建 SuiteContext
        suite_ctx = framework_ctx.ctx_manager.derive_suite_context(
            framework_ctx,
            suite_id=suite_id,
            suite_name=suite_name,
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
        )
        cfg = framework_ctx.config
        total = passed = failed = error = 0
        details: list[dict[str, Any]] = []

        for idx, scenario in enumerate(suite.suite):
            logger.debug("[Engine] 开始执行 Suite 中第 {}/{} 个 Scenario: scenario_id={}",
                         idx + 1, len(suite.suite), scenario.scenarioId)
            result = runner.run(scenario, suite_ctx)
            total += 1
            if result.passed:
                passed += 1
            elif result.status == "error":
                error += 1
            else:
                failed += 1
            details.append({
                "scenario_id": result.scenario_id,
                "status":      result.status,
                "duration_ms": result.duration_ms,
            })
            logger.info("[Engine] Scenario 完成: scenario_id={} status={} duration_ms={:.2f} ({}/{})",
                        result.scenario_id, result.status, result.duration_ms, idx + 1, len(suite.suite))
            if cfg.fail_fast and not result.passed:
                logger.warning("[Engine] fail_fast 触发：在 {} 后停止执行", result.scenario_id)
                break

        logger.info("[Engine] Suite 执行完成: suite_id={} total={} passed={} failed={} error={} exit_code={}",
                    suite_id, total, passed, failed, error, 0 if (failed + error) == 0 else 1)

        return RunResult(
            exit_code=0 if (failed + error) == 0 else 1,
            total=total, passed=passed,
            failed=failed, error=error,
            details=details,
        )

