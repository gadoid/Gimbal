# 阶段二待修：`normalizeRegistry` 把「读侧容忍」写回了服务端（E）

> **模块**：`gimbal-platform/frontend`（断言注册表水化与保存）
> **状态**：已知未修复（**待裁定**，见 §3）
> **来源**：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §6.3 / §7（E）
> **适用范围**：`assertion_registry` 场景级节的四个水化入口 → 任意保存路径。

---

## 0. 现状：同一份数据，两个方向

`normalizeRegistry` 存在的理由是**渲染防御**——`assertion_registry` 来自服务端 `/draft`，是不可信 JSON：

- V2 之前的场景**无** `assertion_registry` 键，后端 pydantic default 补成 `{}`（truthy、无 `entries`），`?? { entries: [] }` 兜不住 ⇒ 直灌会在 `registry.entries.length` 崩渲染；
- 条目里 `junk` / `null` / `7` / `[]` 之类非对象值，模板渲染 `e.id` 先于任何判定就 TypeError；
- `asserts` 缺键或非数组，编辑器详情 `selected.asserts.length` / `v-for` 崩渲染。

（以上三条是 `frontend/src/utils/assertion-registry.ts:107-117` 的 docstring 原文口径。）

它的实现做两件事（`frontend/src/utils/assertion-registry.ts:118-133`）：

```ts
if (typeof e !== 'object' || e === null || Array.isArray(e)) continue     // ① 丢弃非对象条目
entries.push(Array.isArray(entry.asserts) ? entry
  : { ...entry, asserts: [] })                                            // ② 补 asserts: []
```

**读侧容忍到这里为止都正确。问题在于它的返回值被当成了「当前注册表」继续往下走。**

---

## 1. 缺陷：容忍面被当成数据面，原样 PUT 回去

水化的四个入口都是**同一个形状**——把归一结果赋给**可编辑的** `registry.value`：

| 入口 | 位置 |
|---|---|
| 编排器运行面板 | `frontend/src/components/composer/RunPanelHost.vue:128` |
| 断言管理编辑器 | `frontend/src/views/AssertionRegistryEditor.vue:371` |
| 编排器（加载 / 水化重试） | `frontend/src/views/CaseComposer.vue:781`、`:872` |
| 数据页 | `frontend/src/views/CaseDataSetsList.vue:172` |

而 `registry.value` 就是**写侧的载荷**：

- `frontend/src/views/AssertionRegistryEditor.vue:420`
  `await updateScenario(scenarioId, { ...draft.value, assertion_registry: registry.value })`
- `frontend/src/views/CaseComposer.vue:896`（保存草稿的 `ScenarioDraft.assertion_registry`）
- `frontend/src/views/CaseComposer.vue:489`（写进共享 draft store，任何从该 store 保存的路径同样带它）

### 触发条件

1. 存量 `assertion_registry.entries` 里存在**至少一个非对象值**（`null` / 数字 / 字符串 / 数组）。来源：手改 JSON、更早的写入方、或任何非本前端的写入路径；
2. 用户打开上述四个视图中的**任意一个**（水化即丢弃那些条目）；
3. 用户**保存**（编辑器保存 / 编排器保存 / 自动保存 / 从共享 draft store 的任何落盘）。

### 影响

服务端那份注册表里的非对象条目**被永久删除**——不是报错、不是提示，是一次「静默写回」。用户下次打开时数据已经不在，且没有任何痕迹说明它何时消失。

- 区分：`asserts: []` 的补键是**加法**（不改用户语义），不属此列；
- 真正丢数据的是 ①：非对象条目**整条**消失。

这就是 README 对 P0 的定义（丢数据）——spec §6.3 因此写作「P0 候选」。

---

## 2. 优先级：P0（候选）

- **后果属于 P0 类**：静默丢用户数据，且丢在服务端（不是本地视图状态）。
- **触发面窄于典型 P0**：需要「存量数据里真的存在非对象条目」这一前提（正常 UI 写出的条目都是对象）。spec §6.3 因此写作「P0 候选」。
- 结论：**按后果定级 P0**；修法需要 §3 的职责拆分裁定，不能只改一行。

---

## 3. 待裁定

> 原文见 spec §7：**E `normalizeRegistry` 职责拆分** —— *读侧容忍（渲染防御）与写侧保真（不得静默删用户数据）如何分家。*

留给维护者的决策（**本记录不下结论**）：

1. **分家方式**：读侧继续容忍（渲染不崩），写侧在保存前**逐条比对**「归一前 vs 归一后」并在有差异时显式拦截/告警？还是写侧改为原样透传、只让渲染层消费归一结果？还是把丢弃的非对象条目**搬到一个显式的隔离键**（不删、不可渲染）？
2. **要不要告知用户**：静默丢弃 vs 保存前弹一次「有 N 条无法识别的条目，保存将丢弃」的显式确认；
3. **服务端是否也应有防线**：后端 `app/schemas/scenario_composer.py` 对 `assertion_registry` 的形状容忍到什么程度（现状见 `app/services/run_injection.entry_issues` 的容忍面：非 dict 的 `path` 判 `legacy-entry`，不是丢弃）。若后端落库前就能拒收/隔离这些值，前端这一侧的写回后果会被截断。

**相关的既有事实**（供裁定参考，不是结论）：

- 后端 `entry_issues`（`src/gimbal-platform/backend/app/services/run_injection.py:189-243`）对同一条数据的处置是「判 `legacy-entry` → skip + 告警」——**判死但保留数据**，与前端「丢弃并写回」不同向。两处容忍面「看齐」的说法目前只覆盖**判据形态**，不覆盖**数据去留**。
- `RegistryIssue` 已有的 `legacy-entry` 死因可以复用为「这条读不了」的用户可见信号（前端 `registryIssues`，`frontend/src/utils/assertion-registry.ts:63`）。

---

## 4. 何时重开

1. **用户反馈条目消失**：任何一次「我保存后条目不见了」的复盘；
2. **出现非 UI 写入方**：任何脚本 / 导入 / 迁移工具开始写 `assertion_registry`；
3. **H 落点裁定**（spec §7）：判定面收为单一定义那一轮，注册表的读/写职责必须一并定清；
4. **断言注册表加新字段**：新增字段时归一函数与写侧的耦合面会扩大（今仅 `entries` / `asserts` 两处）。
