# step 分支表达力验证（D-1）

> 日期：2026-10-10　基线：`feat/plate-s1` @ `87e8a1a3`（含工作区未提交改动）
> 状态：**已完成——结论：M2 的 Step / Strategy 结构无需改动**，M2 步骤 1 定义可按 v2.2 定稿。
> 触发：M2 v2.2 §10 步骤 1 定稿前置；Release v4.0 §8 前置；决策 D-1（2026-10-10，排在一切开工事项之前）。
> 方法：两侧结构取证 + 全量真实语料盘点 + 逐流程模式判定。

## 1. 验证问题

step 分支表达力是 M2 与 Release 两方案共同登记的最大未知数（可行性评估风险 1，级别「高」）：若验证结论要求更强的分支/并行表达，修改应落在 M2 步骤 1 的定义里，而不是反转完成后再改。本验证回答：**现有两侧结构能否承载真实业务流程的分支形态，是否需要给 Step / Strategy 加字段。**

## 2. 两侧现状（证据）

**知识侧（Statement kind=step，`dialect/validation.py`）**：槽位 = `cap`（必填）+ `order`（必填整数，S1 校验 :292-296）+ `branch_on`（可选，词条类型限定 outcome / value，:161）。全序 + 单值触发。

**用例侧（执行器）**：
- Step 模型（`src/gimbal/schema/step.py`）：kind / description / call / request / strategy——**没有任何条件、分支、并行字段**；
- 执行严格顺序（`core/scenario_runner.py:438` 逐 step 枚举）；runner 注释原文（:30-33）：运行时控制只允许按 step index 提前跳出，**「其它控制（条件分支、循环某个 step 等）仍走插件层」**——引擎明确把场景内条件/循环留在插件层，不进 schema；
- 失败分支按策略粒度承载：`strategy.py:53` `onFailure: FailurePolicy`（ABORT/继续等）。

**Suite 编排面（`src/gimbal/schema/scenario.py`）**：`UnitDecl`（needs DAG 边 :63 = 单元级并行+汇合；inputs/outputs/map 连线传值；repeat 展开）、`Control`（only / from_node / to_node 链切片 :53）、`GateDecl`（聚合度量判定门 :98）、`CheckDecl`（按 refs/bracket/tags 选择器注入横切断言 :92）。

## 3. 真实语料盘点

| 语料 | 规模 | 分支形态 |
|---|---|---|
| platform user_story（`systems/platform/deliverables/`，全部既有故事） | 5 个故事 / 23 个 step 片段 | 全部线性；3 处 `branch_on`，每处单值正向触发（`outcome:user.last_admin` / `outcome:suite.member_not_owned` / `outcome:suite.run_in_progress`）；无 else 分支对、无并行、无循环 |
| fin | **无 deliverables** | — |
| 仓库 YAML 用例（gimbal-bootstrap 等） | 全量 grep `condition/branch_on/when:` | **零命中**——现有可执行用例没有任何分支键 |

## 4. 逐模式判定

| 流程模式 | 判定 | 承载方式 |
|---|---|---|
| P1 顺序 | ✅ | 两侧原生 |
| P2 条件步骤（某结果发生才执行该步） | ✅ | 知识侧 `branch_on`；派生时 `paths` 展开为多条线性路径，**一条路径 = 一个场景**（plate-design 第 9 项已定），场景本身不需要条件字段 |
| P3 if/else 分支对 | ✅（有边界） | 各分支用自己的可观测量触发（如 `value:order.status.filled` vs `value:order.status.pending`，枚举可穷尽互补）；**「X 未发生」的负向触发不可表达**——用 note 片段兜底（登记，非阻塞；现有语料未出现此形态） |
| P4 并行 + 汇合 | ✅（不在 step 层） | 承载位 = Suite 的 `UnitDecl.needs` DAG（单元粒度）——这与执行器顺序执行的事实一致：场景内步骤级并行在引擎里本就不存在，给 M2 Step 加并行字段也不会被执行；知识侧按 plate-design 6.6 既定兜底（note + transition），fin 交叉检验时复核 |
| P5 循环 | ✅（不在 step 层） | 重试 = RetryPolicy（策略级）；循环 = runner 明示走插件层；知识侧不表达（全序） |

## 5. 结论

1. **M2 Step / Strategy 结构无需改动**，v2.2 §9.2 草案照此定稿。分支表达力由四层分工承载，各层均已存在或已登记：
   - 知识侧 `branch_on`（现状够用）；
   - `paths` 展开（branch_on → 多线性路径 → 一路一场景）；
   - Suite 编排面（needs DAG 并行汇合 + Control 切片 + GateDecl 判定门 + CheckDecl 横切断言）；
   - 插件层（场景内条件/循环的预留通道，引擎注释原文在案）。
2. 「给 step 增加并行组」（plate-design 6.6 的待评估项）**维持延后**：语料零需求 + 引擎顺序执行 + Suite 已承接单元级并行，三重依据。
3. 数据边界声明：本验证基于 platform 全部故事（23 步）+ YAML 用例全量（零分支键）+ 结构论证；**fin 尚无 deliverables**，fin 交叉检验铺开时若出现并行/负向触发形态，按 6.6 兜底复核，仍不改 M2 结构（改的是知识侧片段或 Suite 面）。

## 6. 连带登记（随 D-0 批④折入文档）

- **`paths` 动作未实现**（plate-design 7.2 规划项）：现有的 `action_endpoint_resolve_paths`（`routes_grammar.py:721`）是接口 JSONPath 候选解析（API Surface B1），与故事路径展开**同名不同义**——实现故事 `paths` 动作时须避开这个名字混淆，建议命名 `story-paths` 或挂在 statement dim。
- 知识侧 `branch_on` 不支持取值列表（OR/且语义都没有）；outcome 片段的 `when` 支持列表表「且」（已定）。若未来需要 OR，作为知识侧加法演进评估。
- `Control.only/from_node/to_node` 与 RunOptions 的 `step_from/step_to` 是两层不同的区间控制（单元级 vs 场景内步骤级），M2 §9.2 草案无冲突，特此留证。
