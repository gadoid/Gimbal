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
from gimbal.context.resolver import SpecResolver
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
        config,
        service_base_url: str = "",
    ) -> None:
        self._dispatcher = dispatcher
        self._ctx_manager = ctx_manager
        self._service_base_url = service_base_url
        self._config = config
        logger.debug("[StepRunner] 初始化: service_base_url=%s", service_base_url)

    def run(
        self,
        step_schema: Step,
        scenario_ctx: ScenarioContext,
        step_index: int,
    ) -> StepRunResult:
        step_id = f"step-{step_index:03d}"
        logger.debug("[StepRunner] 开始执行 Step: step_id=%s scenario_id=%s",
                     step_id, scenario_ctx.scenario_id)

        # 1. 创建 StepContext（由上层 scenario_ctx 派生）
        step_ctx = self._ctx_manager.derive_step_context(
            scenario_ctx,
            step_id=step_id,
            step_name=step_id,
            strategy_kind="multi",
            strategy_spec=step_schema.model_dump(),
            resolved_vars={},
        )
        logger.debug("[StepRunner] StepContext 创建完成: step_id=%s", step_id)
        view = StepContextAdapter(step_ctx)
        resolved_schema = SpecResolver(view, self._config).resolve(step_schema)  # 新增

        # 2. 构造状态机，注入全部执行依赖
        sm = StepStateMachine(
            step_id=step_id,
            step_schema=resolved_schema,
            dispatcher=self._dispatcher,
            view=StepContextAdapter(step_ctx),
            service_base_url=self._service_base_url,
        )
        logger.debug("[StepRunner] StepStateMachine 构造完成: step_id=%s", step_id)

        # 3. 状态机自驱动运行
        result = sm.run()
        logger.debug("[StepRunner] Step 执行完成: step_id=%s status=%s duration_ms=%.2f",
                     step_id, result.status, result.duration_ms)

        # 4. finalize StepContext
        step_status = StepStatus(result.status) \
            if result.status in StepStatus._value2member_map_ \
            else StepStatus.ERROR
        self._ctx_manager.finalize_step(step_ctx, step_status)
        logger.debug("[StepRunner] StepContext finalized: step_id=%s status=%s", step_id, step_status)

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
        logger.debug("[ScenarioRunner] 初始化完成")

    def run(
        self,
        scenario_schema: Scenario,
        suite_ctx: SuiteContext,
    ) -> ScenarioRunResult:
        started_at = datetime.utcnow()
        sid = scenario_schema.scenarioId
        logger.info("[ScenarioRunner] 开始执行 Scenario: scenario_id=%s scenario_name=%s step_count=%d",
                    sid, scenario_schema.meta.name, len(scenario_schema.steps))

        # 1. 派生 ScenarioContext（挂载在 suite_ctx 下）
        scenario_ctx = self._ctx_manager.derive_scenario_context(
            suite_ctx,
            scenario_id=sid,
            scenario_name=scenario_schema.meta.name,
            description=scenario_schema.meta.description,
        )
        logger.debug("[ScenarioRunner] ScenarioContext 创建完成: scenario_id=%s", sid)

        # 2. 注入 serviceDict / authDict
        self._inject_config(scenario_schema, scenario_ctx)
        print(f"config : {scenario_ctx.config}")

        # 3. 逐步执行
        step_runner = StepRunner(
            dispatcher=self._dispatcher,
            ctx_manager=self._ctx_manager,
            config = scenario_ctx.config,
            service_base_url=self._pick_base_url(scenario_schema),
        )

        step_results: list[StepRunResult] = []
        overall_status = "passed"

        for idx, step_union in enumerate(scenario_schema.steps):
            if not hasattr(step_union, "api"):
                logger.warning("[ScenarioRunner] step[%d] 是未展开的 Ref，跳过", idx)
                continue

            logger.debug("[ScenarioRunner] 开始执行第 %d/%d 个 Step: scenario_id=%s",
                        idx + 1, len(scenario_schema.steps), sid)
            result = step_runner.run(step_union, scenario_ctx, idx)
            step_results.append(result)

            logger.info("[ScenarioRunner] Step 完成: step_id=%s status=%s duration_ms=%.2f (%d/%d)",
                       result.step_id, result.status, result.duration_ms, idx + 1, len(scenario_schema.steps))

            if not result.passed:
                overall_status = result.status
                logger.warning("[ScenarioRunner] Scenario 中断: step_id=%s 失败，后续 step 不再执行", result.step_id)
                break   # fail_fast，后续 step 不再执行

        # 4. finalize ScenarioContext
        self._ctx_manager.finalize_scenario(scenario_ctx, overall_status)
        logger.debug("[ScenarioRunner] ScenarioContext finalized: scenario_id=%s status=%s", sid, overall_status)

        return ScenarioRunResult(
            scenario_id=sid,
            status=overall_status,
            step_results=step_results,
            started_at=started_at,
            ended_at=datetime.utcnow(),
        )

    # ── 内部辅助 ─────────────────────────────────────────────────────────────

    def _inject_config(self, schema: Scenario, ctx: ScenarioContext) -> None:
        """把 serviceDict / authDict 注入到上下文中。

        - serviceDict: 写入 channels，供 ${service.*} 引用
        - authDict: 转换为 AuthSession，存入 users_pool，并触发认证
        """
        from gimbal.context.base import ContextLayer
        from gimbal.schema.auth import AuthSession
        from gimbal.auth import AuthManager

        # 1. 注入 serviceDict 到 channels
        service_dict = getattr(schema.config, "serviceDict", None) or {}
        logger.debug("[ScenarioRunner] 注入配置: service_count=%d", len(service_dict))

        for k, v in service_dict.items():
            ctx.channels.promote_from(
                key=f"service.{k}", value=v,
                from_layer=ContextLayer.STEP,
                by_step_id="__framework__",
            )

        # 2. 注入 authDict 到 users_pool 并触发认证
        auth_dict = getattr(schema.config, "authDict", None) or {}
        if auth_dict:
            tag = auth_dict.pop("tag", None)
            if tag:
                auth_session = AuthSession(**auth_dict)
                ctx.config.users_pool[tag] = auth_session
                logger.info("[ScenarioRunner] authDict 注入完成: tag=%s", tag)

                # 触发一次认证
                auth_manager = AuthManager(ctx.config)
                try:
                    auth_manager.get_auth(tag)
                    auth_session = ctx.config.users_pool.get(tag)
                    logger.info("[ScenarioRunner] 认证成功: tag=%s token=%s", tag, auth_session.token if auth_session else None)
                except Exception as e:
                    logger.error("[ScenarioRunner] 认证失败: tag=%s error=%s", tag, e)
                    raise

    def _pick_base_url(self, schema: Scenario) -> str:
        sd = getattr(schema.config, "serviceDict", None) or {}
        base_url = next(iter(sd.values()), "")
        logger.debug("[ScenarioRunner] 选取 base_url: %s", base_url)
        return base_url