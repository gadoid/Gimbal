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
| 编排器运行面板 `components/composer/RunPanelHost.vue` | `onMounted(() => surface.ensure())` |
| 断言管理编辑器 `views/AssertionRegistryEditor.vue` | `:225` |
| 编排器 `views/CaseComposer.vue` | `:522` |
| 数据页 `views/CaseDataSetsList.vue` | `:140` |

后两个（数据页、断言管理编辑器）**不渲染画布**，只显示条目列表与数据集 —— 它们照样会把**该场景每个步骤的**端点契约全量拉一遍。

**成本上界（只对成功路径成立）**：`ensureEndpointFull` 对**未过期**的缓存条目与**在飞**端点都直接返回（`useEndpointFull.ts` 的 `ensureEndpointFull`：TTL 命中 / 在飞收敛各一条早返回），所以**成功取回的端点每个 `FULL_TTL_MS`（300 s）窗口内至多 1 次 `/full`**；N 个不同端点 ⇒ 每窗口至多 N 次。步骤面变化（`stepEndpointIds` 变化）时只补取**新出现**的端点（已缓存且未过期的照旧早返回）。**这个上界只约束自发取数**：用户手动重试与降级退避走 `force`，会跳过 TTL 与负缓存两道闸（故它们各自的次数另有上界，不计入本行的 N 次）。

**失败路径**不在这个上界内：失败的端点写负缓存 `failedAt`，只在 `FAILED_RETRY_MS = 10_000` 窗口内拦截（`useEndpointFull.ts` 的 `FAILED_RETRY_MS` / `ensureEndpointFull`）—— 窗口过后允许重发；自发重发由 `ensure()` 触发，**降级后另有 `useInjectableSurface` 的有界退避自动重试（`[10s, 30s, 60s]` 三档，试满即停）**与三处宿主的手动重试入口兜住（见 `no-retry-after-degradation.md` 的修复记录）。即「每窗口 ≤1 次」是成功端点的性质，不是端点的性质。

---

## 1. 为什么接受

1. **不预取就没有候选面**：v3.1 §2.1 的放宽（carry / 未落 body 的 collapse 字段可寻址）服务的就是「给**尚无条目的步骤**挑字段」这条路径；若按「被引用才取」，新条目的候选集永远停在 body 面 —— 那正是这条放宽要消灭的静默缺陷。
2. **代价是确定且有界的**：N 次请求 / 会话、可被负缓存与在飞收敛压住（plate 故障时不会逐渲染重发 —— 这是 F 项要解决的形态），不会随渲染次数增长。
3. **不需要新增协议**：不需要「哪些步骤真的需要契约」的额外声明面，也不需要前端猜。

---

## 2. 残余风险与读者应当怎么做

**残余风险**：

- **对 plate 的额外压力**：打开一个步骤数很多、端点各异的场景，仅**浏览**数据页也会触发全量 `/full`（每个 300 s 窗口、每端点一次）。轻量页的本意是「只看数据」，现在也付出契约取数成本。
- **plate 故障期的负缓存窗口**：失败会写 `failedAt`（`useEndpointFull.ts` 的 `FAILED_RETRY_MS` = 10 s），窗口内不发；窗口过后由 `ensure()`（挂载 / 步骤面变化）或**降级后的有界退避**（`[10s, 30s, 60s]` 三档）重试（见 `no-retry-after-degradation.md` 的修复记录）。
- **预期落空不是错误**：取到的 `/full` 若信封形状不对，`sanitizeEndpointFull`（出口）+ 缓存入口各消毒一次（`useEndpointFull.ts:24-30`），失败按 `undefined` 处理，页面不报错 —— 即「没取到」与「端点真没声明」在 UI 上可能同观感（后端侧有 `None` vs `[]` 的区分，见 `endpoint_declarations.py:222-232`）。

**读者应当这么做**：

1. 看到轻量页发 `/full` **不是 bug**，先读 `useInjectableSurface.ts:64-83` 的取/分离注释再判断要不要改。
2. 想减少请求，**不要**把 `stepEndpointIds` 缩成「被引用的步骤」—— 那会重新引入「新条目候选集停在 body 面」的静默缺陷（注释 `:119-125` 专门警告过同类简化）。可行的方向是页面级：让**不需要候选面的页面**不挂 `useInjectableSurface`（或让 `ensure()` 可选）。
3. 压测 / 容量评估时按「**每 `FULL_TTL_MS`（300 s）窗口、每不同端点 1 次** `/full`」（外加降级期的有界退避）估算，不要按「每次判定 1 次」。

---

## 3. 优先级：P2

按 README：**结构性 / 可维护性问题，不影响功能**。

- 没有非预期业务结果，没有丢数据；成本上界明确（每 300 s 窗口、每端点 1 次，N 个端点 ⇒ 每窗口 N 次）；
- 它是**为了修复静默缺陷而付的代价**（取/分离 + 候选面完整），不是疏忽；
- spec §6.3 把它列在「已接受局限」而非「阶段二待修」中。

---

## 4. 何时重开

1. **plate 侧观测到 `/full` 压力**（QPS / 超时率）与轻量页的浏览行为相关；
2. **新增第五个宿主**：每加一个挂载点就多一类页面付出全量预取成本 —— 加之前先按本记录 §1 的收益核对一遍；
3. **H 落点裁定**（spec §7）：若改「后端算、前端消费」，前端可能不再需要自己取全量 `/full`；
4. **`ensure()` 的触发时机变化**（例如引入定时器 / 可见性触发），会影响上界假设 —— 已发生过一次（阶段二 T8 的降级退避定时器），上界已按上文重核。
