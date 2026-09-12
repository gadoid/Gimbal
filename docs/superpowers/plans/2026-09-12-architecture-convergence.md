# 架构收敛(阶段一)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修掉可注入面 v3.1 引入的 9 条真缺陷,并把产生它们的两个结构成因收敛掉 —— ①判定面(纯函数)不再耦合网络 I/O 与渲染路径;②前端四处副本收成一个 surface composable、后端判定收口并复用既有 `TtlLruCache`。

**Architecture:** 前端新增 `useInjectableSurface` 作为唯一的判定消费面(记忆化 + 显式预取 + 死因分组),`useEndpointFull` 改 Vue 原生响应式(删手工版本号协议);后端判定改为「每步一次预计算可注入面 + 纯判定函数」,缓存复用 `TtlLruCache`(获 LRU 上界与 stale-while-error),判定取数改 3s 有界软取。

**Tech Stack:** Vue 3 + TS(vitest/@vue/test-utils)/ FastAPI + Pydantic + SQLAlchemy(pytest)。

**Spec:** `docs/superpowers/specs/2026-09-12-architecture-convergence-design.md`(权威)

## Global Constraints

- **分支**: `feat/dataset-driven-refactor`(勿在 master/main 上实施)。
- **plate/执行核零改动**: `src/gimbal-plate/**`、`export/gimbal.py`、`src/gimbal/**` **一行不动**(读它们以确认语义是允许且被要求的)。
- **永不提交/触碰**: `gimbal-tmp/`、`reports/test-report.html`、`probe_ui.js`、`src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_add_demo.py` 及 `endpoint/__init__.py` 的 3 行演示副本。
- **用户 WIP 文件**: `FieldActionMenu.vue` / `FieldForm.vue` —— 本计划**完全不碰**。
- **安全**: SUT 凭证不回显、不入库、不提交;绝不自动重登录。
- **git**: `git add` 点名文件,不用 `git add -A`;commit message 尾行 `Co-Authored-By: Claude Code <noreply@anthropic.com>`;**不 push**。
- **环境命令**(Bash 每次调用自带 `cd /d/Gimbal/Gimbal`;`python` = `D:\python\python.exe`,后端无 venv):
  - 后端单测 `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/<file> -v`
  - 前端单测 `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run <file>`;类型 `npm run typecheck`
- **全仓编码约定(本计划立规,spec §5)**: **禁止用真值合并有意义但 falsy 的值** —— `None` / `0` / `""` / `[]` / `False` 一律显式判别(`is None`、`len(x) == 0`),不得写 `x or default`。例外仅当"双方同为该类型缺省且一眼可辨等价",并须注释写明。
- **过程纪律(P8,沿用上一计划)**: 报告里凡「已修复 / 已覆盖 / 已对齐」,写之前先自己 grep 或跑一遍;声称某用例有判别力,给**证伪证据**(改坏 → 红 → 还原 + 哈希校验)。
- **四道门不得退步**: 后端全量(**513 passed**)、前端全量(**84 files / 796 tests**)、`vue-tsc` **0**、plate/执行核守卫 **CLEAN**(基 `fc6edb9`)。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `frontend/src/utils/declarations.ts` | 路径可用性**唯一定义** + 六个投影函数共用 | 改 |
| `frontend/src/composables/useEndpointFull.ts` | 会话级契约缓存:改 Vue 原生响应式 + 负缓存 | 改 |
| `frontend/src/composables/useInjectableSurface.ts` | **判定面的唯一消费面**(记忆化 / 预取 / 死因分组) | 新建 |
| `frontend/src/views/AssertionRegistryEditor.vue`、`CaseComposer.vue`、`CaseDataSetsList.vue`、`components/composer/RunPanelHost.vue` | 四处副本退场,只消费 composable | 改 |
| `frontend/src/components/composer/RunDialog.vue` | 停止自行掩空 deadIds(掩空决策上移到宿主) | 改 |
| `backend/app/services/query_view_cache.py` | `TtlLruCache` 载荷泛化(`rows` → `payload`) | 改 |
| `backend/app/services/query_view_runner.py` | 泛化的唯一既有消费者(机械跟随) | 改 |
| `backend/app/services/endpoint_declarations.py` | 改持 `TtlLruCache` + 旧值保留 + 投影缓存 + 告警老化 | 改 |
| `backend/app/services/run_injection.py` | 判定纯函数化(`injectable_universe` / `as_step_index`)+ 死代码清理 | 改 |
| `backend/app/services/run_dispatcher.py` | 原始索引基数、universe 预计算、降级可见、有界软取接线 | 改 |
| `backend/app/core/config.py` | 三个新设置(TTL 上界 / 回退窗 / 判定超时) | 改 |
| `docs/PLATFORM-SCENARIO-COMPOSER-API.md`、`docs/adr/0003-*.md`、`docs/known-issues/**`、v3.1 spec 头部 | 文档收敛 | 改/新建 |

---

### Task 1(S1): 边界消毒一次(`iterFlat` 唯一定义,修 A)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts`、`src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts`

**Interfaces:**
- Produces: `export function hasUsablePath(e: DeclarationEntryView | null | undefined): boolean`(判据 = `typeof e?.path === 'string' && e.path !== ''`);`iterFlat` 只吐**可用路径**的条目,但**仍遍历其 children**。

- [ ] **Step 1: 写失败测试**

在 `declarations.test.ts` 追加:

```ts
describe('路径可用性唯一定义(spec 架构收敛 §2.3)', () => {
  it('DP-1: 真值非字符串 path 不收录,且不抛;其 children 仍被遍历', () => {
    const decls = [
      { name: 'bad', path: 7 as any, children: [{ name: 'kid', path: '$.kid', required: false, description: '' }] },
      { name: 'empty', path: '' as any },
      { name: 'ok', path: '$.ok', required: false, description: '' },
    ] as any
    const flat = iterFlat(decls)
    expect(flat.map((e) => e.path)).toEqual(['$.kid', '$.ok'])   // bad 自身剔除,但其子保留
    expect(hasUsablePath({ path: 7 } as any)).toBe(false)
    expect(hasUsablePath({ path: '' } as any)).toBe(false)
    expect(hasUsablePath({ path: '$.a' } as any)).toBe(true)
    expect(hasUsablePath(undefined)).toBe(false)
  })

  it('DP-2: 六个投影函数共享该判据(畸形条目既不入目录也不崩)', () => {
    const decls = [{ name: 'bad', path: 7 as any }, { name: 'ok', path: '$.ok', required: false, description: '' }] as any
    expect([...catalogPaths(decls)]).toEqual(['$.ok'])
    expect(assertablePaths(decls.map((d: any) => ({ ...d, assertable: true })))).toEqual(['$.ok'])
    expect(carryPaths(decls)).toEqual([])
    expect(searchCorpus(decls).map((r) => r.path)).toEqual(['$.ok'])
  })
})
```

在 `AssertionRegistryEditor.test.ts` 追加(修 A 的消费面 —— 渲染期不再抛):

