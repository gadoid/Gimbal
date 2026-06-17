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
├── channels.py       # Channels / ChannelsPolicy / Promotion / Policies / ArtifactRef
├── views.py          # StepContextAdapter（Strategy 视图）
├── projections.py    # project_scenario_* / project_step_* / project_promotion
├── template.py       # 模板渲染（变量替换、{{}}、${}、$.jsonpath）
├── resolver.py       # 引用解析
├── functions.py      # 上下文函数
└── exceptions.py     # SealedContextError / PromotionRejected
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

数据只能从低层向高层提升（Promote），不能反向。`ContextLayer.is_above(other)` 判断当前层是否在 other 之上（更靠近 root）：

```python
class ContextLayer(str, Enum):
    FRAMEWORK = "framework"
    SUITE = "suite"
    SCENARIO = "scenario"
    STEP = "step"

    def is_above(self, other: "ContextLayer") -> bool:
        """判断当前 layer 是否在 other 之上(更靠近 root)。
        例如：SUITE.is_above(SCENARIO) == True
        """
        order = [STEP, SCENARIO, SUITE, FRAMEWORK]
        return order.index(self) > order.index(other)
```

### SealedBaseModel

所有 Context 的基类，封装 seal 机制：

```python
class SealedBaseModel(BaseModel):
    """所有 Context 的基类。

    seal 后:
    - 模型字段不可重新赋值(身份/状态字段冻结)
    - 但 Channels 这种"通道型"字段内部走 promote_from,不经过 __setattr__,
      因此 seal 不影响合法的变量提升。这是有意设计。
    """
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True,
        extra="forbid",
    )

    _sealed: bool = PrivateAttr(default=False)
    _sealed_at: Optional[datetime] = PrivateAttr(default=None)

    @property
    def layer(self) -> ContextLayer:
        """子类实现:声明自己所属的层级。"""
        raise NotImplementedError

    def seal(self) -> None:
        """将当前 context 标记为已封存(sealed),冻结所有字段赋值;
        仅在未封存时生效,并记录封存时间(timezone-aware UTC)。"""
        if not self._sealed:
            self._sealed = True
            self._sealed_at = datetime.now(timezone.utc)

    @property
    def is_sealed(self) -> bool: ...
    @property
    def sealed_at(self) -> Optional[datetime]: ...

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if getattr(self, "_sealed", False):
            raise SealedContextError(
                f"{type(self).__name__} sealed at {self._sealed_at}; "
                f"cannot reassign field '{name}'. "
                f"If you need to add variables, use Channels.promote_from()."
            )
        super().__setattr__(name, value)
```

子类需实现 `layer` 属性以声明所属层级。

## Context 类

### FrameworkContext

框架级上下文，持有整个 run 的配置与基础设施引用。生命周期属于"一次 run"。

```python
class FrameworkContext(SealedBaseModel):
    """框架级 Context。整个运行期间唯一。"""

    run_id: str
    started_at: datetime
    config: BootstrapConfig
    ctx_manager: Any    # ContextManager
    dispatcher: Any
    event_bus: Any
    archive: Any
    # Channels 字段标记 exclude——序列化时 Channels 自己有 snapshot 方法
    channels: Channels = Field(exclude=True)

    @property
    def environment(self) -> str:        # -> self.config.env
    @property
    def mode(self) -> str:                # -> self.config.mode
    @property
    def framework_version(self) -> str:  # -> self.config.framework_version
    @property
    def layer(self) -> ContextLayer:      # -> FRAMEWORK
```

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

三通道数据载体（variables / metadata / artifacts）。所有写入必须经过 `promote_from()` —— 这是显式建模的"向上提升"操作；`seal` 不影响 `Channels`（设计意图就是接受演化）。

