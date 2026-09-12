# 可注入面(契约声明字段地址化)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「可注入面」从「该步 `request.body` 里已 materialize 的值」放宽为「契约声明的 body 字段(全状态 form/collapse/carry)∪ body 现存 ∪ 容器前缀」,前后端判定同构,并在编辑器提示层按层给出三面字段与状态标注。

**Architecture:** 前端把四处 dead 判定收成**唯一投影** `injectablePathSetOf(bodyLeaves, declarations)`(声明面走既有 `catalogPaths`,下标归一走既有 `toTemplatePath`);后端在 §2.5 悬空过滤前,按被选中条目引用到的步骤取一次 plate `/full` 的声明面(进程缓存 + TTL + fail-soft 降级从严),`entry_issues` 增 `declared_of` 参数并把 path 判定改为「两种形态都试」。

**Tech Stack:** Vue 3 + TS + Element Plus(vitest/@vue/test-utils)/ FastAPI + Pydantic(pytest)/ plate `/full` 契约。

**Spec:** `docs/superpowers/specs/2026-09-12-injectable-path-surface-design.md`(权威;本计划是它的实施论证)

## Global Constraints

- **分支**: `feat/dataset-driven-refactor`(现有工作分支;勿在 master/main 上实施)。
- **plate/执行核零改动**: `src/gimbal-plate/**`、`export/gimbal.py`、`src/gimbal/**` **一行不动**(读它们以确认语义是允许且被要求的)。
- **永不提交/触碰**: `gimbal-tmp/`、`reports/test-report.html`、`probe_ui.js`、`src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_add_demo.py` 及 `endpoint/__init__.py` 的 3 行演示副本改动。
- **用户 WIP 文件**: `FieldActionMenu.vue` / `FieldForm.vue` —— 本计划**完全不碰**。
- **安全**: SUT 凭证(Authorization token/Cookie/加密密码)不回显、不入库、不提交;绝不自动重登录。
- **git**: `git add` 点名文件,不用 `git add -A`;commit message 尾行 `Co-Authored-By: Claude Code <noreply@anthropic.com>`;**不 push**。
- **环境命令**(Bash 每次调用自带 `cd /d/Gimbal/Gimbal`;`python` = D:\python\python.exe,后端无 venv):
  - 后端单测: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/<file> -v`
  - 后端全量: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest -q`
  - 前端单测: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run <file>`
  - 前端全量 + 类型: `npx vitest run` / `npm run typecheck`
- **每任务自检 `vue-tsc`**(后端任务跑 `python -m pytest`):本任务属主文件零错误;未迁移文件的诊断视为外部状态。
- **降级纪律**(spec §2.2):拿不到声明面时判定**从严**(只认 body 面)+ 记一条 warning,**绝不阻塞执行**。
- **行为变化申报**(spec §5.1):原先锚在 carry / 未落 body 的 collapse 上、被判悬空而在 dispatch 静默跳过的条目,**升级后会真正执行** —— 这是本次放宽的必然结果,须在 T6 写进文档。

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/utils/assertion-registry.ts` | 可注入面投影 + 判定(纯函数) | 改 |
| `src/composables/useEndpointFull.ts` | 契约声明面读取(共享缓存之上) | 改 |
| `src/components/composer/JsonPathInput.vue` | 提示行(新增字段状态标注) | 改 |
| `src/views/AssertionRegistryEditor.vue` | 判定接线 + 请求侧候选换源 | 改 |
| `src/views/CaseComposer.vue` / `src/components/composer/RunPanelHost.vue` / `src/views/CaseDataSetsList.vue` | 同款判定接线 | 改 |
| `app/core/config.py` | `DECLARED_PATHS_TTL_SEC` | 改 |
| `app/services/endpoint_declarations.py` | 声明面取数(缓存 + TTL + fail-soft) | 新建 |
| `app/services/run_injection.py` | path 判定放宽(`declared_of`) | 改 |
| `app/services/run_dispatcher.py` | §2.5 前取声明面并接线 | 改 |

---

### Task 1: 前端可注入面投影(纯函数)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/assertion-registry.ts`
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts`(追加 describe)

**Interfaces:**
- Consumes: `fieldPathsOf`(`@/utils/dataset-segments`,调用方已用)、`bodyPathSetOf`(本文件)、`catalogPaths` / `toTemplatePath`(`@/utils/declarations`,**均已存在**:前者返回模板形态的声明全景,后者 `$.a[0].b → $.a.b`)。
- Produces(Task 2 消费,签名逐字):
  - `function injectablePathSetOf(bodyLeaves: Array<{ source: string; path: string }>, declarations?: DeclarationEntryView[] | null): ReadonlySet<string>`
  - `function pathResolvable(jsonpath: string, injectablePaths: ReadonlySet<string>): boolean`(第二参语义由「body 面」改为「可注入面」;两种形态都试)

- [ ] **Step 1: 写失败测试**(在 `src/utils/__tests__/assertion-registry.test.ts` 末尾追加)

```ts
// ── 可注入面(spec v3.1 §2.1):body 现存 ∪ 契约声明(全状态)──────────
const DECLS = [
  { name: 'bl_no', path: '$.bl_no', state: 'form', required: true, description: '' },
  { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true, description: '' },
  { name: 'items', path: '$.items', state: 'form', required: false, description: '',
    children: [{ name: 'sku', path: '$.items.sku', state: 'form', required: true, description: '' }] },
] as any
const STEP_FORM_ONLY = { request: { body: { bl_no: '${var.bl_no}' } } }

