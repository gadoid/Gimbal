# Context 模块

> 上下文管理模块，维护 Framework → Suite → Scenario → Step 的层级执行上下文

## 目录结构

```
gimbal/context/
├── __init__.py
├── base.py           # ContextLayer, SealedBaseModel
├── framework.py      # FrameworkContext
├── suite.py          # SuiteContext
├── scenario.py        # ScenarioContext
├── step.py           # StepContext, StepInputs, StepOutcome, HttpExchange
├── manager.py        # ContextManager
├── channels.py       # Channels, ChannelsPolicy, Promotion
├── views.py          # StepContextAdapter, StrategyContextView
├── template.py       # 模板渲染
├── resolver.py       # 引用解析
├── functions.py      # 上下文函数
└── exceptions.py     # 上下文相关异常
```

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

数据只能从低层向高层提升（Promote），不能反向。

### SealedBaseModel

所有 Context 的基类，支持 `seal()` 机制：

```python
class SealedBaseModel(BaseModel):
    """seal 后字段不可重新赋值"""

    _sealed: bool = PrivateAttr(default=False)
    _sealed_at: Optional[datetime] = PrivateAttr(default=None)

    def seal(self) -> None:
        """封印上下文，封印后不可修改"""
        self._sealed = True
        self._sealed_at = datetime.utcnow()

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise SealedContextError(...)
        super().__setattr__(name, value)
```

## Context 类

### FrameworkContext

框架级上下文，持有整个运行的配置和基础设施引用。

### SuiteContext

Suite 级上下文，属于某个 Framework。

### ScenarioContext

Scenario 级上下文，属于某个 Suite。

### StepContext

Step 级上下文，属于某个 Scenario。

```python
class StepContext(SealedBaseModel):
    inputs: StepInputs          # 输入态（不可变）
    outcome: StepOutcome        # 产物态（执行期间累积）
    http_exchange: HttpExchange # HTTP 交换记录
    started_at: datetime
    ended_at: datetime | None

    @property
    def layer(self) -> ContextLayer:
        return ContextLayer.STEP
```

### HttpExchange

HTTP 交换记录：

```python
class HttpExchange:
    request_method: str
    request_url: str
    request_headers: dict
    request_body: Any
    response_status: int
    response_headers: dict
    response_body: Any
    duration_ms: float
```

## Channels 通道机制

三通道数据载体（variables/metadata/artifacts）：

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
    overwritable_keys: frozenset[str]            # 允许覆盖的 key
    forbidden_keys: frozenset[str]               # 禁止的 key
    require_reason: bool                          # 是否要求 reason
    allowed_key_prefixes: frozenset[str]         # 允许的 key 前缀
```

### 预设策略

```python
class Policies:
    @staticmethod
    def scenario_default() -> ChannelsPolicy:
        """Scenario: 接受 step 提升，大部分 key 可覆盖"""
        return ChannelsPolicy(
            accept_from_layers=frozenset({ContextLayer.STEP}),
        )

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
        return ChannelsPolicy(
            accept_from_layers=frozenset(),
        )
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

## StepContextAdapter

把 StepContext 适配成 StrategyContextView：

```python
class StepContextAdapter:
    """Strategy 拿到的是 view，不是 ctx 本身——避免越权访问"""

    # 读
    def read_variable(self, key: str, from_layer: ContextLayer = SCENARIO) -> Any
    def resolve(self, key: str, default: Any = None) -> Any

    # 写（向上提升）
    def promote_variable(self, key: str, value: Any, to: ContextLayer = SCENARIO, ...)

    # HTTP Exchange
    def read_http_exchange(self, *keys: str) -> dict[str, Any]
    def write_http_exchange(self, **kwargs)
    def reset_http_exchange()
    def seal_http_exchange()
```

## 设计原则

1. **层级分明**: 四层 Context，每层职责清晰
2. **数据单向流动**: 低层 → 高层，通过 `promote_from()` 受控提升
3. **Seal 机制**: Context 执行完毕后封印，防止意外修改
4. **视图隔离**: Strategy 通过 Adapter 访问 Context，避免直接操作
5. **Policy 检查**: 每次提升都检查 ChannelsPolicy，防止越权