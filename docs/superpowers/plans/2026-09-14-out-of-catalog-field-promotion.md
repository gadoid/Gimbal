# 目录外请求字段提升进 form 树 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 目录外 body 字段可提升进 form 树(field_states 记 form/collapse 增量,值不动),修 plate 导出顶层目录外键丢弃,放宽后端 stale 判定。

**Architecture:** Canvas 层单点拼接 `effectiveDecls = [...目录, ...promotedDecls(合成条目)]`,下游 buildTree/searchCorpus/cascadeIncrements/extraBodyPaths 天然获得提升语义;carry 对提升面禁(UI 门禁 FieldStateSelect.noCarry + cascadeIncrements 防御纵深);后端 `validate_field_states` 加可选 body 参把 stale 判定放宽为「目录外且 body 无实有」;plate `_render_request_view` 末尾补顶层差集并入。

**Tech Stack:** Vue 3 + TypeScript + vitest + @vue/test-utils;FastAPI + pytest;plate(Pydantic)pytest。

**Spec:** [docs/superpowers/specs/2026-09-14-out-of-catalog-field-promotion-design.md](../specs/2026-09-14-out-of-catalog-field-promotion-design.md)(提交 854d775b,用户已确认)

## Global Constraints

- 分支:`feat/dataset-driven-refactor-phase2`(直接在其上续作,不建 worktree)。
- **选择性暂存**:每个 commit 只 `git add` 该任务「Files」列出的文件。以下永不 add/触碰:`gimbal-tmp/`、`probe_ui.js`、`reports/test-report.html`、`src/gimbal-plate/gimbal_plate/systems/fin/**`(工作树里有他人未提交改动)。
- **plate 冻结豁免仅限**:实现改 `src/gimbal-plate/gimbal_plate/export/platform.py` 的 `_render_request_view`(Task 8 一处),回归测试写 `tests/plate/test_v3_export_platform.py`;验证只跑 `python -m pytest tests/plate/test_v3_export_platform.py -q`,plate 套件其余文件零触碰。
- commit message 尾加:`Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 前端测试命令在 `src/gimbal-platform/frontend/` 下执行,后端在 `src/gimbal-platform/backend/` 下,plate 在仓库根 `d:/Gimbal/Gimbal/` 下。
- 每任务收尾跑:`npx vue-tsc --noEmit`(前端任务)确认 0 错误。
- 提升语义三铁律(spec §2/§3):①提升目标态只 form/collapse 不设 carry;②提升 = 渲染归属迁移,值通路(body)不动;③目录与提升面同 path 重叠时目录赢。

---

### Task 1: `promotedDecls` + `entryPaths`(declarations.ts 纯函数)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`(文件尾部 `extraSurfaceBindings` 之后新段)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts`(文件尾部追加 describe)

**Interfaces:**
- Consumes: 既有 `catalogPaths(decls): Set<string>`、`toTemplatePath(path): string`、`getByPath`(已 import)、`hasUsablePath`、`DeclarationEntryView`。
- Produces(Task 4/7 依赖,签名逐字):
  - `promotedDecls(decls: DeclarationEntryView[] | undefined | null, fieldStates: Record<string, string> | null | undefined, body: unknown): DeclarationEntryView[]`
  - `entryPaths(entries: DeclarationEntryView[] | undefined | null): Set<string>`

- [ ] **Step 1: 写失败测试**

在 `declarations.test.ts` 文件尾部追加(文件头部 import 列表补 `promotedDecls, entryPaths`;`mkDecl` fixture 文件内已有):

```ts
// ─── 目录外字段提升(2026-09-14 spec §4.1/§4.2)─────────────────────

