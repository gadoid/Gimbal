from datetime import datetime
from typing import Optional, TYPE_CHECKING
from .base import ContextLayer
from .channels import Channels, ChannelsPolicy, Policies, Promotion
from .framework import FrameworkContext
from .suite import SuiteContext
from .scenario import ScenarioContext
from .step import StepContext, StepInputs, StepStatus
from gimbal.core.boostrap import Configuration
from .events import (
    ScenarioStartedEvent, ScenarioCompletedEvent,
    project_step_started, project_step_completed, project_promotion,
)


class ContextManager:
    """Context 生命周期协调器。无业务状态。"""
    
    def __init__(self, archive, event_bus):
        self._archive = archive
        self._event_bus = event_bus
    
    # ── Framework ─────────────────────────────────────
    def create_framework_context(
        self, *, run_id: str, cfg: Configuration, 
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> FrameworkContext:
        # 增加配置层的初始化
        channels = Channels(
            owner_layer=ContextLayer.FRAMEWORK,
            policy=channels_policy or Policies.framework_locked(),
        )
        self._wire_promotion_listener(channels, run_id)
        
        ctx = FrameworkContext(
            run_id=run_id,
            started_at=datetime.utcnow(),
            config=cfg.cfg,
            ctx_manager=cfg.ctx_manager,
            dispatcher=cfg.dispatcher,
            event_bus=cfg.event_bus,
            archive=cfg.archive,
            channels=channels,
        )
        ctx.seal()
        return ctx
    
    # ── Suite ─────────────────────────────────────────
    def derive_suite_context(
        self, framework_ctx: FrameworkContext,
        *, suite_id: str, suite_name: str,
        tags: list[str], plugins: dict[str, dict],
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> SuiteContext:
        channels = Channels(
            owner_layer=ContextLayer.SUITE,
            policy=channels_policy or Policies.suite_default(),
        )
        self._wire_promotion_listener(channels, framework_ctx.run_id)

        return SuiteContext(
            suite_id=suite_id,
            suite_name=suite_name,
            tags=tags,
            started_at=datetime.utcnow(),
            parent=framework_ctx,
            config=framework_ctx.config,  # 引用传递
            plugins=plugins,
            channels=channels,
        )
    
    def finalize_suite(self, ctx: SuiteContext, status: str = "passed") -> None:
        # 用 object.__setattr__ 绕过 seal 检查写入终态字段
        # 这是 ContextManager 的特权操作,业务代码无法这样写
        object.__setattr__(ctx, "ended_at", datetime.utcnow())
        object.__setattr__(ctx, "status", status)
        ctx.seal()
        self._archive.save_suite(ctx)
    
    # ── Scenario ──────────────────────────────────────
    def derive_scenario_context(
        self, suite_ctx: SuiteContext,
        *, scenario_id: str, scenario_name: str,
        description: Optional[str] = None,
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> ScenarioContext:
        channels = Channels(
            owner_layer=ContextLayer.SCENARIO,
            policy=channels_policy or Policies.scenario_default(),
        )
        self._wire_promotion_listener(channels, suite_ctx.run_id)
        
        ctx = ScenarioContext(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            description=description,
            started_at=datetime.utcnow(),
            parent=suite_ctx,
            config=suite_ctx.config,  # 引用传递
            channels=channels,
        )
        self._event_bus.publish(ScenarioStartedEvent(
            timestamp=ctx.started_at,
            run_id=ctx.run_id,
            suite_id=ctx.suite_id,
            scenario_id=ctx.scenario_id,
        ))
        return ctx
    
    def finalize_scenario(self, ctx: ScenarioContext, status: str) -> None:
        object.__setattr__(ctx, "ended_at", datetime.utcnow())
        object.__setattr__(ctx, "status", status)
        ctx.seal()
        self._event_bus.publish(ScenarioCompletedEvent(
            timestamp=ctx.ended_at,
            run_id=ctx.run_id,
            suite_id=ctx.suite_id,
            scenario_id=ctx.scenario_id,
            status=status,
            step_count=len(ctx.step_refs),
        ))
        self._archive.save_scenario(ctx)
    
    # ── Step ──────────────────────────────────────────
    def derive_step_context(
        self, scenario_ctx: ScenarioContext,
        *, step_id: str, step_name: str,
        strategy_kind: str, strategy_spec: dict,
        resolved_vars: dict,
    ) -> StepContext:
        inputs = StepInputs(
            step_id=step_id,
            step_name=step_name,
            strategy_kind=strategy_kind,
            strategy_spec=strategy_spec,
            resolved_vars=resolved_vars,
        )
        ctx = StepContext(
            inputs=inputs,
            started_at=datetime.now(),
            parent=scenario_ctx,
        )
        self._event_bus.publish(project_step_started(ctx, scenario_ctx.run_id))
        return ctx
    
    def finalize_step(self, ctx: StepContext, status: StepStatus) -> None:
        ended = datetime.now()
        # outcome 是 validate_assignment 的可变模型,这些写入是合法的
        ctx.outcome.status = status
        ctx.outcome.duration_ms = (ended - ctx.started_at).total_seconds() * 1000
        # step 自身的字段——seal 前修改
        object.__setattr__(ctx, "ended_at", ended)
        
        # 把本 step 登记到 scenario 的 step_refs(scenario 此时未 seal,直接 append)
        ctx.parent.step_refs.append(ctx.step_id)
        
        ctx.seal()
        self._event_bus.publish(project_step_completed(ctx, ctx.parent.run_id))
        self._archive.save_step(ctx)
        if ctx.http_exchange is not None:
            self._archive.save_exchange(ctx.http_exchange, ctx.step_id)
    
    # ── 内部:把 Channels 的 Promotion 转事件 ──────────
    def _wire_promotion_listener(self, channels: Channels, run_id: str) -> None:
        def listener(promotion: Promotion):
            self._event_bus.publish(project_promotion(promotion, run_id))
        channels.add_listener(listener)