describe('可注入面 — 契约声明字段地址化(spec v3.1 §2.1)', () => {
  it('IS-1: 声明面进集合(含 carry 与容器条目,模板形态)', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), DECLS)
    expect(s.has('$')).toBe(true)
    expect(s.has('$.bl_no')).toBe(true)          // form
    expect(s.has('$.customer_id')).toBe(true)    // carry —— 本次放宽的核心对象
    expect(s.has('$.items')).toBe(true)          // 容器条目自身也是合法地址
    expect(s.has('$.items.sku')).toBe(true)      // children 平铺
  })

  it('IS-2: body 现存路径进集合(实例形态)', () => {
    const step = { request: { body: { items: [{ sku: 'x' }] } } }
    const s = injectablePathSetOf(fieldPathsOf(step as any), [])
    expect(s.has('$.items[0].sku')).toBe(true)
  })

  it('IS-3: 声明命中即可解析 —— 实例与模板两种形态都试', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), DECLS)
    expect(pathResolvable('$.customer_id', s)).toBe(true)   // carry:放宽后可用
    expect(pathResolvable('$.items[0].sku', s)).toBe(true)  // 实例形态对齐模板声明
    expect(pathResolvable('$.items[1]', s)).toBe(true)      // 容器前缀
    expect(pathResolvable('$.nope', s)).toBe(false)         // 两边都没有 → 仍判死(拼写错误仍被抓)
  })

  it('IS-4: 无声明面(降级)→ 判定等于旧的 body 面(从严)', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), undefined)
    expect(pathResolvable('$.bl_no', s)).toBe(true)
    expect(pathResolvable('$.customer_id', s)).toBe(false)
  })

  it('IS-5: body 实例路径不因下标归一被吃掉(旧行为不回退)', () => {
    const step = { request: { body: { items: [{ sku: 'x' }, { sku: 'y' }] } } }
    const s = injectablePathSetOf(fieldPathsOf(step as any), [])
    expect(pathResolvable('$.items[1].sku', s)).toBe(true)
    expect(pathResolvable('$.items[0]', s)).toBe(true)
    expect(pathResolvable('$.items', s)).toBe(true)
  })
})
```

(文件顶部 import 行补 `injectablePathSetOf`;`fieldPathsOf` 需从 `../../utils/dataset-segments` 引入。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/assertion-registry.test.ts`
Expected: FAIL —— `injectablePathSetOf` 未导出(`is not a function` / 导入报错)。

- [ ] **Step 3: 实现**

`src/utils/assertion-registry.ts` —— 顶部补 import:

```ts
import { catalogPaths, toTemplatePath } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'
```

在 `bodyPathSetOf` 之后插入:

```ts
/** 可注入面(spec v3.1 §2.1)= body 现存(body 源叶子)
 *  ∪ 契约声明的 body 字段(全状态 form/collapse/carry,模板形态)。
 *  声明面是本次放宽的核心:carry / 未落 body 的 collapse 字段此前不可寻址,
 *  而引擎 Assign 对它们同样生效(spec §2.3 执行序)。 */
export function injectablePathSetOf(
  bodyLeaves: Array<{ source: string; path: string }>,
  declarations?: DeclarationEntryView[] | null,
): ReadonlySet<string> {
  const out = new Set<string>(['$'])
  for (const p of bodyPathSetOf(bodyLeaves)) out.add(p)
  for (const p of catalogPaths(declarations)) out.add(toTemplatePath(p))
  return out
}
```

把 `pathResolvable` 改为两种形态都试(前缀规则不动):

