# 迁移路径与兼容策略

> Status: **Stash（待评审）**
> 范围: 3 个阶段的实施顺序、回滚策略、兼容矩阵

---

## 1. 3 个阶段的核心依赖

```
阶段 1（first-class 控制）  ──┐
                             ├──→ 阶段 2（StepResolver 抽象）
                             │      └──→ 阶段 3（DataQuery 解耦）
                             │
                             └──→ 可独立上线（解决 --step-to 需求）
```

| 阶段 | 是否可独立上线 | 上线后解决的问题 |
|---|---|---|
| 阶段 1 | ✅ 是 | `--step-to` 真正可用；多种中断语义统一 |
| 阶段 2 | ⚠️ 强烈建议阶段 1 后做 | 动态 step 生成；step 来源可替换 |
| 阶段 3 | ⚠️ 强烈建议阶段 2 后做 | 接口/数据解耦；plugin 化数据查询 |

**关键原则**：每个阶段都解决一个真实问题，不做空中楼阁。

## 2. 阶段 1 迁移路径

### 2.1 实施顺序

```
Step 1: 抽象定义
   └── 新增 gimbal/control/ 模块（4 个文件）
       - gate/point.py
       - gate/signal.py
       - gate/flow.py
       - gate/runtime.py
   不影响任何现有代码

Step 2: Context 扩展
   └── 修改 gimbal/context/scenario.py
       - 新增 run_state: ScenarioRunState 字段
       - ContextManager 派生时支持注入
   兼容：run_state 默认值确保老路径行为不变

Step 3: Hook 扩展
   └── 修改 gimbal/core/hooks.py
       - 新增 HookPoint.STEP_BEFORE_ENTER
   兼容：纯加法，无破坏

Step 4: ScenarioRunner 改造
   └── 修改 gimbal/core/scenario_runner.py
       - run() 接 runtime_control 参数
       - for 循环调 gate_runner
       - Result 扩展 halted 字段
   兼容：runtime_control=None 时走原路径

Step 5: Engine 透传
   └── 修改 gimbal/core/runner.py
       - _run_scenario 透传 runtime_control
       - RunResult 加 halted 字段
   兼容：halted 默认为 0

Step 6: Configuration 扩展
   └── 修改 gimbal/config/models.py
       - Configuration 加 runtime: RuntimeControl 字段
   兼容：RuntimeControl 默认为空

Step 7: CLI 接通
   └── 修改 gimbal/cli/commands/run_scenario.py
       - 把 --step-from/--to/--breakpoint 组装为 RuntimeControl
   兼容：行为变化是"真正生效"（之前是 stub）

Step 8: Reporter 适配
   └── 修改 gimbal/reporter/* (3-4 个 reporter)
       - 渲染 halted 状态
   兼容：老 status 渲染不变

Step 9: 单元测试 + 集成测试
   └── tests/control/ 新增测试
   兼容：所有老测试通过

Step 10: 文档更新
   └── docs/RUNBOOK.md / docs/CONFIGURATION.md
       - 文档化新 flag 行为
```

### 2.2 风险点与回滚

| 风险 | 检测方法 | 回滚策略 |
|---|---|---|
| RuntimeControl 注入导致老 scenario 行为变化 | 跑老 scenario JSON，对比 pass/fail | runtime_control=None 时跳过 gate_runner |
| gate_runner 影响 step 顺序 | 跑顺序敏感测试 | gate_result 默认值（CONTINUE）保证放行 |
| Reporter 渲染异常 | 单元测试 | 老 status 渲染代码保留为 fallback |
| Result 序列化失败 | 序列化往返测试 | halted 字段为 Optional，老 reader 跳过 |

**回滚开关**：阶段 1 引入 `feature_flag: "step_control_v1"`，默认 False，老路径完整保留。

### 2.3 验收测试

- [ ] `gimbal run scenario tests/data/order.json --step-to=5` 停在第 5 个 step
- [ ] `gimbal run scenario tests/data/order.json --step-from=3` 从第 3 个 step 开始
- [ ] `gimbal run scenario tests/data/order.json --breakpoint=2 --breakpoint=4` 在 step 2 / 4 暂停（交互模式留待后续）
- [ ] 不传任何 flag 时，所有老 scenario JSON 行为完全一致
- [ ] Reporter 渲染 halted 状态为黄色 banner
- [ ] 单元测试覆盖率 ≥ 80%