```ts
it('ARE-13: 契约含真值非字符串 path 的声明 → 编辑器不抛、正常渲染', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [{ name: 'bad', path: 7 }, { name: 'amount', path: '$.amount', state: 'form', required: true, description: '' }] },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG })
  await w.find('input').setValue('$.')          // 触发建议行渲染 → stateOf 逐条调用
  await flushPromises()
  expect(w.find('.are-editor').exists()).toBe(true)   // 未白屏
  w.unmount()
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/declarations.test.ts src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: FAIL —— `hasUsablePath` 未导出;ARE-13 抛 `TypeError: e.path.replace is not a function`。

- [ ] **Step 3: 实现**

`utils/declarations.ts` —— 在 `iterFlat` 之前插入唯一定义,并改 `iterFlat`:

```ts
/** 路径可用性**唯一定义**(spec 架构收敛 §2.3):`/full` 是不可信来源,
 *  真值但非字符串的 path(如 `path: 7`)会让下游 `toTemplatePath` 抛
 *  `path.replace is not a function` —— 在**边界**判一次,消费方不再各自守卫
 *  (与后端 `field_state_resolution.composite_states` 的「守卫一次、下游继承」同款)。 */
export function hasUsablePath(e: DeclarationEntryView | null | undefined): boolean {
  return typeof (e as { path?: unknown } | null | undefined)?.path === 'string'
    && (e as unknown as { path: string }).path !== ''
}

/** children 树先序平铺(**只吐可用路径的条目**);防御:非数组/非对象跳过。
 *  ⚠ 路径不可用的条目**自身剔除但仍遍历其 children** —— 容器条目缺 path 时
 *  若整棵剪掉,其子孙会从树里消失(那是语义丢失,不是消毒)。 */
