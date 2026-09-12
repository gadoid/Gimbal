# 已接受局限：轻量页也预取「每个步骤的 `/full`」

> **模块**：`gimbal-platform/frontend`（`useInjectableSurface.ensure` + `useEndpointFull`）
> **状态**：**已接受**（不是待修缺陷；本记录说明边界与残余风险）
> **来源**：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §6.3（「轻量页新增 `/full` 取数」）

---

## 0. 局限是什么

判定面把所有取数收成一个显式副作用 `ensure()`，而它的覆盖面**故意**是「**全部**带 `endpoint_id` 的步骤」，不是「被条目引用到的步骤」：

```ts
// frontend/src/composables/useInjectableSurface.ts:72-83
const stepEndpointIds = computed<string[]>(() => {
  const out = new Set<string>()
  for (let si = 0; si < steps.value.length; si++) { … out.add(eid) … }
  return [...out]
})
function ensure(): void {
  for (const eid of stepEndpointIds.value) void ensureEndpointFull(eid)
}
watch(stepEndpointIds, () => ensure(), { immediate: false })
```

理由写在同文件的注释里（`:68-71`）：**读端不取数**（渲染期零请求，IS-7 钉住），所以取数必须**一次取全** —— 否则「给新条目挑契约字段」这条路径（候选/取态要问**任意** `si`，含**无条目引用**的 `si`）永远没有数据。注意 `pending`（在途面）用的是另一个更窄的集合（`neededEndpoints`，`:90-100`，只算被条目引用到的步骤）—— 即**多取数**与**少悬置**是两件事，前者被有意放宽。

**「轻量页」的含义**：宿主在挂载时调 `ensure()`，于是**任何**挂载判定面的页面都会预取。当前四个宿主：

| 宿主 | 挂载点 |
|---|---|
| 编排器运行面板 `components/composer/RunPanelHost.vue` | `:102` `onMounted(() => surface.ensure())` |
| 断言管理编辑器 `views/AssertionRegistryEditor.vue` | `:225` |
| 编排器 `views/CaseComposer.vue` | `:522` |
| 数据页 `views/CaseDataSetsList.vue` | `:140` |

后两个（数据页、断言管理编辑器）**不渲染画布**，只显示条目列表与数据集 —— 它们照样会把**该场景每个步骤的**端点契约全量拉一遍。

**成本上界（只对成功路径成立）**：`ensureEndpointFull` 对**已缓存**端点与**在飞**端点都直接返回（`useEndpointFull.ts:61-69`），所以**成功取回的端点在一次页面会话内至多 1 次 `/full`**；N 个不同端点 ⇒ 至多 N 次。步骤面变化（`stepEndpointIds` 变化）时只补取**新出现**的端点。

**失败路径**不在这个上界内：失败的端点写负缓存 `failedAt`，只在 `FAILED_RETRY_MS = 10_000` 窗口内拦截（`useEndpointFull.ts:46`、`:64-67`）—— 窗口过后**再次调用 `ensure()`（重新挂载 / 步骤面变化）会重发**。即「每会话 ≤1 次」是成功端点的性质，不是端点的性质；失败端点既可能重发、也可能在无人触发 `ensure()` 时一直不重试（两面同见 `no-retry-after-degradation.md`）。

---

## 1. 为什么接受

1. **不预取就没有候选面**：v3.1 §2.1 的放宽（carry / 未落 body 的 collapse 字段可寻址）服务的就是「给**尚无条目的步骤**挑字段」这条路径；若按「被引用才取」，新条目的候选集永远停在 body 面 —— 那正是这条放宽要消灭的静默缺陷。
2. **代价是确定且有界的**：N 次请求 / 会话、可被负缓存与在飞收敛压住（plate 故障时不会逐渲染重发 —— 这是 F 项要解决的形态），不会随渲染次数增长。
3. **不需要新增协议**：不需要「哪些步骤真的需要契约」的额外声明面，也不需要前端猜。

---

## 2. 残余风险与读者应当怎么做

**残余风险**：

- **对 plate 的额外压力**：打开一个步骤数很多、端点各异的场景，仅**浏览**数据页也会触发全量 `/full`（每端点一次）。轻量页的本意是「只看数据」，现在也付出契约取数成本。
- **plate 故障期的负缓存窗口**：失败会写 `failedAt`（`useEndpointFull.ts:77-80`），窗口 `FAILED_RETRY_MS = 10_000` 内不再发起；窗口过后**只有再次调用 `ensure()` 才会重试** —— 而 `ensure()` 只在挂载 / 步骤面变化时触发（见 `no-retry-after-degradation.md`）。
- **预期落空不是错误**：取到的 `/full` 若信封形状不对，`sanitizeEndpointFull`（出口）+ 缓存入口各消毒一次（`useEndpointFull.ts:24-30`），失败按 `undefined` 处理，页面不报错 —— 即「没取到」与「端点真没声明」在 UI 上可能同观感（后端侧有 `None` vs `[]` 的区分，见 `endpoint_declarations.py:222-232`）。

**读者应当这么做**：

1. 看到轻量页发 `/full` **不是 bug**，先读 `useInjectableSurface.ts:64-83` 的取/分离注释再判断要不要改。
2. 想减少请求，**不要**把 `stepEndpointIds` 缩成「被引用的步骤」—— 那会重新引入「新条目候选集停在 body 面」的静默缺陷（注释 `:119-125` 专门警告过同类简化）。可行的方向是页面级：让**不需要候选面的页面**不挂 `useInjectableSurface`（或让 `ensure()` 可选）。
3. 压测 / 容量评估时按「每会话每不同端点 1 次 `/full`」估算，不要按「每次判定 1 次」。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 没有非预期业务结果，没有丢数据；成本上界明确（N 次 / 会话）；
- 它是**为了修复静默缺陷而付的代价**（取/分离 + 候选面完整），不是疏忽；
- spec §6.3 把它列在「已接受局限」而非「阶段二待修」中。

---

## 4. 何时重开

1. **plate 侧观测到 `/full` 压力**（QPS / 超时率）与轻量页的浏览行为相关；
2. **新增第五个宿主**：每加一个挂载点就多一类页面付出全量预取成本 —— 加之前先按本记录 §1 的收益核对一遍；
3. **H 落点裁定**（spec §7）：若改「后端算、前端消费」，前端可能不再需要自己取全量 `/full`；
4. **`ensure()` 的触发时机变化**（例如引入定时器 / 可见性触发），会影响上界假设。