## 3. 阶段 2 迁移路径

### 3.1 实施顺序

```
Step 1: 抽象定义
   └── 新增 gimbal/resolver/ 模块
       - base.py（StepResolver Protocol + ResolvedStep dataclass）
       - json_ref.py（默认实现）

Step 2: JsonRefStepResolver 实现
   └── 从 ScenarioPreprocessor 提取物化逻辑
       - 引用物化
       - 模板展开
       - 不包含认证（认证仍由 ScenarioRunner 处理）
   兼容：与原 preprocessor 行为一致

Step 3: Engine.create_resolver() factory
   └── 修改 gimbal/core/runner.py
       - create_resolver() 默认产 JsonRefStepResolver
       - 接受 plugin 注册的 ResolverFactory

Step 4: ScenarioRunner 改造
   └── 修改 gimbal/core/scenario_runner.py
       - run() 接受 StepResolver | Scenario
       - 内部统一为 StepResolver

Step 5: 旧 preprocessor 软删除
   └── gimbal/preprocessor/scenario_preprocessor.py
       - 标记 deprecated（保留兼容导入）
       - 内部调用 JsonRefStepResolver

Step 6: 内置 resolver 实现
   └── 新增 gimbal/resolver/loop.py
       - LoopStepResolver
       - BranchStepResolver
       - ChainStepResolver
   兼容：纯加法

Step 7: 单元测试 + 集成测试
   └── tests/resolver/ 新增测试
   兼容：所有老测试通过

Step 8: 文档更新
   └── docs/CUSTOMIZATION.md
       - 文档化如何写自定义 resolver
```

### 3.2 风险点与回滚

| 风险 | 检测方法 | 回滚策略 |
|---|---|---|
| JsonRefStepResolver 与原 preprocessor 行为不一致 | 跑老 scenario，对比结果 | 行为对齐测试 + 灰度切换 |
| lazy 评估时机错误导致 step 顺序错乱 | 跑顺序敏感测试 | JsonRefStepResolver 仍用 list 缓冲 |
| Plugin 注册的 ResolverFactory 干扰默认 | 单元测试 + 集成测试 | factory 接受黑名单机制 |

**回滚开关**：`feature_flag: "step_resolver_v1"`，默认 False。

### 3.3 验收测试

- [ ] 老 scenario JSON（无 `StepRef`）行为完全不变
- [ ] 老 scenario JSON（含 `StepRef`）行为完全不变
- [ ] `Engine.run(scenario)` 自动构造 `JsonRefStepResolver`
- [ ] `Engine.run(resolver)` 接受自定义 resolver
- [ ] `LoopStepResolver` 正确生成多个 step
- [ ] `BranchStepResolver` 正确分支
- [ ] 阶段 1 的 FlowControl 仍正常工作

## 4. 阶段 3 迁移路径

### 4.1 实施顺序

```
Step 1: Schema 扩展
   └── 新增 gimbal/schema/data_query.py
       - DataQueryUnion + 6 个内置 query 类
   兼容：纯加法

Step 2: Step.data_query 字段
   └── 修改 gimbal/schema/step.py
       - 新增 data_query 字段（Optional）
       - request 字段降级为 Optional
   兼容：data_query 默认为 None

Step 3: DataQueryResolver 实现
   └── 新增 gimbal/runtime/data_query_resolver.py
       - 6 个内置 resolver（inline / file / sql / callable / random / extract / merge / chain）
   兼容：纯加法

Step 4: ApiContract schema
   └── 新增 gimbal/schema/api_contract.py
       - ApiContract + ApiContractRef
   兼容：现有 Api / ApiRef 仍可用

Step 5: ApiContractResolver 实现
   └── 新增 gimbal/runtime/api_contract_resolver.py
   兼容：现有 Api 直接走原路径

Step 6: DataQueryRegistry
   └── 新增 gimbal/plugins/data_query_registry.py
       - plugin 化注册机制
   兼容：纯加法

Step 7: 内置 contrib
   └── 新增 gimbal/contrib/data_query/ 模块
       - 6 个内置 query 的标准实现
   兼容：纯加法

Step 8: 兼容层
   └── 修改 gimbal/runtime/data_query_resolver.py
       - 如果 step.data_query is None：
         自动转 InlineQuery(body=step.request.body)
   兼容：老 JSON 自动走兼容路径

Step 9: 单元测试 + 集成测试
   └── tests/data_query/ 新增测试

Step 10: 文档更新
   └── docs/DATA_QUERY.md
       - 文档化所有内置 query
       - 文档化如何写自定义 query plugin
```