```python
class ArtifactRef(BaseModel):
    """不可变 artifact 引用。"""
    model_config = ConfigDict(frozen=True)
    key: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class Promotion(BaseModel):
    """一次变量提升的不可变审计记录。"""
    model_config = ConfigDict(frozen=True)
    key: str
    value: Any
    from_layer: ContextLayer
    to_layer: ContextLayer
    by_step_id: str
    by_scenario_id: Optional[str] = None
    at: datetime
    reason: Optional[str] = None
    overwrote_previous: bool = False     # 是否覆盖了已有值


class Channels:
    """三通道数据载体(variables/metadata/artifacts)。

    所有写入必须经过 promote_from()——这是显式建模的"向上提升"操作。
    seal 不影响本类——本类的设计意图就是接受演化。
    数据通过私有属性持有,外部只能通过受控接口访问。
    """

    def __init__(self, *, owner_layer: ContextLayer, policy: ChannelsPolicy): ...

    # ── 监听器:ContextManager 注册,用于把 Promotion 转事件 ──
    def add_listener(self, listener: PromotionListener) -> None: ...

    # ── 只读访问 ──
    def get_variable(self, key: str, default: Any = None) -> Any:
        """key 以 '$.' 开头按 JSONPath 解析,否则按 dict key 查找。"""
        ...
    def has_variable(self, key: str) -> bool: ...
    def _jsonpath_get(self, path: str, default: Any = None) -> Any: ...
    def variables_snapshot(self) -> dict[str, Any]: ...   # 防御性拷贝
    def get_metadata(self, key: str, default: Any = None) -> Any: ...
    def metadata_snapshot(self) -> dict[str, Any]: ...
    def get_artifact(self, name: str) -> Optional[ArtifactRef]: ...
    def artifacts_snapshot(self) -> dict[str, ArtifactRef]: ...
    @property
    def promotions(self) -> tuple[Promotion, ...]: ...    # 提升的完整历史，只读
    @property
    def owner_layer(self) -> ContextLayer: ...
    @property
    def policy(self) -> ChannelsPolicy: ...

    # ── 写入:promote_from 是唯一入口 ──
    def promote_from(
        self,
        *,
        key: str,
        value: Any,
        from_layer: ContextLayer,
        by_step_id: str,
        by_scenario_id: Optional[str] = None,
        reason: Optional[str] = None,
        allow_overwrite: bool = False,
    ) -> Promotion:
        """接受下层向本层提升一个变量。

        allow_overwrite: 调用方显式声明"我知道这会覆盖"。
          policy 中也必须把这个 key 列入 overwritable_keys 才会真正放行。
        """
        ...

    def attach_artifact_from(
        self, *, name: str, ref: ArtifactRef,
        from_layer: ContextLayer, by_step_id: str,
    ) -> None:
        """大对象引用的附加(走同样的 policy 检查思路,这里简化)。"""
        ...

    def write_metadata_from(
        self, *, key: str, value: Any,
        from_layer: ContextLayer, by_step_id: str,
    ) -> None:
        """metadata 用于框架层数据(retry 次数、耗时等),policy 相对宽松。
        但同样必须经过受控接口,不直接暴露字典。"""
        ...
```

### ChannelsPolicy

声明本层 channels 接受什么样的提升。Policy 在 Context 创建时由 ContextManager 注入，运行期间不可变。

```python
class ChannelsPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 接受来自哪些 layer 的提升
    accept_from_layers: frozenset[ContextLayer] = Field(
        default_factory=lambda: frozenset({ContextLayer.STEP})
    )
    # 默认所有 key 不可覆盖(只能新增);列在这里的 key 允许覆盖
    overwritable_keys: frozenset[str] = frozenset()
    # 显式禁止的 key(如 framework 配置不允许被业务覆盖)
    forbidden_keys: frozenset[str] = frozenset()
    # 提升时是否强制要求 reason
    require_reason: bool = False
    # 允许的 key 前缀(空集表示不限制)
    allowed_key_prefixes: frozenset[str] = frozenset()
```

### 预设策略

```python
class Policies:
    @staticmethod
    def scenario_default() -> ChannelsPolicy:
        """Scenario 层:接受 step 提升,大部分 key 可覆盖(支持 token 刷新)。"""
        return ChannelsPolicy(
            accept_from_layers=frozenset({ContextLayer.STEP}),
            overwritable_keys=frozenset(),   # 由 step 在 promote 时显式声明
            require_reason=False,
        )

    @staticmethod
    def suite_default() -> ChannelsPolicy:
        """Suite 层:接受 scenario 提升,key 不可覆盖(共享资源一次性产出)。"""
        return ChannelsPolicy(
            accept_from_layers=frozenset({ContextLayer.SCENARIO}),
            overwritable_keys=frozenset(),
            require_reason=True,    # suite 级提升必须说明原因
        )

    @staticmethod
    def framework_locked() -> ChannelsPolicy:
        """Framework 层:不接受任何提升。"""
        return ChannelsPolicy(
            accept_from_layers=frozenset(),
            require_reason=True,
        )
```

### 提升检查（`_check_policy`）

每次 `promote_from` 调用时按以下顺序检查：
1. `from_layer` 必须在 `accept_from_layers` 内
2. `key` 不能在 `forbidden_keys` 内
3. 若设置了 `allowed_key_prefixes`，`key` 必须以其中一个前缀开头
4. 若 `key` 已存在：调用方必须 `allow_overwrite=True`，且该 key 必须在 `overwritable_keys` 内
5. 若 `require_reason=True`，`reason` 必填

违反任一规则抛 `PromotionRejected`。

## ContextManager

Context 生命周期协调器（无业务状态）：

