"""events/types.py
框架事件类型定义。
所有事件必须继承 FrameworkEvent，event_type 自动用类名生成。
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class FrameworkEvent(BaseModel):
    """所有框架事件的基类。"""
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_type: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    run_id: Optional[str] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 自动从类名生成 event_type（去掉 Event 后缀，PascalCase -> snake_case）
        if not cls.__dict__.get("event_type", ""):
            name = cls.__name__
            if name.endswith("Event"):
                name = name[:-5]
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
            # 必须设置到类属性上（不是 instance default）
            cls.__annotations__ = cls.__annotations__
            # 直接设置 field default
            if "event_type" in cls.model_fields:
                cls.model_fields["event_type"].default = snake


# ── 框架级 ─────────────────────────────────────────────
class FrameworkInitEvent(FrameworkEvent):
    event_type: Literal["framework.init"] = "framework.init"
    framework_version: str


class FrameworkTeardownEvent(FrameworkEvent):
    event_type: Literal["framework.teardown"] = "framework.teardown"


# ── Run 级 ─────────────────────────────────────────────
class RunStartEvent(FrameworkEvent):
    event_type: Literal["run.start"] = "run.start"
    env: str
    mode: str


class RunEndEvent(FrameworkEvent):
    event_type: Literal["run.end"] = "run.end"
    total: int
    passed: int
    failed: int
    error: int


# ── Suite/Scenario 级 ─────────────────────────────────
class SuiteStartEvent(FrameworkEvent):
    event_type: Literal["suite.start"] = "suite.start"
    suite_id: str
    suite_name: str


class SuiteEndEvent(FrameworkEvent):
    event_type: Literal["suite.end"] = "suite.end"
    suite_id: str
    status: str


class ScenarioStartEvent(FrameworkEvent):
    event_type: Literal["scenario.start"] = "scenario.start"
    scenario_id: str
    scenario_name: str
    step_count: int


class ScenarioEndEvent(FrameworkEvent):
    event_type: Literal["scenario.end"] = "scenario.end"
    scenario_id: str
    status: str
    step_count: int


# ── Step 级 ───────────────────────────────────────────
class StepStartEvent(FrameworkEvent):
    event_type: Literal["step.start"] = "step.start"
    step_id: str
    step_name: str


class StepEndEvent(FrameworkEvent):
    event_type: Literal["step.end"] = "step.end"
    step_id: str
    status: str
    duration_ms: float


class StepFailedEvent(FrameworkEvent):
    event_type: Literal["step.failed"] = "step.failed"
    step_id: str
    error: str
    phase: str


# ── HTTP 级 ───────────────────────────────────────────
class HttpRequestEvent(FrameworkEvent):
    event_type: Literal["http.request"] = "http.request"
    step_id: str
    method: str
    url: str
    request_body: Any = None
    request_headers: dict = Field(default_factory=dict)


class HttpResponseEvent(FrameworkEvent):
    event_type: Literal["http.response"] = "http.response"
    step_id: str
    method: str
    url: str
    status_code: int
    duration_ms: float
    response_body: Any = None


# ── Context 提升 ─────────────────────────────────────
class ContextPromotionEvent(FrameworkEvent):
    event_type: Literal["context.promotion"] = "context.promotion"
    key: str
    from_layer: str
    to_layer: str
    by_step_id: str
    by_scenario_id: Optional[str] = None
    overwrote_previous: bool = False


# ── 插件生命周期 ─────────────────────────────────────
class PluginActivatedEvent(FrameworkEvent):
    event_type: Literal["plugin.activated"] = "plugin.activated"
    plugin_name: str
    version: str
    capabilities: list[str] = Field(default_factory=list)


class PluginFailedEvent(FrameworkEvent):
    event_type: Literal["plugin.failed"] = "plugin.failed"
    plugin_name: str
    error: str
    stage: str


class PluginDeactivatedEvent(FrameworkEvent):
    event_type: Literal["plugin.deactivated"] = "plugin.deactivated"
    plugin_name: str
