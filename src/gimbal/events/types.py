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

历史说明（Issue 5 合并）：早期另有一份 context/events.py 定义了 *Started/*Completed
事件（"step.started" / "step.completed" / "scenario.started" / "scenario.completed"）。
本文件已合并双方字段（strategy_kind、assertion_count、assertion_passed、promotion_count、
error_brief、suite_id、reason 等），event_type 字符串统一为 "step.start" / "step.end" /
"scenario.start" / "scenario.end" / "variable.promoted"。
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
    # Run 级元数据（CI/CD / git / 构建上下文等），由 CLI 在 bootstrap 之后 publish
    RUN_META = "run.meta"

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

    # Context 提升（合并自旧 context/events.py 的 VariablePromotedEvent）
    CONTEXT_PROMOTION = "context.promotion"  # 兼容旧订阅；新订阅应使用 VARIABLE_PROMOTED
    VARIABLE_PROMOTED = "variable.promoted"

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


class RunMetaEvent(FrameworkEvent):
    """Run 级元数据（CI/CD 上下文 / git 信息 / 触发人 / 业务自定义键值）。

    由 CLI 在 bootstrap() 之后、Engine.run() 之前 publish 一次。
    所有 reporter 可通过订阅此事件获得本次运行的元信息，而无需直接
    读取 BootstrapConfig 或 FrameworkContext（保持 reporter 层的
    "一切皆事件" 架构一致性，且支持事件流重放）。

    设计要点：
      - meta 字段为开放 dict，允许扩展任意 KV。
      - 不订阅此事件的 reporter 完全无感。
      - run_id 可为 None（CLI 此时通常还没拿到真正的 run_id，
        Engine 后续会发出带 run_id 的 RUN_START 事件，reporter
        可在 on_event 中按需关联）。
    """
    event_type: Literal["run.meta"] = "run.meta"
    meta: dict[str, Any] = Field(default_factory=dict)


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
    # suite_id 由 ContextManager 填充；ScenarioRunner 直接发时为空
    suite_id: str = ""
    scenario_id: str
    scenario_name: str
    step_count: int


class ScenarioEndEvent(FrameworkEvent):
    event_type: Literal["scenario.end"] = "scenario.end"
    # suite_id 由 ContextManager 填充；ScenarioRunner 直接发时为空
    suite_id: str = ""
    scenario_id: str
    status: str
    step_count: int
    # Scenario.meta 的 dump（tags / author / priority / version / description ...）
    # 默认空 dict 保证向后兼容；ScenarioRunner 在发布时填充
    meta: dict[str, Any] = Field(default_factory=dict)


# ── Step 级 ───────────────────────────────────────────
class StepStartEvent(FrameworkEvent):
    event_type: Literal["step.start"] = "step.start"
    scenario_id: str = ""
    step_id: str
    step_name: str
    # 由 ContextManager.project_step_started 填充；statemachine 直接发时为空
    strategy_kind: str = ""


class StepEndEvent(FrameworkEvent):
    event_type: Literal["step.end"] = "step.end"
    scenario_id: str = ""
    step_id: str
    status: str
    duration_ms: float
    # 以下字段由 ContextManager.project_step_completed 填充；statemachine 直接发时为 0/None
    assertion_count: int = 0
    assertion_passed: int = 0
    promotion_count: int = 0
    error_brief: Optional[str] = None


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
class VariablePromotedEvent(FrameworkEvent):
    """变量从一层 Context 提升到另一层时发布。

    合并自旧 context/events.py.VariablePromotedEvent。
    """
    event_type: Literal["variable.promoted"] = "variable.promoted"
    key: str
    from_layer: str
    to_layer: str
    by_step_id: str
    by_scenario_id: Optional[str] = None
    overwrote_previous: bool = False
    reason: Optional[str] = None


# 旧名：保留以兼容旧订阅代码（已 deprecated，新代码应使用 VariablePromotedEvent）
ContextPromotionEvent = VariablePromotedEvent  # type: ignore[assignment,misc]


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