```python
class ContextManager:
    """Context 生命周期协调器。无业务状态。"""

    def __init__(self, archive, event_bus):
        """持有 archive(用于持久化)和 event_bus(用于发布事件)两个无业务状态的依赖。"""
        ...

    # ── Framework ─────────────────────────────────────
    def create_framework_context(
        self, *, run_id: str, cfg: Configuration,
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> FrameworkContext:
        """创建并封存 FrameworkContext:注入 channels(默认 framework_locked policy),
        挂接 promotion 监听器;返回 sealed 后的 FrameworkContext。"""
        ...

    # ── Suite ─────────────────────────────────────────
    def derive_suite_context(
        self, framework_ctx: FrameworkContext,
        *, suite_id: str, suite_name: str,
        tags: list[str], plugins: dict[str, dict],
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> SuiteContext:
        """基于 framework_ctx 派生 SuiteContext:用 suite_default policy 创建 channels,
        挂接 promotion 监听器,引用父 context 的 config;返回未 seal 的 SuiteContext。"""
        ...

    def finalize_suite(self, ctx: SuiteContext, status: str = "passed") -> None:
        """结束 SuiteContext:用 object.__setattr__ 写入 ended_at/status(绕过 seal),
        seal 后归档。status 默认 "passed"。"""
        ...

    # ── Scenario ──────────────────────────────────────
    def derive_scenario_context(
        self, suite_ctx: SuiteContext,
        *, scenario_id: str, scenario_name: str,
        description: Optional[str] = None,
        channels_policy: Optional[ChannelsPolicy] = None,
    ) -> ScenarioContext:
        """基于 suite_ctx 派生 ScenarioContext:用 scenario_default policy 创建 channels,
        挂接 promotion 监听器,发布 scenario.start 事件;返回未 seal 的 ScenarioContext。"""
        ...

    def finalize_scenario(self, ctx: ScenarioContext, status: str) -> None:
        """结束 ScenarioContext:写入 ended_at/status,seal 后发布 scenario.end 事件并归档。"""
        ...

    # ── Step ──────────────────────────────────────────
    def derive_step_context(
        self, scenario_ctx: ScenarioContext,
        *, step_id: str, step_name: str,
        strategy_kind: str, strategy_spec: dict,
        resolved_vars: dict,
    ) -> StepContext:
        """基于 scenario_ctx 派生 StepContext:构造 StepInputs,发布 step.start 事件;
        返回未 seal 的 StepContext。"""
        ...

    def finalize_step(self, ctx: StepContext, status: StepStatus) -> None:
        """结束 StepContext:写入 outcome.status/duration_ms/ended_at,登记到 scenario.step_refs,
        归档 step 与 exchange,清空 scratch,seal 后发布 step.end 事件。"""
        ...

    # ── 内部:把 Channels 的 Promotion 转事件 ──────────
    def _wire_promotion_listener(self, channels: Channels, run_id: str) -> None:
        """内部辅助:为 channels 注册一个监听器,把每次 Promotion 投影为
        VariablePromotedEvent 并发布到 event_bus。"""
        def listener(promotion: Promotion):
            self._event_bus.publish(project_promotion(promotion, run_id))
        channels.add_listener(listener)
```

### 提升监听器（wire_promotion_listener）

ContextManager 在创建每一层 Context（Framework/Suite/Scenario）时都会调用 `_wire_promotion_listener(channels, run_id)`，将 Channels 的 `PromotionListener` 接到一个内部 lambda：

```python
def _wire_promotion_listener(self, channels: Channels, run_id: str) -> None:
    def listener(promotion: Promotion):
        self._event_bus.publish(project_promotion(promotion, run_id))
    channels.add_listener(listener)
```

**工作机制**：
1. Channels 在 `promote_from()` 成功后调用 `_notify(record)`
2. `_notify` 同步调用所有已注册的 listener，异常被 logger 吞掉不中断
3. listener 把 `Promotion` 通过 `project_promotion()` 投影为 `VariablePromotedEvent` 并 publish 到 event_bus
4. 所有 reporter / 订阅者即可通过 `bus.subscribe(handler, "variable.promoted")` 实时收到提升事件

这样**变量提升事件化**：reporter 与事件流保持一致，无需直接读取 Context 内部状态。

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
def project_scenario_started(scenario_ctx, run_id: str) -> ScenarioStartEvent:
    """把 scenario_ctx 投影为 ScenarioStartEvent:从 ctx 读取 started_at/suite_id/
    scenario_id/scenario_name/step_count;返回对外事件对象。"""
    ...

def project_scenario_completed(scenario_ctx, run_id: str) -> ScenarioEndEvent:
    """把 scenario_ctx 投影为 ScenarioEndEvent:使用 ended_at(若为空则取当前 UTC)
    与 status/step_count;返回对外事件对象。"""
    ...