```ts
/** path 是否可解析(spec v3.1 §2.1):实例形态对齐 body 面、模板形态对齐
 *  契约声明面,二者任一命中即可;或为某路径的容器前缀(`p.` / `p[`
 *  开头 —— 条目可锚在容器上,Assign 整体覆写该容器,spec §2)。 */
export function pathResolvable(jsonpath: string, injectablePaths: ReadonlySet<string>): boolean {
  for (const form of [jsonpath, toTemplatePath(jsonpath)]) {
    if (injectablePaths.has(form)) return true
    for (const p of injectablePaths) {
      if (p.startsWith(`${form}.`) || p.startsWith(`${form}[`)) return true
    }
  }
  return false
}
```

`registryIssues` / `isDeadEntry` 的第二回调参数改名 `bodyPathsOfStep` → `injectablePathsOfStep`(**位置参数不变**,既有调用与测试不受影响;改名是为了不撒谎)。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/assertion-registry.test.ts`
Expected: PASS —— 既有 RG-1..6 与新增 IS-1..5 全绿。

再跑一次类型检查(本文件属主): `npm run typecheck` → 本文件零错误。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/utils/assertion-registry.ts src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts && git commit -m "feat(assertion): 可注入面投影 — body 现存 ∪ 契约声明(全状态),判定两形态都试

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 前端接线(四处判定同源 + 提示换源与状态标注)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/composables/useEndpointFull.ts`(加 `requestDeclarationsOf`)
- Modify: `src/gimbal-platform/frontend/src/components/composer/JsonPathInput.vue`(`stateOf` prop + 状态徽标)
- Modify: `src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue`
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue`
- Modify: `src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/JsonPathInput.test.ts`、`src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts`

**Interfaces:**
- Consumes: Task 1 的 `injectablePathSetOf(leaves, decls)`;`endpointFullVersion` / `ensureEndpointFull` / `getEndpointFull`(`@/composables/useEndpointFull`);`iterFlat` / `resolveState` / `toTemplatePath`(`@/utils/declarations`)。
- Produces: `requestDeclarationsOf(step: unknown): DeclarationEntryView[] | undefined`;`JsonPathInput` 新 prop `stateOf?: (path: string) => 'form' | 'collapse' | 'carry' | undefined`。

- [ ] **Step 1: 写失败测试**

(a) `JsonPathInput.test.ts` 追加(该文件的 `CANDIDATES` 为 `['$.amount','$.items[0].sku','$.items[1].sku','$.items[2].qty']`,故 `$.` 下第 0 项段为 `amount`、第 1 项为 `items`):

```ts
  it('JP-8: 有 stateOf → 逐行标注字段状态;carry 附「平台带入」说明', async () => {
    const stateOf = (p: string) =>
      p === '$.amount' ? ('form' as const) : p === '$.items' ? ('carry' as const) : undefined
    const { input, items } = mountInput({ stateOf })
    await input().setValue('$.')
    expect(items()[0].text()).toContain('form')
    expect(items()[1].text()).toContain('carry')
    expect(items()[1].find('.jpi-state').attributes('title')).toContain('平台从上游带入')
  })

  it('JP-9: 无 stateOf → 不渲染状态徽标(零行为变化)', async () => {
    const { input, items } = mountInput()
    await input().setValue('$.')
    expect(items()[0].find('.jpi-state').exists()).toBe(false)
  })
```

(b) `AssertionRegistryEditor.test.ts` 追加:

```ts
it('ARE-11: 请求侧候选含契约声明的 carry 字段,并标注状态', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [
      { name: 'amount', path: '$.amount', state: 'form', required: true, description: '' },
      { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true, description: '' },
    ] },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG })
  const pathInput = w.findComponent(JsonPathInput)
  expect(pathInput.props('candidates')).toContain('$.customer_id')   // 声明面(body 里没有)
  expect(pathInput.props('candidates')).toContain('$.amount')
  expect((pathInput.props('stateOf') as any)('$.customer_id')).toBe('carry')
  w.unmount()
})

it('ARE-12: 契约声明但 body 无的路径 → 不再判悬空(由死转活)', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [{ name: 'amount', path: '$.amount', state: 'form', required: true, description: '' }] },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const reg = { entries: [{ id: 'inj-carry', name: 'carry 偏离',
    path: { stepIndex: 0, source: 'body', jsonpath: '$.customer_id' }, value: 1, asserts: [] }] }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: reg })
  await flushPromises()
  expect(w.findAll('.are-row')[0].classes()).not.toContain('are-dead')
  w.unmount()
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `npx vitest run src/components/composer/__tests__/JsonPathInput.test.ts src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: FAIL —— JP-8 无 `.jpi-state`;ARE-11 候选不含 `$.customer_id` 且 `stateOf` 未定义;ARE-12 条目仍显 `are-dead`。

- [ ] **Step 3: 实现 —— 契约声明面读取**

`src/composables/useEndpointFull.ts` 追加(文件顶部 import `DeclarationEntryView` 类型):

```ts
/** 步骤的契约声明面(读共享缓存;未拉取则发起)。上层投影用。
 *  无 endpoint_id / 未回填 → undefined(调用方降级为「只认 body 面」)。 */
export function requestDeclarationsOf(step: unknown): DeclarationEntryView[] | undefined {
  const eid = (step as { api?: { view_hints?: { endpoint_id?: string } } } | null | undefined)
    ?.api?.view_hints?.endpoint_id
  if (!eid) return undefined
  void ensureEndpointFull(eid)
  return getEndpointFull(eid)?.request?.declarations
}
```

- [ ] **Step 4: 实现 —— 四处判定同源**

四个文件各把 body 面投影换成可注入面投影。**改名 + 改调用点,两处都在同一文件内**(每个文件各一处定义、一处调用):

`AssertionRegistryEditor.vue`(定义约 221 行、调用在 `deadOf`/`deadCount`)、`CaseComposer.vue`(`registryBodyPathsOf` 约 521 行)、`RunPanelHost.vue`(`bodyPathsOfStep` 约 93 行)、`CaseDataSetsList.vue`(`bodyPathsOfStep` 约 136 行)——四处统一改成(以编辑器为例,其余三处按各自函数名替换):

```ts
/** 可注入面(spec v3.1 §2.1):body 现存 ∪ 契约声明(全状态 form/collapse/carry)。
 *  声明面来自共享 /full 缓存 —— 契约未回填时退化为 body 面(从严)。 */
