# Context 模块

> 上下文管理模块：Framework → Suite → Scenario → Step 四层执行上下文、Channels 通道、ContextManager 生命周期、Step 投影事件

## 目录结构

```
gimbal/context/
├── __init__.py
├── base.py           # ContextLayer / SealedBaseModel
├── framework.py      # FrameworkContext
├── suite.py          # SuiteContext
├── scenario.py       # ScenarioContext
├── step.py           # StepContext / StepInputs / StepOutcome / StepScratch / AssertionResult / ErrorInfo
├── manager.py        # ContextManager
├── channels.py       # Channels / ChannelsPolicy / Promotion / Policies
├── views.py          # StepContextAdapter（Strategy 视图）
├── projections.py    # project_scenario_* / project_step_* / project_promotion
├── template.py       # 模板渲染（变量替换、{{}}、${}、$.jsonpath）
├── resolver.py       # 引用解析
├── functions.py      # 上下文函数
└── exceptions.py     # SealedContextError 等
```

> 旧的 `context/events.py` 已合并到 `events/types.py`（Issue 5）；投影函数集中在 `context/projections.py`。

## 核心概念

### ContextLayer 层级

```
FRAMEWORK (最高层)
    │
    └── SUITE
            │
            └── SCENARIO
                    │
                    └── STEP (最低层)
```

数据只能从低层向高层提升（Promote），不能反向。`ContextLayer.is_above(other)` 判断当前层是否在 other 之上。

### SealedBaseModel

所有 Context 的基类，封装 seal 机制：

```python
class SealedBaseModel(BaseModel):
    """seal 后:
    - 模型字段不可重新赋值（身份/状态字段冻结）
    - 但 Channels 这种"通道型"字段内部走 promote_from，不经过 __setattr__，
      因此 seal 不影响合法的变量提升。这是有意设计。
    """
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True, extra="forbid",
    )

    _sealed: bool = PrivateAttr(default=False)
    _sealed_at: Optional[datetime] = PrivateAttr(default=None)

    def seal(self) -> None: ...
    @property def is_sealed(self) -> bool: ...
    @property def sealed_at(self) -> Optional[datetime]: ...

    def __setattr__(self, name, value):
        # 内部 attr（以 _ 开头）绕过 seal
        # seal 后再赋值 → 抛 SealedContextError
        ...
```

子类需实现 `layer` 属性以声明所属层级。

## Context 类

### FrameworkContext

框架级上下文，持有整个 run 的配置与基础设施引用。生命周期属于"一次 run"。

### SuiteContext

Suite 级上下文。单 scenario 执行时 framework 用 `suite_id="__default__"` 派生。

### ScenarioContext

```python
class ScenarioContext(SealedBaseModel):
    scenario_id: str
    scenario_name: str
    description: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str = "pending"
    step_refs: list[str] = Field(default_factory=list)

    parent: SuiteContext = Field(exclude=True)
    config: BootstrapConfig = Field(exclude=True)   # 引用传递
    channels: Channels = Field(exclude=True)
```

### StepContext

```python
class StepContext(SealedBaseModel):
    inputs: StepInputs                  # 输入态（frozen）
    outcome: StepOutcome = Field(default_factory=StepOutcome)   # 产物态
    scratch: StepScratch = Field(default_factory=StepScratch, exclude=True)
    started_at: datetime
    ended_at: Optional[datetime] = None

    parent: ScenarioContext = Field(exclude=True)
```

### StepInputs / StepOutcome

```python
class StepInputs(BaseModel):
    """开始时定型，执行期间只读。frozen=True"""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    step_id: str
    step_name: str
    strategy_kind: str
    strategy_spec: dict
    resolved_vars: dict[str, Any]


class StepOutcome(BaseModel):
    """执行期间累积，finalize 时定型。"""
    model_config = ConfigDict(validate_assignment=True)

    status: StepStatus = StepStatus.PENDING
    extracted: dict[str, Any] = Field(default_factory=dict)
    assertions: list[AssertionResult] = Field(default_factory=list)
    response_artifact: Optional[str] = None     # 指向 scenario.channels 中 artifact name
    error_info: Optional[ErrorInfo] = None
    duration_ms: Optional[float] = None
    retry_count: int = 0
    promotions_made: list[str] = Field(default_factory=list)  # 本 step 提升过的 key


class AssertionResult(BaseModel):
    name: str
    passed: bool
    expected: Any
    actual: Any
    message: Optional[str] = None


class ErrorInfo(BaseModel):
    type: str
    message: str
    traceback: Optional[str] = None
```

### StepScratch（取代旧的 HttpExchange）

```python
class StepScratch:
    """Step 级统一临时存储。

    生命周期随 StepContext，finalize 后 clear。
    所有 Step 内临时数据统一存储，通过 JSONPath 导航读取。

    约定 key：
        request_method / request_url / request_headers / request_body
        response_status / response_headers / response_body
        duration_ms
        其余 key 为业务临时变量
    """
    def __init__(self) -> None: ...

    def set(self, key: str, value: Any) -> None
        # key 以 "$.xxx" 开头 → JSONPath 写入嵌套结构
        # 普通 key → _data[key] = value
        # sealed 后 set → 抛 SealedContextError

    def _set_jsonpath(self, path: str, value: Any) -> None: ...
    def get(self, key: str, default: Any = None) -> Any
    def has(self, key: str) -> bool
    def as_dict(self) -> dict[str, Any]      # 暴露给 JSONPath 引擎的根对象
    def seal(self) -> None
    def clear(self) -> None
    @property def is_sealed(self) -> bool
```

