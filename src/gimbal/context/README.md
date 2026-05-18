# Context 模块

运行时上下文管理，负责协调整个执行生命周期中的状态、数据和事件。

## 设计理念

### 1. 层次化 Context

采用**树形层次结构**，自顶向下：

```
FrameworkContext  (根节点，唯一)
└── SuiteContext     (Suite 级别)
    └── ScenarioContext  (Scenario 级别)
        └── StepContext    (Step 级别)
```

### 2. Seal 机制

每个 Context 在**完成后冻结**，防止意外修改：

- `seal()` 调用后，字段不可重新赋值
- `object.__setattr__` 仅 `ContextManager` 可用（特权操作）
- `Channels` 的 `promote_from()` 不经过 `__setattr__`，不受 Seal 影响

### 3. 变量提升 (Promotion)

变量只能**向上提升**，不能向下或平级流动：

```
StepContext  →  ScenarioContext  →  SuiteContext  →  FrameworkContext
   (变量)          (变量)            (共享资源)
```

通过 `Channels.promote_from()` 实现，受 `ChannelsPolicy` 约束。

### 4. 受控接口

外部代码不能直接修改 Context，只能通过受控接口：
- `promote_variable()` - 变量提升
- `record_assertion()` - 记录断言
- `attach_artifact()` - 附加产物

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `base.py` | `SealedBaseModel`, `ContextLayer` 枚举 |
| `manager.py` | `ContextManager` 主类 |
| `framework.py` | `FrameworkContext` |
| `suite.py` | `SuiteContext` |
| `scenario.py` | `ScenarioContext` |
| `step.py` | `StepContext`, `StepInputs`, `StepOutcome` |
| `channels.py` | `Channels`, `ChannelsPolicy`, `Promotion` |
| `views.py` | `StrategyContextView`, `StepContextAdapter` |
| `events.py` | 事件类型定义 |
| `exceptions.py` | 异常定义 |

---

## ContextLayer 枚举

```python
class ContextLayer(str, Enum):
    FRAMEWORK = "framework"   # 框架级别
    SUITE = "suite"          # Suite 级别
    SCENARIO = "scenario"     # Scenario 级别
    STEP = "step"            # Step 级别
```

层级比较：`is_above(other)` 判断当前层级是否在 other 之上（更靠近 root）。

---

## Context 类

### FrameworkContext