export function iterFlat(
  decls: DeclarationEntryView[] | undefined | null,
): DeclarationEntryView[] {
  const out: DeclarationEntryView[] = []
  const walk = (entries: DeclarationEntryView[] | undefined) => {
    for (const e of entries ?? []) {
      if (!e || typeof e !== 'object') continue
      if (hasUsablePath(e)) out.push(e)
      walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}
```

随后把六个投影函数里各自的 path 守卫**替换为对 `hasUsablePath` 的调用**(或直接删除 —— 若其数据源已是 `iterFlat` 的输出):
- `catalogPaths`:`.filter((p): p is string => typeof p === 'string' && p !== '')` → 因迭代源已是 `iterFlat`,`catalogPaths` 变为 `new Set(iterFlat(decls).map((e) => e.path))`;
- `assertablePaths`:`.filter((e) => e.assertable && typeof e.path === 'string' && e.path !== '')` → `.filter((e) => e.assertable)`(迭代源已消毒);
- `carryPaths` / `searchCorpus` / `cascadeIncrements` 的 `locate`/`walk`:这些函数**自带递归**(需要祖先链语义),把它们的 `!e.path` / `!e || typeof e !== 'object' || !e.path` 判据统一改为 `!hasUsablePath(e)`(保留各自递归结构,只统一**判据**)。

`views/AssertionRegistryEditor.vue` 的 `stateOfPendingPath`:把手写的 `if (!e.path) continue` 改为消费消毒后的 `iterFlat`(其输出已保证可用路径),或显式 `if (!hasUsablePath(e)) continue` —— 二者取一,**不得**再直接 `toTemplatePath(e.path)` 而不判。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上 + `npx vitest run src/utils/__tests__/assertion-registry.test.ts src/views/__tests__/CaseDataSetsList.test.ts`
Expected: PASS(新增 DP-1/DP-2/ARE-13;既有全绿)。
`npm run typecheck` → 0。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/utils/declarations.ts src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue && git commit -m "fix(declarations): 路径可用性收敛为唯一定义 — 真值非字符串 path 不再崩渲染

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2(S2): `useEndpointFull` 改 Vue 原生响应式 + 负缓存(修 F/L)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/composables/useEndpointFull.ts`
- Modify(删除手工依赖语句): `useFieldDescriptions.ts`、`AssertionRegistryEditor.vue`、`CaseComposer.vue`、`CaseDataSetsList.vue`、`RunPanelHost.vue`、`CaseComposerCanvas.vue`
- Test: `src/gimbal-platform/frontend/src/composables/__tests__/useEndpointFull.test.ts`

**Interfaces:**
- Produces: `ensureEndpointFull` / `getEndpointFull` / `endpointFullState` / `requestDeclarationsOf`(**签名不变**;失败端点带负缓存);**`endpointFullVersion` 退役删除**。
- 负缓存语义:失败后 `FAILED_RETRY_MS`(10s)内不再发起;窗口过后允许重试。

- [ ] **Step 1: 写失败测试**(改写 `useEndpointFull.test.ts`:删掉对 `endpointFullVersion` 的断言,换成响应式与负缓存)

```ts
  it('EF-6(新): 响应式 — computed 读 getEndpointFull 会在回填后自动重算', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue(FULL)
    const seen = computed(() => getEndpointFull('ep-r') === undefined ? 'none' : 'have')
    expect(seen.value).toBe('none')
    await ensureEndpointFull('ep-r')
    expect(seen.value).toBe('have')          // 无需任何手工 bump
  })

  it('EF-7(新): 失败负缓存 — 窗口内不重发,窗口过后允许重试', async () => {
    const spy = vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('boom'))
    expect(await ensureEndpointFull('ep-f')).toBeUndefined()
    expect(await ensureEndpointFull('ep-f')).toBeUndefined()
    expect(spy).toHaveBeenCalledTimes(1)                     // 窗口内不重发
    vi.setSystemTime(Date.now() + 11_000)                    // 越过 FAILED_RETRY_MS
    await ensureEndpointFull('ep-f')
    expect(spy).toHaveBeenCalledTimes(2)                     // 窗口后允许重试
  })
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/composables/__tests__/useEndpointFull.test.ts`
Expected: FAIL —— `getEndpointFull` 的响应式不成立(EF-6 停在 `'none'`)、EF-7 的调用次数为 2(无负缓存)。

- [ ] **Step 3: 实现**

`useEndpointFull.ts`:

```ts
import { reactive } from 'vue'
// …(其余 import 不变)

/** 失败重试窗口(ms):窗口内不再发起,避免 plate 故障时渲染路径反复重发(spec §1.1 F)。 */
export const FAILED_RETRY_MS = 10_000

/** 会话级缓存 —— **reactive** 容器:Vue 原生跟踪 Map.get / Map.has / Set.has,
 *  消费方读缓存即建立依赖,不再需要任何 `void endpointFullVersion.value` 手工声明
 *  (旧的版本号协议在本任务退役)。 */
const fullByEndpoint = reactive(new Map<string, EndpointFullView>())
const inFlight = new Map<string, Promise<EndpointFullView | undefined>>()
/** eid → 失败时刻(ms);负缓存,窗口内不重发 */
const failedAt = reactive(new Map<string, number>())

export function ensureEndpointFull(endpointId: string): Promise<EndpointFullView | undefined> {
  const cached = fullByEndpoint.get(endpointId)
  if (cached) return Promise.resolve(cached)
  const at = failedAt.get(endpointId)
  if (at !== undefined && Date.now() - at < FAILED_RETRY_MS) {
    return Promise.resolve(undefined)          // 负缓存命中:窗口内不重发
  }
  const pending = inFlight.get(endpointId)
  if (pending) return pending
  const p = getFullEndpoint(endpointId)
    .then((full) => {
      fullByEndpoint.set(endpointId, full)
      failedAt.delete(endpointId)
      return full
    })
    .catch(() => {
      failedAt.set(endpointId, Date.now())
      return undefined
    })
    .finally(() => inFlight.delete(endpointId))
  inFlight.set(endpointId, p)
  return p
}

export function getEndpointFull(endpointId: string): EndpointFullView | undefined {
  return fullByEndpoint.get(endpointId)
}

export function endpointFullState(endpointId: string | undefined): 'loading' | 'failed' | '' {
  if (!endpointId) return ''
  if (fullByEndpoint.has(endpointId)) return ''
  return failedAt.has(endpointId) ? 'failed' : 'loading'
}
```

`_resetEndpointFullCacheForTest()` 同步清 `failedAt`(删除 `endpointFullVersion.value++`)。

**六个消费文件**:删除所有 `void endpointFullVersion.value` 语句(全仓 14 处)与 `endpointFullVersion` 的 import。以 grep 自证:

```bash
cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && grep -rn "endpointFullVersion" src/ || echo "CLEAN(0 处)"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/composables/__tests__/useEndpointFull.test.ts src/composables/__tests__/useFieldDescriptions.test.ts src/components/composer/__tests__/CaseComposerCanvas.test.ts src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: PASS(EF-1..7;既有全绿 —— 删掉手工依赖后,凡**真读缓存**的 computed 仍会重算,这是 EF-6 钉住的性质)。
`npm run typecheck` → 0。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/composables/useEndpointFull.ts src/gimbal-platform/frontend/src/composables/__tests__/useEndpointFull.test.ts <其余五个消费文件> && git commit -m "refactor(contract-cache): 契约缓存改 Vue 原生响应式 — 手工版本号协议退役 + 失败负缓存

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3(S3): `useInjectableSurface` + 四视图接线 + 死因分组(修 C、消 K、收 Q)

**Files:**
- Create: `src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts`
- Create: `src/gimbal-platform/frontend/src/composables/__tests__/useInjectableSurface.test.ts`
- Modify: `views/AssertionRegistryEditor.vue`、`views/CaseComposer.vue`、`views/CaseDataSetsList.vue`、`components/composer/RunPanelHost.vue`、`components/composer/RunDialog.vue`
- Test: `components/composer/__tests__/RunPanelHost.test.ts`、`views/__tests__/CaseComposer.run.test.ts`

**Interfaces:**
- Produces:

```ts
export interface InjectableSurface {
  pathsOfStep(si: number): ReadonlySet<string>
  deadOf(e: AssertionEntry | LegacyAssertionEntry): RegistryIssue[]
  /** 死因分组(spec §2.1):intrinsic 任何时刻都死;contractDependent 仅因契约未定/取数失败而判死 */
  dead: ComputedRef<{ intrinsic: string[]; contractDependent: string[] }>
  stateOf(path: string): FieldState | undefined
  pending: ComputedRef<boolean>
  ensure(): void
}
export function useInjectableSurface(
  steps: Ref<any[]>,
  entries: Ref<Array<AssertionEntry | LegacyAssertionEntry>>,
): InjectableSurface
```

- [ ] **Step 1: 写失败测试**

`useInjectableSurface.test.ts`:

```ts
it('IS-1: dead 分两组 — step-oob/legacy 入 intrinsic,契约未定而 path-unresolvable 入 contractDependent', async () => {
  // 契约未回填(getFullEndpoint 挂起)→ pending=true
  const steps = ref([{ request: { body: { amount: 'x' } }, api: { view_hints: { endpoint_id: 'ep-x' } } }])
  const entries = ref([
    { id: 'a', name: 'A', path: { stepIndex: 9, source: 'body', jsonpath: '$.z' }, value: 1, asserts: [] },      // step-oob → intrinsic
    { id: 'b', name: 'B', anchor: {}, asserts: [] },                                                            // legacy → intrinsic
    { id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] }, // 契约未定 → contractDependent
  ] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await nextTick()
  expect(s.pending.value).toBe(true)
  expect(s.dead.value.intrinsic.sort()).toEqual(['a', 'b'])
  expect(s.dead.value.contractDependent).toEqual(['c'])
})

it('IS-2: 契约落定后 contractDependent 清空(声明面命中)', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({ id: 'ep-x', request: { declarations: [
    { name: 'carry_field', path: '$.carry_field', state: 'carry', required: true, description: '' }] } } as any)
  /* 同上构造 → ensure() → await flushPromises() */
  expect(s.pending.value).toBe(false)
  expect(s.dead.value.contractDependent).toEqual([])
})

it('IS-3: 契约取数**失败** → 判定从严,path-unresolvable 归 intrinsic(不是悬置)', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))
  const steps = ref([{ request: { body: {} }, api: { view_hints: { endpoint_id: 'ep-down' } } }])
  const entries = ref([{ id: 'c', name: 'C', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_field' }, value: 1, asserts: [] }] as any)
  const s = useInjectableSurface(steps, entries)
  s.ensure()
  await flushPromises()
  expect(s.pending.value).toBe(false)                 // 有答案了(失败也是答案)
  expect(s.dead.value.contractDependent).toEqual([])  // 不悬置
  expect(s.dead.value.intrinsic).toEqual(['c'])       // 从严:真死
})
```

> **口径**(已写进用例注释):`pending` = "还没答案"(契约在途);`failed` = "答案拿不到" ⇒ 判定**从严**(只认 body 面),`path-unresolvable` 即真死归 `intrinsic`。

`RunPanelHost.test.ts` 追加(修 C 的可观察面 —— 必须让 getFullEndpoint **挂起**,否则 pending 为假、用例空转):

```ts
it('RH-6: 契约 pending 期间 — intrinsic 死条目仍禁选,contractDependent 不标死', async () => {
  let release: (v: any) => void = () => {}
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise((res) => { release = res }) as any)
  vi.spyOn(api, 'getScenario').mockResolvedValue({ meta: { scenarioId: 'sc-h', name: 'h' }, steps: [], stepCount: 1 } as any)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
    definition: { kind: 'scenario', scenarioId: 'sc-h', meta: { name: 'h' }, config: {},
      steps: [{ kind: 'step', api: { kind: 'api', service: 's', method: 'POST', path: '/p', headers: {},
        view_hints: { endpoint_id: 'ep-h' } }, request: { kind: 'request', body: {} }, strategy: [] }] },
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-oob', name: '越界', path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
      { id: 'inj-carry', name: '契约依赖', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] },
    ] },
  } as any)
  const w = mountRunPanelHost()          // 复用本文件既有的宿主挂载辅助
  await flushPromises()                  // /full 仍挂起 ⇒ pending 为真
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('pendingContract')).toBe(true)
  const boxes = dlg.findAll('.rd-injection .el-checkbox')
  expect(boxes[0].find('input').attributes('disabled')).toBeDefined()   // step-oob:intrinsic ⇒ 仍禁选
  expect(boxes[0].text()).toContain('悬空')
  expect(boxes[1].find('input').attributes('disabled')).toBeUndefined() // 契约依赖 ⇒ pending 期间不禁选
  release({ id: 'ep-h', request: { declarations: [] } })                // 契约落定后收窄
  await flushPromises()
  expect(w.findComponent(RunDialog).findAll('.rd-injection .el-checkbox')[1]
    .find('input').attributes('disabled')).toBeDefined()
  w.unmount()
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/composables/__tests__/useInjectableSurface.test.ts src/components/composer/__tests__/RunPanelHost.test.ts`
Expected: FAIL —— 模块不存在;RH-6 因 `pending` 时 `deadIds` 被掩空而红。

- [ ] **Step 3: 实现 `useInjectableSurface.ts`**

```ts
/**
 * useInjectableSurface —— 判定面的**唯一消费面**(spec 架构收敛 §2.1)。
 *
 * 收敛前:四个视图各自定义 injectablePathsOfStep / assertTargetsOf / deadOf /
 * contractPending(四份副本,且已在同一波内漂移)。收敛后:判定、记忆化、
 * 预取时机、死因分组都在这里,**视图只消费**。
 *
 * 取数时机(修 F 的结构成因):`ensure()` 是**显式副作用**,由宿主在挂载 /
 * 步骤变化时调用;渲染期只读缓存 —— 纯判定不再与网络 I/O 耦合。
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { injectablePathSetOf, registryIssues } from '@/utils/assertion-registry'
import type { RegistryIssue } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { iterFlat, resolveState, toTemplatePath } from '@/utils/declarations'
import type { FieldState } from '@/types/plate'
import {
  endpointFullState, ensureEndpointFull, getEndpointFull, requestDeclarationsOf,
} from '@/composables/useEndpointFull'

export function useInjectableSurface(
  steps: Ref<any[]>,
  entries: Ref<Array<AssertionEntry | LegacyAssertionEntry>>,
): InjectableSurface {
  /* ── 预取:只为"被条目引用到的步骤"的 endpoint 取数(显式副作用) ── */
  const neededEndpoints = computed<string[]>(() => {
    const out = new Set<string>()
    for (const e of entries.value) {
      if (isLegacyEntry(e)) continue
      const si = e.path?.stepIndex
      if (!Number.isInteger(si)) continue
      const eid = steps.value[si]?.api?.view_hints?.endpoint_id
      if (typeof eid === 'string' && eid) out.add(eid)
    }
    return [...out]
  })
  function ensure(): void {
    for (const eid of neededEndpoints.value) void ensureEndpointFull(eid)
  }
  watch(neededEndpoints, () => ensure(), { immediate: false })

  /** 契约是否尚未落定:任一被引用端点状态为 'loading' */
  const pending = computed(() =>
    neededEndpoints.value.some((eid) => endpointFullState(eid) === 'loading'))
  /** 契约是否**取数失败**(降级:判定从严) */
  const degraded = computed(() =>
    neededEndpoints.value.some((eid) => endpointFullState(eid) === 'failed'))

  /* ── 记忆化:同一 (si, 契约版本) 只重建一次 ── */
  const pathsCache = new Map<number, ReadonlySet<string>>()
  watch(neededEndpoints, () => pathsCache.clear())
  function pathsOfStep(si: number): ReadonlySet<string> {
    const hit = pathsCache.get(si)
    if (hit) return hit
    const step = steps.value[si]
    const built = injectablePathSetOf(fieldPathsOf(step as any), requestDeclarationsOf(step))
    pathsCache.set(si, built)
    return built
  }
  function assertTargetsOf(si: number): ReadonlySet<string> {
    const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
    return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)));
  }

  function deadOf(e: AssertionEntry | LegacyAssertionEntry): RegistryIssue[] {
    return registryIssues(e, steps.value.length, pathsOfStep, assertTargetsOf)
  }

  const dead = computed(() => {
    const intrinsic: string[] = []
    const contractDependent: string[] = []
    for (const e of entries.value) {
      const issues = deadOf(e)
      if (!issues.length) continue
      // 判据(spec §2.1):**契约未定**时,只有"全部 issue 都是 path-unresolvable"
      // 的条目可悬置(它可能在契约到位后变活);契约**取数失败**时判定从严
      // (faces 已退回 body 面),此时 path-unresolvable 即真死 ⇒ 归 intrinsic。
      const suspended = pending.value && issues.every((i) => i.kind === 'path-unresolvable')
      ;(suspended ? contractDependent : intrinsic).push(e.id)
    }
    return { intrinsic, contractDependent }
  })

  /** 提示行的字段状态标注(原编辑器 stateOfPendingPath 的实现搬入并**显式按步**)。
   *  `si` 必填:编辑器候选来自"当前待选步骤",调用方(编辑器)手里就有该下标。 */
  function stateOf(si: number, path: string): FieldState | undefined {
    const step = steps.value[si] as any
    const key = toTemplatePath(path)
    for (const d of iterFlat(requestDeclarationsOf(step))) {
      if (toTemplatePath(d.path) === key) {
        return resolveState(d.path, d.state, step?.field_states)
      }
    }
    return undefined
  }

  return { pathsOfStep, deadOf, dead, stateOf, pending, ensure }
}
```


**四处视图接线(以 `CaseComposer.vue` 为例,其余三处同款)**:删除 `registryInjectablePathsOf` / `registryAssertTargetsOf` / `deadEntryIds` / `contractPending` 四段本地定义,改为:

```ts
const surface = useInjectableSurface(steps, computed(() => registry.value.entries))
onMounted(() => surface.ensure())
const deadEntryIds = computed(() => surface.dead.value.intrinsic)          // 任何时刻都死
const contractDeadIds = computed(() => surface.dead.value.contractDependent) // 仅契约未定时悬置
```

传给 `RunDialog` 的 `deadEntryIds` 改为 **`intrinsic ∪ (pending ? ∅ : contractDependent)`**(即**掩空决策上移到宿主**,`RunDialog` 不再自行掩空)。

**`RunDialog.vue`**:删除 `props.contractPending ? new Set() : …` 的掩空逻辑,直接用传入的 `deadEntryIds`;`presetSettled` 与落定后收窄逻辑保留(收窄只以宿主给的 id 集为准)。

- [ ] **Step 4: 跑测试确认通过**

Run: `npx vitest run src/composables/__tests__/useInjectableSurface.test.ts src/components/composer/__tests__/RunPanelHost.test.ts src/views/__tests__/CaseComposer.run.test.ts src/views/__tests__/AssertionRegistryEditor.test.ts src/views/__tests__/CaseDataSetsList.test.ts src/components/composer/__tests__/RunDialog.injection.test.ts`
Expected: PASS(IS-1..3、RH-6、既有全绿)。
`npm run typecheck` → 0;`grep -rn "function injectablePathsOfStep\|registryInjectablePathsOf" src/` → 0 处(副本退场自证)。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/composables/useInjectableSurface.ts src/gimbal-platform/frontend/src/composables/__tests__/useInjectableSurface.test.ts src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue src/gimbal-platform/frontend/src/components/composer/RunDialog.vue src/gimbal-platform/frontend/src/components/composer/__tests__/RunPanelHost.test.ts src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.run.test.ts && git commit -m "refactor(surface): 判定面收成一个 surface composable — 四视图副本退场,死因分组修 pending 掩空

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4(S4): `TtlLruCache` 载荷泛化 + `endpoint_declarations` 改持该缓存(修 D/S/R/U)

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/query_view_cache.py`、`app/services/query_view_runner.py`、`app/core/config.py`
- Modify: `src/gimbal-platform/backend/app/services/endpoint_declarations.py`
- Test: `tests/test_query_view_cache.py`、`tests/test_endpoint_declarations.py`

