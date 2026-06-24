from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from .base import ContextLayer
from .channels import Channels, ChannelsPolicy, Policies, Promotion
from .framework import FrameworkContext
from .suite import SuiteContext
from .scenario import ScenarioContext
from .step import StepContext, StepInputs, StepStatus
from gimbal.core.bootstrap import Configuration
from .projections import (
    project_scenario_started, project_scenario_completed,
    project_step_started, project_step_completed, project_promotion,
)
from gimbal.log import get_logger

logger = get_logger(__name__)


class ContextManager:
    """Context 生命周期协调器。无业务状态。"""
    
    def __init__(self, archive, event_bus):
        """初始化 ContextManager;持有 archive(用于持久化)和 event_bus(用于发布事件)两个无业务状态的依赖。"""
        self._archive = archive
        self._event_bus = event_bus
        logger.debug("[ContextManager] Initialized with archive={} event_bus={}", archive, event_bus)

    # ── Framework ─────────────────────────────────────
    def create_framework_context(
        self, *, run_id: str, cfg: Configuration,
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> FrameworkContext:
        """创建并封存 FrameworkContext:注入 channels(默认 framework_locked policy),挂接 promotion 监听器;返回 sealed 后的 FrameworkContext。"""
        # 增加配置层的初始化
        channels = Channels(
            owner_layer=ContextLayer.FRAMEWORK,
            policy=channels_policy or Policies.framework_locked(),
        )
        self._wire_promotion_listener(channels, run_id)

        ctx = FrameworkContext(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
            config=cfg.cfg,
            ctx_manager=cfg.ctx_manager,
            dispatcher=cfg.dispatcher,
            event_bus=cfg.event_bus,
            archive=cfg.archive,
            channels=channels,
        )
        ctx.seal()
        logger.info("[ContextManager] FrameworkContext created: run_id={}", run_id)
        return ctx

    # ── Suite ─────────────────────────────────────────
    def derive_suite_context(
        self, framework_ctx: FrameworkContext,
        *, suite_id: str, suite_name: str,
        tags: list[str], plugins: dict[str, dict],
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> SuiteContext:
        """基于 framework_ctx 派生 SuiteContext:用 suite_default policy 创建 channels,挂接 promotion 监听器,引用父 context 的 config;返回未 seal 的 SuiteContext。"""
        channels = Channels(
            owner_layer=ContextLayer.SUITE,
            policy=channels_policy or Policies.suite_default(),
        )
        self._wire_promotion_listener(channels, framework_ctx.run_id)

        logger.debug("[ContextManager] SuiteContext deriving: suite_id={} suite_name={}", suite_id, suite_name)
        return SuiteContext(
            suite_id=suite_id,
            suite_name=suite_name,
            tags=tags,
            started_at=datetime.now(timezone.utc),
            parent=framework_ctx,
            config=framework_ctx.config,  # 引用传递
            plugins=plugins,
            channels=channels,
        )

    def finalize_suite(self, ctx: SuiteContext, status: str = "passed") -> None:
        """结束 SuiteContext:用 object.__setattr__ 写入 ended_at/status(绕过 seal),seal 后归档;status 默认 "passed"。"""
        # 用 object.__setattr__ 绕过 seal 检查写入终态字段
        # 这是 ContextManager 的特权操作,业务代码无法这样写
        object.__setattr__(ctx, "ended_at", datetime.now(timezone.utc))
        object.__setattr__(ctx, "status", status)
        ctx.seal()
        self._archive.save_suite(ctx)
        logger.info("[ContextManager] SuiteContext finalized: suite_id={} status={}", ctx.suite_id, status)

    # ── Scenario ──────────────────────────────────────
    def derive_scenario_context(
        self, suite_ctx: SuiteContext,
        *, scenario_id: str, scenario_name: str,
        description: Optional[str] = None,
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> ScenarioContext:
        """基于 suite_ctx 派生 ScenarioContext:用 scenario_default policy 创建 channels,挂接 promotion 监听器,发布 scenario.start 事件;返回未 seal 的 ScenarioContext。"""
        channels = Channels(
            owner_layer=ContextLayer.SCENARIO,
            policy=channels_policy or Policies.scenario_default(),
        )
        self._wire_promotion_listener(channels, suite_ctx.run_id)

        ctx = ScenarioContext(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            description=description,
            started_at=datetime.now(timezone.utc),
            parent=suite_ctx,
            config=suite_ctx.config,  # 引用传递
            channels=channels,
        )
        self._event_bus.publish(project_scenario_started(ctx, ctx.run_id))
        logger.info("[ContextManager] ScenarioContext created: scenario_id={} suite_id={}",
                    scenario_id, suite_ctx.suite_id)
        return ctx

    def finalize_scenario(self, ctx: ScenarioContext, status: str) -> None:
        """结束 ScenarioContext:写入 ended_at/status,seal 后发布 scenario.end 事件并归档。"""
        object.__setattr__(ctx, "ended_at", datetime.now(timezone.utc))
        object.__setattr__(ctx, "status", status)
        ctx.seal()
        self._event_bus.publish(project_scenario_completed(ctx, ctx.run_id))
        self._archive.save_scenario(ctx)
        logger.info("[ContextManager] ScenarioContext finalized: scenario_id={} status={} step_count={}",
                    ctx.scenario_id, status, len(ctx.step_refs))

    # ── Step ──────────────────────────────────────────
    def derive_step_context(
        self, scenario_ctx: ScenarioContext,
        *, step_id: str, step_name: str,
        strategy_kind: str, strategy_spec: dict,
        resolved_vars: dict,
        description: Optional[str] = None,
    ) -> StepContext:
        """基于 scenario_ctx 派生 StepContext:构造 StepInputs,发布 step.start 事件;返回未 seal 的 StepContext。"""
        inputs = StepInputs(
            step_id=step_id,
            step_name=step_name,
            description=description,
            strategy_kind=strategy_kind,
            strategy_spec=strategy_spec,
            resolved_vars=resolved_vars,
        )
        ctx = StepContext(
            inputs=inputs,
            started_at=datetime.now(timezone.utc),
            parent=scenario_ctx,
        )
        self._event_bus.publish(project_step_started(ctx, scenario_ctx.run_id))
        logger.debug("[ContextManager] StepContext created: step_id={} scenario_id={} strategy={}",
                     step_id, scenario_ctx.scenario_id, strategy_kind)
        return ctx

    def finalize_step(self, ctx: StepContext, status: StepStatus) -> None:
        """结束 StepContext:写入 outcome.status/duration_ms/ended_at,登记到 scenario.step_refs,归档 step 与 exchange,清空 scratch,seal 后发布 step.end 事件。"""
        ended = datetime.now(timezone.utc)
        # outcome 是 validate_assignment 的可变模型,这些写入是合法的
        ctx.outcome.status = status
        ctx.outcome.duration_ms = (ended - ctx.started_at).total_seconds() * 1000
        # step 自身的字段——seal 前修改
        object.__setattr__(ctx, "ended_at", ended)

        # 把本 step 登记到 scenario 的 step_refs(scenario 此时未 seal,直接 append)
        ctx.parent.step_refs.append(ctx.step_id)

        # 归档前快照 HTTP 数据（scratch clear 之前）
        self._archive.save_step(ctx)
        scratch_snapshot = ctx.scratch.as_dict()
        if any(k in scratch_snapshot for k in (
            "response_status", "response_body", "request_url"
        )):
            self._archive.save_exchange(scratch_snapshot, ctx.step_id)

        # scratch 随 Step 生命周期结束
        ctx.scratch.clear()

        ctx.seal()
        self._event_bus.publish(project_step_completed(ctx, ctx.parent.run_id))
        logger.info("[ContextManager] StepContext finalized: step_id={} status={} duration_ms={:.2f}",
                    ctx.step_id, status.value, ctx.outcome.duration_ms)

    # ── 内部:把 Channels 的 Promotion 转事件 ──────────
    def _wire_promotion_listener(self, channels: Channels, run_id: str) -> None:
        """内部辅助:为 channels 注册一个监听器,把每次 Promotion 投影为 VariablePromotedEvent 并发布到 event_bus。"""
        def listener(promotion: Promotion):
            self._event_bus.publish(project_promotion(promotion, run_id))
        channels.add_listener(listener)