### 4.2 风险点与回滚

| 风险 | 检测方法 | 回滚策略 |
|---|---|---|
| 自动兼容层（data_query=None → InlineQuery）行为不一致 | 跑老 scenario，对比结果 | 行为对齐测试 |
| SqlQuery 的连接管理出错 | 集成测试 | 复用现有 connection 池 |
| 性能（lazy 评估）不如 eager | 性能测试 | 提供 eager 选项 |

**回滚开关**：`feature_flag: "data_query_v1"`，默认 False。**注意**：阶段 3 的 schema 改动（Step.data_query 字段）需要更谨慎——可能需要"老 JSON 走兼容路径"作为长期 fallback。

### 4.3 验收测试

- [ ] 老 scenario JSON（带 `request.body`）行为完全不变
- [ ] 新 scenario JSON 可用 `data_query` 替代 `request.body`
- [ ] `SqlQuery` 支持从数据库动态生成数据
- [ ] `MergeQuery` 支持多数据源合并
- [ ] `ExtractQuery` 支持从 ctx 提取数据
- [ ] plugin 可注册新的 `DataQuery` 类型
- [ ] `ApiContract` 可独立资产化

## 5. 总体兼容矩阵

### 5.1 兼容性总览

| 维度 | 阶段 1 | 阶段 2 | 阶段 3 |
|---|---|---|---|
| 老 scenario JSON | ✅ 完全兼容 | ✅ 完全兼容 | ✅ 完全兼容（自动兼容层）|
| 老 CLI 调用 | ✅ 完全兼容 | ✅ 完全兼容 | ✅ 完全兼容 |
| 老 Plugin 体系 | ✅ 不动 | ✅ 不动 | ✅ 扩展（plugin 可注册 DataQuery）|
| 老 Reporter | ✅ 不动 | ✅ 不动 | ✅ 不动 |
| 老 Result 字段 | ✅ 不动 | ✅ 新增 `total_resolved_steps` | ✅ 不动 |
| 老 HookPoint | ✅ 不动 | ✅ 新增 `STEP_BEFORE_RESOLVE` | ✅ 不动 |
| 老 Api / ApiRef | ✅ 不动 | ✅ 不动 | ✅ 不动（ApiContract 是增强）|
| 老 Step schema | ✅ 不动 | ✅ 不动 | ⚠️ `request.body` 降级为可选（兼容）|

### 5.2 升级路径总览

```
v0.x 现状
   ↓
v1.0 阶段 1 上线
   - 新增 control 模块
   - 真正支持 --step-to
   - 老 JSON 行为不变
   ↓
v1.x 阶段 2 上线（建议 1-2 个迭代后）
   - 新增 resolver 模块
   - 老 preprocessor 标记 deprecated
   - 老 JSON 走 JsonRefStepResolver
   ↓
v2.0 阶段 3 上线（建议阶段 2 稳定后）
   - 新增 data_query 模块
   - request.body 自动转 InlineQuery
   - 老 JSON 仍可使用
   - 新 JSON 推荐用 data_query
```

## 6. 灰度发布策略

### 6.1 阶段 1 灰度

| 阶段 | 范围 | 验证 |
|---|---|---|
| 1a 内部测试 | 团队内部 | 单元测试 + 集成测试通过 |
| 1b canary | 5% 流量 | 关键 scenario 对比通过率 |
| 1c 全量 | 100% 流量 | 监控 1 周无异常 |

### 6.2 阶段 2 灰度

| 阶段 | 范围 | 验证 |
|---|---|---|
| 2a 影子模式 | 双跑：老 preprocessor + 新 resolver，结果对比 | 一致性 ≥ 99.99% |
| 2b 切换 | JsonRefStepResolver 上线，老 preprocessor 软删除 | 监控 1 周无异常 |
| 2c 清理 | 移除老 preprocessor | — |