**Interfaces:**
- `CacheEntry.payload`(原 `rows`);`TtlLruCache.put(key, payload, fetched_wall, truncated=False)`。
- `endpoint_declarations` 改持 `TtlLruCache(ttl=settings.DECLARED_PATHS_TTL_SEC, max_entries=settings.DECLARED_PATHS_MAX_ENTRIES, stale_max_window=settings.DECLARED_PATHS_STALE_WINDOW_SEC)`;载荷 = `(decls: list, paths: frozenset[str])`。

- [ ] **Step 1: 写失败测试**

`test_endpoint_declarations.py` 追加:

```python
async def test_stale_snapshot_survives_a_failed_refresh(monkeypatch):
    """D:TTL 过期后刷新失败 → **旧快照仍服务**(stale-while-error)。"""
    calls = {"n": 0, "fail": False}
    PAY = {"ok": True, "dim": "endpoint", "data": {"item": {"request": {"declarations": [
        {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True}]}}}}

    async def handler(request):
        calls["n"] += 1
        if calls["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json=PAY)

    plate_client.set_client_for_tests(httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)        # 立即过期
    monkeypatch.setattr(settings, "DECLARED_PATHS_STALE_WINDOW_SEC", 3600.0)
    assert await declared_paths_of("ep-s") == frozenset({"$.customer_id"})   # 先成功入缓存
    calls["fail"] = True
    got = await declared_paths_of("ep-s")
    assert got == frozenset({"$.customer_id"}), "刷新失败时应回退旧快照,而不是降级为 None"
    plate_client.set_client_for_tests(None)


async def test_projection_is_cached_not_recomputed(monkeypatch):
    """R:投影只在**取数**时算一次;TTL 命中路径不再重算(以 catalog_paths 调用计数断言)。"""
    import app.services.endpoint_declarations as ed

    calls = {"n": 0}
    real = ed.catalog_paths

    def _counting(decls):
        calls["n"] += 1
        return real(decls)

    async def _ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "dim": "endpoint", "data": {"item": {
            "request": {"declarations": [{"name": "a", "path": "$.a", "state": "form", "required": True}]}}}})

    monkeypatch.setattr(ed, "catalog_paths", _counting)
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(_ok_handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    await declared_paths_of("ep-p")
    after_first = calls["n"]
    await declared_paths_of("ep-p")          # TTL 内命中缓存
    assert calls["n"] == after_first == 1     # 投影没有第二次遍历
    plate_client.set_client_for_tests(None)


async def test_cache_has_lru_bound(monkeypatch):
    """S:超过 max_entries 时逐出最旧 —— 不再是"永不淘汰"。"""
    hits: list[str] = []

    async def handler(request):
        hits.append(request.url.path)
        return httpx.Response(200, json={"ok": True, "dim": "endpoint",
                                         "data": {"item": {"request": {"declarations": []}}}})

    monkeypatch.setattr(settings, "DECLARED_PATHS_MAX_ENTRIES", 1)
    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    await declared_paths_of("ep-1")
    await declared_paths_of("ep-2")
    await declared_paths_of("ep-1")           # ep-1 已被逐出 ⇒ 必须重取
    assert len(hits) == 3
    plate_client.set_client_for_tests(None)
```

