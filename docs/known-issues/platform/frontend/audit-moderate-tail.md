# 前端 dev 依赖审计的 moderate 尾巴（升级边界记录）

> **模块**：`gimbal-platform/frontend`（package.json devDependencies × CI）
> **状态**：已收口（2026-11-24 升级轮：critical/high 清零 + CI 审计门在位；
> 剩余 moderate 为无修复版本尾巴，升级 vue-tsc 3 的路径被上游回归阻塞）
> **来源**：外部评估清单 P0-3（供应链风险：vitest/tinypool critical、vite high）

---

## 0. 已落地的处置（2026-11-24）

- **升级**：vitest 2.1.9 → 5.1.1（清除 tinypool ≤2.1.1 两条 critical RCE gadget
  与 vitest UI critical）、vite 5.4 → 6.4.6（清除 dev-server high）、
  @vitejs/plugin-vue → 6.0.11。生产依赖审计仍为 0。
- **CI 审计门**：plate-ci frontend job 新增 `npm audit --audit-level=high`
  （Node 同步 20→22：vitest 5 与 plugin-vue 6 均要求 ≥22.12；
  生产 dist 构建亦须 Node 22 —— Node 18 在 plugin-vue 6 即挂）。
- **测试面适配**（3 文件 9 用例，vitest≥4 语义变化）：
  router.roles — push promise 早于守卫链落定，改为 await 落定后读；
  SchemeWorkbench 405 — restoreAllMocks 不再恢复模块 mock 工厂默认，
  显式声明确认值；WorkbenchView — forks 池满载挂载超 1s，waitFor 宽限 3s。

## 1. 剩余尾巴（moderate ×4，均为无修复版本）

`npm audit` 剩 4 moderate，全部 dev-only、**当前无任何可安装的修复版本**：

1. `editorconfig 1.0.3-3.0.2`（全版本带洞，经它引入 minimatch/glob/js-beautify）；
2. `minimatch 7-11`、`glob 9-14`、`js-beautify ≥1.14.9` —— editorconfig 的传递链。

另 2 个 moderate 随 vue-tsc 3 升级可清（`vue-tsc ≤3.0.1`、
`@vue/language-core ≤3.0.1`，同样引入 minimatch/glob），**但升级被上游回归阻塞**：

- vue-tsc 3 在 **reactive 对象的组件 v-model** 上误插 `.value`
  （实测 CaseComposerConfig 8 处误报；ref 形态不误报）；
- vue-tsc 3 对**兄弟条件分支后的模板收窄**不再延续外层 `v-if`
  （实测 ServiceAdmin 26 处误报）。

## 2. 重开条件（触发即重试 vue-tsc 3）

- vue-tsc/@vue/language-core 发布修复上述两类回归的版本；或
- 本仓前端测试面迁到不依赖这两类模式的写法（成本 > 收益时不做）。

在 CI 审计门把守下，新的 critical/high advisory 落地即红 —— 本记录只追
moderate 尾巴，不再需要人工跑 `npm audit` 巡检。
