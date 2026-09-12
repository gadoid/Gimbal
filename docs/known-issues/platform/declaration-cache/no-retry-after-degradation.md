# 降级失败后没有重试通道（会话内停留从严姿态）

> **模块**：`gimbal-platform/frontend`（`useEndpointFull` 失败负缓存 × `useInjectableSurface.ensure` 触发时机）
> **状态**：已知未修复
> **来源**：架构收敛执行会话自查（非 spec 条目）

---

## 0. 机制

契约取数失败会写一个**有窗口的负缓存**，窗口内不再发起：

```ts
// src/gimbal-platform/frontend/src/composables/useEndpointFull.ts:46
export const FAILED_RETRY_MS = 10_000
// :64-67  窗口内直接返回 undefined
// :77-80  catch 里 failedAt.set(endpointId, Date.now())
```

而状态是**持久**的（只有成功才清）：

```ts
// :74  成功：failedAt.delete(endpointId)
// :92-96  endpointFullState：已缓存 → ''；failedAt 命中 → 'failed'；否则 'loading'
```

判定面把 `'failed'` 读作**已落定的答案**（不是「在途」），于是姿态**从严**：

```ts
// src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts:103-104
const pending = computed(() =>
  neededEndpoints.value.some((eid) => endpointFullState(eid) === 'loading'))
// :159（同文件）suspended = pending && 全部 issue 都是 path-unresolvable
```

即：取数失败 ⇒ `pending === false` ⇒ `path-unresolvable` 归 `intrinsic`（**真死**）⇒ 进入 `deadIds`（`:169-172`）。

**而重试只有一个触发口**：`ensure()`（唯一的取数副作用），它由两处调用：

```ts
// :83
watch(stepEndpointIds, () => ensure(), { immediate: false })
```

以及各宿主的挂载钩子 —— `components/composer/RunPanelHost.vue:102`、`views/AssertionRegistryEditor.vue:225`、`views/CaseComposer.vue:522`、`views/CaseDataSetsList.vue:140`。

**没有任何定时器、可见性回调、或读路径触发的重试** —— 后者是**故意**的：读/取分离（裁定 C18）就是为了让渲染期零请求（IS-7），所以读函数不许内部取数。

---

## 1. 后果

**触发条件**：用户进入页面（挂载）时 plate 抖动一下（超时 / 5xx / 信封坏）⇒ 该端点的负缓存被写下。

**影响**：这一次会话里，判定面**一直**按「声明面不可得」的姿态工作 —— 锚在契约声明上的条目被算作 `intrinsic` 死条目：

- 运行面板里**不可勾选**（`deadIds` 是禁选的唯一派生，`:43-47`、`:169-172`）；
- 数据页 / 断言管理里标成「悬空」。

**恢复路径**（只有两条，且都不是自动的）：

1. **步骤面变化**：`stepEndpointIds` 变化（增删步骤 / 改某步的 `endpoint_id`）⇒ `watch` 触发 `ensure()`；
2. **重新挂载**：路由切走再回来 / 刷新页面 ⇒ 宿主 `onMounted` 触发 `ensure()`。

**注意一条不成立的直觉**：**修改条目不会重试**。`neededEndpoints`（条目引用面）只影响 `pending` 的计算，不触发 `ensure()`（`ensure` 的输入是 `stepEndpointIds`）—— 用户改了条目、甚至新增了条目，取数**不会**重来。请勿按「改一下条目就好了」去指导用户。

**另有一条时间边界**：负缓存窗口是 10s，且**只在 `ensureEndpointFull` 内部判定**。所以即使窗口已过，没有新的 `ensure()` 也**不会**重发；反之在窗口内即使调 `ensure()` 也**不会**重发。

---

## 2. 优先级：P1

按 README：**触发条件明确、可控、规避成本低**。

- 触发条件明确：**挂载时刻**的 plate 抖动（一次失败即锁一整个会话）；
- 可控 + 规避成本低：刷新页面 / 切走回来即可恢复，且失败是「从严」而非「从宽」—— 不会错误执行，只会少给候选、多标悬空；
- 不是 P0：不产生非预期的业务结果（不会静默注入错值），最坏是用户**看到假悬空**、无法选择本可选中的条目；
- 若把「条目被误标悬空导致漏跑注入」视为业务结果（用户以为跑了、其实条目被 skip 且他只当成 UI 灰显），**应改判 P0** —— 该衔接见 `judge-degraded-observability.md` 的 `entriesSkippedWhileDegraded`（那条遥测正是为这种「降级造成跳过」准备的）。

---

## 3. 读者应当怎么做

1. 遇到「刚打开页面时条目一片悬空、刷新后好了」⇒ 按本条判据解释：挂载时刻 plate 抖动 + 无重试通道；
2. 需要恢复：**刷新页面**或**切走再回来**（不要等，也不会自己好）；
3. 若要收口（**方向备查，不是结论**）：给 `ensure()` 加一次「失败后延时重试」或把 `endpointFullState` 的 `'failed'` 在窗口到期后回落为 `'loading'`（使 `pending` 重新为真、并触发一次取数）—— 两条都要小心 **IS-7**（渲染期零请求）与负缓存防抖的既有约定，不要在读路径里发请求。

---

## 4. 何时重开

1. **plate 抖动期的用户反馈**集中在「条目灰显 / 不可勾选」；
2. **H 落点裁定**（spec §7）：若判定面改为后端算、前端消费，本条的触发时机模型整体改变；
3. **`ensure()` 触发时机调整**（新增定时器 / 可见性触发 / 步骤面之外的依赖）—— 上界与恢复路径都要重核；
4. **IS-7（渲染期零请求）约定被修订** —— 那会给「读路径重试」打开口子。