框架级 Context，整个运行期间唯一。

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_id` | `str` | 唯一运行 ID |
| `started_at` | `datetime` | 开始时间 |
| `config` | `dict` | 配置字典 |
| `environment` | `str` | 运行环境 |
| `channels` | `Channels` | 数据通道 |

### SuiteContext

Suite 级 Context。

| 字段 | 类型 | 说明 |
|------|------|------|
| `suite_id` | `str` | Suite ID |
| `suite_name` | `str` | Suite 名称 |
| `tags` | `list[str]` | 标签列表 |
| `started_at` | `datetime` | 开始时间 |
| `ended_at` | `datetime` | 结束时间 |
| `status` | `str` | 执行状态 |
| `plugins` | `dict` | 插件配置 |

### ScenarioContext

Scenario 级 Context。

| 字段 | 类型 | 说明 |
|------|------|------|
| `scenario_id` | `str` | Scenario ID |
| `scenario_name` | `str` | Scenario 名称 |
| `description` | `str` | 描述 |
| `step_refs` | `list[str]` | Step ID 列表 |
| `started_at` | `datetime` | 开始时间 |
| `ended_at` | `datetime` | 结束时间 |
| `status` | `str` | 执行状态 |

### StepContext

Step 级 Context。

| 字段 | 类型 | 说明 |
|------|------|------|
| `inputs` | `StepInputs` | 输入态（frozen） |
| `outcome` | `StepOutcome` | 产物态 |
| `started_at` | `datetime` | 开始时间 |
| `ended_at` | `datetime` | 结束时间 |

---

## StepInputs (不可变)

执行期间只读的输入数据。

```python
class StepInputs(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    step_name: str
    strategy_kind: str
    strategy_spec: dict
    resolved_vars: dict[str, Any]
```

---

## StepOutcome (可变)

执行期间累积的产物数据。

```python
class StepOutcome(BaseModel):
    status: StepStatus = StepStatus.PENDING
    extracted: dict[str, Any] = {}           # 提取的变量
    assertions: list[AssertionResult] = []    # 断言结果
    response_artifact: Optional[str] = None   # 产物引用
    error_info: Optional[ErrorInfo] = None    # 错误信息
    duration_ms: Optional[float] = None       # 执行耗时
    retry_count: int = 0                      # 重试次数
    promotions_made: list[str] = []           # 提升记录
```

---

## Channels 与 Policy

### Channels

三通道数据载体：`variables` / `metadata` / `artifacts`

```python
class Channels:
    def promote_from(
        self,
        key: str,
        value: Any,
        from_layer: ContextLayer,
        by_step_id: str,
        reason: Optional[str] = None,
        allow_overwrite: bool = False,
    ) -> Promotion: ...
```

### ChannelsPolicy

声明本层接受什么样的提升。

```python
class ChannelsPolicy:
    accept_from_layers: frozenset[ContextLayer]  # 接受哪些层级的提升
    overwritable_keys: frozenset[str]            # 允许覆盖的 key
    forbidden_keys: frozenset[str]              # 禁止的 key
    require_reason: bool                         # 是否必须提供原因
    allowed_key_prefixes: frozenset[str]         # key 前缀白名单
```

### 预设 Policy

```python
class Policies:
    @staticmethod
    def framework_locked() -> ChannelsPolicy:
        """Framework 层:不接受任何提升"""
        return ChannelsPolicy(accept_from_layers=frozenset())

    @staticmethod
    def suite_default() -> ChannelsPolicy:
        """Suite 层:接受 scenario 提升，key 不可覆盖"""
        return ChannelsPolicy(accept_from_layers=frozenset({ContextLayer.SCENARIO}))

    @staticmethod
    def scenario_default() -> ChannelsPolicy:
        """Scenario 层:接受 step 提升，大部分 key 可覆盖"""
        return ChannelsPolicy(accept_from_layers=frozenset({ContextLayer.STEP}))
```

---

## ContextManager

Context 生命周期协调器。

### 核心方法

| 方法 | 说明 |
|------|------|
| `create_framework_context()` | 创建 Framework Context |
| `derive_suite_context()` | 派生 Suite Context |
| `derive_scenario_context()` | 派生 Scenario Context |
| `derive_step_context()` | 派生 Step Context |
| `finalize_suite()` | 完成 Suite（seal + 归档） |
| `finalize_scenario()` | 完成 Scenario（seal + 归档） |
| `finalize_step()` | 完成 Step（seal + 归档） |

### 执行流程

```
bootstrap()
    │
    └── Configuration (持有 ctx_manager)
            │
            └── Engine.run()
                    │
                    └── ContextManager.create_framework_context()
                            │
                            └── for each Suite:
                                └── ContextManager.derive_suite_context()
                                        │
                                        └── for each Scenario:
                                            └── ContextManager.derive_scenario_context()
                                                    │
                                                    └── for each Step:
                                                        └── ContextManager.derive_step_context()
                                                                │
                                                                └── 执行策略...
                                                                    │
                                                                    └── ContextManager.finalize_step()
                                                                    │
                                                            ContextManager.finalize_scenario()
                                                            │
                                                    ContextManager.finalize_suite()
```

---

## StrategyContextView

策略代码访问 Context 的**视图接口**（只读必要信息）。

```python
class StrategyContextView(Protocol):
    @property
    def step_id(self) -> str: ...
    @property
    def scenario_id(self) -> str: ...
    @property
    def strategy_spec(self) -> dict: ...
    @property
    def resolved_vars(self) -> dict[str, Any]: ...

    def read_variable(self, key: str, from_layer: ContextLayer, default: Any) -> Any: ...
    def promote_variable(self, key: str, value: Any, to: ContextLayer, reason: Optional[str], allow_overwrite: bool) -> None: ...
    def record_assertion(self, result: AssertionResult) -> None: ...
    def attach_artifact(self, name: str, ref: ArtifactRef, to: ContextLayer) -> None: ...
```

### StepContextAdapter

将 `StepContext` 适配为 `StrategyContextView`，防止策略越权访问。

---

## 事件

### 事件类型

| 事件 | 说明 |
|------|------|
| `StepStartedEvent` | Step 开始 |
| `StepCompletedEvent` | Step 完成 |
| `ScenarioStartedEvent` | Scenario 开始 |
| `ScenarioCompletedEvent` | Scenario 完成 |
| `VariablePromotedEvent` | 变量提升 |

### 事件发布

`ContextManager` 在关键生命周期节点发布事件：

```python
# Step 开始
self._event_bus.publish(project_step_started(ctx, scenario_ctx.run_id))

# Step 完成
self._event_bus.publish(project_step_completed(ctx, ctx.parent.run_id))

# Scenario 开始
self._event_bus.publish(ScenarioStartedEvent(...))

# Scenario 完成
self._event_bus.publish(ScenarioCompletedEvent(...))

# 变量提升（通过 Channels listener 转发）
self._event_bus.publish(project_promotion(promotion, run_id))
```

---

## 异常

| 异常 | 说明 |
|------|------|
| `SealedContextError` | 对已 sealed 的 Context 字段重新赋值 |
| `PromotionRejected` | 变量提升被 Policy 拒绝 |
| `LayerResolutionError` | 目标 layer 在链路中不存在 |

---

## 运行测试

```bash
python -m gimbal.context.manager
```
