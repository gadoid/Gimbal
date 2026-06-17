"""gimbal_collector/report_data.py

报告数据结构。事件流（run/scenario/step/http/promotion）按
`run_id → scenario_id → step_id` 串成树，渲染时直接 dump 为 JSON。

所有字段都使用基础类型（str / int / float / bool / None / dict / list），
以保证 `json.dumps` 能直接序列化。
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HttpExchange:
    """一次 HTTP 请求/响应对。

    request_* 来自 HttpRequestEvent，response_* 由 HttpResponseEvent 补全。
    """
    method: str
    url: str
    status_code: Optional[int] = None
    request_body: Any = None
    request_headers: dict = field(default_factory=dict)
    response_body: Any = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "status_code": self.status_code,
            "request_body": self.request_body,
            "request_headers": self.request_headers,
            "response_body": self.response_body,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class StepReport:
    step_id: str
    step_name: str
    status: str = "unknown"            # "running" | "passed" | "failed" | "error" | "skipped"
    duration_ms: float = 0.0
    http_exchanges: list[HttpExchange] = field(default_factory=list)
    promotions: list[dict] = field(default_factory=list)
    assertion_count: int = 0
    assertion_passed: int = 0
    error_brief: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "http_exchanges": [ex.to_dict() for ex in self.http_exchanges],
            "promotions": list(self.promotions),
            "assertion_count": self.assertion_count,
            "assertion_passed": self.assertion_passed,
            "error_brief": self.error_brief,
        }


@dataclass
class ScenarioReport:
    scenario_id: str
    scenario_name: str
    status: str = "unknown"
    started_at: str = ""
    ended_at: str = ""
    # 用 OrderedDict 保留 step 执行顺序
    steps: "OrderedDict[str, StepReport]" = field(default_factory=OrderedDict)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "steps": [s.to_dict() for s in self.steps.values()],
        }


@dataclass
class RunReport:
    run_id: str
    env: str = ""
    mode: str = ""
    started_at: str = ""
    ended_at: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    scenarios: "OrderedDict[str, ScenarioReport]" = field(default_factory=OrderedDict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "env": self.env,
            "mode": self.mode,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "error": self.error,
            },
            "scenarios": [s.to_dict() for s in self.scenarios.values()],
        }