### 6.3 阶段 3 灰度

| 阶段 | 范围 | 验证 |
|---|---|---|
| 3a 自动兼容层验证 | 老 JSON 自动走 InlineQuery 路径 | 行为对比 100% 一致 |
| 3b 新写法测试 | 部分用例改用 data_query | 监控 2 周 |
| 3c 文档化推荐写法 | 文档 + 工具链支持 data_query | — |

## 7. 风险登记表

| 阶段 | 风险 | 严重度 | 缓解措施 |
|---|---|---|---|
| 阶段 1 | RuntimeControl 注入导致老 scenario 行为变化 | 中 | 默认值确保兼容 + 灰度 |
| 阶段 1 | gate_runner 影响 step 顺序 | 低 | gate_result 默认值放行 |
| 阶段 1 | Reporter 渲染异常 | 低 | 老 status 渲染保留 |
| 阶段 2 | JsonRefStepResolver 与原 preprocessor 行为不一致 | 高 | 影子模式对比 |
| 阶段 2 | lazy 评估时机错误 | 中 | JsonRefStepResolver 仍可缓冲 |
| 阶段 2 | Plugin ResolverFactory 干扰默认 | 低 | 黑名单机制 |
| 阶段 3 | 自动兼容层行为不一致 | 高 | 行为对齐测试 |
| 阶段 3 | SqlQuery 连接管理出错 | 中 | 复用现有连接池 |
| 阶段 3 | Step schema 改动破坏老 JSON | 中 | 自动兼容层 + Optional 字段 |

## 8. 时间表（建议）

| 阶段 | 工期 | 资源 |
|---|---|---|
| 阶段 1 实施 | 2-3 周 | 1 后端 + 1 测试 |
| 阶段 1 灰度 | 1-2 周 | 1 SRE |
| 阶段 1 稳定 | 1 周 | — |
| 阶段 2 实施 | 3-4 周 | 1 后端 + 1 测试 |
| 阶段 2 灰度 | 2-3 周 | 1 SRE |
| 阶段 2 稳定 | 1-2 周 | — |
| 阶段 3 实施 | 4-6 周 | 2 后端 + 1 测试 |
| 阶段 3 灰度 | 3-4 周 | 1 SRE |

**总时间**：约 4-6 个月（含灰度稳定期）。

## 9. 决策检查点

实施过程中需要决策的检查点：

| 检查点 | 时机 | 决策内容 |
|---|---|---|
| **CP1** | 阶段 1 启动前 | `RuntimeControl` 放在 Configuration 还是 Engine 入参？ |
| **CP2** | 阶段 1 实施中 | `STEP_BEFORE_ENTER` 与 `STEP_START` 是否合并？ |
| **CP3** | 阶段 1 上线前 | 是否需要 `CONTROL_HALT` 终态？（还是只加 halted 字段）|
| **CP4** | 阶段 2 启动前 | StepResolver 接口是否需要 `has_next / peek / stop`？ |
| **CP5** | 阶段 2 启动前 | 旧 `ScenarioPreprocessor` 立即删除还是软删除？ |
| **CP6** | 阶段 3 启动前 | ApiContract 资产化是否本期做？ |
| **CP7** | 阶段 3 实施中 | `request.body` 字段是否保留？保留多久？ |

## 10. 退出标准

### 阶段 1 退出标准
- [ ] `gimbal run scenario --step-to=N` 在 100% 测试用例上行为正确
- [ ] 老 scenario JSON 全部回归通过
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 文档更新完成
- [ ] 灰度 1 周无 P0/P1 问题

### 阶段 2 退出标准
- [ ] 影子模式对比 100% 一致
- [ ] 自定义 resolver 至少 3 个内部使用案例
- [ ] 旧 preprocessor 完全移除
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 灰度 2 周无 P0/P1 问题

### 阶段 3 退出标准
- [ ] 老 JSON 100% 回归通过
- [ ] 至少 5 种内置 DataQuery 类型稳定
- [ ] plugin 注册的 DataQuery 至少 2 个外部使用案例
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 灰度 3 周无 P0/P1 问题
