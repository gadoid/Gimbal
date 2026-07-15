# 架构影响评估

> Status: **Stash（待评审）**
> 范围: 3 个阶段对 10 层架构的影响、改动量、风险评估

---

## 1. 10 层架构影响总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        现有架构分层                                │
├──────────────────────────────────────────────────────────────────┤
│  CLI 层        run_scenario.py / run_suite.py / run_match.py     │ ← ① 阶段 1
├──────────────────────────────────────────────────────────────────┤
│  配置层        BootstrapConfig / Configuration                   │ ← ② 阶段 1
├──────────────────────────────────────────────────────────────────┤
│  框架层        Engine / FrameworkContext                          │ ← ③ 阶段 1+2
├──────────────────────────────────────────────────────────────────┤
│  编排层        ScenarioRunner / StepRunner                        │ ← ④ 阶段 1+2
├──────────────────────────────────────────────────────────────────┤
│  状态机层      StepStateMachine / StepState                       │ ← ⑤ 阶段 1
├──────────────────────────────────────────────────────────────────┤
│  上下文层      ScenarioContext / StepContext                      │ ← ⑥ 阶段 1
├──────────────────────────────────────────────────────────────────┤
│  Hook/Event    HookPoint / EventType / HookRegistry              │ ← ⑦ 阶段 1
├──────────────────────────────────────────────────────────────────┤
│  Schema        Step / Scenario / Config                           │ ← ⑧ 阶段 3
├──────────────────────────────────────────────────────────────────┤
│  Result        ScenarioRunResult / RunResult / StepRunResult      │ ← ⑨ 阶段 1+2
├──────────────────────────────────────────────────────────────────┤
│  Reporter      console / html / json / junit                      │ ← ⑩ 阶段 1
└──────────────────────────────────────────────────────────────────┘
```

**10 层全部受影响**——3 个阶段累计改动是 first-class feature 的代价。

## 2. 按阶段逐层评估

### 阶段 1 影响矩阵

| 架构层 | 改动 | 风险 | 关键决策 |
|---|---|---|---|
| ① CLI | 小 | 低 | `--breakpoint` 交互模式是否本期做 |
| ② 配置 | 中 | **高** | `RuntimeControl` 与 `BootstrapConfig` 的语义边界 |
| ③ 框架 | 小 | 低 | `Engine.run()` 透传 `runtime_control` |
| ④ 编排 | **大** | **高** | `ScenarioRunner` 是核心改造点 |
| ⑤ 状态机 | 中 | 中 | 新增 `CONTROL_HALT` 终态或只用 halted 字段 |
| ⑥ 上下文 | **大** | **高** | `ScenarioContext` 新增 `run_state` 字段 |
| ⑦ Hook/Event | 小 | 低 | 新增 `STEP_BEFORE_ENTER` 埋点 |
| ⑧ Schema | 小 | 低 | 不改（`FlowControl` 是内部抽象）|
| ⑨ Result | 中 | 低 | 三层 dataclass 都要扩展，新增 halted 维度 |
| ⑩ Reporter | 中 | 低 | console / html / json 同步改造 |

**阶段 1 改动量**：~330-540 行

### 阶段 2 影响矩阵

| 架构层 | 改动 | 风险 | 关键决策 |
|---|---|---|---|
| ① CLI | 极小 | 低 | CLI 不变（仍传 Scenario）|
| ② 配置 | 极小 | 低 | 不动 |
| ③ 框架 | 中 | 中 | `Engine.create_resolver()` factory |
| ④ 编排 | **大** | **高** | `ScenarioRunner` 接受 `StepResolver` |
| ⑤ 状态机 | 极小 | 低 | 不动 |
| ⑥ 上下文 | 小 | 低 | 不动 |
| ⑦ Hook/Event | 小 | 低 | 新增 `STEP_BEFORE_RESOLVE`（可选）|
| ⑧ Schema | 极小 | 低 | 不动 |
| ⑨ Result | 小 | 低 | 新增 `total_resolved_steps` 字段 |
| ⑩ Reporter | 小 | 低 | 渲染新增字段 |

**阶段 2 改动量**：~360-570 行

### 阶段 3 影响矩阵

| 架构层 | 改动 | 风险 | 关键决策 |
|---|---|---|---|
| ① CLI | 极小 | 低 | CLI 不变 |
| ② 配置 | 极小 | 低 | 不动 |
| ③ 框架 | 极小 | 低 | 不动 |
| ④ 编排 | 中 | 中 | 集成 `DataQueryResolver` |
| ⑤ 状态机 | 小 | 低 | 不动 |
| ⑥ 上下文 | 极小 | 低 | 不动 |
| ⑦ Hook/Event | 极小 | 低 | 不动 |
| ⑧ Schema | **大** | **高** | `Step.data_query` 字段 + DataQuery schema |
| ⑨ Result | 极小 | 低 | 不动 |
| ⑩ Reporter | 极小 | 低 | 不动 |

**阶段 3 改动量**：~810-1300 行

### 累计影响矩阵

| 架构层 | 阶段 1 | 阶段 2 | 阶段 3 | 累计风险 |
|---|---|---|---|---|
| ① CLI | 小 | 极小 | 极小 | 低 |
| ② 配置 | 中 | 极小 | 极小 | **中** |
| ③ 框架 | 小 | 中 | 极小 | 中 |
| ④ 编排 | **大** | **大** | 中 | **高** |
| ⑤ 状态机 | 中 | 极小 | 小 | 中 |
| ⑥ 上下文 | **大** | 小 | 极小 | **中** |
| ⑦ Hook/Event | 小 | 小 | 极小 | 低 |
| ⑧ Schema | 小 | 极小 | **大** | **高** |
| ⑨ Result | 中 | 小 | 极小 | 低 |
| ⑩ Reporter | 中 | 小 | 极小 | 低 |

**核心风险点**：② 配置、④ 编排、⑥ 上下文、⑧ Schema

## 3. 3 个最高风险点

### 🔴 风险 1：场景级状态 vs step 级状态的边界混淆

"step_to 到点了"是 **scenario 级别的控制意图**（属于 `ScenarioRunControl` / `ScenarioRunState`），"当前 step 是否被控制中止"是 **step 级别的标记**（属于 `StepRunResult.controlled_halt`）。

**正确做法**：ScenarioContext 持有 `run_state` + `runtime_control`，**但 StepRunResult 也要带 `controlled_halt` 字段（镜像）**。两个地方都要有，**不是二选一**。

如果只放在 ScenarioContext 上、step 不带标记，reporter 在打印 step 列表时就**无法标红"这一步是被框架停的"**——只能从 scenario 顶层 halted 字段反推。

### 🔴 风险 2：Context 序列化的破坏性

ScenarioContext 如果有 `model_dump()`，新增字段会让所有**老 JSON 报告解析失败**。

**对策**：
- 用 `extra="allow"` 的 Pydantic 配置，老 reader 跳过未知字段
- 保证新增字段是可选且 default 不破坏语义
- 用 `total_resolved_steps` 这类新字段，老 reader 看到也无所谓

### 🔴 风险 3：4 套"中断语义"汇聚到一个 for 循环

现在 `ScenarioRunner.run()` 的 for 循环里已经有 3 套中断：
- `cfg_timeout`（[src/gimbal/core/scenario_runner.py:280-295](src/gimbal/core/scenario_runner.py#L280)）
- `is_cancelled()`（[src/gimbal/core/scenario_runner.py:297-306](src/gimbal/core/scenario_runner.py#L297)）
- `if not result.passed`（[src/gimbal/core/scenario_runner.py:325-331](src/gimbal/core/scenario_runner.py#L325)）

新增第 4 套"step_to 控制中止"会让**中断原因的管理变成 ad-hoc 拼接**。

**对策**：抽出一个统一的"中断检查器"（`GateRunner`），4 种来源都过同一个函数；`ScenarioRunResult` 用统一的 `halted / halted_reason / halted_at_idx` 字段，**不要每种中断都发明新的字段名**。

## 4. 改动量汇总

| 阶段 | 新增文件 | 修改文件 | 总行数估计 |
|---|---|---|---|
| 阶段 1 | 5-7 | 7-9 | ~330-540 |
| 阶段 2 | 6-8 | 3-4 | ~360-570 |
| 阶段 3 | 10-13 | 3-4 | ~810-1300 |
| **累计** | **21-28** | **13-17** | **~1500-2410** |

**核心改动集中在**：
- 阶段 1：`core/scenario_runner.py` + `context/scenario.py`（编排 + 上下文）
- 阶段 2：`resolver/` 模块（新增）+ `core/runner.py`（factory）
- 阶段 3：`schema/data_query.py` + `runtime/data_query_resolver.py`（schema + runtime）

## 5. 开闭原则评估

| 阶段 | 之前的方案 | 推荐方案 | 开闭原则 |
|---|---|---|---|
| 阶段 1 | 硬编码到 ScenarioRunner for 循环 | GatePoint / FlowControl / ControlSignal | ✅ 符合 |
| 阶段 2 | preprocessor 紧耦合 | StepResolver Protocol | ✅ 符合 |
| 阶段 3 | step 持有完整 body | DataQuery discriminated union | ✅ 符合 |

**3 个阶段的开闭原则都达标**——具体场景通过 plugin / discriminated union 注册，框架核心只持有抽象。

## 6. 5 个具体架构建议

### 建议 1：不要发明 5 套中断术语

timeout / cancelled / step_to / fail_fast 在 result 层用统一的 `halted: bool + halt_reason: str` 表达，区分只在 reason 字符串里。

### 建议 2：RuntimeControl 作为独立顶层对象

不塞进 `BootstrapConfig`，与 `AssetStore` 同级注入 `Engine`。

### 建议 3：Step.data_query 替代 request.body 时保留老字段

`request.body` 降级为可选（自动转 `InlineQuery`），老 JSON 完全兼容。

### 建议 4：CONTROL_HALT 终态可选

如果不希望加新终态，可以只在 `ScenarioRunResult` 加 `halted` 字段，`status` 字符串仍用 `passed` / `failed` / `error`，reporter 通过 `halted` 字段判断。

**两种实现对比**：

| 维度 | 新增 CONTROL_HALT 终态 | 只用 halted 字段 |
|---|---|---|
| 状态机复杂度 | 高（要加跃迁）| 低（不改）|
| 兼容性 | 中（StepState 枚举变化）| 高 |
| 语义清晰度 | **高** | 中（status 与 halted 重复表达）|
| 推荐 | 阶段 1 长期方案 | 阶段 1 短期方案 |

### 建议 5：StepResolver 接口最小化

`has_next` / `peek` / `stop` 三个方法不是必须的——阶段 2 可以只实现 `__iter__`，把 `has_next` / `peek` / `stop` 留到阶段 3 或后续迭代。

**最小接口**：

```python
# 阶段 2 最小接口
class StepResolver(Protocol):
    def __iter__(self) -> Iterator[ResolvedStep]: ...
    def stop(self, reason: str) -> None: ...  # 可选
