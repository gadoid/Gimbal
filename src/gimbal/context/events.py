from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict

from .base import ContextLayer
from .channels import Promotion


class _EventBase(BaseModel):
    model_config = ConfigDict(frozen=True)
    timestamp: datetime
    run_id: str


class StepStartedEvent(_EventBase):
    event_type: Literal["step.started"] = "step.started"
    scenario_id: str
    step_id: str
    strategy_kind: str


class StepCompletedEvent(_EventBase):
    event_type: Literal["step.completed"] = "step.completed"
    scenario_id: str
    step_id: str
    status: str
    duration_ms: float
    assertion_count: int
    assertion_passed: int
    promotion_count: int
    error_brief: Optional[str] = None


class ScenarioStartedEvent(_EventBase):
    event_type: Literal["scenario.started"] = "scenario.started"
    suite_id: str
    scenario_id: str


class ScenarioCompletedEvent(_EventBase):
    event_type: Literal["scenario.completed"] = "scenario.completed"
    suite_id: str
    scenario_id: str
    status: str
    step_count: int


class VariablePromotedEvent(_EventBase):
    event_type: Literal["variable.promoted"] = "variable.promoted"
    key: str
    from_layer: str
    to_layer: str
    by_step_id: str
    by_scenario_id: Optional[str] = None
    overwrote_previous: bool
    reason: Optional[str] = None


# 投影函数
def project_step_started(ctx, run_id: str) -> StepStartedEvent:
    return StepStartedEvent(
        timestamp=ctx.started_at,
        run_id=run_id,
        scenario_id=ctx.scenario_id,
        step_id=ctx.step_id,
        strategy_kind=ctx.inputs.strategy_kind,
    )


def project_step_completed(ctx, run_id: str) -> StepCompletedEvent:
    passed = sum(1 for a in ctx.outcome.assertions if a.passed)
    return StepCompletedEvent(
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


def project_promotion(p: Promotion, run_id: str) -> VariablePromotedEvent:
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