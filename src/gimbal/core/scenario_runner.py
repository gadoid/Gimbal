"""core/scenario_runner.py

ScenarioRunner 驱动整个 Scenario，StepRunner 构造状态机并调用 run()。

StepRunner 不再感知状态流转的细节，那是状态机自己的事。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
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


# ── ScenarioRunResult ─────────────────────────────────────────────────────────

@dataclass
class ScenarioRunResult:
    scenario_id: str
    status: str
    step_results: list[StepRunResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def duration_ms(self) -> float:
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
    ) -> None:
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._service_base_url = service_base_url
        self._hooks = hook_registry
        self._bus = event_bus
        logger.debug("[StepRunner] 初始化: service_base_url={}", service_base_url)

    def run(
        self,
        step_schema: Step,
        scenario_ctx: ScenarioContext,
        step_index: int,
    ) -> StepRunResult:
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


# ── ScenarioRunner ────────────────────────────────────────────────────────────

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
        asset_store: Optional[Any] = None,
    ) -> None:
        """
        Args:
            ...: 原有参数
            asset_store: 资产仓库（None 时跳过 Phase 0 引用物化）。
                         传入即在 preprocessor 中启用对 scenario.steps 树中
                         所有 RefBase 节点的结构化实例化。
        """
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._hooks = hook_registry
        self._bus = event_bus
        self._auth_registry = auth_registry
        self._asset_store = asset_store
        logger.debug(
            "[ScenarioRunner] 初始化完成: asset_store={}",
            type(asset_store).__name__ if asset_store is not None else "None",
        )

    def run(
        self,
        scenario_schema: Scenario,
        suite_ctx: SuiteContext,
    ) -> ScenarioRunResult:
        started_at = datetime.utcnow()
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
            asset_store=self._asset_store,
        )
        resolved_steps, base_url = preprocessor.run()
        logger.debug(
            "[ScenarioRunner] 预处理完成: resolved_steps={} base_url={}",
            len(resolved_steps), base_url,
        )

        # 3. 触发 SCENARIO_START 事件
        self._emit_scenario_start(scenario_schema, sid, len(resolved_steps))

        # 4. 逐步执行（使用已展开的 resolved_steps）
        step_runner = StepRunner(
            dispatcher=self._dispatcher,
            ctx_manager=self._ctx_manager,
            service_base_url=base_url,
            hook_registry=self._hooks,
            event_bus=self._bus,
        )

        step_results: list[StepRunResult] = []
        overall_status = "passed"

        for idx, step_union in enumerate(resolved_steps):
            if not hasattr(step_union, "api"):
                logger.warning("[ScenarioRunner] step[{}] 是未展开的 StepRef，跳过", idx)
                continue

            logger.debug(
                "[ScenarioRunner] 开始执行第 {}/{} 个 Step: scenario_id={}",
                idx + 1, len(resolved_steps), sid,
            )
            result = step_runner.run(step_union, scenario_ctx, idx)
            step_results.append(result)

            logger.info(
                "[ScenarioRunner] Step 完成: step_id={} status={} duration_ms={:.2f} ({}/{})",
                result.step_id, result.status, result.duration_ms,
                idx + 1, len(resolved_steps),
            )

            if not result.passed:
                overall_status = result.status
                logger.warning(
                    "[ScenarioRunner] Scenario 中断: step_id={} 失败，后续 step 不再执行",
                    result.step_id,
                )
                break

        # 5. finalize ScenarioContext
        self._ctx_manager.finalize_scenario(scenario_ctx, overall_status)
        logger.debug(
            "[ScenarioRunner] ScenarioContext finalized: scenario_id={} status={}",
            sid, overall_status,
        )

        # 6. 触发 SCENARIO_END 事件
        self._emit_scenario_end(sid, overall_status, len(resolved_steps))

        return ScenarioRunResult(
            scenario_id=sid,
            status=overall_status,
            step_results=step_results,
            started_at=started_at,
            ended_at=datetime.utcnow(),
        )

    # ── 埋点辅助 ──
    def _emit_scenario_start(self, scenario: Scenario, sid: str, step_count: int) -> None:
        if self._bus is None:
            return
        try:
            from gimbal.events.types import ScenarioStartEvent
            self._bus.publish(ScenarioStartEvent(
                scenario_id=sid,
                scenario_name=scenario.meta.name,
                step_count=step_count,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[ScenarioRunner] emit SCENARIO_START failed")

    def _emit_scenario_end(self, sid: str, status: str, step_count: int) -> None:
        if self._bus is None:
            return
        try:
            from gimbal.events.types import ScenarioEndEvent
            self._bus.publish(ScenarioEndEvent(
                scenario_id=sid,
                status=status,
                step_count=step_count,
            ))
        except Exception:  # noqa: BLE001
            logger.debug("[ScenarioRunner] emit SCENARIO_END failed")
