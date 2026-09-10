# 数据驱动重构(期望行级化 + step 段网格 + 关联导航)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 断言 expected 可提升为期望变量(`${var.exp_*}` 模板 + 数据集行逐行供值,负向数据驱动闭环)+ 数据集编辑器列作用域收缩到单 step 段(行宽与过程长度解耦)+ 扰动位 ↔ 期望列双向导航。

**Architecture:** 全部改动落前端(编排器 StrategyForm/Canvas/CaseComposer + 数据集编辑器 DataSetEditor + 新纯函数工具 dataset-segments)。存储三分零变化(steps[].strategy 结构 / config.vars 列宇宙+基线 / dataset.rows 纯数据),绑定 = var 名单一符号;段/期望列/共享标记全部打开编辑器时对场景做引用扫描**投影期派生**,零第二份存储。零引擎/零后端/零 plate 改动 —— 运行链(dispatcher 行 layer + preprocess 展开)全既有。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript + Element Plus + Pinia;vitest + @vue/test-utils 挂载级测试;vue-tsc 类型门。

**Spec:** [docs/superpowers/specs/2026-09-10-dataset-driven-refactor-design.md](../specs/2026-09-10-dataset-driven-refactor-design.md)(§5 编排器 / §6 编辑器 / §7 命名 / §9 兼容 / §11 测试矩阵是本计划的验收依据)

## Global Constraints

- **零引擎/零后端/零 plate 改动**(spec §1 目标 4):本计划全部改动 ⊆ `src/gimbal-platform/frontend/`;gimbal resolver / export / dispatch 物化链一行不动。
- **plate / backend 测试套件期间禁跑**(用户计数钉纪律:plate 有后台任务跑着,计数会被污染);本计划只跑前端套件(`src/gimbal-platform/frontend` 下 `npx vitest run` 与 `npx vue-tsc --noEmit`,以 package.json scripts 为准校准命令)。
- **选择性暂存纪律**:工作树常带用户多股 WIP。每个任务只暂存本任务 Files 清单内的文件;`git add` 前用 `git status` 核对;`gimbal-tmp/`、`reports/test-report.html`、`probe_ui.js` 永不触碰、永不提交。
- **FieldForm.vue 含用户未提交 WIP**(菜单钮形态改造:.fa-slot 框外方形钮、.cand-btn 样式区、svg 图标):FieldActionMenu.vue 本计划**零改动**;Task 3 修改 FieldForm.vue 时新增代码集中在叶子行 label 区与容器模板态徽标区(与用户 WIP 的菜单钮区不重叠),提交由控制者以 `git diff src/.../FieldForm.vue` 逐 hunk 核验后**只暂存本任务 hunk**(git add -p 或 git apply --cached),用户 WIP hunk 绝不入提交。
- commit message 尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- **期望命名 = `exp_` + target 末段**;撞名 → ElMessageBox.prompt 对话框提示改名,**不静默 `_2` 后缀**(spec §5.2)。
- **行只标量**(既有 `_scalar_vars` 门);operator+expected 打包进行 = 红线拒(spec §7)。
- **编辑器列宇宙 = config.vars(裁定 A)**:DataSetEditor 只消费不声明;promote/demote/demoteLast 整体退场(spec §6.3)。
- **TSV 粘贴(单列纵向 + 矩形块首列)、三态 cell、行增删、caseNames、CSV 导入导出全保留,既有测试钉死**(spec §6.3)。
- **存储模型零变化**:dataset.rows 形状、config.vars 形状、strategy schema 均不动;唯一数据面变化是 expected 的**值**可从字面量变模板串(spec §9.1)。
- 死行键**软提示不硬门禁**;exp_* 在 VarSelector **标注不禁选**(spec §7/§5.2)。
- view name 不可变;绝不自动重登录(§6.2 继承)。
- 回归基线:前端 vitest 全绿 + vue-tsc 0(基线 673 通过 + 本计划新增用例;Task 6 删除 promote 既有用例属裁定 A 的显式例外,删改文件须在任务里列明)。

---

### Task 0: 消费方盘点(spec §9.3,调研任务)

**Files:**
- Create: `.superpowers/sdd/2026-09-10-dataset-driven-refactor/task-0-report.md`(SDD workspace,git-ignored)
- Modify(仅当发现 §9.2 矩阵外的新消费方): `docs/superpowers/specs/2026-09-10-dataset-driven-refactor-design.md` §9.2

**Interfaces:**
- Consumes: spec §9.2 兼容矩阵(9 行)。
- Produces: 盘点报告(每个消费方一行结论);若全部落在矩阵内 → 零提交、报告留台账;若发现新消费方 → 补矩阵行并提交 spec。

- [ ] **Step 1: 重新 grep 全部消费方(不靠记忆,靠盘点)**

在 `src/gimbal-platform/frontend/src` 下运行(计划期预 grep 的起点清单,须重新验证完整性):

```
Grep pattern: dataSetIds
Grep pattern: getDataSet|listDataSets|saveDataSet|deleteDataSet
Grep pattern: datasets
Grep pattern: exportScenario|materialize
```

计划期已知命中面(逐一复核):`api/executions.ts`、`api/scenario-composer.ts`(datasets CRUD)、`CaseComposer.vue`、`Executions.vue`、`RunDialog.vue`(dataSetIds 选择)、`stores/scenario-draft.ts:36`(导出有意不带)、`ScenarioExportMenu.scheme.test.ts`。

- [ ] **Step 2: 每个消费方过 §9.2 矩阵**

对每个命中文件回答三个问题并写入报告:①消费什么数据(dataset.rows / dataSetIds / scenario definition);②本设计改动(前端 expected 模板串 + 编辑器渲染)是否触达其读取路径;③结论(✓ 零变化 / ✓+ 变好 / 需适配)。逐文件记一行:

```markdown
# Task 0 消费方盘点报告(2026-09-10)

| 文件 | 消费什么 | 触达 | 结论 |
|---|---|---|---|
| RunDialog.vue | RunRequest.dataSetIds → dispatcher | 否(运行链全既有) | ✓ |
| ...(全部命中面) |
```

- [ ] **Step 3: 结论裁决**

全部落在矩阵内 → 报告写"零新消费方,§9.2 矩阵完整",任务完成(零提交,台账留痕)。发现矩阵外消费方 → 在 spec §9.2 表追加一行(功能/消费什么/影响/结论),提交 spec:`git add docs/superpowers/specs/2026-09-10-dataset-driven-refactor-design.md` + commit `docs(spec): §9.2 消费方盘点补录`。

---

### Task 1: 段派生扫描器 utils/dataset-segments.ts(纯函数,零 IO)

**Files:**
- Create: `src/gimbal-platform/frontend/src/utils/dataset-segments.ts`
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/dataset-segments.test.ts`

**Interfaces:**
- Consumes: 无(自包含正则,不依赖 dataset-palette 内部)。
- Produces(Task 2/4/5 消费的精确签名):
  - `interface GridVarColumn { varName: string; baseline: unknown; stepIndex: number; source: 'body' | 'headers' | 'expect'; field: string; expect?: { target: string; operator: string; strategyIdx: number } }`
  - `interface Segment { stepIndex: number; inputs: InputColumn[]; expects: ExpectColumn[] }`
  - `deriveSegments(steps: SegmentStepShape[], vars: Record<string, unknown> | null | undefined): Segment[]` — 段 = 有列的步骤,按步骤序
  - `gridColumnsOf(seg: Segment): GridVarColumn[]` — 段内可编辑列(输入列在前,期望列在后)
  - `sharedVarNames(segments: Segment[]): Set<string>` — 跨段引用同名 var
  - `deadRowKeys(vars: Record<string, unknown> | null | undefined, rows: Array<Record<string, unknown>>): string[]` — 行键 ∉ config.vars 键集
  - `expectVarNameOf(target: string): string` — `exp_` + target 末段,非法字符压 `_`
  - `TPL_FULL_RE: RegExp` — `/^\$\{var\.([A-Za-z0-9_.]+)\}$/`(整串模板判定,Task 2/3 复用)

- [ ] **Step 1: 写失败测试**

```typescript
// src/gimbal-platform/frontend/src/utils/__tests__/dataset-segments.test.ts
/**
 * dataset-segments — 段派生扫描器单测(spec §4.1/§6.2)。
 * 纯函数零 IO:输入列(body/headers ${var.x} 引用,深扫)+ 期望列
 * (assertion expected 模板,带 target/operator/strategyIdx)+
 * 共享 var(跨段)+ 死行键(行键 ∉ config.vars)。
 */
import { describe, it, expect } from 'vitest'
import {
  deriveSegments, gridColumnsOf, sharedVarNames, deadRowKeys,
  expectVarNameOf, type SegmentStepShape,
} from '../dataset-segments'

const VARS = { amount: 100, exp_code: 200, exp_msg: 'ok' }

