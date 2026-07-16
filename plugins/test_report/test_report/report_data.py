"""report_data.py
报告数据结构（v2 全量版）。

新增于 v2：
  - HttpExchange：单次 HTTP 请求/响应对
  - VariablePromotion：变量从一层 Context 提升到另一层的记录
  - StepReport 新增字段：strategy_kind / description / promotion_count /
                       phase / traceback / http_exchanges / promotions
  - ScenarioReport 新增：suite_id / meta（tags / author / priority / version）
  - RunReport 新增：framework_version / suites

字段全部为 JSON-safe 类型（str / int / float / bool / None / dict / list）。
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HttpExchange:
    """一次 HTTP 请求/响应对。

    request_* 由 HttpRequestEvent 填充，response_* 由 HttpResponseEvent 填充。
    """
    request_method: str = ""
    request_url: str = ""
    request_headers: dict = field(default_factory=dict)
    request_body: Any = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    response_body: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_method": self.request_method,
            "request_url": self.request_url,
            "request_headers": dict(self.request_headers),
            "request_body": self.request_body,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "response_body": self.response_body,
            "error": self.error,
        }


@dataclass
class VariablePromotion:
    """一次变量提升事件。

    from_layer → to_layer，例 step → scenario 或 scenario → suite。
    """
    key: str = ""
    from_layer: str = ""
    to_layer: str = ""
    by_step_id: str = ""
    by_scenario_id: Optional[str] = None
    overwrote_previous: bool = False
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "by_step_id": self.by_step_id,
            "by_scenario_id": self.by_scenario_id,
            "overwrote_previous": self.overwrote_previous,
            "reason": self.reason,
        }


@dataclass
class StepReport:
    step_id: str
    step_name: str
    status: str = "unknown"
    duration_ms: float = 0.0
    assertion_count: int = 0
    assertion_passed: int = 0
    promotion_count: int = 0
    # ── v2 新增 ──
    strategy_kind: str = ""          # http / sql / poll / extract / multi ...
    # 结构化 DSL 描述（断言 / 请求 / 提取 / 重试 / 条件等），来自
    # StepInputs.strategy_spec。reporter 可在 HTML 报告里完整展开
    # 让用户看到"这个 step 实际配置的策略参数"。
    strategy_spec: dict = field(default_factory=dict)
    description: Optional[str] = None
    # 实际执行的重试次数（来自 StepOutcome.retry_count，>0 表示重试过）
    retry_count: int = 0
    error_brief: Optional[str] = None
    phase: Optional[str] = None      # 失败阶段，由 StepFailedEvent 填
    traceback: Optional[str] = None  # 完整 traceback（预留）
    http_exchanges: list[HttpExchange] = field(default_factory=list)
    promotions: list[VariablePromotion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "strategy_kind": self.strategy_kind,
            "strategy_spec": dict(self.strategy_spec),
            "description": self.description,
            "retry_count": self.retry_count,
            "assertion_count": self.assertion_count,
            "assertion_passed": self.assertion_passed,
            "promotion_count": self.promotion_count,
            "error_brief": self.error_brief,
            "phase": self.phase,
            "traceback": self.traceback,
            "http_exchanges": [ex.to_dict() for ex in self.http_exchanges],
            "promotions": [p.to_dict() for p in self.promotions],
        }


@dataclass
class ScenarioReport:
    scenario_id: str
    scenario_name: str
    status: str = "unknown"
    started_at: str = ""
    ended_at: str = ""
    suite_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    steps: "OrderedDict[str, StepReport]" = field(default_factory=OrderedDict)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.steps.values() if s.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for s in self.steps.values() if s.status == "failed")

    @property
    def errored(self) -> int:
        return sum(1 for s in self.steps.values() if s.status == "error")

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def http_total(self) -> int:
        return sum(len(s.http_exchanges) for s in self.steps.values())

    @property
    def promotion_total(self) -> int:
        return sum(len(s.promotions) for s in self.steps.values())

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "suite_id": self.suite_id,
            "meta": dict(self.meta),
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "error": self.errored,
                "http_total": self.http_total,
                "promotion_total": self.promotion_total,
            },
            "steps": [s.to_dict() for s in self.steps.values()],
        }


@dataclass
class SuiteReport:
    suite_id: str
    suite_name: str = ""
    status: str = "unknown"
    started_at: str = ""
    ended_at: str = ""
    scenarios: "OrderedDict[str, ScenarioReport]" = field(default_factory=OrderedDict)

    @property
    def total(self) -> int:
        return sum(s.total for s in self.scenarios.values())

    @property
    def passed(self) -> int:
        return sum(s.passed for s in self.scenarios.values())

    @property
    def failed(self) -> int:
        return sum(s.failed for s in self.scenarios.values())

    @property
    def errored(self) -> int:
        return sum(s.errored for s in self.scenarios.values())

    def to_dict(self) -> dict:
        return {
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "error": self.errored,
            },
            "scenarios": [s.to_dict() for s in self.scenarios.values()],
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
    skipped: int = 0
    framework_version: str = ""
    suites: "OrderedDict[str, SuiteReport]" = field(default_factory=OrderedDict)
    # 没收到 SuiteStart 的 scenario 会归到这里（向后兼容）
    _loose_scenarios: "OrderedDict[str, ScenarioReport]" = field(
        default_factory=OrderedDict, repr=False
    )
    meta: dict[str, Any] = field(default_factory=dict)

    def scenario_iter(self):
        """跨 suite/loose 收集所有 scenario，给 summary 用。"""
        if self.suites:
            for s in self.suites.values():
                yield from s.scenarios.values()
        yield from self._loose_scenarios.values()

    @property
    def http_total(self) -> int:
        return sum(s.http_total for s in self.scenario_iter())

    @property
    def promotion_total(self) -> int:
        return sum(s.promotion_total for s in self.scenario_iter())

    def to_dict(self) -> dict:
        all_scenarios = list(self.scenario_iter())
        return {
            "run_id": self.run_id,
            "env": self.env,
            "mode": self.mode,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "framework_version": self.framework_version,
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "error": self.error,
                "skipped": self.skipped,
                "http_total": self.http_total,
                "promotion_total": self.promotion_total,
            },
            "meta": dict(self.meta),
            "suites": [s.to_dict() for s in self.suites.values()],
            "scenarios": [s.to_dict() for s in all_scenarios],
        }


# 为了让 RunReport 在没有收到 suite 事件时也能展示 scenario，
# store 里会优先把 scenario 挂到对应 suite；没 suite 时走 _loose_scenarios。
# 这里提供一个 __init_subclass__ / __post_init__ 兼容老路径：
# 老 v1 数据流里 store 直接写 report.scenarios[...]=ScenarioReport(...),
# 为了兼容，我们在 store.py 里统一走 _attach_scenario() helper。
