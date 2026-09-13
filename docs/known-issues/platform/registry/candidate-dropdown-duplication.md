# 两处候选输入的 UI 不统一（**已评估，不做**）

> **模块**：`gimbal-platform/frontend`（候选输入组件 × 两处消费方）
> **状态**：**已评估，不做**（阶段二·① 裁定 N；本记录保留判据，避免重复提议统一）
> **来源**：阶段二·①（判定面与取数收敛）执行会话裁定，2026-09-13

---

## 0. 事实：两处候选输入长什么样

| | 断言管理编辑器（条目路径 / 断言目标） | 编排页画布（策略路径 target / expression） |
|---|---|---|
| 组件 | `components/composer/JsonPathInput.vue` | `components/composer/FieldForm.vue` 的扁平候选列表（`.cand-btn` + `.cand-list`，裸 `<input>` + 一个 `▾` 按钮） |
| 调用点 | `views/AssertionRegistryEditor.vue` 的两处 `JsonPathInput`（新建条目 `:candidates="pathCandidates"`、新建断言 `:candidates="targetCandidates"`） | `CaseComposerCanvas.vue` 的 `strategyCandidates(s)` 按字段名映射，经 `StrategyForm` → `FieldForm` 的 `candidates` prop 传入 |
| 候选内容 | **只有契约声明面**（`pathCandidates` = 该步可注入面；`targetCandidates` = 契约 `assertable` 面） | **声明面 ∪ 用户粘贴的响应样本**（`currentAssertable ∪ samplePaths`） |
| 交互 | **分层**：输入即提示「当前这一层还有哪些段」，点选叶子补全整条路径、点选容器补全并留一个 `.` 继续下钻；↑↓ 移动、Enter 采纳、Esc 关闭；每行标注「叶子 / 容器」与字段状态 | **扁平**：一次列出全部候选，点一下填整条 |

## 1. 裁定：**不统一**

统一两处候选 UI 的提案**已评估并否决**：

- `JsonPathInput` 是**分层选择器**（按层提示 + 下钻 + 容器补 `.` + 方向键 / Enter / Esc +
  状态标注）；扁平候选列表是**一次列全、点一下即填**，没有「层」的概念。
- **统一到扁平** ⇒ **删掉按层提示这个功能** —— 契约声明树是**分层**的，编辑器选条目路径
  时「先点容器、再点下一层」正是它的用法；用一次性长列表替代，长目录下不可用。
- **统一到分层** ⇒ 要在画布的策略表单里换上一个更重的输入组件，而那里只需要「从列表里
  点一个」（候选已由后端声明面与响应样本算好，用户不需要在树上探索）。
- 两者**服务的对象不同**（编辑器 = 条目路径，需要在契约树上探索；画布 = 策略 target /
  expression，候选已是算好的扁平集合），保持一致的成本高于收益。

⇒ 差异是**有意的**，不是遗漏；两侧候选**内容**的差异（画布多一份「用户粘贴的响应样本」）
另见 `docs/PLATFORM-SCENARIO-COMPOSER-API.md` §10.5 的裁定 M。

## 2. 前提更正（读者须知）

裁定记录里把扁平那一侧写作 `el-autocomplete`。**本仓前端没有 `el-autocomplete`**
（全仓 0 处组件用法；只有登录 / 注册页 `input` 上的 HTML `autocomplete` 属性）。扁平的
载体是 `FieldForm.vue` 的 `.cand-btn` / `.cand-list`。裁定的实质（分层 vs 扁平）不受
影响，但**按组件名去检索会落空**，故在此写明。

## 3. 何时重开

1. 候选输入被要求支持**第三种**形态（例如「模糊搜索 + 分层下钻」的混合体）；
2. `JsonPathInput` 被替换或并入通用组件库（届时「差异成本」的基线变了）；
3. **画布侧也要求按层探索**契约声明树（届时这处差异才不再值得维持）；
4. 候选 UI 出现**用户可复现的误操作**，且复盘指向「两处交互不一致」。