function injectablePathsOfStep(si: number): ReadonlySet<string> {
  void endpointFullVersion.value
  const step = steps.value[si]
  return injectablePathSetOf(fieldPathsOf(step as any), requestDeclarationsOf(step))
}
```

同时把该文件里传给 `isDeadEntry(...)` / `registryIssues(...)` 的**第二个回调**换成新函数名(`deadOf` / `deadEntryIds` / `deadCount` 等消费点不必改,它们只闭包引用该回调)。

import 变动(四个文件各按现状增删):
- 增:`injectablePathSetOf` from `@/utils/assertion-registry`;
- 增:`requestDeclarationsOf`(以及 `endpointFullVersion`,若该文件尚未引)from `@/composables/useEndpointFull`;
- **删**该文件中已无引用的 `bodyPathSetOf`(`AssertionRegistryEditor.vue` / `CaseComposer.vue` / `RunPanelHost.vue` / `CaseDataSetsList.vue` 均只有这一处消费它)。

> `CaseDataSetsList.vue` / `RunPanelHost.vue` 的 `steps` 是 `ref<any[]>` 或 computed,`requestDeclarationsOf(step)` 直接吃该值即可。

- [ ] **Step 5: 实现 —— 提示层换源 + 状态标注**

`JsonPathInput.vue` 加 prop 与徽标:

```ts
  /** 建议行的字段状态标注(spec v3.1):无则完全不渲染徽标 */
  stateOf?: (path: string) => 'form' | 'collapse' | 'carry' | undefined
```
```ts
const props = withDefaults(defineProps<{ /* 既有 ··· */ }>(), { /* 既有 ··· */ stateOf: undefined })
/** carry 的说明文案:平台整包注入,注入条目会覆盖它(spec §2.3 执行序) */
function stateTitle(p: string): string {
  return props.stateOf?.(p) === 'carry' ? '默认由平台从上游带入,注入条目会覆盖它' : ''
}
```
模板里在 `.jpi-seg` 之后插:

```html
        <span
          v-if="stateOf && stateOf(s.path)"
          class="jpi-state"
          :class="`s-${stateOf(s.path)}`"
          :title="stateTitle(s.path)"
        >{{ stateOf(s.path) }}</span>
```
样式追加:

```css
.jpi-state {
  font-size: 10px; padding: 0 4px; border-radius: 3px;
  background: var(--c-bg-secondary, #f3f4f6); color: var(--c-text-tertiary, #6b7280);
}
.jpi-state.s-carry { background: #fef3c7; color: #92400e; }
```

`AssertionRegistryEditor.vue`:

```ts
/** 请求侧候选(spec v3.1 §2.1)= 可注入面(body 现存 ∪ 契约声明全状态) */
const pathCandidates = computed<string[]>(() => {
  void endpointFullVersion.value
  const step = steps.value[pendingPath.value.stepIndex]
  return [...injectablePathSetOf(fieldPathsOf(step as any), requestDeclarationsOf(step))]
})

/** 建议行状态标注:契约共识 + 步骤增量(与画布同一解析链 resolveState) */
function stateOfPendingPath(path: string): FieldState | undefined {
  const step = steps.value[pendingPath.value.stepIndex] as any
  const decls = requestDeclarationsOf(step)
  if (!decls?.length) return undefined
  const key = toTemplatePath(path)
  for (const e of iterFlat(decls)) {
    if (toTemplatePath(e.path) === key) return resolveState(e.path, e.state, step?.field_states)
  }
  return undefined
}
```
模板的 path 输入加 `:state-of="stateOfPendingPath"`。import 补 `iterFlat, resolveState, toTemplatePath`(`@/utils/declarations`)与 `FieldState` 类型。

- [ ] **Step 6: 跑测试确认通过**

Run: `npx vitest run src/components/composer/__tests__/JsonPathInput.test.ts src/views/__tests__/AssertionRegistryEditor.test.ts src/components/composer/__tests__/CaseComposerCanvas.test.ts src/components/composer/__tests__/RunPanelHost.test.ts src/views/__tests__/CaseDataSetsList.test.ts`
Expected: PASS(JsonPathInput 9、编辑器 13、画布 88、RunPanelHost 3、CaseDataSetsList 3)。
再跑 `npm run typecheck` → 零错误。

- [ ] **Step 7: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/composables/useEndpointFull.ts src/gimbal-platform/frontend/src/components/composer/JsonPathInput.vue src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue src/gimbal-platform/frontend/src/components/composer/__tests__/JsonPathInput.test.ts src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts && git commit -m "feat(assertion): 四处 dead 判定同源可注入面;提示含契约声明字段与状态标注

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 后端声明面取数(缓存 + TTL + fail-soft)

**Files:**
- Modify: `src/gimbal-platform/backend/app/core/config.py`(Plate 段加 TTL 设置)
- Create: `src/gimbal-platform/backend/app/services/endpoint_declarations.py`
- Test: `src/gimbal-platform/backend/tests/test_endpoint_declarations.py`

**Interfaces:**
- Consumes: `plate_client.get_client()`(既有共享 AsyncClient)、`field_state_resolution.catalog_paths(declarations) -> set[str]`(既有,返回树内全部条目 path)、`settings.DECLARED_PATHS_TTL_SEC`。
- Produces(Task 4 消费,签名逐字):
  - `async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None`(取不到 → `None`)
  - `def _reset_declared_paths_cache() -> None`(测试钩子)

- [ ] **Step 1: 写失败测试**(新建 `tests/test_endpoint_declarations.py`)

```python
"""声明面取数(spec v3.1 §3):契约 request.declarations 的 path 全集,
进程缓存 + TTL + fail-soft。"""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services import plate_client
from app.services.endpoint_declarations import (
    _reset_declared_paths_cache, declared_paths_of,
)


@pytest.fixture(autouse=True)
def _install_transport(monkeypatch):
    """plate 单例换成可编程 MockTransport;每例前清缓存。"""
    calls: list[str] = []
    payload = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": [
            {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
            {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True},
            {"name": "items", "path": "$.items", "state": "form", "required": False,
             "children": [{"name": "sku", "path": "$.items.sku", "state": "form", "required": True}]},
        ]}}},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=payload)

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test")
    )
    _reset_declared_paths_cache()
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 300.0)
    yield calls
    plate_client.set_client_for_tests(None)