/** 两步场景:step1 输入列 amount + 期望 exp_code/exp_msg;step2 输入 bl_no */
const STEPS: SegmentStepShape[] = [
  {
    request: { body: { amount: '${var.amount}', nested: { policy: '${var.amount}' } } },
    api: { headers: { 'X-Trace': '${var.bl_no}', Authorization: '${auth.userA.token}' } },
    strategy: [
      { kind: 'extract', target: 't', expression: '$.a' },
      { kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' },
      { kind: 'assertion', target: '$.response_body.msg', operator: 'eq', expected: 'prefix ${var.exp_msg} postfix' },
      { kind: 'assertion', target: '$.response_status', operator: 'eq', expected: 200 },
    ],
  },
  { request: { body: { bl_no: '${var.bl_no}' } }, strategy: [] },
  { request: { body: { plain: '字面量' } }, strategy: [] },   // 无引用 → 不成段
]

describe('deriveSegments', () => {
  it('S1: 段派生 — 输入列(body 深路径/headers/auth 域排除)+ 期望列 + 空段不入', () => {
    const segs = deriveSegments(STEPS, VARS)
    expect(segs.map((s) => s.stepIndex)).toEqual([0, 1])       // step2(索引 2)无引用不成段
    const s0 = segs[0]
    // 输入列:body amount(深路径二次引用同 var 去重)+ headers bl_no;
    // ${auth.*} 非 var 域不产列
    expect(s0.inputs.map((c) => c.varName)).toEqual(['amount', 'bl_no'])
    expect(s0.inputs[0]).toMatchObject({ stepIndex: 0, source: 'body', field: 'amount', baseline: 100 })
    expect(s0.inputs[1]).toMatchObject({ source: 'headers', field: 'X-Trace', baseline: undefined })
    // 期望列:整串 + 混串模板都产列(各带 target/operator/strategyIdx);
    // 非字符串 expected(数字 200)跳过;非 assertion 跳过
    expect(s0.expects.map((e) => e.varName)).toEqual(['exp_code', 'exp_msg'])
    expect(s0.expects[0]).toMatchObject({ target: '$.response_body.code', operator: 'eq', strategyIdx: 1 })
    expect(s0.expects[1].strategyIdx).toBe(2)
  })

  it('S2: 共享 var = 跨段引用(bl_no 两段),单段重复引用不算', () => {
    const segs = deriveSegments(STEPS, VARS)
    expect(sharedVarNames(segs)).toEqual(new Set(['bl_no']))
  })

  it('S3: gridColumnsOf — 段内可编辑列,输入在前期望在后,expect 上下文内嵌', () => {
    const cols = gridColumnsOf(deriveSegments(STEPS, VARS)[0])
    expect(cols.map((c) => c.varName)).toEqual(['amount', 'bl_no', 'exp_code', 'exp_msg'])
    expect(cols[2].source).toBe('expect')
    expect(cols[2].expect).toEqual({ target: '$.response_body.code', operator: 'eq', strategyIdx: 1 })
  })
})

describe('expectVarNameOf', () => {
  it('E1: target 末段命名 + 非法字符压 _ + 空 target 兜底', () => {
    expect(expectVarNameOf('$.response_body.code')).toBe('exp_code')
    expect(expectVarNameOf('$.response_status')).toBe('exp_status')
    expect(expectVarNameOf("$.data['weird key']")).toBe('exp_weird_key')
    expect(expectVarNameOf('')).toBe('exp_value')
  })
})

describe('deadRowKeys', () => {
  it('D1: 行键 ∉ config.vars 键集 → 死键(软提示面);∈ 键集不算', () => {
    expect(deadRowKeys({ amount: 1 }, [{ amount: 2, ghost: 3 }, { other: 4 }]))
      .toEqual(['ghost', 'other'])
    expect(deadRowKeys(null, [{ a: 1 }])).toEqual(['a'])
    expect(deadRowKeys({ a: 1 }, [])).toEqual([])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/dataset-segments.test.ts`
Expected: FAIL — Cannot find module '../dataset-segments'

- [ ] **Step 3: 写实现**

```typescript
// src/gimbal-platform/frontend/src/utils/dataset-segments.ts
/**
 * dataset-segments — 数据集编辑器段派生扫描器(spec §4.1/§6.2,纯函数零 IO)。
 *
 * 打开编辑器时对场景做一次引用扫描:
 *   输入列 = step 的 request body/headers 里 ${var.x} 引用(深扫,数组带 [i]);
 *   期望列 = step.strategy 中 kind=assertion 且 expected 含 ${var.x}(带
 *   target/operator/strategyIdx,供列头徽标与跳转);
 *   段 = 有列的步骤;共享 = 跨段同名 var;列宇宙 = config.vars(裁定 A,
 *   baseline 从 vars 取值,编辑器只消费不声明)。
 * 与 dataset-palette 的 deriveBaselineColumns(traversal 有 endpoint_id 纪律,
 * 服务直填列基线显示)互不依赖:引用扫描与端点契约无关,不设 endpoint_id 门。
 */
export const TPL_RE = /\$\{var\.([A-Za-z0-9_.]+)\}/g
export const TPL_FULL_RE = /^\$\{var\.([A-Za-z0-9_.]+)\}$/

export interface InputColumn {
  stepIndex: number
  source: 'body' | 'headers'
  /** 引用所在字段路径(body 深路径点连;headers 键) */
  field: string
  varName: string
  /** config.vars[varName](未声明 = undefined → 行 placeholder 空) */
  baseline: unknown
}

export interface ExpectColumn {
  varName: string
  target: string
  operator: string
  /** 断言在 step.strategy 数组的下标(跳转 #strategy-card-N 用) */
  strategyIdx: number
  stepIndex: number
}

export interface SegmentStepShape {
  request?: { body?: unknown } | null
  api?: { headers?: Record<string, unknown> | null } | null
  strategy?: unknown[]
}

export interface Segment {
  stepIndex: number
  inputs: InputColumn[]
  expects: ExpectColumn[]
}

/** 段网格可编辑列(输入/期望统一:行键 = varName,单一 join key spec §4) */
export interface GridVarColumn {
  varName: string
  baseline: unknown
  stepIndex: number
  source: 'body' | 'headers' | 'expect'
  field: string
  expect?: { target: string; operator: string; strategyIdx: number }
}

function scanValue(
  v: unknown, source: 'body' | 'headers', path: string,
  stepIndex: number, out: (c: InputColumn) => void, vars: Record<string, unknown>,
): void {
  if (typeof v === 'string') {
    for (const m of v.matchAll(TPL_RE)) {
      out({ stepIndex, source, field: path || '(root)', varName: m[1], baseline: vars[m[1]] })
    }
  } else if (Array.isArray(v)) {
    v.forEach((item, i) => scanValue(item, source, `${path}[${i}]`, stepIndex, out, vars))
  } else if (v && typeof v === 'object') {
    for (const [k, child] of Object.entries(v)) {
      scanValue(child, source, path ? `${path}.${k}` : k, stepIndex, out, vars)
    }
  }
}

export function deriveSegments(
  steps: SegmentStepShape[] | null | undefined,
  vars: Record<string, unknown> | null | undefined,
): Segment[] {
  const v = vars ?? {}
  const out: Segment[] = []
  ;(steps ?? []).forEach((step, stepIndex) => {
    const inputs: InputColumn[] = []
    const seen = new Set<string>()
    const push = (c: InputColumn) => {
      if (!seen.has(c.varName)) { seen.add(c.varName); inputs.push(c) }   // 同步去重(首引用位)
    }
    scanValue(step?.request?.body, 'body', '', stepIndex, push, v)
    const headers = step?.api?.headers
    if (headers && typeof headers === 'object') {
      for (const [k, val] of Object.entries(headers)) {
        if (typeof val === 'string') {
          for (const m of val.matchAll(TPL_RE)) {
            push({ stepIndex, source: 'headers', field: k, varName: m[1], baseline: v[m[1]] })
          }
        }
      }
    }
    const expects: ExpectColumn[] = []
    ;(step?.strategy ?? []).forEach((s, strategyIdx) => {
      const st = s as { kind?: string; expected?: unknown; target?: unknown; operator?: unknown }
      if (st?.kind !== 'assertion' || typeof st.expected !== 'string') return
      for (const m of st.expected.matchAll(TPL_RE)) {
        expects.push({
          varName: m[1], target: String(st.target ?? ''), operator: String(st.operator ?? ''),
          strategyIdx, stepIndex,
        })
      }
    })
    if (inputs.length || expects.length) out.push({ stepIndex, inputs, expects })
  })
  return out
}

/** 段内可编辑列:输入列在前、期望列在后(行读取顺序 = 段内并排 spec §4.3) */
export function gridColumnsOf(seg: Segment): GridVarColumn[] {
  return [
    ...seg.inputs.map((c) => ({ varName: c.varName, baseline: c.baseline, stepIndex: c.stepIndex, source: c.source, field: c.field })),
    ...seg.expects.map((c) => ({
      varName: c.varName, baseline: (c as { baseline?: unknown }).baseline, stepIndex: c.stepIndex,
      source: 'expect' as const, field: c.target,
      expect: { target: c.target, operator: c.operator, strategyIdx: c.strategyIdx },
    })),
  ]
}

/** 共享 var:跨段引用同名(段内多字段引用同一 var 不算共享,列头首引用位代表) */
export function sharedVarNames(segments: Segment[]): Set<string> {
  const seen = new Map<string, number>()
  for (const seg of segments) {
    const names = new Set<string>([
      ...seg.inputs.map((c) => c.varName),
      ...seg.expects.map((c) => c.varName),
    ])
    for (const n of names) seen.set(n, (seen.get(n) ?? 0) + 1)
  }
  return new Set([...seen.entries()].filter(([, n]) => n > 1).map(([k]) => k))
}

/** 死行键:行键 ∉ config.vars 列宇宙(spec §7 软提示,不硬门禁) */
export function deadRowKeys(
  vars: Record<string, unknown> | null | undefined,
  rows: Array<Record<string, unknown>>,
): string[] {
  const universe = new Set(Object.keys(vars ?? {}))
  const dead = new Set<string>()
  for (const row of rows) for (const k of Object.keys(row)) if (!universe.has(k)) dead.add(k)
  return [...dead]
}

/** 期望命名:exp_ + target 末段(spec §5.2;撞名由调用方对话框处理,不静默 _2) */
export function expectVarNameOf(target: string): string {
  const segs = target.split(/[.[\]]+/).filter(Boolean)
  const last = segs.length ? segs[segs.length - 1] : 'value'
  return `exp_${last.replace(/[^A-Za-z0-9_]/g, '_')}`
}
```

注:gridColumnsOf 里期望列 baseline 的取法 `(c as { baseline?: unknown }).baseline` 若想更干净,可直接在 Step 3 实现时给 ExpectColumn 也加 `baseline: unknown` 字段(deriveSegments 里 `baseline: v[m[1]]`)——两种皆可,以实现自洽为准,测试只断言 varName/source/expect 三面。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/dataset-segments.test.ts`
Expected: PASS(全部用例)

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/frontend/src/utils/dataset-segments.ts src/gimbal-platform/frontend/src/utils/__tests__/dataset-segments.test.ts
git commit -m "feat(frontend): dataset-segments 段派生扫描器 — 输入/期望列引用扫描 + 共享/死键推导

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 期望变量提升链(StrategyForm 动作行 + Canvas 接线 + CaseComposer 删键通路 + VarSelector 标注)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue`(sf-body 尾部动作行 + emits)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(StrategyForm 挂载处接线 :349-360 附近 + onExpPromote/onExpRestore/onExpNav + emits 加 varDemote)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(Canvas 挂载 :150-160 加 @var-demotion + onVarDemote 函数)
- Modify: `src/gimbal-platform/frontend/src/components/composer/VarSelectorModal.vue`(exp_* 标注)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(追加 describe)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.vardemote.test.ts`(新建,骨架仿 CaseComposer.autosave.test.ts 的 store/api mock 模式)

**Interfaces:**
- Consumes: Task 1 的 `expectVarNameOf(target: string): string` 与 `TPL_FULL_RE`。
- Consumes: 既有链 FieldForm emit('varPromote', f, name, value) → Canvas onVarPromote(:960) re-emit('varPromote', name, value) → CaseComposer onVarPromote(:486) 登记 config.vars —— 本任务给该链补**删键通路** varDemote。
- Produces(Task 3 消费):
  - StrategyForm emits 追加:`expPromote: []` / `expRestore: []` / `expNav: []`(断言卡动作行;徽标 `sf-exp-badge` + 文案"期望列 {varName}"在卡内渲染)
  - Canvas emits 追加:`varDemote: [name: string]`、`expNav: []`
  - CaseComposer 新函数:`onVarDemote(name: string): void`(config.vars 删键,immutable 替换)

- [ ] **Step 1: 写失败测试(Canvas 挂载级,追加到 CaseComposerCanvas.test.ts 末尾)**

先在文件头部 mock 区的 `getStrategyKindFull` mockImplementation 中,把 assertion 条目的 fields 扩为含 expected(既有用例不依赖 expected 字段不渲染,零影响;新用例的动作行是独立渲染不依赖 FieldForm):

```typescript
    assertion: { kind: 'assertion', label: '断言', phase: 'verifying', fields: [
      { name: 'target', path: 'target', ui_kind: 'text', source_kind: 'independent', required: true, description: null, example: null, default: null, enum: null },
      { name: 'expected', path: 'expected', ui_kind: 'text', source_kind: 'independent', required: false, description: null, example: null, default: null, enum: null },
    ], base_fields: [] },
```

再在 `listStrategyKinds` 需要非空的用例内 mock(既有 B4/T14 模式:`vi.mocked(listStrategyKinds).mockResolvedValue([...])` + finally 恢复)下追加 describe:

```typescript
/**
 * 期望变量提升(spec §5.2,2026-09-10):断言卡 expected 模板化
 * ${var.exp_*} + 基线登记 config.vars(varPromote 链复用)+ 还原
 * (写回基线字面量 + varDemote 删键新通路)+ 撞名对话框(不静默 _2)。
 */
describe('CaseComposerCanvas — 期望变量提升(§5.2)', () => {
  function mountWithAssertion(expected: unknown) {
    const s0 = mkStep({
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected } as any],
    })
    const { listStrategyKinds } = await0importPlaceholder()   // ← 实现时写 `await import('@/api/scenario-composer')`(计划排版占位,实施时按 B4 用例同款)
    return { steps: [s0] }
  }

  it('X1: 设为期望变量 → expected 模板化 ${var.exp_code} + varPromote 上抛基线', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([{ kind: 'assertion', label: '断言' }])
    try {
      const s0 = mkStep({
        strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: 200 } as any],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      await w.find('.sf-head').trigger('click')          // 展开断言卡
      await w.find('.sf-exp-promote').trigger('click')   // 设为期望变量
      await flush()
      expect((s0.strategy[0] as any).expected).toBe('${var.exp_code}')
      const canvas = w.findComponent(CaseComposerCanvas)
      expect(canvas.emitted('varPromote')).toEqual([['exp_code', 200]])
      // 已模板化态:徽标 + 还原入口出现,提升按钮退场
      expect(w.find('.sf-exp-badge').text()).toContain('exp_code')
      expect(w.find('.sf-exp-restore').exists()).toBe(true)
      expect(w.find('.sf-exp-promote').exists()).toBe(false)
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })

  it('X2: 撞名 → ElMessageBox.prompt 改名(不静默 _2);确认后用新名', async () => {
    const { listStrategyKinds, ElMessageBox } = await Promise.all([
      import('@/api/scenario-composer'),
      import('element-plus'),
    ]).then(([a, b]) => ({ listStrategyKinds: a.listStrategyKinds, ElMessageBox: b.ElMessageBox }))
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([{ kind: 'assertion', label: '断言' }])
    const promptSpy = vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({ value: 'exp_code_neg' } as any)
    try {
      // beforeEach 已有 base_url;再造撞名:config.vars 先登记 exp_code
      const draft = useScenarioDraftStore()
      draft.draft!.definition.config.vars = { base_url: 'http://x', exp_code: 200 }
      const s0 = mkStep({
        strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: 404 } as any],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      await w.find('.sf-head').trigger('click')
      await w.find('.sf-exp-promote').trigger('click')
      await flushPromises()
      expect(promptSpy).toHaveBeenCalled()
      expect((s0.strategy[0] as any).expected).toBe('${var.exp_code_neg}')
      expect(w.findComponent(CaseComposerCanvas).emitted('varPromote')).toEqual([['exp_code_neg', 404]])
      w.unmount()
    } finally {
      promptSpy.mockRestore()
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })

  it('X3: 还原 → expected 写回基线字面量 + varDemote 上抛(删键新通路)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([{ kind: 'assertion', label: '断言' }])
    try {
      const draft = useScenarioDraftStore()
      draft.draft!.definition.config.vars = { base_url: 'http://x', exp_code: 200 }
      const s0 = mkStep({
        strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' } as any],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      await w.find('.sf-head').trigger('click')
      await w.find('.sf-exp-restore').trigger('click')
      await flush()
      expect((s0.strategy[0] as any).expected).toBe(200)   // 写回 config.vars 登记的基线
      expect(w.findComponent(CaseComposerCanvas).emitted('varDemote')).toEqual([['exp_code']])
      // 回到未模板化态:提升按钮重现
      expect(w.find('.sf-exp-promote').exists()).toBe(true)
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })

  it('X4: 徽标点击 expNav 上抛(断言卡 → 数据集导航入口)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([{ kind: 'assertion', label: '断言' }])
    try {
      const s0 = mkStep({
        strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' } as any],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      await w.find('.sf-head').trigger('click')
      await w.find('.sf-exp-nav').trigger('click')
      expect(w.findComponent(CaseComposerCanvas).emitted('expNav')).toBeTruthy()
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })

  it('X5: VarSelector exp_* 标注"期望"但不禁选', async () => {
    const { mount: mountModal } = await import('@vue/test-utils')
    const VarSelectorModal = (await import('@/components/composer/VarSelectorModal.vue')).default
    const open = ref(true)
    const w = mountModal(VarSelectorModal, {
      props: {
        modelValue: open.value,
        'onUpdate:modelValue': (v: boolean) => { open.value = v },
        entries: [
          { name: 'exp_code', origin: 'config', stepIdx: null, expression: null },
          { name: 'base_url', origin: 'config', stepIdx: null, expression: null },
        ],
      },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flush()
    const items = [...document.querySelectorAll('.var-item')] as HTMLElement[]
    const expEl = items.find((el) => el.textContent!.includes('exp_code'))!
    expect(expEl.querySelector('.var-exp-tag')).toBeTruthy()          // 标注在场
    expect(expEl.classList.contains('disabled')).toBe(false)          // 不禁选(双用合法)
    expEl.click()                                                      // 可选
    await flush()
    w.unmount()
  })
})
```

注:X1 顶部那个 `mountWithAssertion` 辅助是排版残留,实施时**不要写它**——四个用例各自内联构造(X1-X4 已内联,X5 独立);该辅助函数从测试中删除。

CaseComposer 层删键用例(新建 `CaseComposer.vardemote.test.ts`,骨架 = CaseComposer.autosave.test.ts 的 mock 面复制:store/api mock + route stub;实施时先读该文件再仿写):

```typescript
/**
 * CaseComposer — varDemote 删键通路(§5.2 逆动作):Canvas emit('varDemote')
 * → config.vars 删键(immutable 替换);键不存在 = no-op 不炸。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
// (骨架 import/mock 面从 CaseComposer.autosave.test.ts 复制:pinia/router stub/
//  scenario-composer api mock;在此之上写以下用例)

it('varDemote 删 config.vars 键,其余键保留', async () => {
  // 挂载后从 draft store 取 definition;模拟 Canvas 事件:
  // 找到 CaseComposerCanvas 组件 wrapper,vm.$emit('varDemote', 'exp_code')
  const canvas = w.findComponent(CaseComposerCanvas)
  canvas.vm.$emit('varDemote', 'exp_code')
  await nextTick()
  const vars = (useScenarioDraftStore().draft as any).definition.config.vars
  expect('exp_code' in vars).toBe(false)
  expect(vars.base_url).toBe('http://x')     // 其余键保留
})

it('varDemote 键不存在 = no-op', async () => {
  canvas.vm.$emit('varDemote', 'ghost')
  await nextTick()
  // definition 引用不变(未发生替换)或 vars 原样 — 断言不抛错且 base_url 仍在
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts src/views/__tests__/CaseComposer.vardemote.test.ts`
Expected: FAIL — `.sf-exp-promote` 找不到 / varDemote 无 emit

- [ ] **Step 3: 实现 StrategyForm 动作行**

`StrategyForm.vue` — emits 扩展 + 断言特判 computed + sf-body 尾部(onFailure 块之后)动作行:

```typescript
const emit = defineEmits<{
  remove: []
  expPromote: []
  expRestore: []
  expNav: []
}>()

/** 期望变量提升面(spec §5.2,唯一策略面新增):kind=assertion 才渲染动作行 */
const isAssertion = computed(() => props.detail.kind === 'assertion')
/** expected 已是整串 ${var.x} 模板 → 已提升态(徽标 + 还原) */
const expVarName = computed<string | null>(() => {
  if (!isAssertion.value) return null
  const m = /^\$\{var\.([A-Za-z0-9_.]+)\}$/.exec(String((props.strategy as any).expected ?? ''))
  return m ? m[1] : null
})
```

模板(sf-body 内、onFailure 块之后):

```html
<!-- 期望变量提升(spec §5.2):expected 模板化 + 数据集行逐行供值;
     值落地在 Canvas(跨层动作单一真源),此处只发事件 -->
<div v-if="isAssertion" class="sf-exp-row">
  <template v-if="expVarName">
    <span
      class="sf-exp-badge"
      :title="`期望列 ${expVarName} — 断言 expected 已模板化,数据集行可逐行供值(不挂数据集 = 基线)`"
    >期望列 {{ expVarName }}</span>
    <button type="button" class="sf-exp-nav" title="查看该场景的数据集" @click="emit('expNav')">↗ 数据集</button>
    <button type="button" class="sf-exp-restore" title="expected 写回基线字面量,config.vars 删键;数据集行若引用该键将成死键" @click="emit('expRestore')">还原为字面量</button>
  </template>
  <button
    v-else
    type="button"
    class="sf-exp-promote"
    title="expected 提升为 ${var.exp_*} 模板,基线登记 ③ 共享变量 — 数据集行可逐行供值(负向数据驱动)"
    @click="emit('expPromote')"
  >⟳ 设为期望变量(数据集行可逐行供值)</button>
</div>
```

样式(追加到 scoped style,配色随既有 sf 徽标族):

```css
.sf-exp-row { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border-top: 1px dashed #e6e8ec; }
.sf-exp-badge { font-size: 11px; font-weight: 700; color: #6b21a8; background: #f3e8ff; padding: 2px 8px; border-radius: 4px; }
.sf-exp-promote, .sf-exp-restore, .sf-exp-nav {
  border: none; background: transparent; cursor: pointer;
  font-size: 11px; color: #4f46e5; padding: 2px 6px; border-radius: 4px;
}
.sf-exp-promote:hover, .sf-exp-restore:hover, .sf-exp-nav:hover { background: #eef2ff; }
.sf-exp-restore { color: #b45309; }
.sf-exp-restore:hover { background: #fef3c7; }
```

- [ ] **Step 4: 实现 Canvas 接线**

`CaseComposerCanvas.vue` — StrategyForm 挂载处(:349-360)加事件:

```html
@exp-promote="onExpPromote(idx)"
@exp-restore="onExpRestore(idx)"
@exp-nav="onExpNav"
```

emits 声明追加 `varDemote: [name: string]` 与 `expNav: []`(在既有 varPromote 声明旁,实施时按现场 emits 块形状补)。

handler(放在 onVarPromote :960 旁):

```typescript
import { expectVarNameOf } from '@/utils/dataset-segments'

/** 期望提升(spec §5.2):expected → ${var.exp_*};撞名对话框改名,不静默 _2 */
function onExpPromote(idx: number) {
  const step = currentStep.value
  if (!step) return
  const st = step.strategy[idx] as { expected?: unknown; target?: unknown }
  const base = expectVarNameOf(String(st.target ?? ''))
  const vars = (draftStore.draft?.definition?.config?.vars ?? {}) as Record<string, unknown>
  if (Object.prototype.hasOwnProperty.call(vars, base)) {
    ElMessageBox.prompt(
      `期望变量 ${base} 已存在(③ 共享变量里有同名键)。请换一个名字:`,
      '撞名 — 改名后继续',
      {
        confirmButtonText: '确定', cancelButtonText: '取消',
        inputPattern: /^[A-Za-z_][A-Za-z0-9_]*$/,
        inputErrorMessage: '变量名须以字母/下划线开头,仅含字母/数字/下划线',
      },
    ).then(({ value }) => { if (value) applyExpPromote(st, value.trim()) }).catch(() => {})
    return
  }
  applyExpPromote(st, base)
}

function applyExpPromote(st: { expected?: unknown; target?: unknown }, name: string) {
  const baseline = st.expected ?? null
  ;(st as { expected?: unknown }).expected = `\${var.${name}}`
  emit('varPromote', name, baseline)
  ElMessage.success(`期望已模板化 \${var.${name}} — 数据集行可逐行供值;不挂数据集 = 基线`)
}

/** 逆动作:expected 写回基线字面量 + varDemote 删键;死键软提示(spec §5.2) */
function onExpRestore(idx: number) {
  const step = currentStep.value
  if (!step) return
  const st = step.strategy[idx] as { expected?: unknown }
  const m = /^\$\{var\.([A-Za-z0-9_.]+)\}$/.exec(String(st.expected ?? ''))
  if (!m) return
  const name = m[1]
  const vars = (draftStore.draft?.definition?.config?.vars ?? {}) as Record<string, unknown>
  st.expected = (vars[name] as unknown) ?? null
  emit('varDemote', name)
  ElMessage.warning(`已还原为字面量;数据集行若引用 ${name} 将成死键(运行无效果,可在编辑器看到提示)`)
}

/** 断言卡"↗ 数据集"导航:跳列表页由 CaseComposer 落(编排器不知具体 datasetId) */
function onExpNav() {
  emit('expNav')
}
```

注意:`draftStore` 若现场名不同(测试 beforeEach 写 `useScenarioDraftStore()` 且 Canvas 的 VRP 面板已消费 config vars),以 Canvas 内既有 store 引用名为准 —— Grep `useScenarioDraftStore` in CaseComposerCanvas.vue 对齐。ElMessageBox 若未 import,补 `import { ElMessage, ElMessageBox } from 'element-plus'`。

- [ ] **Step 5: 实现 CaseComposer 删键通路**

`CaseComposer.vue` — Canvas 挂载处(:150-160)`@var-promote="onVarPromote"` 旁加 `@var-demotion="onVarDemote"`,函数放 onVarPromote(:486)旁:

```typescript
/** Canvas 期望还原上报(spec §5.2 逆动作):config.vars 删键(immutable 替换) */
function onVarDemote(name: string) {
  const config = definition.value.config
  if (!config?.vars || !(name in config.vars)) return
  const { [name]: _removed, ...rest } = config.vars
  definition.value = { ...definition.value, config: { ...config, vars: rest } }
}
```

- [ ] **Step 6: 实现 VarSelector exp_* 标注**

`VarSelectorModal.vue` — 条目渲染处(extract 禁选先例旁)加标注 span(不禁选):

```html
<span
  v-if="e.name.startsWith('exp_')"
  class="var-exp-tag"
  title="期望变量 — 断言 expected 的数据集行供值;同值既输入又期望的双用合法,不禁选"
>期望</span>
```

```css
.var-exp-tag { font-size: 10px; font-weight: 700; color: #6b21a8; background: #f3e8ff; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }
```

- [ ] **Step 7: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts src/views/__tests__/CaseComposer.vardemote.test.ts`
Expected: PASS(新 describe X1-X5 + vardemote 两用例,既有用例零回归)

- [ ] **Step 8: 提交**

```bash
git add src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/VarSelectorModal.vue src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.vardemote.test.ts
git commit -m "feat(frontend): 期望变量提升链 — 断言卡动作行 + varDemote 删键通路 + VarSelector exp_* 标注

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 编排器呈现与导航(扰动位徽标 + 同步骤扰动位列表 + focusJump 跨路由跳转 + 多视图前移提示)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(叶子行扰动位徽标 + 容器模板态徽标文案升级 —— **用户 WIP 同文件,选择性暂存纪律见 Global Constraints**)
- Modify: `src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue`(新 prop siblingPerturbs + 同步骤扰动位列表行)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(siblingPerturbs 推导 + focusJump prop 消费 + onVarPromote/onVarInsert 多视图软提示)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(focusStep/focusStrategy query 解析 + expNav 跳数据集列表)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.promote.test.ts`(扰动位徽标用例)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(siblingPerturbs/focusJump/expNav 跳转用例)

**Interfaces:**
- Consumes: Task 1 `TPL_FULL_RE`;Task 2 StrategyForm 的 isAssertion 动作行区。
- Produces(Task 5 消费): 跳转 query 契约 `/composer/:scenarioId?step=4&focusStep=<stepIdx>&focusStrategy=<strategyIdx>`(step=4 直入 Canvas 向导页;focusStep/focusStrategy 0-based);Canvas prop `focusJump?: { stepIdx: number; strategyIdx: number } | null`(挂载后一次性消费:切 activeStepIdx + onStrategyJump)。

- [ ] **Step 1: 写失败测试**

FieldForm.promote.test.ts 追加(骨架仿该文件既有用例的 mount 模式):

```typescript
/**
 * 扰动位徽标(spec §5.1):提升后的输入字段行挂"扰动位"徽标 ——
 * 叶子行值整串 ${var.x} 模板 + 容器模板态(node-tpl-badge)文案从
 * "引用变量"升级为"扰动位"(数据集行可逐行换值的身份呈现,零新通路)。
 */
it('PRT-1: 叶子行值整串 ${var.x} → .perturb-badge "扰动位"', async () => {
  // mount FieldForm,body 含 { amount: '${var.amount}' }(该文件既有 mount 模式)
  // 断言:amount 行的 .field-label 内 .perturb-badge 存在且文案含"扰动位";
  //       字面量字段行无该徽标
})

it('PRT-2: 容器模板态徽标文案升级"扰动位"', async () => {
  // mount FieldForm,body 含整容器模板 { supplier: '${var.supplier}' }(V1 同款形态)
  // 断言:.node-tpl-badge 存在且文案含"扰动位"(不再只是"引用变量")
})
```

(用例体以该文件既有 mount 工具为准内联展开——先读 FieldForm.promote.test.ts 的既有构造器再写,断言面如上两句。)

CaseComposerCanvas.test.ts 追加 describe:

```typescript
/**
 * 编排器呈现与导航(spec §5.1/§5.3):同步骤扰动位列表 + focusJump
 * 跨路由定位(期望列头↔断言卡)+ expNav 上抛跳数据集。
 */
describe('CaseComposerCanvas — 扰动位呈现与跳转(§5.3)', () => {
  it('N1: 断言卡显示"同步骤扰动位"var 名列表(诚实粒度 = 同步骤)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([{ kind: 'assertion', label: '断言' }])
    try {
      const s0 = mkStep({
        request: { kind: 'request', body: { amount: '${var.amount}', policy_id: '${var.policy_id}', plain: 'x' } },
        strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' } as any],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      await w.find('.sf-head').trigger('click')
      const row = w.find('.sf-perturb-row')
      expect(row.exists()).toBe(true)
      expect(row.text()).toContain('amount')
      expect(row.text()).toContain('policy_id')
      expect(row.text()).not.toContain('plain')     // 字面量不是扰动位
      expect(row.text()).not.toContain('exp_code')  // 期望列自身不进扰动位列表
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })

  it('N2: focusJump prop → 切步 + 定位策略卡(sf-flash 复用 B4 通路)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([{ kind: 'assertion', label: '断言' }])
    const origScroll = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = function () {}
    try {
      const s0 = mkStep()
      const s1 = mkStep({
        strategy: [
          { kind: 'assertion', target: '$.response_body.a', operator: 'eq', expected: null } as any,
          { kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' } as any,
        ],
      })
      // mountCanvas 的 Parent h() 里给 Canvas 加 :focus-jump="{ stepIdx: 1, strategyIdx: 1 }"
      // (本地复制 mountCanvas 骨架改 props,不改公用 mountCanvas)
      // 断言:中栏标题输入值为 s2(切步);#strategy-card-1 有 sf-flash 且展开
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
      Element.prototype.scrollIntoView = origScroll
    }
  })

  it('N3: 多视图前移提示 — 同 var 引用字段声明视图 >1 → 软提示(§5.1)', async () => {
    // fixture:新 mock 端点 ep-vs2($.a 绑 view v1,$.b 绑 view v2);
    // body { a: '${var.q}', b: '${var.q}' } → 同 var 双视图 → onVarPromote('q') 时
    // ElMessage.warning 软提示 spy 命中,文案含"多视图"与"手输"
    const warnSpy = vi.spyOn(ElMessage, 'warning').mockImplementation(() => {})
    // ...(挂载后从 Canvas 实例触发 onVarPromote 通路:走 FieldForm"设为变量"
    //     DOM 路径太长 — 直接对 canvas.vm 调用不可得(setup 不暴露);
    //     落法:mountCanvas 后通过 FieldForm 菜单路径或最小化为对
    //     viewsOfVarRef 的间接断言 — 实施时以"断言卡外的请求字段行触发
    //     varPromote 事件 + spy 文案"内联完整用例,spy finally 恢复)
    warnSpy.mockRestore()
  })
})
```

N2/N3 的内联展开:实施者按注释补全 DOM 操作(N2 复制 mountCanvas 骨架加 focusJump prop;N3 若 DOM 路径证实过重,允许降级为对 `viewsOfVarRef` 求值结果的组件级断言——通过挂载后读 `.sf-perturb-row` 等已证明的通路旁证,但 ElMessage.warning spy 必须命中一次)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldForm.promote.test.ts src/components/composer/__tests__/CaseComposerCanvas.test.ts`
Expected: FAIL — .perturb-badge / .sf-perturb-row 找不到

- [ ] **Step 3: 实现 FieldForm 扰动位徽标**

`FieldForm.vue`(注意:只加不改用户 WIP 区;改动集中两处):

① 叶子行 label 区:值整串模板时挂徽标。找到叶子行 `.field-label` 渲染位(label-text/path-badge/strategy-tag 所在行内),追加:

```html
<span
  v-if="isPerturb(n)"
  class="perturb-badge"
  title="扰动位 — 该字段值由 ${var.*} 模板供值,数据集行可逐行换值(spec §5.1)"
>扰动位</span>
```

script 区(computed/函数区,现场按既有命名风格放):

```typescript
/** 扰动位(spec §5.1):叶子值整串 ${var.x} 模板 → 徽标(身份呈现,零新通路) */
function isPerturb(node: FieldNode): boolean {
  const v = nodeBindingValue(node)   // ← 现场对齐:该组件取叶子当前绑定值的既有 getter
  return typeof v === 'string' && /^\$\{var\.[A-Za-z0-9_.]+\}$/.test(v)
}
```

(`nodeBindingValue` 以 FieldForm 现场取值通路为准 —— 叶子行值即 bindings 的 value/body 键,Read 文件对齐;若模板里已有现成值变量直接复用。)

② 容器模板态:`node-tpl-badge` 的文案从"引用变量"改为"扰动位",title 改为"扰动位 — 整容器由 ${var.*} 模板供值,数据集行可逐行换值"。**只改这两个字符串,不动该徽标的结构与样式类名**(V1 用例只断言存在性,零破坏)。

```css
.perturb-badge {
  font-size: 10px; font-weight: 700; color: #1d4ed8;
  background: #dbeafe; padding: 1px 5px; border-radius: 3px; flex-shrink: 0;
}
```

- [ ] **Step 4: 实现 StrategyForm 同步骤扰动位列表**

props 加:

```typescript
/** 同步骤扰动位列表(spec §5.3 反向导航):Canvas 推导的当前步 ${var.*} 名集 */
siblingPerturbs?: string[]
```

sf-exp-row(Task 2 已建)内追加(有扰动位才渲染):

```html
<div v-if="siblingPerturbs && siblingPerturbs.length" class="sf-perturb-row">
  <span class="sf-perturb-label" title="本步骤请求侧的扰动位 — 与本断言的数据关联 = 数据集行共现(spec §4.3,导航粒度诚实停在同步骤)">同步骤扰动位:</span>
  <span v-for="p in siblingPerturbs" :key="p" class="sf-perturb-name">{{ p }}</span>
</div>
```

```css
.sf-perturb-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 4px 10px; }
.sf-perturb-label { font-size: 11px; color: #64748b; }
.sf-perturb-name { font-family: var(--font-mono); font-size: 10px; color: #1d4ed8; background: #dbeafe; padding: 1px 5px; border-radius: 3px; }
```

- [ ] **Step 5: 实现 Canvas siblingPerturbs + focusJump + 多视图提示**

`CaseComposerCanvas.vue`:

```typescript
import { TPL_FULL_RE } from '@/utils/dataset-segments'

/** 同步骤扰动位(spec §5.3):当前步请求侧值整串 ${var.x} 的 var 名集 */
const siblingPerturbs = computed<string[]>(() => {
  const step = currentStep.value
  if (!step) return []
  const names = new Set<string>()
  const visit = (v: unknown): void => {
    if (typeof v === 'string') {
      const m = TPL_FULL_RE.exec(v)
      if (m) names.add(m[1])
    } else if (Array.isArray(v)) v.forEach(visit)
    else if (v && typeof v === 'object') Object.values(v).forEach(visit)
  }
  visit(step.request?.body)
  const headers = step.api?.headers
  if (headers && typeof headers === 'object') visit(headers)
  return [...names]
})
```

StrategyForm 挂载处传 `:sibling-perturbs="siblingPerturbs"`。

focusJump(props 类型追加,现场对齐 defineProps 块):

```typescript
/** 跨路由跳转消费(spec §5.3 期望列头→断言卡):挂载后一次性切步+定位 */
focusJump?: { stepIdx: number; strategyIdx: number } | null
```

```typescript
let focusApplied = false
watch(() => props.focusJump, (j) => {
  if (!j || focusApplied) return
  focusApplied = true
  const maxIdx = Math.max(0, (props.steps?.length ?? 1) - 1)
  activeStepIdx.value = Math.min(Math.max(0, j.stepIdx), maxIdx)
  nextTick(() => onStrategyJump(Math.max(0, j.strategyIdx)))
}, { immediate: true })
```

多视图前移提示(onVarPromote/onVarInsert 各加一道,§5.1):

```typescript
/** §5.1 多视图前移提示:引用该 var 的字段,其端点声明 value_source 视图 >1
 *  → 软提示(§8.4 查钮将退化手输)。声明面复用 Canvas 既有的 value_source
 *  查找通路(与 vs 查钮/徽标同源 —— Grep value_source in 本文件对齐变量名)。 */
function warnMultiViewVar(name: string) {
  const step = currentStep.value
  if (!step) return
  const views = new Set<string>()
  const visit = (v: unknown, fullPath: string): void => {
    if (typeof v === 'string') {
      if (TPL_FULL_RE.test(v) && v === `\${var.${name}}`) {
        const vs = valueSourceOfPath(step, fullPath)   // ← 现场对齐:vs 查钮既有声明查找
        if (vs) views.add(vs.view)
      }
    } else if (Array.isArray(v)) v.forEach((item, i) => visit(item, `${fullPath}[${i}]`))
    else if (v && typeof v === 'object') {
      for (const [k, child] of Object.entries(v)) visit(child, fullPath ? `${fullPath}.${k}` : k)
    }
  }
  visit(step.request?.body, '')
  if (views.size > 1) {
    ElMessage.warning(`同 var 多视图(${[...views].join('、')})— 数据集查钮将退化手输(§8.4);统一视图绑定或拆 var 名可解除`)
  }
}
```

`valueSourceOfPath(step, fullPath)` 的实现:在 Canvas 内 Grep 既有 `value_source` 消费(vs 查钮推导/徽标),复用同一声明映射(endpoint /full declarations 按 path 匹配)。若该映射是模板路径(无 [i])键控,visit 里匹配前先剥 `[N]`(toTemplatePath 既有工具,取数源实现先例)。onVarPromote 尾部与 onVarInsert 尾部各调 `warnMultiViewVar(name)`。

- [ ] **Step 6: 实现 CaseComposer query 解析与 expNav 跳转**

`CaseComposer.vue` — onMounted 既有 route.query.step 处理(:560-562)旁追加:

```typescript
const focusJump = ref<{ stepIdx: number; strategyIdx: number } | null>(null)

// onMounted 内(step query clamp 之后):
const fs = Number(route.query.focusStep)
const fy = Number(route.query.focusStrategy)
if (Number.isInteger(fs) && Number.isInteger(fy) && fs >= 0 && fy >= 0) {
  stepIdx.value = 3   // 直入 ④ Canvas 向导页
  focusJump.value = { stepIdx: fs, strategyIdx: fy }
}
```

Canvas 挂载(:150-160)传 `:focus-jump="focusJump"`、加 `@exp-nav="onExpNav"`:

```typescript
/** 断言卡"↗ 数据集"(spec §5.3 反向):跳该场景的数据集列表页 */
function onExpNav() {
  router.push(scenarioDataSetsUrl(scenarioId))
}
```

(`scenarioDataSetsUrl` 若非既有 import,从 `@/utils/links` 引;scenarioId 以现场变量名为准。)

- [ ] **Step 7: 跑测试确认通过 + 全量回归**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldForm.promote.test.ts src/components/composer/__tests__/CaseComposerCanvas.test.ts src/views/__tests__`
Expected: PASS(新增 PRT-1/2、N1-N3 全绿;既有 V1/B4/I3 等零回归)

- [ ] **Step 8: 选择性暂存并提交(控制者执行)**

实施者完成后**不自行提交 FieldForm.vue**。控制者流程:

```bash
git diff src/gimbal-platform/frontend/src/components/composer/FieldForm.vue
# 逐 hunk 核验:只暂存扰动位徽标相关 hunk(叶子行 label 区/node-tpl-badge 文案/
# .perturb-badge 样式),用户 WIP hunk(.fa-slot/.cand-btn/svg 菜单钮区)排除
# 方式:git add -p 选 hunk,或 git diff > /tmp/ff.patch 手工裁剪后 git apply --cached
git add src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.promote.test.ts src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts
git status   # 核验 FieldForm.vue 处于 partially staged(部分暂存)且 FieldActionMenu.vue 未暂存
git commit -m "feat(frontend): 扰动位徽标 + 同步骤扰动位列表 + focusJump 跨路由跳转 + 多视图前移软提示

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: DataSetEditor 段网格核心(段 tabs + 段内列 + 行名列钉选 + "全部"阈值 + 直填列退场)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/DataSetEditor.vue`(表格区 :129-266 段化改造 + 基线区直填行补编辑)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts`(新建,骨架仿 DataSetEditor.palette.test.ts 的挂载/mock 模式)

**Interfaces:**
- Consumes: Task 1 全部导出(deriveSegments/gridColumnsOf/sharedVarNames/GridVarColumn);既有 dataset-grid 的 cellDisplay/gridStats/parseTsvPaste/applyPastePlan(零改动)。
- Consumes: 既有 stepLabel(stepIndex)(本组件内,读 orchestration 步名)。
- Produces(Task 5 消费): 组件内状态 `activeSegment: Ref<'all' | number>`、`visibleColumns: ComputedRef<GridVarColumn[]>`、期望列头徽标渲染(`.exp-col-badge`,title 带 target/operator;跳转按钮 Task 5 加)。

- [ ] **Step 1: 写失败测试**

```typescript
// src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts
/**
 * DataSetEditor 段网格(spec §6.2,2026-09-10):列作用域收缩到单 step 段。
 * 段 tabs 派生(引用扫描)/ 段内列过滤 / 行名列常驻钉选 / "全部"阈值 ≤8
 * 默认全部 / 直填列退场数据表格(基线区可编辑)/ 期望列徽标。
 * 骨架(api mock + route stub)复制 DataSetEditor.palette.test.ts。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
// ...(从 DataSetEditor.palette.test.ts 复制:vi.mock('@/api/scenario-composer')、
//    route params stub、ElementPlus 插件、挂载工厂 mountEditor())

/** 三步场景:step1(amount + exp_code)/ step2(bl_no)/ step3(无引用)→ 两段 */
const DEF_2SEG = {
  meta: { name: 's' }, config: { vars: { amount: 100, exp_code: 200, bl_no: 'BL1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} }, request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '${var.exp_code}' }] },
    { kind: 'step', description: '查单', api: { headers: {} }, request: { kind: 'request', body: { bl_no: '${var.bl_no}' } }, strategy: [] },
    { kind: 'step', description: '第三步', api: { headers: {} }, request: { kind: 'request', body: { plain: 'x' } }, strategy: [] },
  ],
}

describe('DataSetEditor — 段网格(§6.2)', () => {
  it('SEG-1: 段 tabs 派生(两段)+ "全部";总列数 ≤8 默认全部;行名列常驻', async () => {
    const w = await mountEditor(DEF_2SEG)   // 挂载工厂:getDataSet 返回 rows:[{amount:'-1'}], draft 返回 DEF_2SEG
    const tabs = w.findAll('.seg-tab')
    expect(tabs.map((t) => t.text()).join('|')).toContain('步骤1')
    expect(tabs.map((t) => t.text()).join('|')).toContain('步骤2')
    expect(tabs.map((t) => t.text()).join('|')).toContain('全部')
    expect(w.find('.seg-tab.active').text()).toContain('全部')   // 3 列 ≤8 → 默认全部
    // 行名列钉选:数据表格首列数据名输入在场
    expect(w.find('.data-name-input').exists()).toBe(true)
    w.unmount()
  })

  it('SEG-2: 切段 → 段内列过滤(输入+期望并排),他段列退场', async () => {
    const w = await mountEditor(DEF_2SEG)
    await w.findAll('.seg-tab').find((t) => t.text().includes('步骤1'))!.trigger('click')
    // 段1 列头:amount + exp_code(期望徽标);bl_no 退场
    const heads = w.findAll('.row-field .th-data').map((t) => t.text()).join()
    expect(heads).toContain('amount')
    expect(heads).toContain('exp_code')
    expect(heads).toContain('期望')        // 期望列徽标文案
    expect(heads).not.toContain('bl_no')
    w.unmount()
  })

  it('SEG-3: 总列数 >8 默认第一段(阈值 8)', async () => {
    // 9 列场景:step1 9 个 ${var} 字段 + step2 1 个 → 默认选中步骤1
    const w = await mountEditor(DEF_9COLS)
    expect(w.find('.seg-tab.active').text()).toContain('步骤1')
    w.unmount()
  })

  it('SEG-4: 直填列退场数据表格;基线区直填行改为可编辑输入', async () => {
    const w = await mountEditor(DEF_2SEG)   // step3 plain 字面量(直填列)
    await w.findAll('.seg-tab').find((t) => t.text().includes('全部'))!.trigger('click')
    // 数据表格无直填输入(.data-cell-direct 退场)
    expect(w.find('.data-cell-direct').exists()).toBe(false)
    // 基线区直填行有编辑输入(展开基线折叠后可见;baseline-collapse 展开以现场结构为准)
    // 断言:基线区 plain 行内 input.baseline-direct-input 存在
    w.unmount()
  })

  it('SEG-5: 期望列可编辑(行值 = row[varName]),placeholder = config.vars 基线', async () => {
    const w = await mountEditor(DEF_2SEG)
    const expInput = w.findAll('.data-cell-input').find((el) =>
      (el.element as HTMLInputElement).placeholder === '200')
    expect(expInput).toBeTruthy()          // exp_code 基线 200
    w.unmount()
  })

  it('SEG-6: TSV 粘贴/行增删/caseNames 保留(既有行为零回归)', async () => {
    // 复用 palette 测试的粘贴/行操作断言模式:段视图下粘单列纵向 → 段内首列落值;
    // + 新增数据按钮加行;行名输入可改
    // (以 palette.test.ts 既有 paste 断言为蓝本内联,断言面不变)
  })
})
```

(mountEditor 挂载工厂与 DEF_9COLS 构造,实施时从 palette.test.ts 复制 mock 骨架后内联补全——**断言面以上述为准,不得删减**。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/DataSetEditor.segments.test.ts`
Expected: FAIL — .seg-tab 找不到

- [ ] **Step 3: 实现段网格**

`DataSetEditor.vue` script 区追加:

```typescript
import {
  deriveSegments, gridColumnsOf, sharedVarNames, deadRowKeys,
  type GridVarColumn,
} from '@/utils/dataset-segments'

/** 段派生(spec §6.2):打开编辑器对场景一次引用扫描(纯前端投影) */
const segments = computed(() => deriveSegments(
  draft.value?.definition?.steps ?? [],
  draft.value?.definition?.config?.vars ?? {},
))
const segSharedVars = computed(() => sharedVarNames(segments.value))
const ALL_THRESHOLD = 8   // "全部"仅小场景:全段列数 ≤8 默认全部(spec §6.2 初值)

type SegSel = 'all' | number
const activeSegment = ref<SegSel>('all')
const segInitialized = ref(false)
watch(segments, (segs) => {
  if (segInitialized.value || !segs.length) return
  segInitialized.value = true
  const total = segs.reduce((n, s) => n + gridColumnsOf(s).length, 0)
  activeSegment.value = total <= ALL_THRESHOLD ? 'all' : 0
}, { immediate: true })

/** 段内可编辑列(行键 = varName);'all' = 全段并排(小场景) */
const visibleColumns = computed<GridVarColumn[]>(() => {
  if (activeSegment.value === 'all') return segments.value.flatMap(gridColumnsOf)
  const seg = segments.value[activeSegment.value]
  return seg ? gridColumnsOf(seg) : []
})
```

模板改造(数据表格区 :129-266):

① 工具栏下、`grid-scroll` 上加段 tabs:

```html
<div v-if="segments.length > 1" class="seg-tabs">
  <button
    v-for="(seg, si) in segments"
    :key="`segtab:${seg.stepIndex}`"
    type="button"
    class="seg-tab"
    :class="{ active: activeSegment === si }"
    @click="activeSegment = si"
  >步骤{{ seg.stepIndex + 1 }} · {{ stepLabel(seg.stepIndex) }}</button>
  <button
    type="button"
    class="seg-tab"
    :class="{ active: activeSegment === 'all' }"
    @click="activeSegment = 'all'"
  >全部({{ segments.reduce((n, s) => n + gridColumnsOf(s).length, 0) }} 列)</button>
</div>
```

```css
.seg-tabs { display: flex; gap: 6px; flex-wrap: wrap; padding: 8px 12px 0; }
.seg-tab { border: 1px solid #e6e8ec; background: #fff; border-radius: 6px; padding: 4px 12px; font-size: 12px; cursor: pointer; color: #475569; }
.seg-tab.active { border-color: #4f46e5; color: #4f46e5; background: #eef2ff; font-weight: 600; }
```

② 表格列从 `allColumns`(基线列 var+direct)换成 `visibleColumns`:colgroup 的 `col-data` 循环、row-desc/row-field 两个表头行的 th 循环、tbody 的 td 循环全部换迭代源。列头字段行:

```html
<th
  v-for="col in visibleColumns"
  :key="`info-f:${col.stepIndex}:${col.source}:${col.varName}`"
  class="th-data"
  :class="col.source === 'expect' ? 'col-expect' : ''"
  :title="col.source === 'expect'
    ? `期望列 ${col.varName} — 断言 ${col.expect?.target} ${col.expect?.operator}(步骤${col.stepIndex + 1})`
    : `${col.stepIndex + 1} 步 ${col.source} · ${col.field}`"
>
  {{ col.varName }}
  <span
    v-if="segSharedVars.has(col.varName)"
    class="shared-mark"
    title="该变量被多个步骤引用 — 数据行里改一处,所有引用处生效"
  >共享</span>
  <span
    v-if="col.source === 'expect'"
    class="exp-col-badge"
    :title="`期望列 — 断言 ${col.expect?.target} ${col.expect?.operator}`"
  >期望</span>
</th>
```

```css
.col-expect .exp-col-badge { font-size: 10px; font-weight: 700; color: #6b21a8; background: #f3e8ff; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }
.th-data.col-expect { background: #faf5ff; }
```

③ 单元格(期望列与输入列同款,row 键 = varName):

```html
<td
  v-for="col in visibleColumns"
  :key="`c:${i}:${col.stepIndex}:${col.source}:${col.varName}`"
  :class="['td-data', cellClass(row, { kind: 'var', varName: col.varName, baseline: col.baseline }), col.source === 'expect' ? 'col-expect' : '']"
  :title="col.baseline ?? ''"
>
  <input
    :value="row[col.varName] ?? ''"
    class="data-cell-input"
    :placeholder="col.baseline === undefined || col.baseline === null ? '' : String(col.baseline)"
    @input="(e: Event) => onCellInput(i, { kind: 'var', varName: col.varName, baseline: col.baseline } as BaselineColumn, (e.target as HTMLInputElement).value)"
    @paste="(e: ClipboardEvent) => onCellPaste(e, { kind: 'var', varName: col.varName, baseline: col.baseline } as BaselineColumn, i)"
  />
</td>
```

(cellClass/onCellInput/onCellPaste 既有签名消费 BaselineColumn 形状 —— 以最小适配对象 `{kind:'var', varName, baseline}` 传入,现场对齐参数形状;TSV 粘贴的列定位随之落在段内可见列,粘贴语义 = 当前段。)

④ row-step-group(colspan 分组行)与 isStepStart/isPromotableVar 列样式链:段模式下分组行退场 —— `v-if="activeSegment === 'all'"` 保留、单段时不渲染;`isStepStart(ci)` 列分隔样式在段模式下无意义,th/td 的该 class 绑定删除或仅 'all' 下保留(以编译零错为准,倾向删除——段边界已由 tabs 承载)。

⑤ 直填列退场:数据表格不再渲染 direct 单元格(上面 td 循环已只出 var 列);基线区直填行(baseline-row kind==='direct')把只读 `direct-val` span + 提升按钮换为编辑输入(提升按钮 Task 6 再退,本任务先补编辑):

```html
<template v-else>
  <input
    class="baseline-direct-input"
    :value="directBaselineValue(col)"
    :placeholder="col.baseline || '空'"
    @input="(e: Event) => setDirectBaseline(col, (e.target as HTMLInputElement).value)"
  />
  <el-button size="small" text type="primary" @click="promote(col)">提升为变量</el-button>
</template>
```

⑥ varColumns computed(粘贴/CSV/统计消费的既有列集):改为与 visibleColumns 一致的段过滤投影 —— `varColumns = computed(() => visibleColumns.value.map(c => ({ kind: 'var', varName: c.varName, baseline: c.baseline } as BaselineColumn)))`;CSV 导入导出链(varOnlyPalette 消费)**零改动**(全宇宙,不随段过滤)。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/DataSetEditor.segments.test.ts src/views/__tests__/DataSetEditor.palette.test.ts src/utils/__tests__/dataset-grid.test.ts`
Expected: PASS(新 SEG-1~6 + palette/grid 既有零回归)

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/frontend/src/views/DataSetEditor.vue src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts
git commit -m "feat(frontend): DataSetEditor 段网格 — 段 tabs/段内列/行名列钉选/全部阈值8/直填列退场

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 行详情只读垂直呈现 + 期望列头跳转 + 死行键软提示

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/DataSetEditor.vue`(预览弹窗升级行详情 + 期望列头 ↗ 跳转按钮 + 死键提示条)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts`(追加用例)

**Interfaces:**
- Consumes: Task 3 跳转 query 契约(`/composer/:scenarioId?step=4&focusStep=&focusStrategy=`);Task 4 的 visibleColumns/segments;Task 1 的 deadRowKeys。
- Produces: 无(终端呈现)。

- [ ] **Step 1: 写失败测试(追加到 DataSetEditor.segments.test.ts)**

```typescript
describe('DataSetEditor — 行详情 + 期望列头跳转 + 死行键(§6.2/§5.3/§7)', () => {
  it('DET-1: 预览弹窗升级行详情 — 按段分组垂直呈现,含继承态标注', async () => {
    const w = await mountEditor(DEF_2SEG)   // rows: [{amount:'-1', exp_code:'400'}]
    // 勾选首行 + 点"预览选中的数据" → 弹窗按段分组:
    // 段头"步骤1 · 下单"在场;amount 行标注"覆写"、bl_no 行标注"继承基线"
    // (el-dialog teleport:从 document 查 .detail-seg-head / .detail-flag,仿 T12 模式)
    w.unmount()
  })

  it('DET-2: 期望列头 ↗ 跳转按钮 → router.push composer + focusStep/focusStrategy query', async () => {
    // mock useRouter(仿 palette 测试骨架的 vue-router stub 方式):
    // 挂载(两段)→ 切"全部"或步骤1 → 点 exp_code 列头 .exp-jump
    // 断言 push 以 { path: `/composer/${scenarioId}`, query: { step: '4', focusStep: '0', focusStrategy: '0' } }
    // 调用(exp_code 的断言 strategyIdx=0,stepIndex=0)
  })

  it('DET-3: 死行键软提示条 — 行键 ∉ config.vars → 标黄提示,可继续编辑', async () => {
    // rows: [{ amount:'-1', ghost_key:'x' }](ghost_key 不在 vars)
    // 断言:.dead-keys-bar 存在且文案含 ghost_key 与"运行无效果";无任何阻断性 disabled
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/DataSetEditor.segments.test.ts`
Expected: FAIL — .detail-seg-head / .exp-jump / .dead-keys-bar 找不到

- [ ] **Step 3: 实现**

`DataSetEditor.vue`:

① 行详情(previewDialog 弹窗改造 —— 预览 merged JSON 升级为按段分组):

```typescript
/** 行详情(§6.2 v1 只读):整条数据垂直呈现,按段分组 + 继承态标注 */
const previewedDetail = computed(() => previewedRows.value.map((item) => {
  const row = rows.value[item.index] ?? {}
  return {
    ...item,
    groups: segments.value.map((seg) => ({
      stepIndex: seg.stepIndex,
      label: `步骤${seg.stepIndex + 1} · ${stepLabel(seg.stepIndex)}`,
      items: gridColumnsOf(seg).map((c) => ({
        varName: c.varName,
        value: Object.prototype.hasOwnProperty.call(row, c.varName) ? row[c.varName] : c.baseline,
        inherited: !Object.prototype.hasOwnProperty.call(row, c.varName),
        expect: c.expect,
      })),
    })),
    dead: deadRowKeys(draft.value?.definition?.config?.vars ?? {}, [row]),
  }
}))
```

弹窗模板(preview-list 区替换,既有 merged JSON 块退场):

```html
<div v-for="item in previewedDetail" :key="item.index" class="preview-item">
  <div class="preview-header">
    <span class="preview-name">{{ item.name }}</span>
    <span class="muted">第 {{ item.index + 1 }} 行</span>
  </div>
  <div v-for="g in item.groups" :key="g.stepIndex" class="detail-seg">
    <div class="detail-seg-head">{{ g.label }}</div>
    <div v-for="it in g.items" :key="it.varName" class="detail-row">
      <span class="detail-name mono">{{ it.varName }}</span>
      <span v-if="it.expect" class="exp-col-badge" :title="`断言 ${it.expect.target} ${it.expect.operator}`">期望</span>
      <span class="detail-val mono">{{ it.value === undefined ? '(未声明基线)' : JSON.stringify(it.value) }}</span>
      <span class="detail-flag" :class="it.inherited ? 'inh' : 'ovr'">{{ it.inherited ? '继承基线' : '覆写' }}</span>
    </div>
  </div>
  <div v-if="item.dead.length" class="detail-dead">死键(变量已删,运行无效果):{{ item.dead.join(', ') }}</div>
</div>
```

```css
.detail-seg-head { font-size: 12px; font-weight: 700; color: #475569; margin: 8px 0 4px; }
.detail-row { display: flex; gap: 8px; align-items: center; padding: 2px 0 2px 12px; font-size: 12px; }
.detail-name { min-width: 120px; color: #334155; }
.detail-val { color: #0f172a; }
.detail-flag { font-size: 10px; padding: 1px 6px; border-radius: 3px; }
.detail-flag.inh { color: #64748b; background: #f1f5f9; }
.detail-flag.ovr { color: #b45309; background: #fef3c7; }
.detail-dead { margin-top: 6px; font-size: 11px; color: #b45309; background: #fef3c7; padding: 4px 8px; border-radius: 4px; }
```

② 期望列头跳转(Task 4 的 th 内追加,非 expect 列不渲染):

```html
<button
  v-if="col.source === 'expect'"
  type="button"
  class="exp-jump"
  :title="`跳编排器断言卡 — ${col.expect?.target} ${col.expect?.operator}`"
  @click.stop="jumpToAssertion(col)"
>↗</button>
```

```typescript
/** 期望列头 → 断言卡直跳(spec §5.3):路由携带 focusStep/focusStrategy,
 *  CaseComposer onMounted 消费(Task 3 契约)。 */
function jumpToAssertion(col: GridVarColumn) {
  if (!col.expect) return
  router.push({
    path: `/composer/${scenarioId}`,
    query: {
      step: '4',
      focusStep: String(col.stepIndex),
      focusStrategy: String(col.expect.strategyIdx),
    },
  })
}
```

```css
.exp-jump { border: none; background: transparent; color: #7c3aed; cursor: pointer; font-size: 12px; padding: 0 2px; }
.exp-jump:hover { color: #4c1d95; }
```

③ 死键提示条(段 tabs 下):

```typescript
const deadKeys = computed(() => deadRowKeys(draft.value?.definition?.config?.vars ?? {}, rows.value))
```

```html
<div v-if="deadKeys.length" class="dead-keys-bar">
  ⚠ {{ deadKeys.length }} 个行键不在列宇宙(变量已删):{{ deadKeys.join(', ') }} — 运行无效果,可继续编辑(spec §7 软提示)
</div>
```

```css
.dead-keys-bar { margin: 6px 12px 0; font-size: 11px; color: #b45309; background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 5px 10px; }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/DataSetEditor.segments.test.ts`
Expected: PASS(DET-1~3 + SEG-1~6 全绿)

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/frontend/src/views/DataSetEditor.vue src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts
git commit -m "feat(frontend): 行详情按段分组只读呈现 + 期望列头跳断言卡 + 死行键软提示

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 提升退场(裁定 A — promote/demote/demoteLast 整体移除)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/DataSetEditor.vue`(promote 链清理)
- Test: 既有测试中 promote 相关用例的清理(以 grep 结果为准,预期含 `DataSetEditor.palette.test.ts`)

**Interfaces:**
- Consumes: Task 4/5 完成后的段网格(基线区直填行编辑已由 Task 4 补位)。
- Produces: 无(纯退场)。

- [ ] **Step 1: grep 引用面**

Run: Grep `promote|demote|promotedKeys|promotedOrder|isPromotableVar|col-promoted` in `src/gimbal-platform/frontend/src`(views/DataSetEditor.vue + __tests__/ 全部命中)。

- [ ] **Step 2: 删除实现链**

`DataSetEditor.vue` 删除:
- `promote`(:430 附近)/`demote`(:464)/`demoteLast`(:512)三函数;
- `promotedKeys` / `promotedOrder` 状态与顶栏"撤销最近一次提升"按钮(以 grep 定位);
- 基线区直填行"提升为变量"按钮(Task 4 已改该行,本任务删按钮,保留 baseline-direct-input 编辑)与 var 行"撤销提升"按钮(isPromotableVar 块);
- `isPromotableVar` 函数与模板里全部 `col-promoted` class 绑定、相关 scoped 样式。

**保留**:基线区 var 行基线值编辑(baselineValue/setBaseline — config.vars 基线编辑入口)、直填行编辑(Task 4)、全部段网格/行详情/死键提示。

- [ ] **Step 3: 清理既有测试**

`DataSetEditor.palette.test.ts`(及 grep 命中的其它文件)中 promote/demote/撤销提升相关用例删除或改写为退场后语义(如"直填行编辑改基线"保留);**只动 promote 族用例,palette/grid 断言面零删减**(Global Constraints 测试钉死例外条款的显式范围)。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/ src/utils/__tests__/dataset-grid.test.ts`
Expected: PASS(promote 族用例已随退场移除,其余零回归)

- [ ] **Step 5: 提交**

```bash
git add src/gimbal-platform/frontend/src/views/DataSetEditor.vue src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.palette.test.ts
# (以 grep 实际命中文件为准补全 add 清单)
git commit -m "refactor(frontend): 编辑器提升退场(裁定 A)— 列宇宙=config.vars,编辑器只消费不声明

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 终审回归(老数据集兼容 + 前端全套件 + 零漂论证)

**Files:**
- Test: `src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts`(老数据集兼容用例)
- 无产品代码改动(发现问题 → 回对应任务修)

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 回归报告(留 SDD workspace)。

- [ ] **Step 1: 老数据集兼容用例**

```typescript
it('COMPAT-1: 旧提升流数据集(rows 键=var 名,直填列存在)打开不炸,行名/TSV/三态全在', async () => {
  // 场景:两步、step1 body { amount: '${var.amount}', remark: '直填字面量' }、
  // 无任何 assertion expected 模板(旧形态);dataset rows: [{amount:'5'},{amount:'6'}]
  // 挂载断言:段 tabs 派生正常(step1 一段);数据名输入 2 个;amount 单元格
  // 值 '5'/'6' 三态正常;remark 直填不出数据表格(基线区可编辑);
  // 保存链不炸(点保存 → updateScenario 被调,rows 形状零变化)
})
```

- [ ] **Step 2: 前端全套件 + 类型门**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: vitest 全绿(基线 673 通过数 + 新增 − promote 族删除,具体数字以跑出为准,零 fail 零 skip 异常);vue-tsc 0 error。

- [ ] **Step 3: 零漂论证(diff 面自证)**

```bash
git diff --stat 571f24a4..HEAD   # 本分支全部提交(不含用户 WIP)
```

核验:改动 ⊆ `src/gimbal-platform/frontend/`(zero backend / zero plate / zero gimbal 引擎)→ 场景定义存储、端点注册、dispatch 物化输入面零触碰 → dispatch 基线与 plate golden 零漂自证(plate/backend 套件按纪律**不跑**)。结论写入回归报告 `.superpowers/sdd/2026-09-10-dataset-driven-refactor/task-7-report.md`。

- [ ] **Step 4: 提交(兼容用例)**

```bash
git add src/gimbal-platform/frontend/src/views/__tests__/DataSetEditor.segments.test.ts
git commit -m "test(frontend): 老数据集兼容钉 — 旧提升流行键/直填列/保存链零回归

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 自审记录(writing-plans Self-Review)

1. **Spec coverage**:§5.1(扰动位正名+徽标+多视图前移)→ Task 3;§5.2(期望提升/命名/撞名/逆动作/exp_* 标注)→ Task 2;§5.3(双向导航)→ Task 3(focusJump)+ Task 5(列头跳转)+ Task 2(断言卡↗数据集);§6.2(段网格/行详情/阈值8/行名钉选)→ Task 4/5;§6.3(promote 退场 + 保留清单)→ Task 6;§7(死行键软提示/exp_ 命名/行只标量)→ Task 1/5/2;§9.3(Task 0 盘点)→ Task 0;§11 ④(回归)→ Task 7;§12 手验 → 用户手验(不入计划任务)。零缺口。
2. **Placeholder scan**:Task 2/3 测试里的"骨架仿既有文件"处均给出了断言面全量(N3 的 ElMessage spy 命中为硬要求);Task 3 的 isPerturb/valueSourceOfPath 两处标注"现场对齐既有 getter/映射名"(指向既有代码的复用点,非留白逻辑);无 TBD/TODO。
3. **Type consistency**:`GridVarColumn{varName,baseline,stepIndex,source,field,expect?}` Task 1 定义、Task 4/5 消费一致;`deriveSegments(steps, vars)` 双参签名 Task 1/4 一致;`expectVarNameOf` Task 1 定义 Task 2 消费;`focusJump:{stepIdx,strategyIdx}` 与 query 契约 `focusStep/focusStrategy`(0-based)Task 3 定义 Task 5 消费一致;StrategyForm emits(expPromote/expRestore/expNav)Task 2 定义 = Canvas 接线一致;varDemote 链 Canvas emit → CaseComposer @var-demotion 命名一致(Vue kebab-case 映射)。