`test_query_view_cache.py`:载荷改名跟随(机械)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_endpoint_declarations.py tests/test_query_view_cache.py -v`
Expected: FAIL —— 旧快照用例得 `None`(现值行为是 `_CACHE.pop`);LRU 上界用例无上界;`settings` 新键不存在。

- [ ] **Step 3: 实现**

`app/core/config.py`(Plate 段追加):

```python
    # 声明面快照缓存上界与回退窗(spec 架构收敛 §3.1):LRU 容量 + 过期后
    # 仍可回退服务的时间窗(stale-while-error,刷新失败时用旧快照)。
    DECLARED_PATHS_MAX_ENTRIES: int = 256
    DECLARED_PATHS_STALE_WINDOW_SEC: float = 3600.0
```

`query_view_cache.py`:把 `CacheEntry.rows` 改名为 `payload`(含 `__slots__` 与 `put` 形参),docstring 补一句"载荷泛化:query-view 行集与契约声明列表共用一套 TTL/LRU/回退语义"。`query_view_runner.py` 的 4 处 `stale_entry.rows` / `e2.rows` → `.payload`;`RowsResult(name, entry.payload, entry.truncated, …)`。`tests/test_query_view_cache.py` 的 2 处 `.rows` → `.payload`。

`endpoint_declarations.py`:

```python
_CACHE = TtlLruCache(
    ttl=settings.DECLARED_PATHS_TTL_SEC,
    max_entries=settings.DECLARED_PATHS_MAX_ENTRIES,
    stale_max_window=settings.DECLARED_PATHS_STALE_WINDOW_SEC,
)
_INFLIGHT: dict[str, asyncio.Task[list | None]] = {}
_WARNED_AT: dict[str, float] = {}          # eid → 最近一次告警时刻(时间老化,不再只在成功时清)
_WARN_COOLDOWN_SEC = 300.0


def _now_iso() -> str:
    """缓存条目的墙钟时刻(仅用于可读诊断)。"""
    return datetime.now(timezone.utc).isoformat()


def _warn_once(endpoint_id: str, reason: object) -> None:
    """降级告警(**时间老化**):同一端点在 `_WARN_COOLDOWN_SEC` 内至多一条。

    旧实现只在"同 id 后来成功"时才清 `_WARNED` ⇒ 调用方字符串(错拼/改名)驱动的
    无界增长(spec §1.1 S);改为按时间窗老化,与 `TtlLruCache` 的惰性过期同风格。"""
    now = time.monotonic()
    last = _WARNED_AT.get(endpoint_id)
    if last is not None and now - last < _WARN_COOLDOWN_SEC:
        return
    _WARNED_AT[endpoint_id] = now
    logger.warning(
        "endpoint_declarations: {} 声明面不可得({}) — 调用侧降级"
        "(carry 空面 / 悬空判定只认 body 面)",
        endpoint_id, reason,
    )

