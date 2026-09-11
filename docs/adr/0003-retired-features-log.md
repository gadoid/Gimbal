# ADR 0003:已退场功能清单(退场记录收口)

## 状态

已实装 / Accepted。

本文件是**退场知识的唯一归宿**:功能退场后,代码注释不再承载
「已移除/已退场/原为 XX」类历史叙述,统一收录于此。代码中的注释
只描述当前行为;需要追溯历史时查本表与所引 spec/commit。

| # | 功能 | 退场日期 | 替代语义 | 退场提交 |
|---|------|----------|----------|----------|
| 1 | `queryUser` / `query_user`(运行方案查询凭证) | 2026-09-09 | 查询凭证唯一来源 = `config.users` 首键(查询身份 = 执行身份),与运行方案无关 | (裁定日早于本清单,见 spec §3.1/§5) |
| 2 | DataSetEditor 基线区 / 直填列 / 提升入口 | 2026-09-11 | 列宇宙 = `config.vars`(引用扫描派生);var 基线编辑入口 = 置顶基线行;字面值编辑的家在编排器 FieldForm | `bd15cc5`(spec v2 §6/T0) |
| 3 | 期望提升链(exp_*) | 2026-09-11 | 期望偏离的语义位置 = 断言管理注册表(条目自含 injection + asserts,`assertion_registry` 场景级节) | `b912d59`(spec v2 §2/§9) |
| 4 | `step.request.fields_meta` 作为请求目录数据源 | (随会话级现拉改造) | 数据源 = 会话级按 `endpoint_id` 现拉 `/full`,不读持久化快照 | (见 CaseComposerCanvas `stepDecls`) |

## 各条详情

### 1. queryUser(2026-09-09 裁定)

- **原语义**:`ServiceBinding.queryUser`(`query_user`)在运行方案侧车中单独声明查询凭证。
- **现语义**:查询凭证唯一来源 = `config.users` 首键 — 查询身份 = 执行身份,与运行方案解耦。
- **存量处置**:旧侧车残留键由 pydantic `extra=ignore` 静默丢弃,无读兼容、无迁移工具。
- **涉及面**:`frontend/src/api/scenario-composer.ts` ServiceBinding、`backend/app/schemas/scenario_composer.py` ServiceBinding。

### 2. DataSetEditor 基线区 / 直填列 / 提升入口(2026-09-11,spec v2 §6/T0)

- **原语义**:编辑器内折叠式「基线区」直接编辑 step 字面值(直填列);`promote/demote` 在编辑器内声明变量;列派生器 `deriveBaselineColumns / fieldsOf / varNameOf / renderTemplate` 从 step 推导列宇宙。
- **现语义**:列宇宙 = `config.vars`(由 dataset-segments 引用扫描派生,未声明引用变量追加在后);一变量一列;var 基线唯一编辑入口 = 置顶基线行;直填(字面值)的编辑家在编排器 FieldForm;数据集行纯 var-dict(零保留键),CSV 只导值。`dataset-palette.ts` 仅承载 `BaselineColumn` 最小列形状(网格与 CSV 链共用)。
- **存量处置**:数据集行残留直填键由既有死键软提示兜底;无迁移工具。
- **涉及面**:`views/DataSetEditor.vue`、`utils/dataset-palette.ts`、`utils/dataset-grid.ts`、`utils/csv-dataset.ts`。

### 3. 期望提升链 exp_*(2026-09-11,spec v2 §2/§9,提交 `b912d59`)

- **原语义**:断言卡上「设为期望变量」把 expected 提升为 `${var.exp_*}` 变量(撞名改名 / 还原为字面量 / 期望导航 / VarSelector exp_ 紫族标注 / vardemote 链),数据集侧曾按期望列行级化。
- **现语义**:期望偏离的语义位置 = **断言管理注册表**(`assertion_registry` 场景级节,条目自含 injection + asserts;编辑器 = `AssertionRegistryEditor`,运行时汇合 = RunDialog 注入条目多选 → dispatcher 物化注入族)。expected 回归字面量;模板化的一致性断言(`${var.x}` 引用)不受影响 — `deriveSegments` strategy 段 / `ExpectColumn` / 期望徽标 / ↗ 跳断言卡等引用面保留。
- **存量处置**:存量场景的 `${var.exp_*}` 引用与 `config.vars` 的 `exp_*` 键 = 用户手工清理;无读兼容、无迁移工具。测试中 `exp_code`/`exp_msg` 等为夹具变量名,非功能残留。
- **涉及面**:`components/composer/StrategyForm.vue`、`CaseComposerCanvas.vue`、`views/CaseComposer.vue`、`components/composer/VarSelectorModal.vue`、`utils/dataset-segments.ts`(`expectVarNameOf` 已删)。

### 4. fields_meta(随会话级现拉改造)

- **原语义**:`step.request.fields_meta` 持久化字段目录曾作为请求目录数据源。
- **现语义**:会话级按 `endpoint_id` 现拉 `/full`,不读持久化快照(`stepDecls`);`fields_meta` 不再被任何代码读取。

## 维护约定

- 此后退场某功能时:删除代码(含注释),并在本表追加一行 + 详情小节(日期 / 原语义 / 现语义 / 存量处置 / 提交)。
- 代码注释一律现在时描述当前行为;历史性对照(「原为 / 已移除 / 已退场」)只写在本文档。