```

## 7. 5 个具体业务收益

| 收益 | 来源 | 落地阶段 |
|---|---|---|
| `--step-to` 真正可用 | 阶段 1 | 阶段 1 |
| 动态 step 生成（数据库驱动）| 阶段 2 | 阶段 2 |
| 条件分支（登录成功/失败）| 阶段 2 | 阶段 2 |
| 接口/数据解耦 | 阶段 3 | 阶段 3 |
| Plugin 化数据查询 | 阶段 3 | 阶段 3 |

## 8. 3 个潜在架构债

### 债 1：Status 三态 → 多态扩展

`ScenarioRunResult.status` 从 `passed / failed / error` 三态 → `passed / failed / error / halted` 四态。

如果未来加 `pause` / `interrupted` 等更多状态，要持续扩展枚举——**枚举膨胀风险**。

**对策**：用 string literal + 文档化，不要用 `Enum`。

### 债 2：GateRunner 与 HookPoint 的语义重叠

`GatePoint.STEP_BEFORE_ENTER` 与 `HookPoint.STEP_START` 都在 step 开始前触发。

如果未来加更多"决策时机"，GatePoint 会和 HookPoint 越来越像。

**对策**：明确 GatePoint 只承担"决策"语义，HookPoint 只承担"事件"语义。如果一个 hook 抛 STOP，等价于"决策=停"。

### 债 3：DataQuery 与 Generator 的语义重叠

`RandomQuery` 与现有 `VarGenerator`（[src/gimbal/generator/](src/gimbal/generator/)）功能重叠。

**对策**：DataQuery 内部直接用 VarGenerator，避免重复实现。

## 9. 总体评价

| 评估项 | 结论 |
|---|---|
| **架构一致性** | ✅ 与现有 `Ref` 体系 / `AssetMaterializer` 完全契合——是**强化而非替换** |
| **开闭原则** | ✅ 3 个阶段都达标——plugin 化 / discriminated union |
| **兼容性** | ✅ 3 个阶段都向后兼容 |
| **改动量** | ⚠️ 中等——约 1500-2410 行，分散在 30+ 文件 |
| **风险** | 中——核心在配置层、编排层、Schema 层 |
| **业务价值** | ✅ 高——解决 5 个真实业务问题 |
| **是否值得** | ✅ 长期值得，但要分阶段实施 |

## 10. 与现有架构的契合点

| 现有架构 | 本次改造的契合 |
|---|---|
| `HookPoint` 介入型 + `HookSignal.STOP` | ✅ 阶段 1 的 GatePoint 正交扩展 |
| `Strategy` discriminated union | ✅ 阶段 1 的 FlowControl 对称设计 |
| `AssetStore` 资产仓库 | ✅ 阶段 2/3 的 DataQueryRegistry 类似模式 |
| `AssetMaterializer` 引用物化 | ✅ 阶段 2 的 JsonRefStepResolver 复用 |
| `RefBase` 引用基类 | ✅ 阶段 3 的 `DataQueryRef` 复用 |
| `ApiRef` 类型化引用 | ✅ 阶段 3 的 `ApiContractRef` 增强 |
| Plugin 体系 | ✅ 阶段 2/3 的 `ResolverFactory` / `DataQueryRegistry` 扩展点 |

**核心观察**：本次改造**没有发明新概念**——是**强化现有概念 + 补缺失维度**。这降低了实施风险。

## 11. 一句话总结

> 3 个阶段的改造**全部是现有架构的强化**——补充"运行时控制"这个缺失维度，把 step 来源、组装、控制、查询全面 first-class，最终实现"框架/业务完全分离"。**改动量约 1500-2410 行，分散在 30+ 文件，全部向后兼容，可独立灰度上线**。