async def test_declared_paths_of_returns_flat_path_set(_install_transport):
    paths = await declared_paths_of("fin.order.add")
    assert paths is not None
    assert {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"} <= set(paths)
    assert len(_install_transport) == 1


async def test_second_call_hits_cache(_install_transport):
    await declared_paths_of("fin.order.add")
    await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 1          # 缓存命中,只拉一次


async def test_ttl_zero_refetches(monkeypatch, _install_transport):
    await declared_paths_of("fin.order.add")
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)
    await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 2


async def test_failure_returns_none_and_does_not_cache(monkeypatch):
    state = {"fail": True, "calls": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json={
            "ok": True, "dim": "endpoint",
            "data": {"item": {"request": {"declarations": [
                {"name": "a", "path": "$.a", "state": "form", "required": True}]}}},
        })

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test")
    )
    _reset_declared_paths_cache()
    assert await declared_paths_of("ep-x") is None      # 失败 → 降级信号
    state["fail"] = False
    assert await declared_paths_of("ep-x") == frozenset({"$.a"})   # 失败不入缓存 → 可重试
    assert state["calls"] == 2
    plate_client.set_client_for_tests(None)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_endpoint_declarations.py -v`
Expected: FAIL —— `ModuleNotFoundError: app.services.endpoint_declarations`。

- [ ] **Step 3: 实现**

`app/core/config.py` —— Plate 段(`PLATE_BREAKER_THRESHOLD` 之后)加:

```python
    # 声明面取数缓存 TTL(秒),spec v3.1 §3:dispatch 悬空判定用的
    # 「契约声明 path 全集」进程缓存有效期。后端进程可能长期存活,
    # 而 plate 发版是运维事件 —— TTL 给快照过期兜一个上界。
    DECLARED_PATHS_TTL_SEC: float = 300.0
```

`app/services/endpoint_declarations.py`:

```python
"""契约声明面取数(spec v3.1 §3)— dispatch 悬空判定用。

语义:某端点 ``request.declarations`` 的 path 全集(树内全部条目,
模板形态;后端 ``catalog_paths`` 既有实现)。

纪律(与 carry 同款:增强不是前置条件):
* **fail-soft** — 任何故障(plate 不可达 / 非 200 / 信封缺 item / 形状异常)
  返回 ``None``,调用方降级为「只认 body 面」(从严),绝不阻塞执行;
* **不入缓存** — 失败不写缓存,下次调用可重试;
* **进程缓存 + TTL** — 成功入缓存,``DECLARED_PATHS_TTL_SEC`` 到期重取;
* **告警一次** — 同一端点在当前缓存窗口内至多一条 warning,不刷屏。
"""
from __future__ import annotations

import time
from typing import Any

from loguru import logger

from ..core.config import settings
from .field_state_resolution import catalog_paths
from .plate_client import get_client

_CACHE: dict[str, tuple[float, frozenset[str]]] = {}
_WARNED: set[str] = set()


def _reset_declared_paths_cache() -> None:
    """测试钩子:清空缓存与告警去重集。"""
    _CACHE.clear()
    _WARNED.clear()


async def declared_paths_of(endpoint_id: str) -> frozenset[str] | None:
    """端点声明的 request body path 全集;取不到 → None(调用方从严降级)。"""
    now = time.monotonic()
    hit = _CACHE.get(endpoint_id)
    if hit is not None and now - hit[0] < settings.DECLARED_PATHS_TTL_SEC:
        return hit[1]
    try:
        resp = await get_client().get(f"/api/endpoint/{endpoint_id}/full")
        if resp.status_code != 200:
            raise RuntimeError(f"plate status {resp.status_code}")
        item: Any = (resp.json().get("data") or {}).get("item")
        if not isinstance(item, dict):
            raise RuntimeError("no item in plate envelope")
        paths = frozenset(catalog_paths((item.get("request") or {}).get("declarations")))
    except Exception as e:  # noqa: BLE001 — 声明面不可得绝不阻塞判定
        if endpoint_id not in _WARNED:
            _WARNED.add(endpoint_id)
            logger.warning(
                "endpoint_declarations: {} 声明面不可得({}) — 悬空判定降级为 body 面",
                endpoint_id, e,
            )
        _CACHE.pop(endpoint_id, None)
        return None
    _CACHE[endpoint_id] = (now, paths)
    _WARNED.discard(endpoint_id)
    return paths
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_endpoint_declarations.py -v`
Expected: PASS(4 用例)。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/core/config.py src/gimbal-platform/backend/app/services/endpoint_declarations.py src/gimbal-platform/backend/tests/test_endpoint_declarations.py && git commit -m "feat(run): 契约声明面取数 — 进程缓存 + TTL + fail-soft 降级

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 后端判定放宽 + dispatcher 接线

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_injection.py`
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(§2.5)
- Test: `src/gimbal-platform/backend/tests/test_run_injection.py`(追加纯函数用例 + 集成用例)

