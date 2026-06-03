"""events/types.py
框架事件类型定义。
所有事件必须继承 FrameworkEvent，并显式声明 event_type 字面量。

历史说明：早期版本尝试通过 __init_subclass__ 从类名自动推导 event_type，
但 Pydantic v2 的 model_fields 在类创建时已冻结，运行时改 default 不生效。
所有子类都已显式声明 Literal[xxx] = "xxx" 形式，所以那段"自动生成"代码
实际上是死代码。这里删掉以避免误导。

命名约定（Issue 4 修复后与 HookPoint 对称）：
    - event_type 字符串：dot.notation  小写（"http.request"）
    - EventType 枚举：  SCREAMING_SNAKE，但值仍是 dot.notation
    用户可任选其一：
        bus.subscribe(handler, "http.request")         # 字符串
        bus.subscribe(handler, EventType.HTTP_REQUEST)  # 枚举
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


# ── EventType 枚举（与 HookPoint 对称） ──────────────────────

class EventType(str, Enum):
    """事件类型枚举——与 HookPoint 的设计风格一致。

    目的：让"订阅事件"和"注册 hook"的 API 看起来一样：
        bus.subscribe(handler, EventType.STEP_START)
        hook_registry.register(HookPoint.STEP_START, handler)

    字符串字面量仍然有效：
        bus.subscribe(handler, "step.start")
    """
    # 框架生命周期
    FRAMEWORK_INIT = "framework.init"
    FRAMEWORK_TEARDOWN = "framework.teardown"

    # Run 生命周期
    RUN_START = "run.start"
    RUN_END = "run.end"

    # Suite 生命周期
    SUITE_START = "suite.start"
    SUITE_END = "suite.end"

    # Scenario 生命周期
    SCENARIO_START = "scenario.start"
    SCENARIO_END = "scenario.end"

    # Step 生命周期
    STEP_START = "step.start"
    STEP_END = "step.end"
    STEP_FAILED = "step.failed"

    # HTTP 调用
    HTTP_REQUEST = "http.request"
    HTTP_RESPONSE = "http.response"

    # Context 提升
    CONTEXT_PROMOTION = "context.promotion"

    # 插件生命周期
    PLUGIN_ACTIVATED = "plugin.activated"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_DEACTIVATED = "plugin.deactivated"


class FrameworkEvent(BaseModel):
    """所有框架事件的基类。

    子类必须显式声明 event_type 字面量，例如：
        class StepStartEvent(FrameworkEvent):
            event_type: Literal["step.start"] = "step.start"
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_type: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    run_id: Optional[str] = None


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
