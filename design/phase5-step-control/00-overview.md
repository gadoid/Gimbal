# Phase 5: Step 控制能力重构（总览）

> Status: **Stash（待评审）**
> 范围: `core/` / `preprocessor/` / `schema/` / `context/` / `statemachine/` / `cli/`
> 设计目标: 让 step 的来源、组装、控制、查询全面 first-class，并最终实现"框架/业务完全分离"

---

## 1. 起源与动机

`Scenario_Test_14.json` 这类结算/核销用例触发了 3 类需求：

1. **运行时控制**：跑到第 N 个 step 后停止（"跑到这个用例的 step 5 看一下响应"）。
2. **动态 step 生成**：从数据库读 100 条订单，对每条做核销（不是写 100 份 step JSON）。
3. **接口契约与业务数据解耦**：同一个 `orderAdd` 接口被 5 个 step 复用，每个 step 重复 80% 字段；业务数据变更要改 5 处。

现状的 3 个**架构层不足**：

| 不足 | 体现 |
|---|---|
| 控制意图无 first-class 通道 | CLI 3 个 stub flag、schema 无字段、状态机错层级、Hook 缺决策点 |
| step 来源被硬编码 | `ScenarioPreprocessor` 紧耦合 4 件事：引用物化 / 认证 / 模板展开 / base_url 选择 |
| step 持有完整 body | 接口契约与业务数据耦合在一个 JSON 对象里 |

## 2. 重构总目标（一句话）

> **把"框架读数据驱动文件"改为"框架调用 step 解析器"，让 step 持有"接口描述符 + 数据查询描述符"而非"完整 body"，最终实现"框架/业务完全分离"——框架是 step 执行引擎 + API 契约解析 + 数据查询分发的可复用底层，业务数据全部可插拔。**

## 3. 4 个核心抽象（贯穿 3 个阶段）

| 抽象 | 解决的问题 | 引入阶段 |
|---|---|---|
| **GatePoint** | "决策时机"维度（独立于 HookPoint 的正交维度）| 阶段 1 |
| **FlowControl** | "step 间控制策略" first-class 抽象 | 阶段 1 |
| **ControlSignal** | "控制意图"信号（区分异常 STOP vs 计划性 HALT）| 阶段 1 |
| **StepResolver** | "step 从哪来"的可替换抽象 | 阶段 2 |
| **DataQuery** | "业务数据从哪来"的可插拔抽象 | 阶段 3 |

## 4. 3 个阶段路线图

```
阶段 1: First-class 控制能力
   ├── GatePoint（决策时机）
   ├── FlowControl（控制策略，discriminated union）
   ├── ControlSignal（控制信号）
   ├── RuntimeControl（注入到 Configuration）
   ├── ScenarioRunState（ScenarioContext 新字段）
   └── 内置 StepRangeFlowControl（解决 step_to 需求）
   产出: --step-from / --step-to / --breakpoint 真正可用

阶段 2: StepResolver 抽象
   ├── StepResolver Protocol（lazy iterator）
   ├── JsonRefStepResolver（默认实现，兼容现有 JSON）
   ├── 替换 ScenarioPreprocessor 的硬编码组装
   └── Engine.create_resolver() factory
   产出: step 来源可替换，动态 step 生成成为可能

阶段 3: DataQuery 解耦
   ├── DataQuery discriminated union
   ├── Step.data_query 字段（替代 request.body 的查询语义）
   ├── DataQueryRegistry（plugin 化注册）
   ├── 内置 InlineQuery / SqlQuery / FileQuery / CallableQuery
   └── ApiContract 与 step 解耦（强化 ApiRef 体系）
   产出: 框架/业务完全分离，接口契约与业务数据独立演化
```

## 5. 兼容性矩阵

| 维度 | 阶段 1 | 阶段 2 | 阶段 3 |
|---|---|---|---|
| 老 scenario JSON | ✅ 完全兼容 | ✅ 完全兼容 | ✅ 完全兼容（`request` 字段降级为默认 inline） |
| 老 CLI 调用 | ✅ 完全兼容 | ✅ 完全兼容 | ✅ 完全兼容 |
| 老 Plugin 体系 | ✅ 不动 | ✅ 不动 | ✅ 扩展（plugin 可注册 DataQuery）|
| 老 Reporter | ✅ 不动 | ✅ 不动 | ✅ 不动 |
| 老 Result 字段 | ✅ 不动 | ✅ 新增 `total_resolved_steps` | ✅ 不动 |
| 老 HookPoint | ✅ 不动 | ✅ 新增 `STEP_BEFORE_RESOLVE` | ✅ 不动 |

**核心原则：3 个阶段**都是**"换引擎、不换轮胎"**——所有阶段都保持对外行为兼容，只在框架内部做抽象强化。

## 6. 关键架构原则（贯穿 3 个阶段）

### 6.1 开闭原则
所有"具体场景"通过 plugin / discriminated union 注册，框架核心只持有抽象。

### 6.2 正交性
GatePoint 与 HookPoint 正交（决策时机 vs 事件通知）；FlowControl 与 Strategy 正交（step 间 vs step 内）；ControlSignal 与 HookSignal 正交（控制意图 vs 异常中断）。

### 6.3 兼容性
3 个阶段都保持向后兼容，老 JSON / 老 CLI / 老 plugin 完全不动。

### 6.4 渐进式落地
3 个阶段互相依赖：阶段 1 解决 step_to 需求、阶段 2 解耦 step 来源、阶段 3 解耦数据来源。每个阶段都先解决一个真实问题，不做空中楼阁。

## 7. 文档结构

| 文件 | 内容 |
|---|---|
| `00-overview.md` | 本文件——总览 |
| `01-step-control-foundation.md` | 阶段 1：First-class 控制能力（GatePoint / FlowControl / ControlSignal）|
| `02-step-resolver.md` | 阶段 2：StepResolver 抽象 |
| `03-data-query-decoupling.md` | 阶段 3：DataQuery 解耦（框架/业务分离）|
| `04-migration-plan.md` | 3 个阶段的迁移路径与兼容策略 |
| `05-architecture-impact.md` | 架构影响评估（10 层影响、风险点、改动量）|

## 8. 评审检查清单

- [ ] 阶段 1 的 3 个 first-class 抽象（GatePoint / FlowControl / ControlSignal）是否足够
- [ ] 阶段 1 的 `RuntimeControl` 放在 Configuration 还是 Engine 入参
- [ ] 阶段 2 的 StepResolver 接口是否需要 `has_next / peek / stop` 三个方法
- [ ] 阶段 3 的 DataQuery 与现有 `request.body` 字段的兼容策略
- [ ] 阶段 3 的 ApiContract 资产化是否本期做
- [ ] 整体 3 个阶段的依赖顺序是否合理