> 旧 `HttpExchange` 已重命名为 `StepScratch`，并扩展为通用临时存储。

## Channels 通道机制

三通道数据载体（variables / metadata / artifacts）：

```python
class Channels:
    """所有写入必须经过 promote_from()"""

    def promote_from(
        self,
        key: str,
        value: Any,
        from_layer: ContextLayer,
        by_step_id: str,
        allow_overwrite: bool = False,
    ) -> Promotion:
        """接受下层向本层提升一个变量"""
        ...
```

### ChannelsPolicy

声明本层 channels 接受什么样的提升：

```python
class ChannelsPolicy:
    accept_from_layers: frozenset[ContextLayer]  # 接受哪些层的提升
    overwritable_keys:   frozenset[str]            # 允许覆盖的 key
    forbidden_keys:      frozenset[str]            # 禁止的 key
    require_reason:      bool                       # 是否要求 reason
    allowed_key_prefixes: frozenset[str]            # 允许的 key 前缀
```

### 预设策略

```python
class Policies:
    @staticmethod
    def scenario_default() -> ChannelsPolicy:
        """Scenario: 接受 step 提升，大部分 key 可覆盖"""
        return ChannelsPolicy(accept_from_layers=frozenset({ContextLayer.STEP}))

    @staticmethod
    def suite_default() -> ChannelsPolicy:
        """Suite: 接受 scenario 提升，key 不可覆盖"""
        return ChannelsPolicy(
            accept_from_layers=frozenset({ContextLayer.SCENARIO}),
            require_reason=True,
        )

    @staticmethod
    def framework_locked() -> ChannelsPolicy:
        """Framework: 不接受任何提升"""
        return ChannelsPolicy(accept_from_layers=frozenset())
```

## ContextManager

Context 生命周期协调器：

```python
class ContextManager:
    """Context 生命周期协调器"""

    # Framework
    def create_framework_context(self, run_id: str, cfg: Configuration) -> FrameworkContext

    # Suite
    def derive_suite_context(self, framework_ctx, suite_id, suite_name, ...) -> SuiteContext
    def finalize_suite(self, ctx: SuiteContext, status: str)

    # Scenario
    def derive_scenario_context(self, suite_ctx, scenario_id, scenario_name, ...) -> ScenarioContext
    def finalize_scenario(self, ctx: ScenarioContext, status: str)

    # Step
    def derive_step_context(self, scenario_ctx, step_id, step_name, ...) -> StepContext
    def finalize_step(self, ctx: StepContext, status: StepStatus)
```

## StepContextAdapter（Strategy 视图）

把 StepContext 适配成 StrategyContextView，避免 Strategy 直接越权访问 ctx 内部：

```python
class StepContextAdapter:
    """Strategy 拿到的是 view，不是 ctx 本身"""

    # 读
    def read_variable(self, key: str, from_layer: ContextLayer = SCENARIO) -> Any
    def resolve(self, key: str, default: Any = None) -> Any

    # 写（向上提升）
    def promote_variable(self, key: str, value: Any, to: ContextLayer = SCENARIO, ...)

    # StepScratch（旧 HttpExchange）
    def read_scratch(self, *keys: str) -> dict[str, Any]
    def write_scratch(self, **kwargs)
    def reset_scratch()
    def seal_scratch()
```

## 投影函数（`projections.py`）

把 Context 内部状态投影成对外事件：

```python
def project_scenario_started(scenario_ctx, run_id) -> ScenarioStartEvent
def project_scenario_completed(scenario_ctx, run_id) -> ScenarioEndEvent
def project_step_started(ctx: StepContext, run_id) -> StepStartEvent
def project_step_completed(ctx: StepContext, run_id) -> StepEndEvent
def project_promotion(p: Promotion, run_id) -> VariablePromotedEvent
```

`project_step_completed` 自动计算 `assertion_count` / `assertion_passed` / `promotion_count` / `error_brief`，填充 `StepEndEvent` 默认值字段。

> 历史：原 `context/events.py` 同时定义事件类与投影函数，Issue 5 合并后，事件类统一在 `gimbal.events.types`，本文件只剩投影函数。

## 设计原则

1. **层级分明**：四层 Context，每层职责清晰。
2. **数据单向流动**：低层 → 高层，通过 `promote_from()` 受控提升，反向不允许。
3. **Seal 机制**：Context 执行完毕后封印，防止意外修改；但 Channels 走 `promote_from`，不受 seal 影响（有意设计）。
4. **视图隔离**：Strategy 通过 `StepContextAdapter` 访问 Context，避免直接操作。
5. **Policy 检查**：每次提升都检查 `ChannelsPolicy`，防止越权（forbidden_keys / require_reason 等）。
6. **JSONPath 写入**：`StepScratch.set("$.request_body.order_id", v)` → 嵌套结构写入。
7. **投影而非事件双份**：原 events.py 中的 `*Started/*Completed` 事件已合并到 `events/types.py`，`projections.py` 只负责填充字段。
