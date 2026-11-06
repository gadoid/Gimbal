"""context/projections.py

把 Context 内部状态投影成对外事件。

历史：原文件 context/events.py 同时定义了 *Started/*Completed 事件类与 project_* 投影函数。
Issue 5 合并后：
  - 事件类统一在 gimbal.events.types，event_type 字符串规范为 "step.start"/"step.end" 等
  - 本文件只保留投影函数，避免双份定义
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

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
    """把 StepContext 投影为 StepStartEvent:从 inputs 读取 step_name/description/strategy_kind/strategy_spec,记录 started_at;返回对外事件对象。"""
    return StepStartEvent(
        timestamp=ctx.started_at,
        run_id=run_id,
        scenario_id=ctx.scenario_id,
        step_id=ctx.step_id,
        step_name=ctx.inputs.step_name,
        strategy_kind=ctx.inputs.strategy_kind,
        strategy_spec=dict(ctx.inputs.strategy_spec or {}),
        description=ctx.inputs.description,
    )


# step.end 报告面单值上限(字符):断言 actual/expected、提取值超长时截断,
# 防止一个大响应体经断言/提取把事件撑大(证据体走 call.exchange 的截断口径)
_STEP_VALUE_MAX_CHARS = 2000


def _compact(value: Any, limit: int = _STEP_VALUE_MAX_CHARS) -> Any:
    """标量与小结构原样返回;JSON 序列化后超 limit 的值转为截断字符串。"""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"…(+{len(value) - limit})"
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        text = repr(value)
    if len(text) <= limit:
        return value
    return text[:limit] + f"…(+{len(text) - limit})"


def _endpoint_of(evidence: Optional[dict]) -> str:
    """调用证据 → "METHOD url" 摘要;无调用证据为空串。"""
    if not evidence:
        return ""
    req = evidence.get("request") or {}
    method = str(req.get("method", "") or "")
    url = str(req.get("url", "") or "")
    return " ".join(p for p in (method, url) if p)


# 失败现场随步骤行长期保存,单体上限比事件证据(64K)更紧
_FAILURE_BODY_MAX_CHARS = 16 * 1024


def _failure_evidence(evidence: Optional[dict]) -> Optional[dict]:
    """失败步骤的调用证据(已脱敏;请求体/响应体按 16K 截断)。"""
    if not evidence:
        return None
    from gimbal.protocols.result import truncate_oversize
    out = dict(evidence)
    req = dict(out.get("request") or {})
    if "body" in req:
        req["body"] = truncate_oversize(req.get("body"), _FAILURE_BODY_MAX_CHARS)
    out["request"] = req
    resp = dict(out.get("response") or {})
    if "body" in resp:
        resp["body"] = truncate_oversize(resp.get("body"), _FAILURE_BODY_MAX_CHARS)
    out["response"] = resp
    return out


def project_step_completed(ctx: "StepContext", run_id: str,
                           *, call_evidence: Optional[dict] = None) -> StepEndEvent:
    """把 StepContext 投影为 StepEndEvent:计数 + 报告面(步骤名/说明/调用摘要/
    断言明细/提取值;failed/error 时附调用证据)。

    ``call_evidence``:finalize_step 在 scratch 清空前取得的调用证据
    (evidence_from_call_dict 产物,已脱敏 + 响应体截断)。
    """
    from gimbal.protocols.result import is_sensitive_path, redact_value
    passed = sum(1 for a in ctx.outcome.assertions if a.passed)
    assertions = [
        {
            "name": a.name,
            "target": a.target,
            "operator": a.operator,
            "expected": _compact(a.expected),
            "actual": _compact(a.actual),
            "passed": a.passed,
            "message": a.message,
        }
        for a in ctx.outcome.assertions
    ]
    extracts = [
        {"target": k,
         "value": redact_value(v) if is_sensitive_path(k) else _compact(v)}
        for k, v in ctx.outcome.extracted.items()
    ]
    status = ctx.outcome.status.value
    return StepEndEvent(
        timestamp=ctx.ended_at or datetime.now(timezone.utc),
        run_id=run_id,
        scenario_id=ctx.scenario_id,
        step_id=ctx.step_id,
        status=status,
        duration_ms=ctx.outcome.duration_ms or 0.0,
        assertion_count=len(ctx.outcome.assertions),
        assertion_passed=passed,
        promotion_count=len(ctx.outcome.promotions_made),
        retry_count=ctx.outcome.retry_count,
        error_brief=ctx.outcome.error_info.message if ctx.outcome.error_info else None,
        step_name=ctx.inputs.step_name,
        description=ctx.inputs.description,
        call_summary=_endpoint_of(call_evidence),
        assertions=assertions,
        extracts=extracts,
        failure_evidence=(_failure_evidence(call_evidence)
                          if status in ("failed", "error") else None),
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
