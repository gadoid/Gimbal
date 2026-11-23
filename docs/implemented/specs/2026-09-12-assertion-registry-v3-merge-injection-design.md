# 断言管理 v3 — path 直补与数据集合并执行协议(spec v3)

**日期**: 2026-09-12
**状态**: 设计定稿待用户审
**分支**: feat/dataset-driven-refactor
**取代**: `2026-09-11-assertion-registry-field-binding-design.md`(spec v2)的注册表面(T2-T5);v2 已实施数据集侧(T0/T1)与编辑器骨架不变部分见 §0

**修订**: §2 的 `path-unresolvable` 判定面已被 `2026-09-12-injectable-path-surface-design.md`(spec v3.1)放宽为「契约声明 ∪ body 现存」;§1 裁定 2「任意字段直补」的成立范围随之覆盖 form/collapse/carry 三面

---

## 0. 背景与取代关系

spec v2 实施「偏离注入注册表」后,用户重新定纲(2026-09-12):v2 的三处核心拍板不再成立 —

| v2 拍板 | v3 取向 |
|---|---|
| 绑定退场,两组件互不感知,唯一汇合 = 运行时并集(§5) | 执行时**合并进同一 case**(数据集行 × 断言条目交叉) |
| 注入 = varName 覆写 config.vars,「模板即地址」(§3) | 注入 = **path 直补**(引擎 Assign 策略),任意字段可偏离,与 vars 零耦合 |
| 编辑入口 = 配置区「断言管理」节 + 独立编辑视图(§3/§7) | 核心位置 = **测试数据页与数据集同页双区**;配置签退为纯展示 |

v2 保留不动:数据集变量优先双模式(T0)、`fieldPathsOf` 全字段扫描(T1)、asserts patch 的 override/append 语义、运行方案(runSchemes)机制、悬空软提示不阻断编辑的交互纪律。

## 1. 用户裁定记录(2026-09-12)

1. **条目 = `{定位 path, 注入值, 断言}` 三元组**;path 是能锁定到该元素的 jsonpath,一等注入地址
2. **任意字段直补**:「仅模板化字段就收缩回数据集的 scope 了」— 不预设字段模板化
3. **两通道完全解耦**:「断言的值注入和数据集的值注入是完全解耦的」— 数据集走 vars 合入(不动),断言走 path 替换,正交叠加
4. **逐条隔离矩阵**:N 行 × M 条目 = N×M cases,每 case 单一偏离、可直接归因;无数据集 = 基线 × M
5. **IA = 同页双区**:数据集列表页升级「测试数据」页,数据集网格 + 断言条目网格同屏
6. **两个执行入口**:数据集入口(某行/整库 + 勾断言)/ 场景入口(运行/调试临时勾断言),同一运行面板组件
7. **配置签纯展示**:列出当前断言项,可「加入本次执行」;不再是编辑器唯一跳转入口
8. **清理旧实现**(用户明示):退场清单见 §7,不留兼容层
9. **headers = 协议位**:引擎 call 发送 headers 不回读 scratch([call.py:26]),执行核按约束不动 — v1 path 只支持 body 源(GET 的 body 字组分发为 query 参数,恰好覆盖查询参数场景)

## 2. 条目模型(重铸)

权威形状(前端 `types/assertion-registry.ts`,后端自由 dict 不建模):

```ts
interface AssertionEntry {
  id: string
  name: string
  /** 定位面:锁定到该元素的地址。jsonpath 根 = 该步请求 body */
  path: { stepIndex: number; source: 'body'; jsonpath: string }
  /** 注入面:替换该字段的值(字面量,原样覆写不 coerce) */
  value: unknown
  /** 断言面:对替换后结果的期望(继承 v2 语义) */
  asserts: { stepIndex: number; target: string; operator: string
             expected: unknown; mode: 'override' | 'append' }[]
}
```

- **与 config.vars 零耦合**:varName 从条目形状中消失;「模板即地址」对断言自然失效(数据集侧「模板即地址」拍板不变)
- **value 类型**:编辑器按字段当前字面量类型还原展示(int/float/bool/str;对象/数组值 JSON 输入模式);物化原样覆写
- **asserts**:override 匹配键 = stepIndex + target(改 expected)/ append 追加;负向用例必须 override(v2 语义继承)
- **悬空检测**(软提示不阻断,前端 `registryIssues` + 后端 `entry_issues` 同构):
  - `step-oob`:stepIndex 越界(path 与 asserts 各自检)— 保留
  - `override-no-match` — 保留
  - `path-unresolvable`(新):jsonpath 不落在该步 request body 的字段树上(前端 fieldPathsOf 比对;后端 `jsonpath.exists(request.body, jsonpath)`);str body 步骤无可索引字段 → 一律不可解析
  - `var-unknown` — **退役**(不再有 vars 耦合)

