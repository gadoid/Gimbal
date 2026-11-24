# 前端 dev 依赖审计的 moderate 尾巴（升级边界记录）

> **模块**：`gimbal-platform/frontend`（package.json devDependencies × CI）
> **状态**：已收口（2026-11-24 两轮：critical/high 清零 + vue-tsc 3.3.13 落地
> + CI 审计门在位；剩余 4 moderate 全为 editorconfig 链无修复版本尾巴）
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
  显式声明确认值；WorkbenchView — forks 池满载下异步卡动态 import 偶发
  超 vi.waitFor 窗，预热 loader 模块缓存后挂载即时（曾 1s/3s/10s 三档
  实测均偶发，预热后 4 连全绿）。
- **vue-tsc 2.2.12 → 3.3.13（exact 钉）**：清 `vue-tsc/language-core` 链
  2 个 moderate。3.3.14 不可用（上游 #6352），静态属性 `//` 规避见 §1.5。

## 1. 剩余尾巴（moderate ×4，均为无修复版本）

`npm audit` 剩 4 moderate，全部 dev-only、**当前无任何可安装的修复版本**：

1. `editorconfig 1.0.3-3.0.2`（全版本带洞，经它引入 minimatch/glob/js-beautify）；
2. `minimatch 7-11`、`glob 9-14`、`js-beautify ≥1.14.9` —— editorconfig 的传递链。

另 2 个 moderate（`vue-tsc ≤3.0.1`、`@vue/language-core ≤3.0.1`，
同样引入 minimatch/glob）**已于同日升级清零** —— vue-tsc 钉 3.3.13（exact）：

## 1.5 升级过程与上游回归（2026-11-24 勘误 + 收口）

初判「vue-tsc 3 被 reactive v-model 误插 `.value` + 模板收窄重置阻塞」
**机理判断错误**，最小复现二分后真因是上游已知回归：

- **#6322 / #6352（vuejs/language-tools，均 Closed-as-completed 但修复
  PR #6241 未合入、无发行版含修复）**：模板**静态属性值含 `//`**（如
  `placeholder="https://…"`）时，language-core 3.x 展平 props 的正则把
  字符串里的 `//` 当行注释截断 → 生成的 TS 损坏 → 该行起 `.value` 误插
  （3.3.14 的 v-model 面）与**后续兄弟节点收窄全灭**（3.3.13/3.3.14 的
  narrowing 面）。实测本仓 31 处「误报」全部由 7 个含 `//` 的静态属性
  引爆，与 reactive/v-model/条件块本身无关。
- **规避双管**：①钉 `vue-tsc@3.3.13`（exact，绕开 3.3.14 的 v-model 面；
  3.3.13 上 v-model 面本来就好）；②全仓 7 处静态属性 `//` 改脚本常量绑定
  （`:placeholder="PH_URL"`，提示文案原样保留，各处带指回本条的注释）。
  升级后 typecheck 0 错误，vue-tsc/language-core 链 2 个 moderate 清零。

## 2. 重开条件

- 上游 PR #6241 合入并随版本发行后：解除 3.3.13 exact 钉、可撤 7 处
  常量绑定（保留亦无害）；在此之前**不要**往模板静态属性值里写 `//`
  （含 URL 示例文案）—— 写脚本常量绑定。

在 CI 审计门把守下，新的 critical/high advisory 落地即红 —— 本记录只追
moderate 尾巴，不再需要人工跑 `npm audit` 巡检。
