"""context/projections.py

把 Context 内部状态投影成对外事件。

历史：原文件 context/events.py 同时定义了 *Started/*Completed 事件类与 project_* 投影函数。
Issue 5 合并后：
  - 事件类统一在 gimbal.events.types，event_type 字符串规范为 "step.start"/"step.end" 等
  - 本文件只保留投影函数，避免双份定义
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from gimbal.events.types import (
    ScenarioStartEvent,
    ScenarioEndEvent,
    StepStartEvent,
    StepEndEvent,
    VariablePromotedEvent,
)

if TYPE_CHECKING:
    from .step import StepContext
    from .channels import Promotion


def project_scenario_started(scenario_ctx, run_id: str) -> ScenarioStartEvent:
    """把 scenario_ctx 投影为 ScenarioStartEvent:从 ctx 读取 started_at/suite_id/scenario_id/scenario_name/step_count;返回对外事件对象。"""
    return ScenarioStartEvent(
        timestamp=scenario_ctx.started_at,
        run_id=run_id,
        suite_id=scenario_ctx.suite_id,
        scenario_id=scenario_ctx.scenario_id,
        scenario_name=scenario_ctx.scenario_name,
        step_count=len(scenario_ctx.step_refs),
    )


def project_scenario_completed(scenario_ctx, run_id: str) -> ScenarioEndEvent:
    """把 scenario_ctx 投影为 ScenarioEndEvent:使用 ended_at(若为空则取当前 UTC)与 status/step_count;返回对外事件对象。"""
    return ScenarioEndEvent(
        timestamp=scenario_ctx.ended_at or datetime.now(timezone.utc),
        run_id=run_id,
        suite_id=scenario_ctx.suite_id,
        scenario_id=scenario_ctx.scenario_id,
        status=scenario_ctx.status,
        step_count=len(scenario_ctx.step_refs),
    )


def project_step_started(ctx: "StepContext", run_id: str) -> StepStartEvent:
    """把 StepContext 投影为 StepStartEvent:从 inputs 读取 step_name/strategy_kind,记录 started_at;返回对外事件对象。"""
    return StepStartEvent(
        timestamp=ctx.started_at,
        run_id=run_id,
        scenario_id=ctx.scenario_id,
        step_id=ctx.step_id,
        step_name=ctx.inputs.step_name,
        strategy_kind=ctx.inputs.strategy_kind,
    )


def project_step_completed(ctx: "StepContext", run_id: str) -> StepEndEvent:
    """把 StepContext 投影为 StepEndEvent:统计 assertion_passed,汇总 status/duration_ms/assertion_count/promotion_count/error_brief;返回对外事件对象。"""
    passed = sum(1 for a in ctx.outcome.assertions if a.passed)
    return StepEndEvent(
        timestamp=ctx.ended_at or datetime.now(timezone.utc),
        run_id=run_id,
        scenario_id=ctx.scenario_id,
        step_id=ctx.step_id,
        status=ctx.outcome.status.value,
        duration_ms=ctx.outcome.duration_ms or 0.0,
        assertion_count=len(ctx.outcome.assertions),
        assertion_passed=passed,
        promotion_count=len(ctx.outcome.promotions_made),
        error_brief=ctx.outcome.error_info.message if ctx.outcome.error_info else None,
    )


def project_promotion(p: "Promotion", run_id: str) -> VariablePromotedEvent:
    """把 Promotion 记录投影为 VariablePromotedEvent:携带 key/from_layer/to_layer/by_step_id/overwrote_previous/reason;返回对外事件对象。"""
    return VariablePromotedEvent(
        timestamp=p.at,
        run_id=run_id,
        key=p.key,
        from_layer=p.from_layer.value,
        to_layer=p.to_layer.value,
        by_step_id=p.by_step_id,
        by_scenario_id=p.by_scenario_id,
        overwrote_previous=p.overwrote_previous,
        reason=p.reason,
    )