## 3. 物化链(path 直补,引擎/plate 零改动)

引擎原生能力:Assign 策略(`source` = 字面量/`${var}`,`target` = scratch JSONPath),before_request 阶段执行,写嵌套结构;请求优先取被 Assign 修改后的 body([engine.py:415])。scratch 键 `$.request_body`。

```text
compose(definition, row?, entry) =
  deepcopy definition
  → row 行值合入 config.vars(现状,不动)
  → steps[path.stepIndex].strategy 追加
      { "kind": "assign", "source": value,
        "target": "$.request_body" + jsonpath[1:] }   // $.amount → $.request_body.amount
  → asserts patch(现状机制,不动)
  → plate /convert → 凭证注入 → gimbal run launch
```

- **执行序**:vars 渲染 → Assign 直补 → 请求 — 偏离最后生效;字段恰为模板串(`"${var x}"`)时被字面量整体替换,该 case 内数据集行值对此字段不再起效(裁定 3 的必然推论)
- **convert 穿越**:Assign 是 StrategyUnion 合法成员(plate/gimbal schema 双侧均有),与现有 assertion patch 同链路;黄金等价测试(执行/导出同源)继续锁死
- Assign 基座字段全取默认 — Assign 的 scope 只参与 source 解析(字面量 source 无关),写入路径 `write_scratch(target)` 不消费 scope;T2 集成测试锁定

## 4. 执行矩阵与行级选择

**case 展开**(dispatcher `_fanout` entries 重构):

| 选择 | cases | 对比 v2 |
|---|---|---|
| 仅数据集 | N 行(无注入) | 不变 |
| 仅断言 | 基线 × M | 不变 |
| **双选** | **N × M 交叉**:每 case = 一行 + 一条目(Assign 直补 + asserts patch) | v2 为 N+M 并集 — **改** |
| 都不选 | 1 基线行 | 不变 |

统一公式:`行集合 R`(选中行;空 = {[基线]})× `条目集合 E`(选中且悬空检测通过;空 = {[无注入]})。

**RunRequest**(schemas/scenario_composer.py):

- 新权威键 `dataSetSelection: { datasetId: string; rowIndexes?: number[] }[]`(rowIndexes 0-based,与编辑器行号一致;缺省 = 整库)— 数据集入口「某行」所需
- 旧键 `dataSetIds` 保留为兼容读键(存量 runSchemes 回读映射为整库选择;两键同发时 dataSetSelection 优先、dataSetIds 忽略)
- `injectionEntryIds` 照旧;`stepTo/nRuns/parallel` 照旧
- RunScheme 侧car透传 `dataSetSelection`(与 dataSetIds 同款兼容语义)

**审计**:交叉行 JSONL/RowState 同记 `datasetId + rowIndex + injectionId`(三字段已在形状,首次同时有值);case stem 命名带三定位(条目用 id,如 `case-003-ds-x-r1-inj-inj-2-n0`)。

## 5. IA:测试数据页

- **CaseDataSetsList → 「测试数据」页**(路由 `/scenarios/:id/data-sets` 不变,页面标题/语义升级):同页双区 — 数据集卡片网格(现状不动)+ **断言条目卡片网格**(名称 / path 徽标 `步骤N · $.xx` + ↗ 跳编排器 / 值摘要 / 期望数 / 悬空灰 / 旧版条目灰)
- **AssertionRegistryEditor 保留独立路由**(`/scenarios/:id/assertions`),重铸三元组编辑:path 只读 + 跳编排器 / value 类型化编辑 / asserts 编辑(继承);入口搬家至测试数据页卡片
- **配置签**(CaseComposerConfig):断言管理入口卡 → **纯展示列表**(条目名 + 悬空态)+「管理」跳测试数据页 + 每条「加入本次执行」(打开运行面板并预勾该条)
- **编排页标记**(FieldActionMenu,用户 WIP 文件 — 实施时只加必要 hunk):「加入断言管理」落新条目 — `path` 自动(stepIndex + jsonpath),`value` 预填字段当前字面量;varName 不再采集