**Interfaces:**
- Consumes: Task 3 的 `declared_paths_of(endpoint_id) -> frozenset[str] | None`。
- Produces: `entry_issues(entry, step_count, body_of, assert_targets_of, declared_of=None) -> list[dict]`(第 5 参缺省 `None` → 行为等于今天)。

- [ ] **Step 1: 写失败测试**(`tests/test_run_injection.py` 追加)

```python
# ── 可注入面(spec v3.1 §2.1):声明命中的路径不再判悬空 ──────────────
_DECLARED = frozenset({"$.bl_no", "$.customer_id", "$.items", "$.items.sku"})


def test_declared_path_is_resolvable_even_when_absent_from_body():
    """carry 字段(契约声明、body 无)放宽后可寻址 —— 本次 spec 的核心。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.customer_id"},
             "value": 1, "asserts": []}
    body_of = _body_of(DEF["steps"])          # DEF 的 body 只有 $.amount/$.bl_no
    targets = _targets_of(DEF["steps"])
    assert entry_issues(entry, 2, body_of, targets) == []            # 不传 → 旧行为
    assert entry_issues(entry, 2, body_of, targets, lambda si: _DECLARED) == []


def test_undeclared_path_still_dangling():
    """两边都没有 → 仍判死(拼写错误仍被抓)。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.ghost"},
             "value": 1, "asserts": []}
    issues = entry_issues(entry, 2, _body_of(DEF["steps"]), _targets_of(DEF["steps"]),
                          lambda si: _DECLARED)
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.ghost"} in issues


def test_instance_path_matches_template_declaration():
    """实例路径 $.items[0].sku 对齐契约模板声明 $.items.sku。"""
    body_of = _body_of([{"request": {"body": {}}}])       # body 里没有 items
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.items[0].sku"},
             "value": 1, "asserts": []}
    assert entry_issues(entry, 1, body_of, lambda si: set(),
                        lambda si: _DECLARED) == []


def test_empty_declared_of_falls_back_to_body_only():
    """降级:声明面为空集 → 判定等于旧的 body 面(从严)。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body",
                                     "jsonpath": "$.customer_id"},
             "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.customer_id"} in \
        entry_issues(entry, 2, _body_of(DEF["steps"]), _targets_of(DEF["steps"]),
                     lambda si: frozenset())
```

再追加一条 dispatcher 集成用例(声明面来自 plate 契约 stub):

```python
async def test_dispatcher_keeps_entry_anchored_on_declared_carry_path(
    client, plate_mock: PlateMock, monkeypatch
):
    """契约声明了 $.customer_id(carry,body 无)→ 条目不再被 skip;
    plate 不可得声明面时该条目仍被 skip(降级从严)。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(steps=[
        {"id": "s1", "api": {"kind": "api", "service": "fin-svc", "method": "POST",
                             "path": "/order", "headers": {},
                             "view_hints": {"endpoint_id": "ep-carry-x"}},
         "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
        {"id": "s2", "strategy": []},
    ], vars_map={"bl_no": "BL1"})
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-carry", "name": "carry 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 261, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"
    plate_mock.fulls["ep-carry-x"] = {"request": {"declarations": [
        {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
        {"name": "customer_id", "path": "$.customer_id", "state": "carry", "required": True},
    ]}}
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-carry"]})
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1                      # 未被 skip(此前会是 0 case)
    st = cases[0]["steps"][0]["strategy"]
    assert {"kind": "assign", "source": 261, "target": "$.request_body.customer_id"} in st

    # 降级:声明面不可得 → 同一条目重新被判死(skip),不炸 dispatch
    plate_mock.fulls.pop("ep-carry-x")
    from app.services.endpoint_declarations import _reset_declared_paths_cache
    _reset_declared_paths_cache()
    cases.clear()
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-carry"]})
    assert r.status_code == 201, r.text
    await asyncio.sleep(0.3)
    assert cases == []                          # 降级从严:仍 skip,静默不执行
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_injection.py -v`
Expected: FAIL —— 首条纯函数用例因 `entry_issues` 不收第 5 参而 TypeError;集成用例因条目被 skip(`len(cases) == 0`)断言失败。

- [ ] **Step 3: 实现 —— `run_injection.py`**

顶部补 `import re`;在 `entry_issues` 之前插入:

```python
_ARRAY_IDX_RE = re.compile(r"\[\d+\]")


def _template_path(jsonpath: str) -> str:
    """实例路径 → 模板形态(剥数组下标:$ .items[0].sku → $.items.sku)。
    复用前端 `declarations.toTemplatePath` 的同一规则 —— 契约声明是模板
    路径,条目路径是实例路径,判定必须两形态都试(spec v3.1 §2.1)。"""
    return _ARRAY_IDX_RE.sub("", jsonpath)


def _path_resolvable(jsonpath: str, body: Any, declared: Any) -> bool:
    """可解析 = 实例形态或模板形态命中声明面,或是某声明路径的容器前缀;
    否则退回 body 存在性(既有语义,body 面按实例路径精确判)。"""
    declared = declared or ()
    for form in (jsonpath, _template_path(jsonpath)):
        if form in declared:
            return True
        for p in declared:
            if p.startswith(form + ".") or p.startswith(form + "["):
                return True
    return exists(body or {}, jsonpath)
```

`entry_issues` 签名与 path 分支改为:

```python
def entry_issues(
    entry: dict[str, Any],
    step_count: int,
    body_of: Callable[[int], Any],
    assert_targets_of: Callable[[int], set[str]],
    declared_of: Callable[[int], Any] | None = None,
) -> list[dict[str, Any]]:
    """悬空检测(前端 utils/assertion-registry.ts 的 Python 同构,spec v3.1 §2):
    旧形状条目(无 path)/ stepIndex 越界 / path 不落在该步**可注入面**
    (契约声明 ∪ body 现存)上 / override 无匹配。

    ``declared_of`` 缺省 None → 只认 body 面(等于 spec v3 行为)。
    """
    _declared = declared_of or (lambda si: ())
```
```python
    elif not isinstance(jp, str) or not _path_resolvable(jp, body_of(si), _declared(si)):
        issues.append({"kind": "path-unresolvable", "stepIndex": si, "jsonpath": jp})
```

- [ ] **Step 4: 实现 —— dispatcher §2.5 接线**

`app/services/run_dispatcher.py` 的 §2.5 块(注释「2.5 断言注入条目」处)在条目循环**之前**插入:

```python
    # spec v3.1 §2.1/§3:判定面 = 契约声明 ∪ body 现存。只为**被选中条目
    # 实际引用到的步骤**取声明面(懒取,避免无谓的 plate 调用);
    # 取不到 → 空集 → 该步退回 body 面判定(从严,fail-soft 不阻塞)。
    steps_all = steps_from_payload(raw_payload) or []
    needed_steps: set[int] = set()
    for e in entries:
        if not isinstance(e, dict) or e.get("id") not in selected_ids:
            continue
        p = e.get("path")
        if isinstance(p, dict) and isinstance(p.get("stepIndex"), int):
            needed_steps.add(p["stepIndex"])

    async def _declared_for(si: int) -> tuple[int, frozenset[str]]:
        if si < 0 or si >= len(steps_all):
            return si, frozenset()
        step = steps_all[si] if isinstance(steps_all[si], dict) else {}
        eid = ((step.get("api") or {}).get("view_hints") or {}).get("endpoint_id")
        if not isinstance(eid, str) or not eid:
            return si, frozenset()
        got = await declared_paths_of(eid)
        return si, got or frozenset()

    declared_by_step: dict[int, frozenset[str]] = dict(
        await asyncio.gather(*[_declared_for(si) for si in sorted(needed_steps)])
    ) if needed_steps else {}
    _declared_of = lambda si: declared_by_step.get(si, frozenset())  # noqa: E731
```

并把 `entry_issues(...)` 调用补第 5 参:

```python
        issues = entry_issues(
            e,
            len(steps_from_payload(raw_payload) or []),
            _body_of(raw_payload),
            _assert_targets_of(raw_payload),
            _declared_of,
        )
```

