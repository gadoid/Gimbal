"""core/scenario_runner.py

ScenarioRunner 驱动整个 Scenario，StepRunner 构造状态机并调用 run()。

StepRunner 不再感知状态流转的细节，那是状态机自己的事。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from gimbal.context.manager import ContextManager
from gimbal.context.scenario import ScenarioContext
from gimbal.context.step import StepStatus
from gimbal.context.suite import SuiteContext
from gimbal.context.views import StepContextAdapter
from gimbal.schema.scenario import Scenario
from gimbal.schema.step import Step
from gimbal.statemachine.engine import StepStateMachine, StepRunResult
from gimbal.strategy.dispatcher import StrategyDispatcher

logger = logging.getLogger(__name__)


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

    StepRunner 的职责：
      1. 创建 StepContext（在 scenario_ctx 下派生）
      2. 构造 StepStateMachine（注入执行所需的全部依赖）
      3. 调用 sm.run()，拿到结果
      4. finalize StepContext

    状态如何流转、每个阶段做什么——全部交给状态机，这里不感知。
    """

    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
        service_base_url: str = "",
    ) -> None:
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._service_base_url = service_base_url

    def run(
        self,
        step_schema: Step,
        scenario_ctx: ScenarioContext,
        step_index: int,
    ) -> StepRunResult:
        step_id = f"step-{step_index:03d}"

        # 1. 创建 StepContext（由上层 scenario_ctx 派生）
        step_ctx = self._ctx_manager.derive_step_context(
            scenario_ctx,
            step_id=step_id,
            step_name=step_id,
            strategy_kind="multi",
            strategy_spec=step_schema.model_dump(),
            resolved_vars={},
        )

        # 2. 构造状态机，注入全部执行依赖
        sm = StepStateMachine(
            step_id=step_id,
            step_schema=step_schema,
            dispatcher=self._dispatcher,
            view=StepContextAdapter(step_ctx),
            service_base_url=self._service_base_url,
        )

        # 3. 状态机自驱动运行
        result = sm.run()

        # 4. finalize StepContext
        step_status = StepStatus(result.status) \
            if result.status in StepStatus._value2member_map_ \
            else StepStatus.ERROR
        self._ctx_manager.finalize_step(step_ctx, step_status)

        return result


# ── ScenarioRunner ────────────────────────────────────────────────────────────

class ScenarioRunner:
    """驱动整个 Scenario 的执行。

    职责：
      - 在 suite_ctx 下派生 ScenarioContext
      - 把 scenario 配置注入 context
      - 按序调用 StepRunner 执行每个 step
      - 汇总结果，finalize ScenarioContext
    """

    def __init__(
        self,
        dispatcher: StrategyDispatcher,
        ctx_manager: ContextManager,
    ) -> None:
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager

    def run(
        self,
        scenario_schema: Scenario,
        suite_ctx: SuiteContext,
    ) -> ScenarioRunResult:
        started_at = datetime.utcnow()
        sid = scenario_schema.scenarioId

        # 1. 派生 ScenarioContext（挂载在 suite_ctx 下）
        scenario_ctx = self._ctx_manager.derive_scenario_context(
            suite_ctx,
            scenario_id=sid,
            scenario_name=scenario_schema.meta.name,
            description=scenario_schema.meta.description,
        )

        # 2. 注入 serviceDict / authDict
        self._inject_config(scenario_schema, scenario_ctx)

        # 3. 逐步执行
        step_runner = StepRunner(
            dispatcher=self._dispatcher,
            ctx_manager=self._ctx_manager,
            service_base_url=self._pick_base_url(scenario_schema),
        )

        step_results: list[StepRunResult] = []
        overall_status = "passed"

        for idx, step_union in enumerate(scenario_schema.steps):
            if not hasattr(step_union, "api"):
                logger.warning("[Scenario %s] step[%d] 是未展开的 Ref，跳过", sid, idx)
                continue

            result = step_runner.run(step_union, scenario_ctx, idx)
            step_results.append(result)

            if not result.passed:
                overall_status = result.status
                break   # fail_fast，后续 step 不再执行

        # 4. finalize ScenarioContext
        self._ctx_manager.finalize_scenario(scenario_ctx, overall_status)

        return ScenarioRunResult(
            scenario_id=sid,
            status=overall_status,
            step_results=step_results,
            started_at=started_at,
            ended_at=datetime.utcnow(),
        )

    # ── 内部辅助 ─────────────────────────────────────────────────────────────

    def _inject_config(self, schema: Scenario, ctx: ScenarioContext) -> None:
        """把 serviceDict / authDict 写入 scenario channels。"""
        from gimbal.context.base import ContextLayer

        service_dict = getattr(schema.config, "serviceDict", None) or {}
        auth_dict = getattr(schema.config, "authDict", None) or {}

        for k, v in service_dict.items():
            ctx.channels.promote_from(
                key=f"service.{k}", value=v,
                from_layer=ContextLayer.STEP,
                by_step_id="__framework__",
            )
        for k, v in auth_dict.items():
            ctx.channels.promote_from(
                key=f"auth.{k}", value=v,
                from_layer=ContextLayer.STEP,
                by_step_id="__framework__",
            )

    def _pick_base_url(self, schema: Scenario) -> str:
        sd = getattr(schema.config, "serviceDict", None) or {}
        return next(iter(sd.values()), "")