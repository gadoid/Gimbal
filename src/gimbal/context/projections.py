"""context/projections.py

把 Context 内部状态投影成对外事件。

历史：原文件 context/events.py 同时定义了 *Started/*Completed 事件类与 project_* 投影函数。
Issue 5 合并后：
  - 事件类统一在 gimbal.events.types，event_type 字符串规范为 "step.start"/"step.end" 等
  - 本文件只保留投影函数，避免双份定义
"""
from __future__ import annotations

from datetime import datetime
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
    return ScenarioStartEvent(
        timestamp=scenario_ctx.started_at,
        run_id=run_id,
        suite_id=scenario_ctx.suite_id,
        scenario_id=scenario_ctx.scenario_id,
        scenario_name=scenario_ctx.scenario_name,
        step_count=len(scenario_ctx.step_refs),
    )


def project_scenario_completed(scenario_ctx, run_id: str) -> ScenarioEndEvent:
    return ScenarioEndEvent(
        timestamp=scenario_ctx.ended_at or datetime.utcnow(),
        run_id=run_id,
        suite_id=scenario_ctx.suite_id,
        scenario_id=scenario_ctx.scenario_id,
        status=scenario_ctx.status,
        step_count=len(scenario_ctx.step_refs),
    )


def project_step_started(ctx: "StepContext", run_id: str) -> StepStartEvent:
    return StepStartEvent(
        timestamp=ctx.started_at,
        run_id=run_id,
        scenario_id=ctx.scenario_id,
        step_id=ctx.step_id,
        step_name=ctx.inputs.step_name,
        strategy_kind=ctx.inputs.strategy_kind,
    )


def project_step_completed(ctx: "StepContext", run_id: str) -> StepEndEvent:
    passed = sum(1 for a in ctx.outcome.assertions if a.passed)
    return StepEndEvent(
        timestamp=ctx.ended_at or datetime.utcnow(),
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