顶部 import 补 `from .endpoint_declarations import declared_paths_of`(`asyncio` 应已在)。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_injection.py tests/test_run_cross_matrix.py tests/test_endpoint_declarations.py -v`
Expected: PASS(含既有回归)。
再跑邻近: `python -m pytest tests/test_run_m1_capabilities.py tests/test_run_baseline.py -q` → PASS。

- [ ] **Step 6: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/services/run_injection.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_injection.py && git commit -m "feat(run): 悬空判定放宽到契约声明面 — carry/collapse 字段可寻址(降级从严)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 真链路验证(carry 字段注入落到 wire)

**Files:**
- Create: `src/gimbal-platform/backend/tests/test_run_injectable_wire.py`

**Interfaces:**
- Consumes: Task 3/4 的全部产物;`gimbal_launcher`(真 CLI,`settings.GIMBAL_BIN`);PlateMock(`fulls` 契约面 + `behaviour="echo"`)。

- [ ] **Step 1: 写测试**(新建文件,整文件)

```python
"""T5 真链路:声明面放宽后,锚在 carry 字段的注入条目真的执行,
且引擎 Assign 把偏离值写到线上(平台 carry 注入被覆盖)—— spec §2.3/§7。

与其余集成用例的差别:launcher **不 patch**(走真 gimbal CLI),被测服务是
进程内 stub HTTP(断言到达的 body)。缺 GIMBAL_BIN 的环境跳过。
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not settings.GIMBAL_BIN and os.environ.get("GIMBAL_FORCE_REAL") != "1",
    reason="需要真 gimbal CLI(settings.GIMBAL_BIN)",
)

_EXEC_FINAL = {"done", "failed", "canceled"}


class _StubSut(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    hits: list[dict] = []

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        try:
            type(self).hits.append(json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            type(self).hits.append({"_raw": raw})
        out = json.dumps({"code": "0", "msg": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # noqa: D102
        pass


@pytest.fixture
def stub_sut():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubSut)
    _StubSut.hits = []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def test_carry_anchored_entry_runs_and_overrides_on_the_wire(
    client, plate_mock, stub_sut
):
    from .helpers import make_draft as _draft
    from .test_scenario_visibility_and_copy import _member
    from app.services.endpoint_declarations import _reset_declared_paths_cache

    _reset_declared_paths_cache()
    bob = await _member(client, "bob")
    draft = _draft(
        steps=[{
            "id": "s1",
            "api": {"kind": "api", "service": "stubsvc", "method": "POST", "path": "/pay",
                    "headers": {"Content-Type": "application/json"},
                    "view_hints": {"endpoint_id": "ep-carry-wire"}},
            "request": {"body": {"bl_no": "${var.bl_no}"}},
            "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                          "operator": "eq", "expected": "0"}],
        }],
        vars_map={"bl_no": "BL1"},
    )
    draft["assertion_registry"] = {"entries": [{
        "id": "inj-carry", "name": "carry 偏离",
        "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.customer_id"},
        "value": 261, "asserts": []}]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    plate_mock.behaviour = "echo"           # convert 原样回灌 → case 保留 Assign
    plate_mock.fulls["ep-carry-wire"] = {"request": {"declarations": [
        {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
        {"name": "customer_id", "path": "$.customer_id", "state": "carry", "required": True},
    ]}}

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": ["inj-carry"],
        "serviceBindings": {"stubsvc": {"url": stub_sut}},
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    for _ in range(600):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
        if ex["status"] in _EXEC_FINAL:
            break
        await asyncio.sleep(0.1)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)).json()["items"]
    assert len(rows) == 1
    assert rows[0]["injectionId"] == "inj-carry"      # 未被 skip(放宽生效)
    assert len(_StubSut.hits) == 1                    # 真引擎发出去了
    assert _StubSut.hits[0].get("customer_id") == 261 # Assign 覆盖:偏离落到线上
```

- [ ] **Step 2: 跑测试**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_injectable_wire.py -v`
Expected: PASS。

**为何本用例不做红先**:它验证的行为已由 Task 4 实现,红先阶段(条目被 skip → `injectionId == None`)由 Task 4 的 `test_dispatcher_keeps_entry_anchored_on_declared_carry_path` 承担。本用例不可替代的价值是**真引擎的 wire 证据**:断言 stub 被测服务**真的收到了** `customer_id == 261`,即放宽后条目不仅"不被 skip",而且偏离确实覆盖了平台带入值。
若此处 FAIL,说明 Task 4 的放宽未真正生效(条目仍被 skip),回 Task 4 查 —— 不要改本测试的断言。

- [ ] **Step 3: 跑邻近回归**

Run: `python -m pytest tests/ -q -k "inject or cross_matrix or endpoint_declarations"`
Expected: PASS。

- [ ] **Step 4: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/tests/test_run_injectable_wire.py && git commit -m "test(run): 真链路验证 — carry 字段条目执行且偏离落到线上 wire

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 文档修订标注 + 全量回归

**Files:**
- Modify: `docs/superpowers/specs/2026-09-12-assertion-registry-v3-merge-injection-design.md`(头部加修订标注)

- [ ] **Step 1: v3 spec 加修订标注**

在 v3 spec 头部「**取代**」段之后插入一行:

```markdown
**修订**: §2 的 `path-unresolvable` 判定面已被 `2026-09-12-injectable-path-surface-design.md`(spec v3.1)放宽为「契约声明 ∪ body 现存」;§1 裁定 2「任意字段直补」的成立范围随之覆盖 form/collapse/carry 三面
```

- [ ] **Step 2: 全量后端回归**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest -q`
Expected: PASS(全绿;重点看 `test_run_injection` / `test_run_cross_matrix` / `test_endpoint_declarations` / `test_run_injectable_wire`)。

- [ ] **Step 3: 全量前端回归 + 类型检查**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run`
Expected: PASS(全绿)。
Run: `npm run typecheck` → 零错误。

- [ ] **Step 4: plate/执行核零改动守卫**

以**实施开始前记录的 base**(SDD 台账里的 `BASE`,即 Task 1 派发前的 `git rev-parse HEAD`)为基:

Run: `cd /d/Gimbal/Gimbal && git diff --stat <BASE>...HEAD | grep -E "src/gimbal-plate/|src/gimbal/|export/gimbal.py" && echo "VIOLATION" || echo "CLEAN"`
Expected: `CLEAN`(把 `git rev-parse HEAD` 的结果逐字代入 `<BASE>`,不要用 `HEAD~1` —— 那会漏掉多提交任务的中间提交)。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add docs/superpowers/specs/2026-09-12-assertion-registry-v3-merge-injection-design.md && git commit -m "docs(spec): v3 §2 判定面修订标注 — 指向可注入面 spec

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 验收对照(spec ↔ 任务)

| spec 条目 | 落点 |
|---|---|
| §2.1 可注入面定义 + 两形态判定 | Task 1(`injectablePathSetOf` + `pathResolvable`) |
| §2.1 下标归一方向性 | Task 1 IS-3/IS-5 + Task 4 `_template_path` |
| §2.2 降级从严 + 告警 | Task 3(fail-soft + `_WARNED`)+ Task 4(空集退回 body)+ 集成用例 |
| §2.3 执行序(carry 可覆盖) | Task 4 集成用例 + Task 5 真链路 wire 证据 |
| §3 后端取声明面(缓存/TTL/fail-soft) | Task 3 |
| §3.3 `entry_issues` 签名 | Task 4 |
| §4.1 唯一投影 helper 四处接线 | Task 2 |
| §4.2 提示层换源 + 状态标注 | Task 2(`stateOf` + carry 说明) |
| §4.3 响应侧不变 | 无任务(不动) |
| §5.1 存量条目由死转活 | Task 4 集成用例(降级对照)+ Task 6 文档标注 |
| §5.2 只放宽不收紧 | Task 1 IS-5 + Task 4 `test_undeclared_path_still_dangling` |
| §6 边界(YAGNI) | 无任务(headers 源 / 快照表 等均不做) |
| §7 验收要点 | 各任务测试 + Task 6 全量门 |