async def declarations_of(endpoint_id: str) -> list | None:
    entry, fresh = _CACHE.lookup(endpoint_id)
    if entry is not None and fresh:
        return list(entry.payload[0])
    if entry is not None and not fresh:
        # 过期但在回退窗内:尝试刷新;**失败则回退旧快照**(spec §1.1 D)
        try:
            return await _refresh(endpoint_id) or list(entry.payload[0])
        except Exception:               # noqa: BLE001
            _warn_once(endpoint_id, "刷新失败,回退旧快照")
            return list(entry.payload[0])
    try:
        return await _refresh(endpoint_id)
    except Exception as e:              # noqa: BLE001
        _warn_once(endpoint_id, e)
        return None

async def _refresh(endpoint_id: str) -> list | None:
    """在飞收敛(shield + 完成回调摘除)后真正取一次;成功入缓存并**连投影一起**存。"""
    inflight = _INFLIGHT.get(endpoint_id)
    if inflight is None:
        inflight = asyncio.ensure_future(_fetch_declarations(endpoint_id))
        _INFLIGHT[endpoint_id] = inflight
        inflight.add_done_callback(partial(_forget_inflight, endpoint_id=endpoint_id))
    decls = await asyncio.shield(inflight)
    if decls is None:
        raise RuntimeError("declaration fetch failed")
    _CACHE.put(endpoint_id, (decls, frozenset(catalog_paths(decls))), _now_iso())
    return decls
```

> **注意**:`_fetch_declarations` 保留原有 fail-soft(None)与告警语义,但**不再自己写 `_CACHE`**(入缓存统一由 `_refresh` 在成功后做 ⇒ **时间戳取在成功之后**,即 U 的修法);`declared_paths_of` 改为读缓存里的**投影**:

```python
async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """取不到 → None(降级);合法空声明 → **空 frozenset**(非 None)。"""
    entry, fresh = _CACHE.lookup(endpoint_id)
    if entry is not None and fresh:
        return entry.payload[1]
    decls = await declarations_of(endpoint_id)
    if decls is None:
        return None
    entry, _ = _CACHE.lookup(endpoint_id)
    return entry.payload[1] if entry is not None else frozenset(catalog_paths(decls))
```

`_reset_declared_paths_cache()` 改为清 `_CACHE`(用其 `drop_where(lambda k: True)` 或新增 `clear()`)、`_INFLIGHT`、`_WARNED_AT`(测试钩子契约不变)。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_endpoint_declarations.py tests/test_query_view_cache.py tests/test_query_view_runner.py -v`
Expected: PASS(既有 6 条 + 新增 3 条;query-view 侧因改名机械跟随而全绿 —— 若变红说明改名漏改,不是行为变化)。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/services/query_view_cache.py src/gimbal-platform/backend/app/services/query_view_runner.py src/gimbal-platform/backend/app/core/config.py src/gimbal-platform/backend/app/services/endpoint_declarations.py src/gimbal-platform/backend/tests/test_query_view_cache.py src/gimbal-platform/backend/tests/test_endpoint_declarations.py && git commit -m "refactor(decl-cache): 复用 TtlLruCache(LRU 上界 + 回退窗)— 失败保留旧快照,投影随取数缓存

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5(S5): 判定收口(修 B/Y/Z2/Z3/P/T)

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_injection.py`、`app/services/run_dispatcher.py`
- Test: `tests/test_run_injection.py`、`tests/test_run_cross_matrix.py`

**Interfaces:**
- `run_injection` 新增:`as_step_index(x: Any) -> int | None`(拒 bool;收整数与整数值浮点);`injectable_universe(body: Any, declared: Any) -> set[str]`(纯函数,= body 叶子 ∪ 其前缀 ∪ normalize(declared) ∪ 其前缀 ∪ `{"$"}`)。
- `entry_issues(entry, step_count, body_of, assert_targets_of, universe_of=None)` —— **第 5 参语义由 `declared_of` 改为 `universe_of`**(`Callable[[int], set[str]]`)。

- [ ] **Step 1: 写失败测试**

`test_run_injection.py` 追加:

```python
def test_step_index_accepts_integral_float_rejects_bool():
    """Z3:JSON 只有一种数字类型 —— 后端与前端的 Number.isInteger 同构。"""
    assert as_step_index(1) == 1
    assert as_step_index(1.0) == 1          # JSON 1.0 → JS 也是整数
    assert as_step_index(True) is None      # bool 不是数字(前端 Number.isInteger(true) 为假)
    assert as_step_index("0") is None
    assert as_step_index(None) is None


def test_injectable_universe_covers_body_prefixes_and_declared():
    """P/§2.1:universe 是纯函数,可单测(不再藏在判定里每次重建)。"""
    u = injectable_universe({"tags": ["a", "b"]}, frozenset({"$.customer_id"}))
    assert {"$", "$.tags", "$.tags[0]", "$.tags[1]", "$.customer_id"} <= u
```

`test_run_cross_matrix.py` 追加(经 dispatcher,断言 Z2/B/T 的可观察后果):

```python
async def test_dispatcher_uses_raw_step_index_base(client, plate_mock, monkeypatch):
    """Z2:definition.steps 混入非 dict 元素时,声明面/body/asserts 仍按**原始**下标寻址
    (与前端 compose_injection_scenario 同一基准)。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{"id": "s1",
                "api": {"kind": "api", "service": "svc", "method": "POST", "path": "/a", "headers": {},
                        "view_hints": {"endpoint_id": "ep-raw"}},
                "request": {"body": {"amount": "${var.amount}"}}, "strategy": []}],
        vars_map={"amount": 1},
    )
    draft["definition"]["steps"].insert(0, "GARBAGE")     # 过滤版下标会整体前移一位
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-raw", "name": "原始下标",
        "path": {"stepIndex": 1, "source": "body", "jsonpath": "$.amount"},
        "value": 9, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    plate_mock.fulls["ep-raw"] = {"request": {"declarations": [
        {"name": "amount", "path": "$.amount", "state": "form", "required": True}]}}
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-raw"]})
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1                      # 原始下标 1 = 唯一真实步骤 ⇒ 判活并执行
    assert {"kind": "assign", "source": 9, "target": "$.request_body.amount"} in \
        cases[0]["steps"][0]["strategy"]


async def test_dispatcher_tolerates_non_dict_api(client, plate_mock, monkeypatch):
    """B:step.api 为字符串时不再 500(守齐),按无 endpoint_id 降级为 body 面。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{"id": "s1", "api": "svc",                    # ← 非 dict
                "request": {"body": {"amount": "${var.amount}"}}, "strategy": []}],
        vars_map={"amount": 1},
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-b", "name": "body 面可判",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
        "value": 5, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-b"]})
    assert r.status_code == 201, r.text                      # 不是 500
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1


