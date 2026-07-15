# 阶段 2：StepResolver 抽象

> Status: **Stash（待评审）**
> 解决: 把 step 来源从框架核心外置出去，让框架成为"step 执行引擎"而不是"JSON 文件 reader"
> 依赖: 阶段 1（FlowControl 已在 ScenarioRunner 内运行时，StepResolver 才有意义）
> 产出: StepResolver Protocol + 默认 JsonRefStepResolver + Engine.create_resolver() factory

---

## 1. 现状问题

### 1.1 step 来源的硬编码

[src/gimbal/preprocessor/scenario_preprocessor.py:53-131](src/gimbal/preprocessor/scenario_preprocessor.py#L53) `ScenarioPreprocessor` **同时承担 4 件事**：

| 职责 | 现有位置 |
|---|---|
| 引用物化（StepRef / ApiRef / RequestRef / StrategyRef）| `_materialize_refs()` line 135-160 |
| 认证（auth_registry 填充 token）| `_setup_auth()` line 164-228 |
| 模板展开（`${auth.x.token}` 替换）| `_resolve_steps()` line 311-324 |
| 变量生成（random_decorated 等）| `_generate_vars()` line 232-261 |
| base_url 选择 | `_pick_base_url()` line 519-583 |

**问题**：
- 框架核心不知道 step 还能从别处来（plugin / DB / Python DSL）
- 5 件事紧耦合在一个类里，单元测试困难
- `resolved_steps: list[Step]` 是**一次性产物**，框架无法再问"还有别的 step 吗"

### 1.2 step 数量在执行前固定

```
现状：
  Scenario.steps: list[Step]              ← JSON 固化
     ↓ Preprocessor
  resolved_steps: list[Step]              ← 一次性产物
     ↓ for 循环
  执行
```

**3 个能力缺失**：
- ❌ 动态 step 生成（"对数据库里每条订单做一个核销 step"）
- ❌ 条件分支（"登录成功跑 A 流，失败跑 B 流"）
- ❌ 交互模式（"跑到 step 5 停一下，看响应"）

### 1.3 与阶段 1 的关系

阶段 1 的 FlowControl 在 ScenarioRunner 的 for 循环里决策，**前提是 step 已经准备好**。阶段 2 解决"step 怎么准备"的问题——把 for 循环的迭代源从 `list[Step]` 改为 `StepResolver`。

## 2. 边界重画

### 2.1 旧边界

```
┌──────────────────────────────────────────────────────────────┐
│  Step 来源层（硬编码在 preprocessor 内）                      │
│   - scenario.json 静态 list                                  │
│   - StepRef 引用物化                                         │
│   - AssetStore 远程仓库                                      │
└──────────────────────────────────────────────────────────────┘
                            │
                            ↓ preprocessor.run()
┌──────────────────────────────────────────────────────────────┐
│  执行层                                                       │
│   for step in resolved_steps:                                │
│       step_runner.run(step, ...)                             │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 新边界

```
┌──────────────────────────────────────────────────────────────┐
│  Step 来源层（多种实现，职责：提供 step 工厂 / 描述符）        │
│                                                              │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│   │ JsonScenario │   │ AssetRefStep │   │ Programmatic │  │
│   │ Loader       │   │ Factory      │   │ StepBuilder  │  │
│   │  (静态)      │   │  (引用物化)  │   │  (代码生成)  │  │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘  │
│          │                  │                   │           │
│          └──────────┬───────┴─────────┬─────────┘           │
│                     ↓                 ↓                     │
│            ┌─────────────────────────────────┐             │
│            │   StepResolver（统一抽象）       │             │
│            │   resolve(ctx) → Iterator[Step] │             │
│            └──────────────┬──────────────────┘             │
└─────────────────────────── │ ───────────────────────────────┘
                            │
                            ↓ 迭代器（lazy）
┌──────────────────────────────────────────────────────────────┐
│  执行层                                                       │
│   for step in step_resolver:                                 │
│       step_runner.run(step, ...)                             │
│   ↑                                                           │
│   不知道 step 从哪来，不知道 step 数量                       │
└──────────────────────────────────────────────────────────────┘
```

**关键差异**：

| 维度 | 现状 | 新边界 |
|---|---|---|
| step 来源 | preprocessor 内部硬编码 3 种 | 任何实现 `StepResolver` 接口的对象 |
| step 数量 | 固定（list 长度）| 动态（Iterator，可中途生成）|
| step 获取时机 | 一次性（for 循环前全部 ready）| lazy（for 循环内按需 next）|
| 执行层与组装层耦合 | 紧耦合（直接拿 list）| 抽象（执行层不知道 step 从哪来）|

## 3. StepResolver 接口设计

### 3.1 核心协议

```python
# 伪代码描述
class StepResolver(Protocol):
    """统一的 step 解析器抽象。

    设计原则：
      1. 解析是 lazy 的 —— 框架通过 next() 按需拉取
      2. 解析是有状态的 —— 框架可查询剩余数量、peek 下一步
      3. 解析是可中断的 —— 框架可通过 stop() 通知提前结束
      4. 解析是可扩展的 —— 框架 / plugin 都可以实现
    """

    def __iter__(self) -> Iterator[ResolvedStep]:
        """返回一个迭代器，框架用 for 循环消费。

        实现注意：
          - __iter__ 可以返回 self（如果实现了 __next__）
          - 也可以返回独立 generator（更易实现）
          - 第一次调用时触发 lazy 物化（如果有）
        """
        ...

    def has_next(self, ctx: ScenarioContext) -> bool:
        """是否还有下一个 step（不消费，可观察）。

        用于：
          - reporter 提前显示"剩余 N 个 step"
          - 框架决策"还要不要继续"
        """
        ...

    def peek(self, ctx: ScenarioContext) -> Optional[ResolvedStep]:
        """窥视下一个 step（不消费）—— 用于决策。

        应用场景：
          - FlowControl 在执行前 peek 一下，看 step 是不是要 skip
          - 条件分支 resolver peek 然后决定下一个流
        """
        ...

    def stop(self, reason: str) -> None:
        """通知解析器"框架决定停"—— 解析器做清理。

        应用场景：
          - HALT 信号触发时，通知 resolver 释放持有的 resource（如 DB 连接）
          - 析构前给 resolver 一次 graceful shutdown 机会
        """
        ...
```

**为什么不是单纯 `__iter__`**：因为：
- `for ... in` 无法 query 剩余数量
- `for ... in` 无法 peek（决策当前 step 要不要跑）
- `for ... in` 无法中途通知解析器"够了"

### 3.2 数据类定义

```python
# 伪代码
@dataclass
class ResolvedStep:
    """Step 解析器产出的最小 step 单元。

    与 Step schema 的区别：
      - Step schema 包含完整 description / api / request / strategy
      - ResolvedStep 包含执行所需的最小集合
      - 阶段 3 会进一步把 request 拆为 data_query + api_contract
    """
    step_id: str                          # 自动生成
    step_index: int                       # 在 scenario 内的序号
    api: Api                              # 物化后的 Api
    request: Request                      # 物化后的 Request（阶段 3 改造）
    strategy: list[StrategyUnion]         # 物化后的 strategy
    description: Optional[str] = None
    source: Optional[str] = None          # "json" / "asset" / "programmatic"
    source_ref: Optional[str] = None      # 原始引用（如 "step_ref_xxx"）
```

### 3.3 4 个内置实现

#### 实现 1：JsonRefStepResolver（默认）

```python
# 伪代码
class JsonRefStepResolver:
    """默认 StepResolver 实现。

    兼容现有所有 scenario JSON（包括含 StepRef 的）。
    内部使用 AssetMaterializer 处理引用物化。
    """

    def __init__(
        self,
        scenario: Scenario,
        asset_store: AssetStore,
        template_root: dict,
        auth_registry: AuthRegistry,
    ): ...

    def __iter__(self) -> Iterator[ResolvedStep]:
        # 等价于现在 ScenarioPreprocessor 的逻辑
        # 但每次 yield 一个 step，不是 return list
        for idx, step_union in enumerate(self._materialized_steps):
            if isinstance(step_union, StepRef):
                continue  # 跳过未解析的 ref（兼容性）
            yield ResolvedStep(
                step_id=f"step-{idx:03d}",
                step_index=idx,
                api=step_union.api,
                request=step_union.request,
                strategy=step_union.strategy,
                description=step_union.description,
                source="json",
            )
```

#### 实现 2：LoopStepResolver（动态生成）

```python
# 伪代码
class LoopStepResolver:
    """根据数据动态生成 step 的解析器。

    应用场景：
      - 读数据库得到 100 条订单 → 每条生成一个核销 step
      - 上一步响应是 list → 每项生成一个处理 step
    """

    def __init__(
        self,
        source: str,                       # jsonpath 表达式
        step_template: Step,               # 模板 step
        max_iter: int = 100,               # 安全上限
        ctx_provider: Callable = None,     # 从哪取 ctx（用于读取前序 step 的 ctx）
    ): ...

    def __iter__(self) -> Iterator[ResolvedStep]:
        ctx = self._ctx_provider() if self._ctx_provider else None
        items = self._read_source(ctx)
        for i, item in enumerate(items):
            if i >= self.max_iter:
                logger.warning(f"LoopStepResolver: 达到 max_iter={self.max_iter}，停止")
                break
            yield self._materialize_step(self._step_template, item, idx=i)
```

#### 实现 3：BranchStepResolver（条件分支）

```python
# 伪代码
class BranchStepResolver:
    """根据条件选择不同流的解析器。"""

    def __init__(
        self,
        if_step: Step,
        then_resolver: StepResolver,
        else_resolver: StepResolver,
    ): ...

    def __iter__(self) -> Iterator[ResolvedStep]:
        # 先 yield 决策 step
        result = yield self._if_step
        # 根据结果选择后续流
        chosen = self._then_resolver if result.passed else self._else_resolver
        yield from chosen
```

#### 实现 4：ChainStepResolver（顺序组合）

```python
# 伪代码
class ChainStepResolver:
    """把多个 resolver 顺序组合的解析器。"""

    def __init__(self, *resolvers: StepResolver): ...

    def __iter__(self) -> Iterator[ResolvedStep]:
        for resolver in self._resolvers:
            yield from resolver
```

## 4. Engine 集成

### 4.1 Engine.create_resolver() factory

```python
# src/gimbal/core/runner.py - 伪代码
class Engine:
    def create_resolver(
        self,
        scenario: Scenario,
        runtime_control: RuntimeControl,
    ) -> StepResolver:
        """根据 scenario 类型和 runtime_control 创建合适的 StepResolver。

        默认返回 JsonRefStepResolver（兼容现有 scenario）。
        plugin 可注册自己的 ResolverFactory 拦截创建过程。
        """
        # 1. 尝试 plugin 注册的 factory
        for factory in self._resolver_factories:
            if factory.accepts(scenario):
                return factory.create(scenario, runtime_control, self._asset_store)

        # 2. 默认 factory
        return JsonRefStepResolver(
            scenario=scenario,
            asset_store=self._asset_store,
            template_root=self._build_template_root(),
            auth_registry=self._ictx.auth_registry,
        )
```

### 4.2 Engine.run() 接受 StepResolver

```python
# src/gimbal/core/runner.py - 伪代码
class Engine:
    def run(self, target: Scenario | Suite | StepResolver) -> RunResult:
        # ... 现有 setup ...

        try:
            if isinstance(target, StepResolver):
                # 直接接受 resolver（阶段 2 新增路径）
                result = self._run_resolver(target, framework_ctx)
            elif isinstance(target, Scenario):
                # 现有路径：Scenario → JsonRefStepResolver
                resolver = self.create_resolver(target, runtime_control)
                result = self._run_resolver(resolver, framework_ctx)
            elif isinstance(target, Suite):
                # 现有路径：Suite 内每个 Scenario → Resolver
                result = self._run_suite(target, framework_ctx)
            ...
```

### 4.3 ScenarioRunner 改用 resolver

```python
# src/gimbal/core/scenario_runner.py - 伪代码
class ScenarioRunner:
    def run(
        self,
        target: Scenario | StepResolver,        # ← 改为接受 resolver
        suite_ctx: SuiteContext,
        runtime_control: RuntimeControl,
    ) -> ScenarioRunResult:
        # ... 现有 setup ...

        # 构造 resolver（如果 target 是 Scenario）
        if isinstance(target, Scenario):
            step_resolver = self._engine.create_resolver(target, runtime_control)
        else:
            step_resolver = target

        # 用 resolver 替换 resolved_steps
        for idx, resolved_step in enumerate(step_resolver):
            # 阶段 1 的 gate 决策
            gate_result = self._gate_runner.run(GatePoint.STEP_BEFORE_ENTER, ...)
            if gate_result.signal == ControlSignal.SKIP:
                continue
            if gate_result.signal == ControlSignal.HALT:
                self._run_state.halt_requested = True
                break

            # 正常执行
            result = self._step_runner.run(resolved_step, scenario_ctx, idx)
            ...

        # 通知 resolver 框架决定停
        if self._run_state.halt_requested:
            step_resolver.stop(reason=self._run_state.halt_reason)
```

## 5. CLI 集成

### 5.1 CLI 不变

CLI 仍传 `Scenario`，`Engine.create_resolver()` 在内部默认产 `JsonRefStepResolver`。**CLI 调用方式 100% 兼容**。

### 5.2 高级用法：直接传 resolver

```python
# src/gimbal/cli/commands/run_scenario.py - 伪代码
@app.command()
def scenario(
    # ... 现有参数 ...
    step_to: Optional[int] = None,
    step_from: Optional[int] = None,
):
    # 解析 RuntimeControl
    runtime_control = RuntimeControl(...)

    # 加载 scenario
    scenario = load_scenario_from_asset(...)

    # 阶段 2 新增：允许 plugin 包装 scenario
    scenario = plugin_manager.hook_scenario(scenario)

    # 传给 engine
    engine.run(scenario)
```

## 6. 兼容性策略

### 6.1 老 scenario JSON
- 100% 兼容——`Engine.create_resolver()` 默认产 `JsonRefStepResolver`
- 老 JSON 含 `StepRef` → 内部用 `AssetMaterializer` 处理，行为与原版一致

### 6.2 老 CLI 调用
- 100% 兼容——CLI 仍传 `Scenario`，无需传 resolver

### 6.3 老 Plugin 体系
- 100% 兼容——`HookPoint` / `Strategy` / `Reporter` 都不动
- plugin 可注册 `ResolverFactory` 拦截创建过程（可选扩展）

### 6.4 老 Reporter
- 兼容——`ScenarioRunResult.step_results` 保持 list
- 新增 `total_resolved_steps` 字段：原计划 step 数（= resolver 总产出）

### 6.5 老 Result 字段
- 兼容——`passed` / `failed` / `error` / `skipped` 字段不动
- 新增 `halted` / `halt_reason` / `halt_kind` / `total_resolved_steps`

## 7. 改动量估算

| 模块 | 行数估计 |
|---|---|
| `gimbal/resolver/__init__.py` (新) | 5-10 |
| `gimbal/resolver/base.py` (新) | 50-80 |
| `gimbal/resolver/json_ref.py` (新) | 100-150 |
| `gimbal/resolver/loop.py` (新) | 60-100 |
| `gimbal/resolver/branch.py` (新) | 50-80 |
| `gimbal/resolver/chain.py` (新) | 30-50 |
| `gimbal/core/runner.py` | 20-30 |
| `gimbal/core/scenario_runner.py` | 20-40 |
| `gimbal/core/plugin.py` (注册 ResolverFactory) | 20-30 |

**总计：~360-570 行**，分散在 7-9 个文件。

## 8. 测试覆盖

| 测试维度 | 覆盖点 |
|---|---|
| 单元测试（每个 resolver） | JsonRef / Loop / Branch / Chain |
| 集成测试（Engine 集成） | 接受 Scenario / StepResolver 两种输入 |
| 兼容测试 | 老 JSON 走 JsonRefStepResolver 行为不变 |
| lazy 测试 | 100 条数据的 loop 不一次性加载 |
| 错误传播 | resolver 异常时框架能优雅处理 |

## 9. 验收标准

- [ ] `Engine.run(scenario)` 内部自动构造 `JsonRefStepResolver`
- [ ] `Engine.run(resolver)` 接受自定义 resolver
- [ ] 老 scenario JSON 行为完全不变
- [ ] `LoopStepResolver` 支持从 JSON / SQL / 函数动态生成 step
- [ ] `BranchStepResolver` 支持条件分支
- [ ] `ScenarioRunResult.total_resolved_steps` 字段正确填充
- [ ] 阶段 1 的 FlowControl 仍正常工作（gate 在 resolver 上层）