## 6. 两个执行入口(同一运行面板组件)

- RunDialog 抽出为可复用挂载(props 装配走 composable/store,场景加载不绑死 CaseComposer)
- **场景入口**:CaseComposer 内现状挂载 — 数据集选择 + 断言多选保留,选择语义并集 → 交叉(§4);「加入本次执行」预勾透传
- **数据集入口**:测试数据页数据集卡片「运行」(预填整库)/ DataSetEditor 行工具栏「运行此行」(预填单行)— 断言区同款勾选,不造第二套运行 UI

## 7. 退场清单(用户明示:清理不再需要的实现)

**前端**:

| 位置 | 退场内容 |
|---|---|
| `types/assertion-registry.ts` | `AssertionAnchor` 类型、`injection` 字段、旧 `AssertionEntry` 编辑形状(仅留 `isLegacyEntry` 类型守卫供 §8 灰显识别) |
| `utils/assertion-registry.ts` | `isDeadEntry`/`registryIssues` 的 var-unknown 分支与 anchor 消费 |
| `AssertionRegistryEditor.vue` | anchor 联动区 / injection(varName 候选)编辑区 |
| `CaseComposer.vue` | `onRegistryAdd(anchor)` 旧签名、`registryVarNames` computed、dead 计算的 vars 维度 |
| `CaseComposerConfig.vue` | 旧入口卡(计数 + 直跳编辑器) |
| Canvas/FieldActionMenu | anchor 载荷(varName 采集) |
| 测试 | `CaseComposer.registry.test.ts` / `AssertionRegistryEditor.test.ts` 的 anchor/injection 用例 |

**后端**:

| 位置 | 退场内容 |
|---|---|
| `run_injection.py` | `entry_issues` 的 var-unknown 分支与 `var_names` 参数;`compose_injection_scenario` 的 vars 覆写段(整体重写为 Assign patch) |
| `run_dispatcher.py` | `_definition_vars` helper、注入族并集展开(entries 列表构造)、`if not fanout_datasets and not selected_entries` 特判(随交叉矩阵公式重构) |
| schemas | RunRequest/RunScheme **不删键**(dataSetIds 兼容读保留,§4) |
| 测试 | `test_run_injection.py` 旧形状用例、dispatcher 注入族并集断言 |

**文档**:v2 spec 头部加取代标注(本提交)。

## 8. 存量处置(沿用 v2 §9 裁定风格)

- **不建读兼容、不建迁移工具**;旧形状条目(anchor+injection)**保留原样不删**,UI 灰显 +「旧版条目,请重建」(不可编辑、不可选中执行)
- dispatcher 侧无 `path` 的条目自然全量 issues → skip + 告警(现有死条目过滤链不执行它)
- 历史 executions 的 JSONL 注入族行(injectionId)照旧回放(字段未变)

## 9. v1 边界与协议位

协议位(只留位不实现):headers 源(待引擎 headers 回读 scratch)/ 多字段复合条目(一次多 path 偏离)/ 值类别快捷与生成器 / 非断言策略(终止/extract)/ str body 的 path 定位(引擎阶段 2 拆请求子类后可收紧)。

## 10. 任务切分建议(供 writing-plans)

| # | 任务 | 层 |
|---|---|---|
| T1 | types + utils 重铸(新形状 / 悬空三检 / legacy 识别)+ 测试 | 前端 |
| T2 | `run_injection.py` 重铸:`entry_issues`(path 检)+ `compose_injection_scenario`(Assign patch)+ 测试(含 convert 穿越黄金等价) | backend |
| T3 | dispatcher 交叉矩阵 + `dataSetSelection` + RunRequest/RunScheme 键 + 审计三定位 + 测试 | backend |
| T4 | AssertionRegistryEditor 三元组重铸 + 测试 | 前端 |
| T5 | Canvas 标记(FieldActionMenu 协调)+ CaseComposer 装配(onRegistryAdd/dead 计算)+ 测试 | 前端 |
| T6 | 测试数据页双区 + 配置签展示化 + 测试 | 前端 |
| T7 | RunDialog 抽出复用 + 交叉语义 + 预填 + DataSetEditor「运行此行」+ 测试 | 前端 |
| T8 | 退场清单逐项清理(§7)+ v2 取代标注 + 全量回归 | 全部 |