async def test_degraded_face_is_visible_in_run_record(client, plate_mock, monkeypatch):
    """Y:声明面**取数失败**导致的跳过与"端点本无声明"可区分 —— 前者在 run 记录里留标记。"""
    from .helpers import make_draft as _draft
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{"id": "s1",
                "api": {"kind": "api", "service": "svc", "method": "POST", "path": "/a", "headers": {},
                        "view_hints": {"endpoint_id": "ep-absent"}},   # fulls 里不注册 ⇒ 404
                "request": {"body": {}}, "strategy": []}])
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-d", "name": "锚在契约声明上",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 1, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text
    plate_mock.behaviour = "echo"

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-d"]})
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    ex = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    cfg = ex.get("config") or {}
    assert cfg.get("judgeDegraded") is True
    assert cfg.get("entriesSkippedByDegradation") == ["inj-d"]
    # 正对照:端点**存在**但没有该声明 ⇒ 不是降级,不留标记
    plate_mock.fulls["ep-absent"] = {"request": {"declarations": []}}
    from app.services.endpoint_declarations import _reset_declared_paths_cache
    _reset_declared_paths_cache()
    r2 = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-d"]})
    ex2 = (await client.get(f"/api/executions/{r2.json()['executionId']}", headers=bob)).json()
    assert (ex2.get("config") or {}).get("judgeDegraded") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_run_injection.py tests/test_run_cross_matrix.py -v`
Expected: FAIL —— `as_step_index` / `injectable_universe` 不存在;B 用例 500;Z2 用例判定错位。

- [ ] **Step 3: 实现**

`run_injection.py`:

```python
def as_step_index(x: Any) -> int | None:
    """stepIndex 归一(Z3):拒 bool;收整数与**整数值浮点**。
    JSON 只有一种数字类型 ⇒ 前端 `Number.isInteger(1.0)` 为真,后端必须同判;
    `true` 在前端是 false(Number.isInteger(true)),后端 `isinstance(True, int)`
    却为真 —— 那是分裂,故显式拒绝。"""
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return None


def injectable_universe(body: Any, declared: Any) -> set[str]:
    """每步的可注入面(spec v3.1 §2.1 公式;**纯函数**,由调用方按步骤记忆化复用):
    body 叶子 ∪ 其容器前缀 ∪ normalize(declared) ∪ 其前缀 ∪ {"$"}。"""
    universe: set[str] = {"$"}
    for p in _body_leaf_paths(body):
        universe.add(p)
        universe.update(_container_prefixes(p))
    for p in (declared or ()):
        if not isinstance(p, str):
            continue
        t = _template_path(p)
        universe.add(t)
        universe.update(_container_prefixes(t))
    return universe
```

`_path_resolvable` 改为**只吃现成的 universe**(去掉每次重建,并删掉那段已证明为死代码的前缀扫描):

```python
def _path_resolvable(jsonpath: str, body: Any, universe: set[str]) -> bool:
    """判定(spec v3.1 §2.1):两形态命中 universe 即活;否则退回 body 精确存在性
    (既有兜底不退化 —— 它多认"空容器本身",方向是"少判死")。"""
    for form in (jsonpath, _template_path(jsonpath)):
        if form in universe:
            return True
    return exists(body or {}, jsonpath)
```

`entry_issues`:第 5 参改 `universe_of`;`si` 与 asserts 的 `stepIndex` 一律过 `as_step_index`:

```python
def entry_issues(entry, step_count, body_of, assert_targets_of, universe_of=None) -> list[dict]:
    _universe = universe_of or (lambda si: {"$"})
    …
    si = as_step_index(path.get("stepIndex"))
    if si is None or si < 0 or si >= step_count:
        issues.append({"kind": "step-oob", "stepIndex": path.get("stepIndex")})
    elif not isinstance(jp, str) or not _path_resolvable(jp, body_of(si), _universe(si)):
        issues.append({"kind": "path-unresolvable", "stepIndex": si, "jsonpath": jp})
    for a in entry.get("asserts") or []:
        if isinstance(a, dict):
            asi = as_step_index(a.get("stepIndex"))
            if asi is not None:
                …
```

`run_dispatcher.py` §2.5:

```python
    # 索引基数(spec §1.1 Z2):声明面/body/asserts 与前端、与
    # compose_injection_scenario 一律按 definition.steps 的**原始**下标寻址
    # (carry_injection docstring 的既定契约「原始列表索引」)。
    raw_steps = definition_from_payload(raw_payload).get("steps") or []
    step_count = len(raw_steps)
    selected = [e for e in entries if isinstance(e, dict) and e.get("id") in selected_ids]

    needed_steps: set[int] = set()
    for e in selected:
        p = e.get("path")
        si = as_step_index(p.get("stepIndex")) if isinstance(p, dict) else None
        if si is not None:
            needed_steps.add(si)

    def _endpoint_id_of(si: int) -> str | None:
        step = raw_steps[si] if 0 <= si < step_count and isinstance(raw_steps[si], dict) else {}
        api = step.get("api")
        hints = (api.get("view_hints") or {}) if isinstance(api, dict) else {}   # B:守齐
        eid = hints.get("endpoint_id") if isinstance(hints, dict) else None
        return eid if isinstance(eid, str) and eid else None

    async def _face_of(si: int) -> tuple[int, frozenset[str] | None]:
        eid = _endpoint_id_of(si)
        if eid is None:
            return si, frozenset()            # 无端点 = 真无声明(非得降级)
        return si, await declared_paths_of(eid)   # None = 降级(**不抹平**,Y)

    face_by_step: dict[int, frozenset[str] | None] = dict(
        await asyncio.gather(*[_face_of(si) for si in sorted(needed_steps)])
    ) if needed_steps else {}
    for si, face in face_by_step.items():
        if face is None:
            logger.warning(
                "run_dispatcher: step %s 声明面不可得(plate 降级)— 该步判定只认 body 面,"
                "锚在契约声明上的条目可能被误判为悬空并跳过", si,
            )
    universe_by_step: dict[int, set[str]] = {
        si: injectable_universe(
            (raw_steps[si].get("request") or {}).get("body") if isinstance(raw_steps[si], dict) else None,
            face,
        )
        for si, face in face_by_step.items()
    }
    _universe_of = lambda si: universe_by_step.get(si, {"$"})   # noqa: E731

    skipped_by_degradation: list[str] = []
    selected_entries: list[dict] = []
    for e in selected:
        issues = entry_issues(e, step_count, _body_of(raw_payload), _assert_targets_of(raw_payload), _universe_of)
        if issues:
            si = as_step_index(e["path"].get("stepIndex")) if isinstance(e.get("path"), dict) else None
            if si is not None and face_by_step.get(si) is None:
                skipped_by_degradation.append(e.get("id"))      # Y:降级导致的跳过要可见
            logger.warning("run_dispatcher: injection entry %s dangling (%s) — skipped", e.get("id"), issues)
            continue
        selected_entries.append(e)
```

并在该 run 的 `config_json` 里补一个如实字段(仅当非空):

```python
        # spec §1.1 Y:判定降级是可审计事实,不留静默窗口
        **({"judgeDegraded": True, "entriesSkippedByDegradation": skipped_by_degradation}
           if skipped_by_degradation else {}),