def project_step_started(ctx: "StepContext", run_id: str) -> StepStartEvent:
    """把 StepContext 投影为 StepStartEvent:从 inputs 读取 step_name/strategy_kind,
    记录 started_at;返回对外事件对象。"""
    ...

def project_step_completed(ctx: "StepContext", run_id: str) -> StepEndEvent:
    """把 StepContext 投影为 StepEndEvent:统计 assertion_passed,汇总 status/
    duration_ms/assertion_count/promotion_count/error_brief;返回对外事件对象。"""
    ...

def project_promotion(p: "Promotion", run_id: str) -> VariablePromotedEvent:
    """把 Promotion 记录投影为 VariablePromotedEvent:携带 key/from_layer/to_layer/
    by_step_id/overwrote_previous/reason;返回对外事件对象。"""
    ...
```

`project_step_completed` 自动计算 `assertion_count` / `assertion_passed` / `promotion_count` / `error_brief`，填充 `StepEndEvent` 默认值字段。

> 历史：原 `context/events.py` 同时定义事件类与投影函数，Issue 5 合并后，事件类统一在 `gimbal.events.types`，本文件只剩投影函数。

## 使用示例

### 完整生命周期

```python
from gimbal.context import ContextManager
from gimbal.context.channels import Policies
from gimbal.context.step import StepStatus

mgr = ContextManager(archive=my_archive, event_bus=my_bus)

# 1. Framework
fw_ctx = mgr.create_framework_context(run_id="run-001", cfg=cfg)

# 2. Suite
suite_ctx = mgr.derive_suite_context(
    fw_ctx,
    suite_id="suite-001",
    suite_name="Login flow",
    tags=["smoke"],
    plugins={},
)
# ... 业务执行 ...
mgr.finalize_suite(suite_ctx, status="passed")

# 3. Scenario
sc_ctx = mgr.derive_scenario_context(
    suite_ctx, scenario_id="sc-001", scenario_name="login happy path",
)
# ... 业务执行 ...
mgr.finalize_scenario(sc_ctx, status="passed")

# 4. Step
st_ctx = mgr.derive_step_context(
    sc_ctx, step_id="step-001", step_name="POST /login",
    strategy_kind="http_call", strategy_spec={}, resolved_vars={},
)
# ... 业务执行 ...
mgr.finalize_step(st_ctx, StepStatus.PASSED)
```

### 变量提升

```python
# 业务代码从 step 视角提升变量到 scenario
scenario_ctx.channels.promote_from(
    key="auth_token",
    value="xxx",
    from_layer=ContextLayer.STEP,
    by_step_id="step-001",
    allow_overwrite=True,    # 显式声明
    reason="token refresh",
)
# 同步触发 event_bus.publish(VariablePromotedEvent(...))
```

### 自定义 Policy

```python
from gimbal.context.channels import ChannelsPolicy

custom_policy = ChannelsPolicy(
    accept_from_layers=frozenset({ContextLayer.STEP}),
    forbidden_keys=frozenset({"framework_secret"}),
    overwritable_keys=frozenset({"auth_token", "session_id"}),
    require_reason=True,
    allowed_key_prefixes=frozenset({"user_", "session_"}),
)
sc_ctx = mgr.derive_scenario_context(
    suite_ctx, scenario_id="sc-001", scenario_name="...",
    channels_policy=custom_policy,
)
```

## 设计原则

1. **层级分明**：四层 Context，每层职责清晰。
2. **数据单向流动**：低层 → 高层，通过 `promote_from()` 受控提升，反向不允许。
3. **Seal 机制**：Context 执行完毕后封印，防止意外修改；但 Channels 走 `promote_from`，不受 seal 影响（有意设计）。
4. **视图隔离**：Strategy 通过 `StepContextAdapter` 访问 Context，避免直接操作。
5. **Policy 检查**：每次提升都检查 `ChannelsPolicy`，防止越权（forbidden_keys / require_reason / allowed_key_prefixes / overwritable_keys 等）。
6. **JSONPath 写入**：`StepScratch.set("$.request_body.order_id", v)` → 嵌套结构写入。
7. **投影而非事件双份**：原 events.py 中的 `*Started/*Completed` 事件已合并到 `events/types.py`，`projections.py` 只负责填充字段。
8. **提升事件化**：Channels 通过 `_wire_promotion_listener` 把 `Promotion` 自动 publish 为 `VariablePromotedEvent`，reporter 无需读取 Context 内部状态。
9. **timezone-aware**：`sealed_at` / `Promotion.at` 等时间戳使用 `datetime.now(timezone.utc)`，避免 naive/aware 混用。