describe('promotedDecls — 提升条目合成(§4.2)', () => {
  it('PR-1: 顶层标量提升 → 单叶合成条目(number 类型推断)', () => {
    const out = promotedDecls(undefined, { '$.extra': 'form' }, { extra: 7 })
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({
      name: 'extra', path: '$.extra', type: 'number', state: 'form',
      required: false, ui_kind: 'number', source_kind: 'independent',
    })
  })

  it('PR-2: 容器根提升 → object 条目,children 按 body 键递归展开(整子树进树)', () => {
    const out = promotedDecls(undefined, { '$.box': 'form' }, { box: { a: 1, nest: { b: 'x' } } })
    expect(out).toHaveLength(1)
    expect(out[0].type).toBe('object')
    const names = (out[0].children ?? []).map((c) => c.name)
    expect(names).toEqual(['a', 'nest'])
    const nest = out[0].children![1]
    expect(nest.type).toBe('object')
    expect(nest.children).toHaveLength(1)
    expect(nest.children![0]).toMatchObject({ name: 'b', type: 'string' })
  })

  it('PR-3: 深层叶提升 → 合成父壳只含提升子(兄弟键不成子,残留归 extras)', () => {
    const out = promotedDecls(undefined, { '$.box.b': 'form' }, { box: { a: 1, b: 'x' } })
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ path: '$.box', type: 'object' })
    expect(out[0].children).toHaveLength(1)
    expect(out[0].children![0]).toMatchObject({ path: '$.box.b', type: 'string' })
  })

  it('PR-4: 同根多深层候选折叠进同一父容器', () => {
    const out = promotedDecls(
      undefined, { '$.box.b': 'form', '$.box.c': 'collapse' }, { box: {} })
    expect(out).toHaveLength(1)
    expect(out[0].children ?? []).map((c) => c.path).toEqual(['$.box.b', '$.box.c'])
  })

  it('PR-5: body 无值(schema 差集行提升)→ string 叶条目', () => {
    const out = promotedDecls(undefined, { '$.ghost': 'form' }, {})
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ path: '$.ghost', type: 'string', ui_kind: 'text' })
  })

  it('PR-6: carry 值 / 目录内 path / 祖先子孙重叠 → 零产出(目录赢)', () => {
    const decls = [mkDecl({ name: 'y', path: '$.y' })]
    // carry 值:不是提升态
    expect(promotedDecls(decls, { '$.e': 'carry' }, { e: 1 })).toEqual([])
    // 目录内 path
    expect(promotedDecls(decls, { '$.y': 'form' }, { y: 1 })).toEqual([])
    // 目录条目的子孙($.y.z)与祖先($.y 命中)皆让位
    expect(promotedDecls(decls, { '$.y.z': 'form' }, { y: { z: 1 } })).toEqual([])
    expect(promotedDecls([mkDecl({ name: 'z', path: '$.y.z' })], { '$.y': 'form' }, { y: { z: 1 } })).toEqual([])
  })

  it('PR-7: 数组值 → children-less array 条目(行渲染交 buildNode 值驱动)', () => {
    const out = promotedDecls(undefined, { '$.arr': 'form' }, { arr: [1, 2] })
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ type: 'array', ui_kind: 'json' })
    expect(out[0].children).toBeUndefined()
  })

  it('PR-8: entryPaths 深层 path 全收集(含容器自身)', () => {
    const entries = [mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
      mkDecl({ name: 't', path: '$.cfg.t' }),
    ] })]
    expect(entryPaths(entries)).toEqual(new Set(['$.cfg', '$.cfg.t']))
  })

  it('PR-9: 拼接后 extraBodyPaths 残留行消失(§4.1 单点拼接语义)', () => {
    const decls = [mkDecl({ name: 'y', path: '$.y' })]
    const body = { y: 1, extra: 'E' }
    const fs = { '$.extra': 'form' }
    // 提升前:残留
    expect(extraBodyPaths(body, decls, fs)).toEqual([{ path: '$.extra', top: false }])
    // 提升后(拼接 effectiveDecls):残留消失
    const effective = [...decls, ...promotedDecls(decls, fs, body)]
    expect(extraBodyPaths(body, effective, fs)).toEqual([])
    // 树内出现该节点
    const tree = buildTree(effective, fs, body)
    expect(tree.map((n) => n.path)).toContain('$.extra')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/declarations.test.ts`
Expected: FAIL — `promotedDecls`/`entryPaths` 未导出(import 报错)。

- [ ] **Step 3: 实现**

在 `declarations.ts` 文件尾部(`extraSurfaceBindings` 之后)追加。`mk` 辅助放 `synth` 之前(避免 TDZ):

```ts
// ─── 目录外字段提升(2026-09-14 spec §4.1/§4.2)───────────────────────

/** 条目树全 path 集(含 children 深层)— Canvas 的 noCarry 门禁集合。 */
export function entryPaths(
  entries: DeclarationEntryView[] | undefined | null,
): Set<string> {
  const out = new Set<string>()
  const walk = (es: DeclarationEntryView[] | undefined) => {
    for (const e of es ?? []) {
      if (!hasUsablePath(e)) continue
      out.add(e.path)
      walk(e.children)
    }
  }
  walk(entries ?? [])
  return out
}

/** 合成条目基座(§4.2:required=false/描述空/independent;state 固定
 *  'form' —— 真实意图在 field_states 增量里,resolveState 链正常解析)。 */
function mkPromotedEntry(
  path: string, name: string,
  type: string, ui: DeclarationEntryView['ui_kind'],
): DeclarationEntryView {
  return {
    name, path, state: 'form', type,
    required: false, default: null, example: null,
    description: '', enum: null,
    ui_kind: ui, source_kind: 'independent', value_source: null,
    assertable: false,
  }
}

/**
 * 提升条目合成(spec §4.2):field_states 中值 ∈ {form, collapse} 且
 * 目录外的 path(模板化;精确与祖先/子孙重叠皆让位目录,§9)→ 合成
 * DeclarationEntryView 树。结构折叠:深层候选挂合成父容器;容器根
 * 的 children 按 body 实际键递归展开(整子树进树);仅提升叶时父壳
 * 只含提升子(兄弟残留留在 extras)。值不搬家 —— body 是唯一真源,
 * 这里只产渲染/编辑面的目录形状。
 */
export function promotedDecls(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates: Record<string, string> | null | undefined,
  body: unknown,
): DeclarationEntryView[] {
  const universe = catalogPaths(decls)
  const overlaps = (p: string, c: string) =>
    p === c || c.startsWith(`${p}.`) || p.startsWith(`${c}.`)
  const candidates = new Set<string>()
  for (const [rawP, s] of Object.entries(fieldStates ?? {})) {
    if (s !== 'form' && s !== 'collapse') continue
    const p = toTemplatePath(rawP)
    if (p === '$' || !p.startsWith('$.')) continue   // '$' 整包无提升语义
    let covered = false
    for (const c of universe) {
      if (overlaps(p, c)) { covered = true; break }
    }
    if (!covered) candidates.add(p)
  }
  if (!candidates.size) return []
  const relOf = (p: string) => p.replace(/^\$\.?/, '')
  const synth = (path: string, value: unknown): DeclarationEntryView => {
    const name = path.slice(path.lastIndexOf('.') + 1)
    if (Array.isArray(value)) return mkPromotedEntry(path, name, 'array', 'json')
    if (value !== null && typeof value === 'object') {
      return mkPromotedEntry(path, name, 'object', 'json')
    }
    if (typeof value === 'number') return mkPromotedEntry(path, name, 'number', 'number')
    if (typeof value === 'boolean') return mkPromotedEntry(path, name, 'boolean', 'boolean')
    return mkPromotedEntry(path, name, 'string', 'text')
  }
  const build = (path: string, deeper: string[]): DeclarationEntryView => {
    const value = getByPath(body, relOf(path))
    const entry = synth(path, value)
    if (entry.type !== 'object' && entry.type !== 'array') return entry
    // object:body 键整子树展开 + 深层候选并入(去重,body 键序在前)
    // array:children-less(行渲染交 buildNode 值驱动);有深层候选则
    // 作行模板(children 数组语义,buildNode 按行实例化)
    const childSet = new Set<string>()
    if (entry.type === 'object'
      && value !== null && typeof value === 'object' && !Array.isArray(value)) {
      for (const k of Object.keys(value as Record<string, unknown>)) {
        childSet.add(`${path}.${k}`)
      }
    }
    for (const d of deeper) childSet.add(d)
    if (!childSet.size) return entry
    return {
      ...entry,
      children: [...childSet].map((cp) => build(
        cp, deeper.filter((x) => x !== cp && x.startsWith(`${cp}.`)))),
    }
  }
  const isUnder = (p: string, root: string) => p.startsWith(`${root}.`)
  const roots = [...candidates].filter(
    (p) => ![...candidates].some((q) => q !== p && isUnder(p, q)))
  return roots.map((r) =>
    build(r, [...candidates].filter((c) => c !== r && isUnder(c, r))))
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/declarations.test.ts && npx vue-tsc --noEmit`
Expected: PASS(全文件含既有用例)+ vue-tsc 0。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/utils/declarations.ts src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts
git commit -m "feat(frontend): promotedDecls/entryPaths — 目录外提升条目合成(#3 T1)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: `cascadeIncrements` carry 防御(noCarryPaths)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`(`cascadeIncrements`,约 291 行)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts`

**Interfaces:**
- Consumes: Task 1 无关;既有 `cascadeIncrements(decls, fieldStates, path, target)`。
- Produces: `cascadeIncrements(decls, fieldStates, path, target, noCarryPaths?: Set<string>): Record<string, FieldState>` — 第 5 参可选,Task 7 传 `entryPaths(promotedDecls(...))`。

- [ ] **Step 1: 写失败测试**

`declarations.test.ts` 追加(找到既有 cascadeIncrements 的 describe 或新建):

```ts
describe('cascadeIncrements — 提升面 carry 防御(2026-09-14 §4.4)', () => {
  // 合成条目(promotedDecls 产物形状;locate 可命中)
  const SYNTH = [mkDecl({ name: 'extra', path: '$.extra', type: 'string' })]
  const noCarry = new Set(['$.extra'])

  it('PR-10: noCarryPaths 命中 + 目标 carry → 空批(目录外不可能 carry)', () => {
    expect(cascadeIncrements(SYNTH, { '$.extra': 'form' }, '$.extra', 'carry', noCarry))
      .toEqual({})
  })

  it('PR-11: noCarryPaths 命中 + 目标 form/collapse → 正常单条增量', () => {
    expect(cascadeIncrements(SYNTH, { '$.extra': 'form' }, '$.extra', 'collapse', noCarry))
      .toEqual({ '$.extra': 'collapse' })
  })

  it('PR-12: 不传 noCarryPaths(旧调用方)→ 行为不变', () => {
    expect(cascadeIncrements(SYNTH, { '$.extra': 'form' }, '$.extra', 'carry'))
      .toEqual({ '$.extra': 'carry' })
  })
})
```

注:`cascadeIncrements` 若未在文件头 import 列表中,补进。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/declarations.test.ts`
Expected: FAIL — PR-10 得到 `{'$.extra': 'carry'}` 而非 `{}`(第 5 参被忽略,PR-11/12 意外通过)。

- [ ] **Step 3: 实现**

`cascadeIncrements` 签名与函数体头部(`const out` 与 `isValidState` 校验之后、`locate` 之前)插入一行:

```ts
export function cascadeIncrements(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates: Record<string, string> | null | undefined,
  path: string,
  target: FieldState,
  noCarryPaths?: Set<string>,
): Record<string, FieldState> {
  const out: Record<string, FieldState> = {}
  if (!isValidState(target)) return out
  // 提升面 carry 防御纵深(2026-09-14 §4.4):目录外 path 结构上不可能
  // carry(carry 面/值表只遍历目录)—— UI 门禁(FieldStateSelect.noCarry)
  // 是第一道,这里兜底搜索框等旁路。form/collapse 不受限。
  if (target === 'carry' && noCarryPaths?.has(path)) return out
  // ……(locate 及其后全部保持原样)
```

同步更新该函数 docstring 的「目录外 path / 词表外 target → 空对象」条目为「目录外 path(不在 decls 中)/ 词表外 target → 空对象;noCarryPaths 命中且目标 carry → 空批(§4.4)」。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/declarations.test.ts && npx vue-tsc --noEmit`
Expected: PASS + vue-tsc 0。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/utils/declarations.ts src/gimbal-platform/frontend/src/utils/__tests__/declarations.test.ts
git commit -m "feat(frontend): cascadeIncrements noCarryPaths — 提升面 carry 防御纵深(#3 T2)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: `FieldStateSelect` noCarry prop

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldStateSelect.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldStateSelect.test.ts`(新建)

**Interfaces:**
- Produces: prop `noCarry?: boolean` — carry `<option>` 不渲染(Task 4/5 传)。

- [ ] **Step 1: 写失败测试**(新文件)

```ts
/** FieldStateSelect — 三态下拉;noCarry 门禁(2026-09-14 §4.4)。 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FieldStateSelect from '@/components/composer/FieldStateSelect.vue'

describe('FieldStateSelect — noCarry', () => {
  it('缺省三态齐(现行为)', () => {
    const w = mount(FieldStateSelect, { props: { state: 'form' } })
    expect(w.findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse', 'carry'])
  })
  it('noCarry → carry 选项缺席', () => {
    const w = mount(FieldStateSelect, { props: { state: 'form', noCarry: true } })
    expect(w.findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse'])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldStateSelect.test.ts`
Expected: FAIL — noCarry 未知 prop,两例选项均为三态。

- [ ] **Step 3: 实现**

模板 carry option 加 v-if;props 加字段:

```vue
<option v-if="!noCarry" value="carry">carry</option>
```

```ts
defineProps<{
  /** 解析态(增量 × 目录默认合成后,buildTree 节点携带) */
  state: FieldState
  /** 该条目存在显式覆盖(显示 ↺ 重置入口) */
  overlay?: boolean
  /** 提升面门禁(2026-09-14 §4.4):carry 不提供 —— 目录外结构上
   *  不可能 carry(carry 面/值表只遍历目录),选了会静默丢渲染。 */
  noCarry?: boolean
}>()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldStateSelect.test.ts && npx vue-tsc --noEmit`
Expected: PASS + vue-tsc 0。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer/FieldStateSelect.vue src/gimbal-platform/frontend/src/components/composer/__tests__/FieldStateSelect.test.ts
git commit -m "feat(frontend): FieldStateSelect noCarry — 提升面 carry 门禁(#3 T3)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: FieldForm — promotedPaths 门禁 + extras 提升按钮

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(props/emits/extras 模板/全部 FieldStateSelect 实例/nested 转发/import)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.promoted.test.ts`(新建;惯例参照 FieldForm.deep.test.ts 的 mountTree 包装)

**Interfaces:**
- Consumes: Task 3 的 `noCarry` prop;`toTemplatePath`(declarations.ts 已导出)。
- Produces(Task 7 依赖):
  - prop `promotedPaths?: Set<string>`
  - emit `'promote': [path: string]`(extras 残留行提升按钮;path 已模板化)

- [ ] **Step 1: 写失败测试**(新文件)

```ts
/** FieldForm — 提升面(2026-09-14 spec §4.3/§4.4):
 *  extras 残留行「提升」按钮(emit promoted,模板路径);
 *  promotedPaths 命中的树节点行尾下拉无 carry(含嵌套容器内)。
 *  mount 包装镜像 FieldForm.deep.test.ts(父持 body ref)。 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import { buildTree } from '@/utils/declarations'
import type { DeclarationEntryView, FieldState } from '@/types/plate'

function mkDecl(over: Partial<DeclarationEntryView> = {}): DeclarationEntryView {
  return {
    name: 'x', path: '$.x', required: false, description: '',
    ui_kind: 'text', source_kind: 'independent', assertable: false,
    ...over,
  }
}

function mountForm(opts: {
  decls?: DeclarationEntryView[]
  nodes?: ReturnType<typeof buildTree>
  deepExtras?: Array<{ path: string; top: boolean }>
  promotedPaths?: Set<string>
  body?: unknown
}) {
  const body = ref<unknown>(opts.body ?? {})
  const promoted: string[] = []
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        nodes: opts.nodes ?? buildTree(opts.decls ?? [], undefined, body.value),
        deepExtras: opts.deepExtras ?? [],
        body: body.value,
        stateControl: true,
        promotedPaths: opts.promotedPaths,
        'onUpdate:body': (v: unknown) => { body.value = v },
        'onPromote': (p: string) => { promoted.push(p) },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, promoted }
}

describe('FieldForm — extras 提升(§4.3)', () => {
  it('FF-P1: 残留行「提升」按钮 → emit promoted(实例路径剥 [i] 模板化)', async () => {
    const { w, promoted } = mountForm({
      deepExtras: [{ path: '$.arr[0].x', top: false }, { path: '$.extra', top: false }],
      body: { arr: [{ x: 1 }], extra: 'E' },
    })
    await w.find('.extras-toggle').trigger('click')
    const btns = w.findAll('.extra-promote')
    expect(btns).toHaveLength(2)
    await btns[0].trigger('click')   // $.arr[0].x → 模板化 $.arr.x
    await btns[1].trigger('click')
    expect(promoted).toEqual(['$.arr.x', '$.extra'])
  })

  it('FF-P2: 不传 stateControl 的复用面无提升按钮(StrategyForm 零变化)', () => {
    const w = mount(FieldForm, {
      props: { nodes: [], body: {}, deepExtras: [{ path: '$.extra', top: false }] },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('.extra-promote').exists()).toBe(false)
  })
})

describe('FieldForm — promotedPaths carry 门禁(§4.4)', () => {
  it('FF-P3: 命中节点的行尾下拉无 carry;未命中节点三态齐', async () => {
    // 目录树 $.cfg{t} + 提升树 $.extra(promotedDecls 形状:顶层叶)
    const cfg = mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
      mkDecl({ name: 't', path: '$.cfg.t' }),
    ] })
    const extra = mkDecl({ name: 'extra', path: '$.extra', type: 'string' })
    const { w } = mountForm({
      nodes: buildTree([cfg, extra], undefined, { cfg: { t: 1 }, extra: 2 }),
      promotedPaths: new Set(['$.extra']),
      body: { cfg: { t: 1 }, extra: 2 },
    })
    const sels = w.findAll('.fss-sel')
    expect(sels).toHaveLength(2)
    // cfg 头(文档序首个)+ extra 叶:cfg 三态,extra 无 carry
    expect(sels[0].findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse', 'carry'])
    expect(sels[1].findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse'])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldForm.promoted.test.ts`
Expected: FAIL — `.extra-promote` 不存在 / carry 选项仍三态 / `onPromote` 未声明(控制台警告 + promoted 空)。

- [ ] **Step 3: 实现**

五处改动(`FieldForm.vue`):

① script 头部 import 区加值导入(既有 declarations import 是 type-only):

```ts
import { toTemplatePath } from '@/utils/declarations'
```

② props 加字段(放 `stateControl` 之后):

```ts
  /** 提升面 path 集(Canvas 传入,entryPaths(promotedDecls(...))):
   *  命中节点的行尾下拉禁 carry(§4.4 — 目录外结构上不可能 carry)。
   *  复用处不传 → 行为不变。 */
  promotedPaths?: Set<string>
```

③ emits 加(放 `fieldState` 之后):

```ts
  /** extras 残留行提升(§4.3):path 已模板化(剥 [i]);Canvas 落
   *  applyFieldStates({[path]: 'form'})—— 不走 cascade(提升时
   *  合成条目尚不存在,级联定位必然空批)。 */
  'promote': [path: string]
```

④ 模板:全部 `<FieldStateSelect` 实例(约 5 处:object 头 68 行、array 头 171 行、leaf 296 行、平铺行 411 行、749 区行尾)加 prop:

```vue
:no-carry="promotedPaths?.has(templatePathOf(item))"
```

(各处 `templatePathOf(item)` 与既有 `@change` 同参,原样照抄该实参。)

⑤ 模板:嵌套递归的每个 `<FieldForm` 实例(object 子体 109 行、数组行组内、深层递归处 —— 全文搜 `nested` prop 的实例)转发:

```vue
:promoted-paths="promotedPaths"
```

⑥ extras 区 `.extra-control` 内、`.extra-del` 按钮之后加(在 `v-if="row.inBody"` 的删除按钮外——契约差集行也可提升):

```vue
<button
  v-if="stateControl"
  type="button"
  class="extra-promote"
  title="提升进 form 树(field_states 记增量,值不动;↺ 重置回此区)"
  :disabled="readonly"
  @click="emit('promote', toTemplatePath(row.path))"
>↥</button>
```

⑦ style 区加(`.extra-del` 同款):

```css
.extra-promote {
  border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc;
  color: #4f46e5; font-size: 11px; line-height: 1; cursor: pointer;
  padding: 3px 6px;
}
.extra-promote:hover { border-color: var(--accent); background: #eef2ff; }
.extra-promote:disabled { opacity: 0.5; cursor: not-allowed; }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldForm.promoted.test.ts src/components/composer/__tests__/FieldForm.deep.test.ts src/components/composer/__tests__/FieldForm.test.ts && npx vue-tsc --noEmit`
Expected: PASS(新 3 例 + 既有 FieldForm 套件不回归)+ vue-tsc 0。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer/FieldForm.vue src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.promoted.test.ts
git commit -m "feat(frontend): FieldForm extras 提升按钮 + promotedPaths carry 门禁(#3 T4)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: FieldSearchRow.promoted + FieldStateSearch 透传

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/declarations.ts`(`FieldSearchRow` 接口,约 231 行)
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldStateSearch.vue`(FieldStateSelect 加 no-carry)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldStateSearch.test.ts`(追加)

**Interfaces:**
- Consumes: Task 3 `noCarry`。
- Produces: `FieldSearchRow.promoted?: boolean`(Task 7 的 corpus 投影写入)。

- [ ] **Step 1: 写失败测试**

先看 `FieldStateSearch.test.ts` 既有 mount 惯例(它直接传 corpus prop),追加:

```ts
it('提升行(promoted)下拉无 carry — 搜索旁路门禁(§4.4)', async () => {
  // 按既有用例的 mount 方式;corpus 一行 promoted:true
  const w = mount(FieldStateSearch, {
    props: { corpus: [
      { path: '$.extra', name: 'extra', description: '', type: 'string',
        resolved: 'form', overlay: true, breadcrumb: '', promoted: true },
    ] },
  })
  await w.find('input.fss-search-input').setValue('extra')
  const sel = w.find('.fss-sel')
  expect(sel.findAll('option').map((o) => o.attributes('value')))
    .toEqual(['form', 'collapse'])
})
```

(mount import 等按该文件既有头部;若该文件用不同包装,照其惯例改写挂载行,断言不变。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldStateSearch.test.ts`
Expected: FAIL — carry 选项仍在。

- [ ] **Step 3: 实现**

① `declarations.ts` `FieldSearchRow` 接口加字段(`overlay` 之后):

```ts
  /** 提升面行(2026-09-14 §4.4):Canvas 投影写入;搜索行下拉禁 carry */
  promoted?: boolean
```

② `FieldStateSearch.vue` 行内 FieldStateSelect(34 行)加:

```vue
:no-carry="row.promoted"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldStateSearch.test.ts && npx vue-tsc --noEmit`
Expected: PASS + vue-tsc 0。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/utils/declarations.ts src/gimbal-platform/frontend/src/components/composer/FieldStateSearch.vue src/gimbal-platform/frontend/src/components/composer/__tests__/FieldStateSearch.test.ts
git commit -m "feat(frontend): 搜索语料提升行 promoted 标记 — 搜索旁路 carry 门禁(#3 T5)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 后端 stale 判定放宽 + 前端 API 加 body 参

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/field_state_resolution.py`(`validate_field_states` + 新 helper)
- Modify: `src/gimbal-platform/backend/app/routers/endpoint_catalog.py`(`FieldStatesValidateRequest` + 路由透传,37-40 与 164 行)
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`(`validateEndpointFieldStates`,267 行)
- Test: `src/gimbal-platform/backend/tests/test_field_state_resolution.py`(追加)

**Interfaces:**
- Consumes: 无前置任务依赖。
- Produces(Task 7 依赖):
  - `validate_field_states(declarations, field_states=None, body=None) -> dict[str, list[dict]]`(body 实例路径模板化后命中 → 不报 stale)
  - HTTP:`POST /api/endpoint-catalog/{id}/field-states/validate` 接受可选 `body` 键
  - 前端 `validateEndpointFieldStates(endpointId: string, fieldStates: Record<string, string>, body?: unknown): Promise<FieldStatesVerdict>`

- [ ] **Step 1: 写失败测试**

`test_field_state_resolution.py` — `TestValidateFieldStates` 类内(`test_stale_path_soft_warning` 之后)追加:

```python
    def test_stale_path_body_present_relaxed(self) -> None:
        """2026-09-14 §5.1:目录外但 body 实有(提升字段)→ 不报 stale。"""
        body = {"ghost": 1, "gone": {"form": 1}, "arr": [{"x": 1}]}
        out = validate_field_states(
            [_TOP_FORM_LEAF],
            {"$.ghost": "form", "$.gone.form": "form", "$.arr.x": "form"},
            body,
        )
        assert out["warnings"] == []

    def test_stale_path_body_partial(self) -> None:
        """body 传了但该 path 无实有 → 仍 stale(诚实警告)。"""
        out = validate_field_states(
            [_TOP_FORM_LEAF], {"$.ghost": "form"}, {"other": 1})
        assert [w["code"] for w in out["warnings"]] == ["stale_path"]
        assert out["warnings"][0]["path"] == "$.ghost"

    def test_stale_path_no_body_arg_unchanged(self) -> None:
        """不传 body(旧调用方)→ 行为不变(全部目录外报 stale)。"""
        out = validate_field_states(
            [_TOP_FORM_LEAF], {"$.ghost": "form", "$.gone.form": "form"},
            None)
        assert [w["code"] for w in out["warnings"]] == ["stale_path", "stale_path"]
```

路由级(文件尾部既有路由测试后追加;`_VALIDATE_DECLS`/`register_and_login` 已有):

```python
async def test_validate_route_body_relaxes_stale(client, plate) -> None:
    """§5.1:请求体随行 → 提升字段(目录外 body 实有)不报 stale。"""
    plate.fulls = {"fin.settlement.create_order":
                   {"request": {"declarations": _VALIDATE_DECLS}}}
    headers = await register_and_login(client)
    r = await client.post(
        "/api/endpoint-catalog/fin.settlement.create_order"
        "/field-states/validate",
        headers=headers,
        json={"field_states": {"$.extra_flag": "form"},
              "body": {"extra_flag": True}})
    assert r.status_code == 200, r.text
    assert r.json() == {"errors": [], "warnings": []}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_field_state_resolution.py -q`
Expected: FAIL — `validate_field_states` 不收第三参(TypeError)+ 路由忽略 body 键(stale 警告仍在)。

- [ ] **Step 3: 实现**

① `field_state_resolution.py` — 模块级新 helper(放 `validate_field_states` 之前)+ 签名 + stale 循环改造:

```python
def _body_template_paths(body: Any) -> set[str]:
    """body 实例路径集合(模板形态:$.a.b,数组下标剥除)—— stale 判定
    的实有参照(2026-09-14 §5.1)。容器自身与叶子都收:提升根($.a 容器)
    与提升叶($.a.b)都应命中。防御:非 dict 读穿为空集。"""
    out: set[str] = set()

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{prefix}.{k}" if prefix != "$" else f"$.{k}"
                out.add(p)
                _walk(v, p)
        elif isinstance(node, list):
            for item in node:
                _walk(item, prefix)

    if isinstance(body, dict):
        _walk(body, "$")
    return out
```

`validate_field_states` 签名与 docstring 的 `stale_path` 条目更新:

```python
def validate_field_states(
    declarations: Any, field_states: Any = None, body: Any = None,
) -> dict[str, list[dict]]:
```

> `stale_path`(warning):field_states 含目录外 path 且 body 无实有
> (§5.1,2026-09-14:提升字段 = 目录外但 body 实有 → 放行;不传 body
> = 旧行为,全部目录外报 stale)。

stale 循环改为:

```python
    if isinstance(field_states, dict):
        universe = catalog_paths(declarations)
        body_paths = _body_template_paths(body) if body is not None else None
        for path in sorted(set(field_states) - universe):
            if body_paths is not None and path in body_paths:
                continue
            warnings.append({
                "code": "stale_path", "path": path,
                "message": f"目录外 path {path}(plate 目录未声明;已忽略)",
            })
```

② `endpoint_catalog.py`:

```python
class FieldStatesValidateRequest(BaseModel):
    """§3.5 配置编辑校验入参:step 的 field_states 增量(可空)+
    step.request.body(可选,2026-09-14 §5.1:stale 判定实有参照)。"""
    field_states: dict[str, str] = Field(default_factory=dict)
    body: Any | None = None
```

(`Any` 已在 typing import 或补 `from typing import Any`。)路由末行改:

```python
    return validate_field_states(decls, body.field_states, body.body)
```

③ 前端 `scenario-composer.ts`:

```ts
export async function validateEndpointFieldStates(
  endpointId: string,
  fieldStates: Record<string, string>,
  body?: unknown,
): Promise<FieldStatesVerdict> {
  const { data } = await http.post<FieldStatesVerdict>(
    `/endpoint-catalog/${encodeURIComponent(endpointId)}/field-states/validate`,
    { field_states: fieldStates, ...(body !== undefined ? { body } : {}) },
  )
  return data
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_field_state_resolution.py tests/test_endpoint_catalog_proxy.py -q`
Expected: PASS(新 4 例 + 既有不回归)。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/field_state_resolution.py src/gimbal-platform/backend/app/routers/endpoint_catalog.py src/gimbal-platform/frontend/src/api/scenario-composer.ts src/gimbal-platform/backend/tests/test_field_state_resolution.py
git commit -m "feat(backend): stale 判定放宽 — body 随行,目录外提升字段放行(#3 T6)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: Canvas 接线(effectiveDecls 单点拼接)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(约 651-677 行区 + onFieldState/applyFieldStates + 请求签 FieldForm 实例)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(追加 describe)

**Interfaces:**
- Consumes: Task 1 `promotedDecls`/`entryPaths`;Task 2 `noCarryPaths` 参;Task 4 `promotedPaths` prop / `promote` emit;Task 6 `validateEndpointFieldStates` 第三参;既有 `mkStep`/`mountCanvas`/`validateEndpointFieldStates` mock(测试文件内)。
- Produces: 无(终端接线任务)。

- [ ] **Step 1: 写失败测试**

`CaseComposerCanvas.test.ts` 追加 describe(文件内 `validateEndpointFieldStates` 已在 mock 列表):

```ts
// ── 目录外字段提升(2026-09-14 spec §4)──────────────────────────

describe('CaseComposerCanvas — 目录外字段提升(#3)', () => {
  it('PROMO-1: extras 残留提升 → field_states 落键/树出现/extras 消失/validate 携 body', async () => {
    const step = mkStep({
      request: { kind: 'request', body: { orderId: 'ord-1', extra: 'E' } } as any,
    })
    const { w } = mountCanvas([step])
    await flushPromises()
    // extras 区默认折叠:展开后见 $.extra 残留行 + 提升按钮
    await w.find('.extras-toggle').trigger('click')
    const btn = w.find('.extra-promote')
    expect(btn.exists()).toBe(true)
    expect(w.findAll('.path-badge').map((b) => b.text())).not.toContain('$.extra')
    await btn.trigger('click')
    await flushPromises()
    // field_states 落 form 增量;validate 携 body(§5.1)
    expect((step as any).field_states).toEqual({ '$.extra': 'form' })
    expect(validateEndpointFieldStates)
      .toHaveBeenCalledWith('ep-1', { '$.extra': 'form' },
        { orderId: 'ord-1', extra: 'E' })
    // 树内出现 $.extra 节点;extras 区提升按钮随残留行消失
    expect(w.findAll('.path-badge').map((b) => b.text())).toContain('$.extra')
    expect(w.find('.extra-promote').exists()).toBe(false)
  })

  it('PROMO-2: 提升节点行尾下拉无 carry;↺ 重置回 extras', async () => {
    const step = mkStep({
      request: { kind: 'request', body: { orderId: 'ord-1', extra: 'E' } } as any,
      field_states: { '$.extra': 'form' } as any,
    })
    const { w } = mountCanvas([step])
    await flushPromises()
    // 树内 $.extra 节点行尾下拉:两态(无 carry)
    const badges = w.findAll('.path-badge')
    const extraSel = badges
      .filter((b) => b.text() === '$.extra')[0]
      .element.closest('.node-head, .field-row')!
    const sel = extraSel.querySelector('.fss-sel') as HTMLSelectElement
    expect([...sel.options].map((o) => o.value)).toEqual(['form', 'collapse'])
    // ↺ 重置(overlay 行)→ field_states 清空 → 回 extras
    const reset = extraSel.querySelector('.fss-reset') as HTMLButtonElement
    reset.click()
    await flushPromises()
    expect((step as any).field_states).toBeUndefined()
    expect(w.findAll('.path-badge').map((b) => b.text())).not.toContain('$.extra')
  })
})
```

注:PROMO-2 的 DOM 定位若与实际结构有出入(叶子行 class 非 `.field-row`),以实际渲染为准调整选择器,**断言语义不变**(两态下拉/重置回退)。`validateEndpointFieldStates` mock 断言前如 beforeEach 未 reset,先 `vi.mocked(validateEndpointFieldStates).mockClear()`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts -t PROMO`
Expected: FAIL — `.extra-promote` 不存在(Canvas 未传 stateControl 之外还需 FieldForm 已有按钮但 Canvas 未接 promote → PROMO-1 emit 无落点;且 effectiveDecls 未拼接 → 树无 $.extra)。

- [ ] **Step 3: 实现**

`CaseComposerCanvas.vue` 六处:

① import 区补(declarations 既有 import 行内加 `promotedDecls, entryPaths`)。

② `stepDecls` 之后加两个 computed:

```ts
/** 提升条目(2026-09-14 spec §4.1):field_states 目录外 form/collapse
 *  增量 → 合成目录条目,拼进 effectiveDecls —— buildTree/searchCorpus/
 *  cascadeIncrements/extraBodyPaths 天然获得提升语义(单点拼接)。 */
const promotedList = computed(() => promotedDecls(
  stepDecls(currentStep.value), currentStep.value?.field_states,
  currentStep.value?.request?.body))

/** 目录 + 提升条目(消费面一律喂这个;目录在前,文档序稳定) */
const effectiveDecls = computed(() => [
  ...(stepDecls(currentStep.value) ?? []),
  ...promotedList.value,
])

/** 提升面 path 集(含合成子树深层)— noCarry 门禁(FieldForm/cascade) */
const promotedPathSet = computed(() => entryPaths(promotedList.value))
```

③ 四个消费 computed 换源:

```ts
function fieldBindings(step: StepView | undefined): IOFieldBinding[] {
  // 每步各自拼接(非 currentStep 专属;stepDecls 同款按 step 取)
  return formBindings(
    [...(stepDecls(step) ?? []),
     ...promotedDecls(stepDecls(step), step?.field_states, step?.request?.body)],
    step?.field_states)
}
```

(注:`fieldBindings` 接任意 step,不能复用 currentStep 的 computed —— 内联拼接同式。)

```ts
const requestNodes = computed<FieldTreeNode[]>(() => {
  const step = currentStep.value
  return buildTree(effectiveDecls.value, step?.field_states, step?.request?.body)
})

const fieldSearchCorpus = computed(() =>
  searchCorpus(effectiveDecls.value, currentStep.value?.field_states)
    .map((r) => ({ ...r, promoted: promotedPathSet.value.has(r.path) })))

const requestExtras = computed(() =>
  extraBodyPaths(currentStep.value?.request?.body, effectiveDecls.value,
    currentStep.value?.field_states))
```

④ `onFieldState` 级联换源 + 防御:

```ts
  await applyFieldStates(
    cascadeIncrements(effectiveDecls.value, step.field_states, path, state,
      promotedPathSet.value))
```

⑤ `applyFieldStates` 校验携 body:

```ts
    const verdict = await validateEndpointFieldStates(
      eid, step.field_states ?? {}, step.request?.body)
```

⑥ 模板接线:请求签 FieldForm 实例(约 248 行,`:nodes="requestNodes"` 处)加:

```vue
:promoted-paths="promotedPathSet"
@promote="(p: string) => applyFieldStates({ [p]: 'form' })"
```

(响应签契约参考实例不接 —— 该面无 stateControl,语义无关。)

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts && npx vue-tsc --noEmit`
Expected: PASS(新 2 例 + Canvas 全套不回归)+ vue-tsc 0。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts
git commit -m "feat(frontend): Canvas effectiveDecls 单点拼接 — 目录外字段提升接线(#3 T7)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: plate 导出 — 顶层目录外键并入(冻结豁免一处)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/export/platform.py`(`_render_request_view`,步骤 3 之后;258-355 行区)
- Test: `tests/plate/test_v3_export_platform.py`(追加 Test 类;**只跑该文件**)

**Interfaces:**
- Consumes: 既有 `_path_segs`/`iter_declarations`;fixture `_deep_binding_ep`/`_FLAT_ORDER_ID`(测试文件内)。
- Produces: 无(导出行为修复:`_render_request_view` ep 存在时 body 顶层未声明键整块保留)。

- [ ] **Step 1: 写失败测试**

`tests/plate/test_v3_export_platform.py` 文件尾部追加(`_deep_binding_ep`/`DeclarationEntry`/`Request` 已在文件头 import):

```python
# ── 顶层目录外键并入(2026-09-14 提升配套;冻结豁免一处) ──────────


class TestOutOfCatalogTopLevelKeys:
    """目录只覆盖声明面 —— body 顶层未声明键(含子树)在 carry 容器
    并入/fields_meta/声明叶补全三步全不沾,此前被静默丢弃(保存→导出
    →重载丢数据)。修复:步骤 3 之后补顶层差集整块并入。"""

    def test_undeclared_top_level_key_preserved(self) -> None:
        ep = _deep_binding_ep([_FLAT_ORDER_ID])
        body = {"order_id": "O-1", "extra_flag": True,
                "extra_obj": {"k": [1, 2]}}
        out = _render_request_view(Request(body=body), ep)
        assert out["body"]["order_id"] == "O-1"
        assert out["body"]["extra_flag"] is True, "顶层目录外标量键不得丢弃"
        assert out["body"]["extra_obj"] == {"k": [1, 2]}, "顶层目录外子树整块保留"

    def test_declared_root_not_touched(self) -> None:
        """声明根仍走既有三步(值优先级不变);不因差集并入双写/覆写。"""
        ep = _deep_binding_ep([_FLAT_ORDER_ID])
        out = _render_request_view(
            Request(body={"order_id": "O-1"}), ep)
        assert out["body"] == {"order_id": "O-1"}

    def test_deep_declared_container_siblings_still_merged(self) -> None:
        """有 children 声明容器的深层兄弟键(既有 _merge_carry_literal
        路径)不受影响 —— 钉住丢失面收敛于顶层。"""
        ep = _deep_binding_ep([_DEEP_SUPPLIER])
        body = {"supplier": [{"order_supplier_id": "S-1", "extra_in_row": 9}]}
        out = _render_request_view(Request(body=body), ep)
        assert out["body"]["supplier"][0]["extra_in_row"] == 9

    def test_list_body_guard_no_crash(self) -> None:
        """整 body 为数组(根 INDEX)守卫:body.items 不可用,不崩溃。"""
        ep = _deep_binding_ep([DeclarationEntry(
            name="sku", path="$[0].sku", type='string')])
        out = _render_request_view(Request(body=[{"sku": "S-1"}]), ep)
        assert out["body"] == [{"sku": "S-1"}]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal && python -m pytest tests/plate/test_v3_export_platform.py -q`
Expected: FAIL — `test_undeclared_top_level_key_preserved` 缺 extra_flag/extra_obj(被丢弃);其余三例可能已通过(钉住现行为)。

- [ ] **Step 3: 实现**

`platform.py` `_render_request_view` ep 存在分支,步骤 3 的 for 循环之后、`else:` 之前插入:

```python
        # 4) 顶层目录外键整块并入(2026-09-14 提升配套):目录只覆盖声明
        #    面,顶层未声明键(含子树)在三步全不沾会被静默丢弃 ——
        #    platform→gimbal 往返子集契约破坏。与步骤 1 同式整块保留;
        #    声明根不进差集(三步已覆盖,值优先级不变)。
        if isinstance(body, dict):
            declared_roots = {
                segs[0]
                for e in iter_declarations(decls)
                if (segs := _path_segs(e.path)) and isinstance(segs[0], str)
            }
            for k, v in body.items():
                if k not in declared_roots:
                    full_body[k] = v
```

同步在函数 docstring 的设计清单末尾补一行:`- 顶层目录外键整块并入(2026-09-14):步骤 4 差集补全,声明根不受影响`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal && python -m pytest tests/plate/test_v3_export_platform.py -q`
Expected: PASS(新 4 例 + 该文件既有不回归)。**不跑 plate 套件其余文件**(冻结纪律)。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/export/platform.py tests/plate/test_v3_export_platform.py
git commit -m "fix(plate): _render_request_view 顶层目录外键整块并入 — 导出丢键修复(#3 T8,冻结豁免一处)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: 全量回归

**Files:** 无新改动(验证门)。

- [ ] **Step 1: 前端全量**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全绿(基线 881 + 本计划新增约 15 例)+ vue-tsc 0。

- [ ] **Step 2: 后端全量**

Run: `cd src/gimbal-platform/backend && python -m pytest -q`
Expected: 全绿。

- [ ] **Step 3: plate 豁免子集**

Run: `cd /d/Gimbal/Gimbal && python -m pytest tests/plate/test_v3_export_platform.py -q`
Expected: 全绿。

- [ ] **Step 4: 如有失败,修复后重跑至全绿再收尾**(不得带红提交)。

---

## Self-Review 记录

1. **Spec 覆盖**:§4.1 拼接(T7)/§4.2 合成(T1)/§4.3 extras 入口(T4+T7)/§4.4 carry 门禁(T2/T3/T4/T5)/§4.5 显式排除面(无任务 = 无改动,符合)/§5.1 后端(T6)/§6 plate(T8)/§8 测试策略(各任务 Step 1)✓。
2. **无占位符**:所有代码步含完整代码;Task 5/7 的两处「以实际渲染为准调整选择器」是测试 DOM 定位的诚实说明,断言语义已钉死。
3. **类型一致**:`promotedDecls`/`entryPaths`/`noCarryPaths`/`noCarry`/`promotedPaths`/`promote`/`validate_field_states(body)`/`validateEndpointFieldStates(body)` 各任务间签名逐字一致 ✓。
4. **执行序依赖**:T4 依赖 T3;T5 依赖 T3+T1(FieldSearchRow);T7 依赖 T1/T2/T4/T6;T8 独立。T1/T2/T3/T6/T8 相互独立可并行审。