```

`_body_of` / `_assert_targets_of`:改用**原始** steps(与 `raw_steps` 同源)—— 即内部改为 `definition_from_payload(payload).get("steps") or []`,不再走过滤版 `steps_from_payload`。**注**:`run_*` 其它既有调用点若依赖"过滤后下标"语义,须一并核对并保持行为(改动后跑全量验收)。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_run_injection.py tests/test_run_cross_matrix.py tests/test_run_m1_capabilities.py tests/test_run_baseline.py tests/test_run_injectable_wire.py -v`
Expected: PASS(新增 Z3/P/B/Z2/Y 用例 + 既有全绿;真链路 2 条**未跳过**)。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/services/run_injection.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_injection.py src/gimbal-platform/backend/tests/test_run_cross_matrix.py && git commit -m "fix(run): 判定收口 — 原始索引基数/stepIndex 同构/None 不抹平/守齐 + universe 预计算

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6(S6): 判定取数改 3s 有界软取(修 Z4)

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/config.py`、`app/services/endpoint_declarations.py`
- Test: `tests/test_endpoint_declarations.py`

**Interfaces:** 新设置 `DECLARED_PATHS_TIMEOUT_SEC: float = 3.0`;逐请求覆盖(客户端默认 30s 不变)。

- [ ] **Step 1: 写失败测试**

```python
async def test_slow_plate_degrades_within_bounded_time(monkeypatch):
    """Z4:判定取数是**软取** —— plate 慢时在 3s 内降级,不把 /runs 绑到 30s。"""
    async def handler(request):
        await asyncio.sleep(5)                     # 超过 3s 判定超时
        return httpx.Response(200, json={"ok": True, "data": {"item": {}}})

    monkeypatch.setattr(settings, "DECLARED_PATHS_TIMEOUT_SEC", 0.3)   # 测试里收紧
    plate_client.set_client_for_tests(httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    _reset_declared_paths_cache()
    t0 = time.monotonic()
    assert await declared_paths_of("ep-slow") is None       # 超时 → 降级
    assert time.monotonic() - t0 < 2.0                      # 有界(远小于 5s)
    plate_client.set_client_for_tests(None)
```

- [ ] **Step 2: 跑测试确认失败**(当前无逐请求超时 → 该用例会等满 5s 并返回成功,fail)

- [ ] **Step 3: 实现**:`config.py` 加 `DECLARED_PATHS_TIMEOUT_SEC: float = 3.0`(注释:判定是软增强,超时即降级从严;`PLATE_TIMEOUT_SEC` 的 30s 只作用于 convert 等既有链路,勿改);`endpoint_declarations._fetch_declarations` 的 `get()` 传 `timeout=settings.DECLARED_PATHS_TIMEOUT_SEC`。

- [ ] **Step 4: 跑测试确认通过** + `python -m pytest tests/ -q -k "endpoint_declarations or run_"` → 全绿。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/core/config.py src/gimbal-platform/backend/app/services/endpoint_declarations.py src/gimbal-platform/backend/tests/test_endpoint_declarations.py && git commit -m "fix(run): 判定取数改 3s 有界软取 — /runs 不再与前端 axios 30s 超时线相撞

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7(S7): 文档收敛(spec §6 五项)

**Files:**
- Modify: `docs/PLATFORM-SCENARIO-COMPOSER-API.md`(§2.6 / §4.18 / §5 + 新增一节)
- Modify: `docs/adr/0003-retired-features-log.md`(退场表加行)
- Create: `docs/known-issues/` 下各记录
- Modify: `docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md`(头部修订标注)

- [ ] **Step 1: API 文档**:§2.6 `RunRequest` 补 `dataSetSelection` / `injectionEntryIds`(写明两键同发本键优先);§4.18 补交叉公式、409 `row_index_out_of_range`、**有界软取(3s)与降级从严**、悬空 skip 的可见性(`judgeDegraded` 标记);§5 补「判定面不持久化 / 不依赖 JSON 键序 / 显式 null 语义」;**新增一节「断言条目与可注入面」**。
- [ ] **Step 2: ADR 0003**:退场表加行(手工版本号协议 `endpointFullVersion`、四个视图的本地判定函数、`endpoint_declarations._CACHE`、`bodyPathSetOf` 若在本阶段退场);并按该 ADR 的规则清理代码中承载历史叙述的注释。
- [ ] **Step 3: `known-issues/`**:为 Z1(`exists` 属性洞,P0)、E(`normalizeRegistry` 写回,P0)、G(`${...}` 补键,P1)建记录;为已接受局限(前后端缓存新鲜度分歧、轻量页新增 `/full`、`[*]` 归一无覆盖、模板粒度边界)各建一条(按 README 约定:一文件一主题、标优先级、修复时加「## 修复记录」)。
- [ ] **Step 4: v3.1 spec 头部**加一行修订标注指向本收敛 spec。
- [ ] **Step 5: 确认不改**:`docs/architecture.md`(引擎架构)与 NEIGHBOR.md(约定未落地)—— 在 spec §6.5 已记;实施时**只确认、不动**。
- [ ] **Step 6: Commit**

```bash
cd /d/Gimbal/Gimbal && git add docs/ && git commit -m "docs: 架构收敛文档跟随 — API 文档补判定面/ADR 退场表/known-issues 建档/修订标注

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8(S8): 全量回归 + 四道门收口

- [ ] **Step 1: 后端全量** `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest -q` → 期望 ≥513 passed / 0 failed(新增用例后更多)。
- [ ] **Step 2: 前端全量 + 类型** `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run` 与 `npm run typecheck` → 全绿 / 0 错误。
- [ ] **Step 3: plate 守卫** `git diff --stat fc6edb9...HEAD | grep -E "src/gimbal-plate/|src/gimbal/|export/gimbal.py" && echo VIOLATION || echo CLEAN` → CLEAN。
- [ ] **Step 4: 结构自证(grep,写进报告)**
  - `grep -rn "endpointFullVersion" frontend/src/` → 0;
  - `grep -rn "function injectablePathsOfStep\|registryInjectablePathsOf\|function assertTargetsOf" frontend/src/` → 0(仅 composable 内有);
  - `grep -rn "_CACHE" backend/app/services/endpoint_declarations.py` → 0(改用 `TtlLruCache`);
  - `grep -rn "steps_from_payload" backend/app/services/run_injection.py` → 0(原始索引基数)。
- [ ] **Step 5: Commit(若前四步有修正)**

---

## 验收对照(spec ↔ 任务)

| spec 条目 | 落点 |
|---|---|
| §1.1 A(真值非字符串 path 崩渲染) | S1 |
| §1.1 F / §2.2 L(渲染期 IO、手工版本号) | S2 + S3 |
| §1.1 C(pending 掩空无关死因) | S3 |
| §1.1 D/S/R/U(缓存:旧值保留、上界、投影、时刻) | S4 |
| §1.1 B/Y/Z2/Z3 + P/T(判定收口) | S5 |
| §1.1 Z4(有界软取) | S6 |
| §2.1 唯一定义 / §2.3 边界消毒一次 | S1 + S3 |
| §3.1 缓存复用 | S4 |
| §3.2/§3.3 判定收口与软取 | S5 + S6 |
| §4 存储可迁移性四约束 | S4(不持久化/键序/null)+ S4/S6(每进程一份) |
| §5 全仓编码约定(禁止真值合并) | 各任务实施时遵守;S5 为该约定的首个示范 |
| §6 文档收敛五项 | S7 |
| §7 阶段二范围与待裁定 | 无任务(另立 spec) |
| §8 验收要点 | 各任务用例 + S8 四道门 |
