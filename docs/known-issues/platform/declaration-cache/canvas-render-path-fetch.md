# 画布在渲染期取数（读 / 取分离只落到判定面）

> **模块**：`gimbal-platform/frontend`（`CaseComposerCanvas.vue` × `useEndpointFull` 的读 / 取分离约定）
> **状态**：已知未修复（**阶段二**）
> **来源**：架构收敛终稿复核（controller 裁定：画布本体本波不动，记录在案）

---

## 0. 机制

`useEndpointFull` 的消费方约定是**读 / 取分离**（裁定 C18）：读函数是纯缓存读
（`getEndpointFull` / `endpointFullState`），取数只由宿主显式调 `ensureEndpointFull(eid)`：

```ts
// src/gimbal-platform/frontend/src/composables/useEndpointFull.ts:32-43（约定）
// 「判定面的读函数不得内部取数 …… 判定面渲染期零请求（IS-7）就是靠这条纪律钉住的」
```

判定面照此实现，并由测试钉住：

```ts
// src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts:64-71  读 / 取分离
// src/gimbal-platform/frontend/src/composables/__tests__/useInjectableSurface.test.ts:143-170  IS-7
```

**画布没有**：两个 computed 仍在内部取数 ——

```ts
// src/components/composer/CaseComposerCanvas.vue:635-640
function stepDecls(step: StepView | undefined) {
  const eid = step?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)          // ← 渲染期发请求
  return getEndpointFull(eid)?.request?.declarations
}

// src/components/composer/CaseComposerCanvas.vue:1591-1596
const currentFull = computed<EndpointFullView | undefined>(() => {
  const eid = currentStep.value?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)          // ← 渲染期发请求
  return getEndpointFull(eid)
})
```

消费面都是渲染期读：`stepDecls` 被 `requestNodes`（`:650-653`，经 `buildTree`）、
`fieldSearchCorpus`（`:657-658`）、`requestExtras`（`:661-662`）等 computed 消费，
并被 `fieldBindings`（`:644-646`）直接带进模板（`:170`、`:454`）；`currentFull` 被
`currentAssertable`（`:1609-1611`）、`currentRespSpecs`（`:1629-1644`）、
`currentReqSchema`（`:1647-1649`）等 computed 消费。

对照：同一文件里的 `currentFullState`（`:1586-1588`）走的是纯读 `endpointFullState`，
**不取数** —— 即画布内部两种写法并存。

## 1. 后果

**不会**自维持成请求风暴：`ensureEndpointFull` 命中缓存 / 负缓存窗口内 / 在飞时直接返回
（`src/composables/useEndpointFull.ts:67-90`），失败写 10s 负缓存
（`FAILED_RETRY_MS`，`:46`）：

```ts
// useEndpointFull.ts:68-75
const cached = fullByEndpoint.get(endpointId)
if (cached) return Promise.resolve(cached)
const at = failedAt.get(endpointId)
if (at !== undefined && Date.now() - at < FAILED_RETRY_MS) return Promise.resolve(undefined)
const pending = inFlight.get(endpointId)
if (pending) return pending
```

⇒ 每端点每会话最多一次成功请求；失败端点每 10s 窗口最多一次。故这是**约定不一致 +
渲染期 I/O**，不是可观测故障。

**真正的代价**有两条：

1. **约定半真**：「读函数不得内部取数」这条纪律**只在判定面成立**。按旧形状新写消费方
   时，画布是两个现成反例 —— 只读约定会得出错误结论（`useEndpointFull.ts:38-43` 已把
   落实范围写明并指向本条）。
2. **取数时机由渲染决定**：`platform/declaration-cache/no-retry-after-degradation.md`
   的「挂载即失败 ⇒ 一整个会话从严」在画布上**不适用** —— 画布只要重新渲染就会在负缓存
   窗口过后再试一次。两条路径对同一个失败端点的重试行为因此不同。

## 2. 优先级：P2

按 README：**结构性 / 风格性 / 可维护性问题，不影响功能**。

- 不产生非预期业务结果：画布渲染本就需要声明面，请求由会话缓存 + 在飞收敛 + 负缓存兜底；
- 不是 P1：触发条件是**每次渲染**（不是某种特定用户操作），但后果有界（§1），
  且「规避成本低」不成立 —— 收口要动画布：`stepDecls` / `currentFull` 的消费面几乎全是
  渲染期读，改成纯读需要给画布补一个显式的取数时机；
- 不是 P0：不静默产生错误结果，最坏是多一次有界的网络请求。

**已裁定**：画布早于本次架构收敛、不在收敛计划的文件清单内 ⇒ 本波**不改画布**，只把
约定注释的范围写明并登记本条（阶段二继承）。

## 3. 读者应当怎么做

1. 遇到「画布为什么打开就打 plate `/full`」⇒ 按本条解释：两个 computed 内部
   `ensureEndpointFull`，不是渲染期读缓存；
2. **不要**据此推翻判定面的读 / 取分离约定：那条纪律的适用面是判定面，画布是已知例外
   （范围已写进 `useEndpointFull.ts:38-43`）；
3. 若要收口（**方向备查，不是结论**）：把 `stepDecls` / `currentFull` 改为纯读 +
   由画布的挂载 / 步骤面变化显式调 `ensureEndpointFull`（与
   `useInjectableSurface.ensure()` 同款时机），并补一条与 IS-7 同形的
   「画布渲染期零请求」用例。

## 4. 何时重开

1. **阶段二**（判定面单一定义 / `/full` 取数所有权）落到画布，或画布进入任一收敛计划的
   文件清单；
2. 画布出现**可观测**的请求量问题（同一端点重复取数、渲染抖动引发请求）；
3. `useEndpointFull` 的负缓存窗口 / 在飞收敛语义被改动 —— §1 的「有界」结论要重核；
4. 「读函数不得取数」被提升为全仓 lint / 测试约束（届时本文件的 `stepDecls` /
   `currentFull` 会直接变红）。
