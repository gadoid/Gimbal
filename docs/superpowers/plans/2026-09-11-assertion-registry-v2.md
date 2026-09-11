# 断言管理(偏离注入)V2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地断言管理(偏离注入)注册表:场景级 `assertion_registry` 节 + 编辑器 + 编排器标记 + RunDialog 注入条目多选 + backend 物化注入族 + 期望提升链(exp_*)退场。

**Architecture:** 注册表 = 场景文档 payload 第三键(与 orchestration 同级,引擎不感知)。数据集 = 正常数据变体(既有链不动);断言管理 = 偏离注入(条目自含 injection + asserts);唯一汇合点 = 运行时(RunDialog 多选 → RunRequest.injectionEntryIds → dispatcher 物化注入族)。物化 = 平台层 patch(基线 vars 覆写 + strategy patch),`materialize_run_copy` 本体零改动。

**Tech Stack:** Vue 3 + Element Plus + Pinia(vitest + vue-tsc)/ FastAPI + pydantic(pytest)/ plate 引擎零改动。

**Spec:** `docs/superpowers/specs/2026-09-11-assertion-registry-field-binding-design.md`(T0 已实施 bd15cc56;本计划覆盖 §12 的 T1-T6 与 T8)

> **进度 · 暂停点(2026-09-11)**:Task 1-5 已完成并双审收口(SDD 台账:`.superpowers/sdd/2026-09-11-assertion-registry-v2/progress.md`,含 Task 6 dispatch 恢复注记)—
> T1 `8d0da1ce`+`a6502ca4` / T2 `83a25038`+`ce32505f` / T3 `7d2930a6` / T4 `cde95c12`(WIP 选择性暂存) / T5 `244c0138`+`dfdef5eb`。
> 终态基线:前端 vitest 729 + vue-tsc 0,backend 446。**Task 6-8 未开工**(用户裁定暂停);恢复时 BASE = `dfdef5eb`。

## Global Constraints

- **分支**:`feat/dataset-driven-refactor` 续作(基线 ab5f1973);推送仅在用户明示时;PR 作废。
- **测试命令**:前端 `cd src/gimbal-platform/frontend && npx vitest run`(全量)+ `npx vue-tsc --noEmit`;backend `cd src/gimbal-platform/backend && python -m pytest tests -q`(已解冻,2026-09-11 用户裁定);**plate 套件继续冻结不跑**,plate 代码(执行核 resolver/jsonpath/context、export/gimbal.py、`src/gimbal-plate/**`)一行不动。
- **用户 WIP 文件**:`FieldActionMenu.vue`、`FieldForm.vue` 工作树常带用户未提交改动 — 在其当前版本上**只加新代码,不改既有行**;提交时只 add 本任务新增 hunk(`git diff <file> > /tmp/x.patch` 审阅后 `git apply --cached` 挑选,或 `git add -p`)。
- **永不提交/触碰**:`gimbal-tmp/`、`reports/test-report.html`、`probe_ui.js`、`src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_add_demo.py` 及 `endpoint/__init__.py` 的 3 行演示副本改动。
- **安全**:绝不自动重登录;SUT 凭证(Authorization token/Cookie/加密密码)不回显、不入库、不提交。
- **语义红线**(spec §1/§5/§9):数据集行纯 var-dict 零保留键;CSV 只导值;绑定配置 `assertion_bindings` 不建;模板即地址(未模板化字段不可标记进注册表);负向用例 v1 直接失败(不建终止机制);不建 exp_* 读兼容、不建迁移工具。
- **commit message** 尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- **注册表 JSON 键名** = `assertion_registry`(snake 原样,无 camelCase alias — 与 definition 的自由 dict 键策略一致,便于 grep)。

---

### Task 1: fieldPathsOf 全叶子扫描 utils(spec §4,spec 任务 T1)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/utils/dataset-segments.ts`(文件末尾追加)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/dataset-segments.test.ts`(文件末追加 describe)

**Interfaces:**
- Consumes: 同文件既有 `TPL_FULL_RE`(L14)、`SegmentStepShape`(L37-41)。
- Produces(Task 3 编辑器候选列表消费):
  ```ts
  export interface FieldLeaf { source: 'body' | 'headers'; path: string; varName?: string }
  export function fieldPathsOf(step: SegmentStepShape | null | undefined): FieldLeaf[]
  ```
  语义:`path` 带 `$.` 前缀(`$.amount` / `$.items[0].id`);值整串匹配 `${var.x}` 的叶子带 `varName`;未模板化/非字符串叶子只有 path;headers 只浅扫一层;null 算叶子,空对象/空数组无叶。

- [x] **Step 1: 写失败测试**(追加到 dataset-segments.test.ts 末尾)

```ts
import { fieldPathsOf } from '../dataset-segments'   // 若文件头已 import 同名模块则并入既有 import

describe('fieldPathsOf — 全叶子扫描(spec v2 §4)', () => {
  it('FP-1: body 深扫全叶子(模板/直填/深层/数组),path 带 $. 前缀,模板叶带 varName', () => {
    const step = {
      request: { body: {
        amount: '${var.amount}', remark: '直填',
        items: [{ id: 'x' }, { id: '${var.no}' }],
        nested: { deep: '1' },
      } },
    }
    expect(fieldPathsOf(step)).toEqual([
      { source: 'body', path: '$.amount', varName: 'amount' },
      { source: 'body', path: '$.remark' },
      { source: 'body', path: '$.items[0].id' },
      { source: 'body', path: '$.items[1].id', varName: 'no' },
      { source: 'body', path: '$.nested.deep' },
    ])
  })

  it('FP-2: 非字符串/null 叶仍报路径;空容器无叶;headers 浅扫且 ${auth.*} 不算 varName', () => {
    const step = {
      api: { headers: { Authorization: 'Bearer ${auth.u1.token}', X: '1' } },
      request: { body: { n: 5, b: true, nil: null, empty: {}, list: [] } },
    }
    expect(fieldPathsOf(step)).toEqual([
      { source: 'body', path: '$.n' },
      { source: 'body', path: '$.b' },
      { source: 'body', path: '$.nil' },
      { source: 'headers', path: '$.Authorization' },
      { source: 'headers', path: '$.X' },
    ])
  })

  it('FP-3: null step / 空 body 返回空数组', () => {
    expect(fieldPathsOf(null)).toEqual([])
    expect(fieldPathsOf({})).toEqual([{ source: 'headers', path: '$.Authorization' }].filter(() => false) && [])
    // {} 无 request.body 且无 api.headers → [];上一行可读性差,直接:
    expect(fieldPathsOf({ request: {} })).toEqual([])
  })
})
```

- [x] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/dataset-segments.test.ts`
Expected: FAIL — `fieldPathsOf is not a export`(import 报错)。

- [x] **Step 3: 实现**(dataset-segments.ts 末尾追加)

```ts
// ── 全叶子路径扫描(spec v2 §4)──────────────────────────────
export interface FieldLeaf {
  source: 'body' | 'headers'
  /** jsonpath 风格,$. 前缀;数组带 [i] 实例下标 */
  path: string
  /** 值整串 ${var.x} 模板时在场;未模板化叶无此键 */
  varName?: string
}

function leafOf(source: 'body' | 'headers', path: string, v: unknown): FieldLeaf {
  const leaf: FieldLeaf = { source, path }
  if (typeof v === 'string') {
    const m = TPL_FULL_RE.exec(v)
    if (m) leaf.varName = m[1]
  }
  return leaf
}

/** 报告 step 请求面(body 深扫 / headers 浅扫)的全叶子路径 — 模板与直填一视同仁;
 *  anchor 候选与「未模板化字段」兜底报告的数据源(§4 新增能力)。 */
export function fieldPathsOf(step: SegmentStepShape | null | undefined): FieldLeaf[] {
  const out: FieldLeaf[] = []
  if (!step) return out
  const walk = (v: unknown, path: string) => {
    if (Array.isArray(v)) { v.forEach((it, i) => walk(it, `${path}[${i}]`)); return }
    if (v && typeof v === 'object') {
      for (const [k, val] of Object.entries(v)) walk(val, path ? `${path}.${k}` : `$.${k}`)
      return
    }
    out.push(leafOf('body', path || '$', v))
  }
  walk(step?.request?.body, '')
  for (const [k, val] of Object.entries(step?.api?.headers ?? {})) {
    out.push(leafOf('headers', `$.${k}`, val))
  }
  return out
}
```

- [x] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/dataset-segments.test.ts`
Expected: PASS(新增 3 测全绿,既有不红)。

- [x] **Step 5: 全量回归 + 类型检查**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全绿(基线 702 通过 + 3 新增)/ vue-tsc 0 error。

- [x] **Step 6: Commit**

```bash
git -C d:/Gimbal/Gimbal add src/gimbal-platform/frontend/src/utils/dataset-segments.ts src/gimbal-platform/frontend/src/utils/__tests__/dataset-segments.test.ts
git -C d:/Gimbal/Gimbal commit -m "feat(frontend): fieldPathsOf 全叶子扫描 — anchor 候选与未模板化兜底(spec v2 §4)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 注册表模型 + 场景文档回路 + 悬空检测(spec §3,spec 任务 T2 前半)

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:123-136`(ScenarioDraft 加第三键)
- Modify: `src/gimbal-platform/backend/tests/test_scenario_composer_container.py`(追加 roundtrip 测试)
- Create: `src/gimbal-platform/frontend/src/types/assertion-registry.ts`(纯类型)
- Create: `src/gimbal-platform/frontend/src/utils/assertion-registry.ts`(悬空检测 + id 生成)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts`(新建)
- Modify: `src/gimbal-platform/frontend/src/types/scenario-composer.ts:33-39`(ScenarioDraft 加键)
- Modify: `src/gimbal-platform/frontend/src/stores/scenario-draft.ts:28-33`(DraftSnapshot 加键)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(loadScenario 重建 + registry ref + saveDraft 796-799 组装 + setDraft 调用点 456-466)

**Interfaces:**
- Consumes: 无(首任务)。
- Produces(Task 3/4/5 消费):
  ```ts
  // types/assertion-registry.ts
  export interface AssertionAnchor { stepIndex: number; source: 'body' | 'headers'; jsonpath: string; varName?: string }
  export interface AssertionInject { varName: string; value: unknown }
  export interface AssertPatch { stepIndex: number; target: string; operator: string; expected: unknown; mode: 'override' | 'append' }
  export interface AssertionEntry { id: string; name: string; anchor?: AssertionAnchor; injection: AssertionInject[]; asserts: AssertPatch[] }
  export interface AssertionRegistry { entries: AssertionEntry[] }
  // utils/assertion-registry.ts
  export type RegistryIssue = { kind: 'step-oob'; stepIndex: number } | { kind: 'var-unknown'; varName: string } | { kind: 'override-no-match'; stepIndex: number; target: string }
  export function registryIssues(entry: AssertionEntry, stepCount: number, varNames: ReadonlySet<string>, assertTargetsOf: (stepIndex: number) => ReadonlySet<string>): RegistryIssue[]
  export function isDeadEntry(entry, stepCount, varNames, assertTargetsOf): boolean
  export function genEntryId(): string   // `inj-<6位base36时间戳><3位随机>`
  ```
- backend:`ScenarioDraft.assertion_registry: dict[str, Any] = Field(default_factory=dict)` — create/update/copy 的 model_dump 重铸自动携带;`GET /draft` 自动回读。存储/校验策略 = 自由 dict(与 definition 同;条目形状权威在前端 TS 类型 + Task 6 的 Python 物化函数)。

**背景(为什么动这些点)**:pydantic `_CAMEL` 未建模键会被静默丢弃 — `scenario_store.create`(66-69)/`update`(141-144)/`copy`(231)全经 model_dump 重铸 payload;前端 `CaseComposer.saveDraft`(796-799)与 `loadScenario`(666-726)、draftStore `DraftSnapshot`(28-33)也是显式两键。**不改这些点 = 编排器每次保存丢注册表**。`DataSetEditor` 的基线保存(570-582)把 GET /draft 的产物原样 PUT,backend 加字段后自动 round-trip,无需改。

- [x] **Step 1: backend 失败测试**(test_scenario_composer_container.py 追加)

```python
def test_draft_roundtrips_assertion_registry(client, db, owner_headers):
    """spec v2 §3:assertion_registry 与 orchestration 同级,create/update/draft 全链携带。"""
    entry = {"entries": [{
        "id": "inj-1", "name": "金额为负",
        "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount", "varName": "amount"},
        "injection": [{"varName": "amount", "value": "-1"}],
        "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                     "operator": "eq", "expected": "400", "mode": "override"}],
    }]}
    sid = _create_scenario(client, owner_headers)   # 既有测试的建场景辅助;若无则按文件内既有用例的建法内联
    draft = _minimal_draft(sid)                     # 既有辅助:合法 definition+orchestration
    draft["assertion_registry"] = entry
    resp = client.put(f"/api/scenarios/{sid}", json=draft, headers=owner_headers)
    assert resp.status_code == 200
    # GET draft 原样回读
    out = client.get(f"/api/scenarios/{sid}/draft", headers=owner_headers).json()
    assert out["assertion_registry"] == entry
    # 不带 registry 的 PUT(旧客户端)→ 字段回落空 dict,不炸不 422
    draft.pop("assertion_registry")
    resp2 = client.put(f"/api/scenarios/{sid}", json=draft, headers=owner_headers)
    assert resp2.status_code == 200
    out2 = client.get(f"/api/scenarios/{sid}/draft", headers=owner_headers).json()
    assert out2["assertion_registry"] == {}
```

注:`_create_scenario`/`_minimal_draft` 按该测试文件既有用例的夹具/辅助实际名称调整;文件里已有建场景 + PUT + GET draft 的用例可仿抄。

- [x] **Step 2: 跑 backend 测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_scenario_composer_container.py -q`
Expected: FAIL — `out["assertion_registry"]` KeyError(未建模被丢)。

- [x] **Step 3: backend 实现**(schemas/scenario_composer.py ScenarioDraft)

```python
class ScenarioDraft(BaseModel):
    """definition: the plate Scenario structure as a free-form dict...
    orchestration: platform-only rendering/orchestration fields, never sent to plate
    assertion_registry: 断言管理注册表(spec v2 §3)— 平台侧偏离注入条目,
    与 orchestration 同级;引擎不感知,不进 plate convert。自由 dict,
    条目形状权威在前端 types/assertion-registry.ts 与运行时物化函数。"""
    model_config = _CAMEL

    definition: dict[str, Any]
    orchestration: Orchestration = Field(default_factory=Orchestration)
    assertion_registry: dict[str, Any] = Field(default_factory=dict)
```

(保留原 docstring 前两行内容,追加 assertion_registry 行;键名不加 alias — JSON 键 = `assertion_registry` 原样。)

- [x] **Step 4: 跑 backend 测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_scenario_composer_container.py tests -q`
Expected: 该文件 PASS + 全套件绿。

- [x] **Step 5: 前端类型 + 检测 utils 失败测试**(新建 utils/__tests__/assertion-registry.test.ts)

```ts
import { describe, expect, it } from 'vitest'
import { genEntryId, isDeadEntry, registryIssues } from '../assertion-registry'
import type { AssertionEntry } from '../../types/assertion-registry'

const E = (over: Partial<AssertionEntry> = {}): AssertionEntry => ({
  id: 'inj-1', name: 'n',
  anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
  injection: [{ varName: 'amount', value: '-1' }],
  asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }],
  ...over,
})
const VARS = new Set(['amount', 'bl_no'])
const targets = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])

describe('registryIssues — 悬空检测(spec §3)', () => {
  it('RG-1: 全匹配零 issue', () => {
    expect(registryIssues(E(), 2, VARS, targets({ 0: ['$.response_body.code'] }))).toEqual([])
    expect(isDeadEntry(E(), 2, VARS, targets({ 0: ['$.response_body.code'] }))).toBe(false)
  })
  it('RG-2: stepIndex 越界(anchor + asserts 都查)', () => {
    const e = E({ anchor: { stepIndex: 5, source: 'body', jsonpath: '$.x' } })
    const issues = registryIssues(e, 2, VARS, targets({}))
    expect(issues).toContainEqual({ kind: 'step-oob', stepIndex: 5 })
  })
  it('RG-3: injection.varName ∉ config.vars → var-unknown', () => {
    const e = E({ injection: [{ varName: 'ghost', value: '1' }] })
    expect(registryIssues(e, 2, VARS, targets({ 0: ['$.response_body.code'] })))
      .toContainEqual({ kind: 'var-unknown', varName: 'ghost' })
  })
  it('RG-4: override 匹配不到既有断言 → override-no-match;append 不查匹配', () => {
    const base = { 0: ['$.response_body.other'] }
    expect(registryIssues(E(), 2, VARS, targets(base)))
      .toContainEqual({ kind: 'override-no-match', stepIndex: 0, target: '$.response_body.code' })
    const app = E({ asserts: [{ stepIndex: 0, target: '$.new', operator: 'eq', expected: '1', mode: 'append' }] })
    expect(registryIssues(app, 2, VARS, targets(base))).toEqual([])
  })
  it('RG-5: genEntryId 前缀 inj- 且同毫秒不撞', () => {
    const a = genEntryId()
    expect(a).toMatch(/^inj-[a-z0-9]{9}$/)
    expect(new Set([a, genEntryId(), genEntryId()]).size).toBe(3)
  })
})
```

- [x] **Step 6: 跑确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/assertion-registry.test.ts`
Expected: FAIL — 模块不存在。

- [x] **Step 7: 实现 types/assertion-registry.ts(全文)+ utils/assertion-registry.ts(全文)**

```ts
// types/assertion-registry.ts
/** 断言管理注册表(spec v2 §3)— 平台侧偏离注入条目,场景级资产,
 *  住场景文档 payload.assertion_registry(与 orchestration 同级,引擎不感知)。 */

/** 溯源面:编排器标记自动带来;编辑器联动/展示用,执行不依赖 */
export interface AssertionAnchor {
  stepIndex: number
  source: 'body' | 'headers'
  /** jsonpath 风格,$. 前缀(实例路径,数组带 [i]) */
  jsonpath: string
  varName?: string
}

/** 值偏离面:物化 = 基线 vars 覆写 */
export interface AssertionInject {
  varName: string
  value: unknown
}

/** 期望偏离面:override 覆写既有断言(匹配键 = stepIndex+target)/ append 追加 */
export interface AssertPatch {
  stepIndex: number
  target: string
  operator: string
  expected: unknown
  mode: 'override' | 'append'
}

export interface AssertionEntry {
  id: string
  name: string
  anchor?: AssertionAnchor
  injection: AssertionInject[]
  asserts: AssertPatch[]
}

export interface AssertionRegistry {
  entries: AssertionEntry[]
}
```

```ts
// utils/assertion-registry.ts
import type { AssertionEntry } from '@/types/assertion-registry'

export type RegistryIssue =
  | { kind: 'step-oob'; stepIndex: number }
  | { kind: 'var-unknown'; varName: string }
  | { kind: 'override-no-match'; stepIndex: number; target: string }

/** 悬空检测(spec §3):stepIndex 越界 / injection.varName ∉ config.vars /
 *  override 匹配不到既有断言。assertTargetsOf 由调用方从 steps[si].strategy
 *  的 assertion 条目投影(target 集合)。 */
export function registryIssues(
  entry: AssertionEntry,
  stepCount: number,
  varNames: ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): RegistryIssue[] {
  const issues: RegistryIssue[] = []
  const idxs = new Set<number>()
  if (entry.anchor) idxs.add(entry.anchor.stepIndex)
  for (const a of entry.asserts) idxs.add(a.stepIndex)
  for (const si of idxs) {
    if (si < 0 || si >= stepCount) issues.push({ kind: 'step-oob', stepIndex: si })
  }
  for (const inj of entry.injection) {
    if (!varNames.has(inj.varName)) issues.push({ kind: 'var-unknown', varName: inj.varName })
  }
  for (const a of entry.asserts) {
    if (a.mode === 'override' && a.stepIndex >= 0 && a.stepIndex < stepCount
      && !assertTargetsOf(a.stepIndex).has(a.target)) {
      issues.push({ kind: 'override-no-match', stepIndex: a.stepIndex, target: a.target })
    }
  }
  return issues
}

export function isDeadEntry(
  entry: AssertionEntry,
  stepCount: number,
  varNames: ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): boolean {
  return registryIssues(entry, stepCount, varNames, assertTargetsOf).length > 0
}

/** 条目 id:inj-<6位base36时间戳><3位随机>(genScenarioId 同款纪律,无依赖) */
export function genEntryId(): string {
  const ts = Date.now().toString(36).slice(-6)
  const rnd = Math.floor(Math.random() * 36 ** 3).toString(36).padStart(3, '0')
  return `inj-${ts}${rnd}`
}
```

- [x] **Step 8: ScenarioDraft TS 加键**(types/scenario-composer.ts:33-39)

```ts
export interface ScenarioDraft {
  definition: ScenarioView
  orchestration: Orchestration
  /** 断言管理注册表(spec v2 §3);缺省 = 空(旧场景/旧客户端) */
  assertion_registry?: AssertionRegistry
}
```

(文件头 `import type { AssertionRegistry } from './assertion-registry'`。)

- [x] **Step 9: draftStore 快照加键**(stores/scenario-draft.ts:28-33)

```ts
interface DraftSnapshot {
  definition: ScenarioView
  orchestration: Orchestration
  assertion_registry?: AssertionRegistry
}
```
同步 `setDraft` 调用点(CaseComposer.vue 456-466 deep watch)传 `assertion_registry: registry.value`。

- [x] **Step 10: CaseComposer 回路**(防编排器保存丢注册表)

CaseComposer.vue:
1. `const registry = ref<AssertionRegistry>({ entries: [] })`(orchestration ref 旁);
2. `loadScenario` 从 GET /draft 产物补:`registry.value = draft.assertion_registry ?? { entries: [] }`(在显式两键重建处 666-726 内加第三行);
3. `saveDraft` 796-799 组装加:`assertion_registry: registry.value`;
4. deep watch setDraft(456-466)同步加 `assertion_registry: registry.value`;
5. 新建场景路径(无 loadScenario)registry 保持默认 `{ entries: [] }`。

- [x] **Step 11: 前端全量回归 + 类型**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全绿 + 0 error(ScenarioDraft 新键可选,既有测试不受影响;CaseComposer 现有测试若 pin draft 形状则按需补断言)。

- [x] **Step 12: backend 全量**

Run: `cd src/gimbal-platform/backend && python -m pytest tests -q`
Expected: 全绿。

- [x] **Step 13: Commit**

```bash
git -C d:/Gimbal/Gimbal add src/gimbal-platform/backend/app/schemas/scenario_composer.py \
  src/gimbal-platform/backend/tests/test_scenario_composer_container.py \
  src/gimbal-platform/frontend/src/types/assertion-registry.ts \
  src/gimbal-platform/frontend/src/types/scenario-composer.ts \
  src/gimbal-platform/frontend/src/utils/assertion-registry.ts \
  src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts \
  src/gimbal-platform/frontend/src/stores/scenario-draft.ts \
  src/gimbal-platform/frontend/src/views/CaseComposer.vue
git -C d:/Gimbal/Gimbal commit -m "feat: assertion_registry 场景级节 — pydantic 第三键 + TS 类型 + 悬空检测 + 编排器保存回路(spec v2 §3)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 断言管理编辑器(spec §7/§10,spec 任务 T2 后半)

**Files:**
- Create: `src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue`
- Test: `src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts`(新建)
- Modify: `src/gimbal-platform/frontend/src/router/index.ts`(48-53 旁加路由)
- Modify: `src/gimbal-platform/frontend/src/utils/links.ts`(末尾加 URL 函数)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue`(加「断言管理」跳转卡)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(143-147 传 scenarioId + assertion-count)

**Interfaces:**
- Consumes: Task 1 `fieldPathsOf`、Task 2 全套类型/`registryIssues`/`genEntryId`;既有 `getScenarioDraft`/`updateScenario`(api/scenario-composer.ts:39-54)、`composerUrl`(utils/links.ts:20-22)。
- Produces(Task 4 跳转目标、Task 5 无依赖):路由 `/scenarios/:scenarioId/assertions`;`scenarioAssertionsUrl(scenarioId): string`;编辑器整体 PUT 保存通道(仅动 `assertion_registry` 键)。

**编辑器 IA(spec §7)**:列表(名称/锚定徽标/偏离值摘要/期望数/死条目灰)+ 详情(anchor 跳编排器 + injection 编辑 + asserts 编辑)+ 手工新建;值类别快捷/生成器等 v2 协议位不做。

- [x] **Step 1: 路由 + URL 函数**

router/index.ts(48-53 data-sets 编辑路由之后):
```ts
{
  // 断言管理(偏离注入)编辑器 — 场景级注册表(spec v2 §7)
  path: '/scenarios/:scenarioId/assertions',
  component: () => import('@/views/AssertionRegistryEditor.vue'),
  meta: { requiresAuth: true },
},
```

links.ts 末尾:
```ts
export function scenarioAssertionsUrl(scenarioId: string): string {
  return `/scenarios/${encodeURIComponent(scenarioId)}/assertions`
}
```

- [x] **Step 2: 写失败测试**(views/__tests__/AssertionRegistryEditor.test.ts,骨架仿 DataSetEditor.varview.test.ts:vue-router mock + api spyOn)

```ts
/**
 * AssertionRegistryEditor — 断言管理注册表编辑器(spec v2 §7):
 * 条目列表(锚定徽标/偏离摘要/死条目灰)+ 详情(anchor 跳编排器 +
 * injection/asserts 编辑)+ 手工新建 + 整体 PUT(只动 assertion_registry 键)。
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const routerMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-rg' } }),
  useRouter: () => ({ push: routerMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import AssertionRegistryEditor from '@/views/AssertionRegistryEditor.vue'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-rg', meta: { name: 'rg' },
  config: { vars: { amount: 100, bl_no: 'BL1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {} },
      request: { kind: 'request', body: { bl_no: '${var.bl_no}' } }, strategy: [] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-1', name: '金额为负',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
      injection: [{ varName: 'amount', value: '-1' }],
      asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }] },
    { id: 'inj-dead', name: '死条目',
      anchor: { stepIndex: 9, source: 'body', jsonpath: '$.x' },
      injection: [{ varName: 'ghost', value: '1' }], asserts: [] },
  ],
}

async function mountEditor(draft: any = { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG }) {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(draft as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  const w = mount(AssertionRegistryEditor, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

beforeEach(() => { setActivePinia(createPinia()); routerMock.push.mockReset() })
afterEach(() => { vi.restoreAllMocks() })

it('ARE-1: 列表渲染条目(名称/锚定徽标/偏离摘要/期望数)', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(2)
  expect(rows[0].text()).toContain('金额为负')
  expect(rows[0].text()).toContain('步骤1 · $.amount')        // anchor 徽标
  expect(rows[0].text()).toContain('amount = -1')             // injection 摘要
  expect(rows[0].text()).toContain('1 期望')                  // asserts 数
  w.unmount()
})

it('ARE-2: 死条目标灰(stepIndex 越界 + var 未知);活条目不灰', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows[1].classes()).toContain('are-dead')
  expect(rows[0].classes()).not.toContain('are-dead')
  w.unmount()
})

it('ARE-3: anchor ↗ 跳编排器(focusStep query)', async () => {
  const w = await mountEditor()
  await w.findAll('.are-anchor-jump')[0].trigger('click')
  expect(routerMock.push).toHaveBeenCalledWith({
    path: '/composer/sc-rg',
    query: { step: '4', focusStep: '0' },
  })
  w.unmount()
})

it('ARE-4: 手工新建 + injection 编辑(varName 候选 = config.vars)+ 保存只动 assertion_registry', async () => {
  const w = await mountEditor()
  await w.findAll('button').find((b) => b.text().includes('新建条目'))!.trigger('click')
  await flushPromises()
  expect(w.findAll('.are-row').length).toBe(3)
  // 选中第 3 条:varName 下拉选 bl_no、值 BL9
  const rows = w.findAll('.are-row')
  await rows[2].trigger('click')
  await flushPromises()
  const detail = w.find('.are-detail')
  expect(detail.exists()).toBe(true)
  ;(w.vm as any).pendingInject.varName = 'bl_no'    // script setup binding 经 vm 可写(EP 纪律)
  ;(w.vm as any).pendingInject.value = 'BL9'
  await w.find('.are-detail .are-add-inject').trigger('click')
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
  await flushPromises()
  expect(api.updateScenario).toHaveBeenCalledTimes(1)
  const payload = vi.mocked(api.updateScenario).mock.calls[0][1] as any
  expect(payload.definition).toEqual(DEF)                        // definition 原样
  expect(payload.assertion_registry.entries.length).toBe(3)
  expect(payload.assertion_registry.entries[2].injection).toEqual([{ varName: 'bl_no', value: 'BL9' }])
  w.unmount()
})
```

(实施时:按钮文案/类名以实现为准对齐;`(w.vm as any)` 写 binding 后 `flushPromises` 等渲染 — EP 下拉/按钮纪律见 varview 测试。)

- [x] **Step 3: 跑确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: FAIL — 视图模块不存在。

- [x] **Step 4: 实现 AssertionRegistryEditor.vue**

结构(页面骨架仿 DataSetEditor:route params → onMounted 拉 draft → 本地 editable registry → 保存整体 PUT):

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionEntry, AssertionRegistry } from '@/types/assertion-registry'
import { genEntryId, isDeadEntry } from '@/utils/assertion-registry'
import { composerUrl } from '@/utils/links'

const route = useRoute()
const router = useRouter()
const scenarioId = route.params.scenarioId as string

const draft = ref<ScenarioDraft | null>(null)
const registry = ref<AssertionRegistry>({ entries: [] })
const selectedId = ref<string | null>(null)
const selected = computed(() => registry.value.entries.find((e) => e.id === selectedId.value) ?? null)
const stepCount = computed(() => draft.value?.definition.steps?.length ?? 0)
const varNames = computed(() => new Set(Object.keys(draft.value?.definition.config?.vars ?? {})))
const stepLabels = computed(() => (draft.value?.definition.steps ?? []).map((s: any, i: number) => `${i + 1}·${s?.description || `Step ${i + 1}`}`))

/** steps[si].strategy 的 assertion target 集合(悬空检测喂食) */
function assertTargetsOf(si: number): ReadonlySet<string> {
  const st = (draft.value?.definition.steps ?? [])[si]?.strategy as any[] | undefined
  return new Set((st ?? []).filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadOf = (e: AssertionEntry) => isDeadEntry(e, stepCount.value, varNames.value, assertTargetsOf)

/** injection 行编辑的暂存(下拉 + 值,「添加」入条目) */
const pendingInject = ref<{ varName: string; value: string }>({ varName: '', value: '' })
/** asserts 行编辑暂存 */
const pendingAssert = ref({ stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'override' as 'override' | 'append' })
const OPERATORS = ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains', 'exists']

onMounted(async () => {
  draft.value = await getScenarioDraft(scenarioId)
  registry.value = draft.value.assertion_registry ?? { entries: [] }
})

function addEntry() {
  const e: AssertionEntry = {
    id: genEntryId(),
    name: `偏离 ${registry.value.entries.length + 1}`,
    injection: [], asserts: [],
  }
  registry.value.entries.push(e)
  selectedId.value = e.id
  pendingInject.value = { varName: [...varNames.value][0] ?? '', value: '' }
  pendingAssert.value = { stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'override' }
}
function removeEntry(id: string) {
  registry.value.entries = registry.value.entries.filter((e) => e.id !== id)
  if (selectedId.value === id) selectedId.value = null
}
function addInject() {
  if (!selected.value || !pendingInject.value.varName) return
  selected.value.injection.push({ ...pendingInject.value })
  pendingInject.value = { varName: pendingInject.value.varName, value: '' }
}
function addAssert() {
  if (!selected.value || !pendingAssert.value.target) return
  selected.value.asserts.push({ ...pendingAssert.value, expected: pendingAssert.value.expected })
}
function jumpToAnchor(si: number) {
  router.push({ path: composerUrl(scenarioId, 4), query: { step: '4', focusStep: String(si) } })
}
async function save() {
  if (!draft.value) return
  await updateScenario(scenarioId, { ...draft.value, assertion_registry: registry.value })
  ElMessage.success('断言管理已保存')
}
</script>
```

模板要点(类名与测试对齐):列表 `.are-row`(`.are-dead` 灰 + title 列 issue 摘要)、`.are-anchor-jump` ↗ 按钮、详情 `.are-detail`(anchor 只读展示 + 跳转;injection 表 + `.are-add-inject`;asserts 表含 mode 列 + 添加行;操作符 `el-select` 用 OPERATORS 且 `allow-create`)、头部「新建条目」「保存」按钮、返回编排器按钮(`composerUrl(scenarioId, 1)`)。样式沿用页面既有 scoped 风格(参照 DataSetEditor 的 scoped css 写法,灰态 `opacity: .55`)。

- [x] **Step 5: 跑编辑器测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: PASS(4 测绿)。

- [x] **Step 6: 配置区入口卡**

CaseComposer.vue 143-147 改为传参:
```html
<CaseComposerConfig v-else-if="stepIdx === 2" key="config" v-model="definition.config"
  :scenario-id="scenarioId" :assertion-count="registry.entries.length" />
```
(scenarioId 是 CaseComposer 既有 ref;若变量名不同按实际。)

CaseComposerConfig.vue 末尾加卡(仿 users 卡结构,`c-card` 通栏):
```html
<div class="c-card are-entry-card">
  <div class="c-card-head">
    <div>
      <h3>断言管理</h3>
      <p class="c-head-desc">偏离注入条目({{ assertionCount }})— 值偏离 + 期望配对,运行时与数据集并列选择</p>
    </div>
    <button class="c-add" @click="goAssertions">管理断言 →</button>
  </div>
</div>
```
```ts
const props = defineProps<{ modelValue: any; scenarioId?: string; assertionCount?: number }>()
function goAssertions() {
  if (!props.scenarioId || props.scenarioId === 'new') { ElMessage.warning('请先保存场景'); return }
  router.push(scenarioAssertionsUrl(props.scenarioId))
}
```
(props/emits 按该组件现状合并 — 它现在是 `defineProps` 还是 `defineModel` 按文件现状适配,不动既有行,只加。)

- [x] **Step 7: 全量回归 + 类型 + Commit**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全绿 + 0 error。

```bash
git -C d:/Gimbal/Gimbal add src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue \
  src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts \
  src/gimbal-platform/frontend/src/router/index.ts src/gimbal-platform/frontend/src/utils/links.ts \
  src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue \
  src/gimbal-platform/frontend/src/views/CaseComposer.vue
git -C d:/Gimbal/Gimbal commit -m "feat(frontend): 断言管理编辑器 — 条目 CRUD/悬空检测/锚定跳转 + 配置区入口(spec v2 §7)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 编排器标记入口(spec §4,spec 任务 T3)⚠️ 用户 WIP 文件 — 只提交新增 hunk

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldActionMenu.vue`(**用户 WIP** — 只加项,不改既有行)
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(**用户 WIP** — 只加透传与守卫)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(registryMark emit + anchor 组装)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(onRegistryAdd 落条目)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldActionMenu.registry.test.ts`(新建,独立小测)
- Test: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.test.ts`(追加 REG-MARK 用例)

**Interfaces:**
- Consumes: Task 2 `AssertionAnchor`/`AssertionEntry`/`genEntryId`、CaseComposer `registry` ref(Task 2 建)。
- Produces: 事件链 `FieldActionMenu --fieldRegistry(field)--> FieldForm --registryMark({field, varName})--> Canvas --registryAdd(anchor)--> CaseComposer(写 registry.entries)`。

**标记语义**:值整串 `${var.x}` 模板的字段可标记;未模板化 → warning「请先设为变量」不上抛(模板即地址);headers 不走字段卡,v1 标记只产 `source:'body'`;stepIndex 由 Canvas 的 `activeStepIdx` 补(FieldForm 无此上下文);anchor.jsonpath = `field.path`(实例路径,溯源展示用)。

- [x] **Step 1: FieldActionMenu 失败测试**(新建 __tests__/FieldActionMenu.registry.test.ts;组件小、独立挂载,不依赖 FieldForm)

```ts
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FieldActionMenu from '../FieldActionMenu.vue'

const FIELD = { name: 'amount', path: '$.amount', required: true } as any

function mountMenu(over: Record<string, unknown> = {}) {
  return mount(FieldActionMenu, {
    props: { field: FIELD, value: '${var.amount}', varChoices: [], injectChoices: [], open: true, ...over },
  })
}

describe('FieldActionMenu — 加入断言管理(spec v2 §4)', () => {
  it('FAM-REG-1: 请求侧渲染「加入断言管理」项,response 侧不渲染', () => {
    const w = mountMenu()
    expect(w.text()).toContain('加入断言管理')
    const w2 = mountMenu({ domain: 'response' })
    expect(w2.text()).not.toContain('加入断言管理')
    w.unmount(); w2.unmount()
  })
  it('FAM-REG-2: 点击 emit fieldRegistry(field) 并关闭', async () => {
    const w = mountMenu()
    await w.findAll('button').find((b) => b.text().includes('加入断言管理'))!.trigger('click')
    expect(w.emitted('fieldRegistry')![0]).toEqual([FIELD])
    w.unmount()
  })
})
```

- [x] **Step 2: 跑确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/FieldActionMenu.registry.test.ts`
Expected: FAIL — 菜单项不存在。

- [x] **Step 3: FieldActionMenu 加项**(在「向该字段动态注入」项之后;不动既有行)

模板(仿既有 li 结构):
```html
<li v-if="domain !== 'response'">
  <button class="fam-item" :disabled="injected" @click="emitRegistry()">
    加入断言管理 <span class="fam-note">Registry</span>
  </button>
</li>
```
script:
```ts
// emits 声明追加一行(与既有 emits 数组/对象合并,不动既有行):
'fieldRegistry': [field: IOFieldBinding]

function emitRegistry() {
  emit('fieldRegistry', props.field)
  closeAll()   // 与既有 pickInject 同款收卡;若函数名不同按现场
}
```
(类名/disabled 悬停文案若与既有 INJECTED_NOTE 模式有出入,按文件现场风格对齐。)

- [x] **Step 4: FieldForm 透传 + 守卫**(WIP 文件,只加)

- emits 声明追加 `'registryMark': [payload: { field: IOFieldBinding; varName: string }]`;
- 10 处 `<FieldActionMenu>` 挂载点追加 `@field-registry="onRegistryMenu"`(全部 10 处:容器头 3 + 叶子行 7);
- script 追加(值提取路径与 onFieldPromote L1292-1305 同源 — 用同款方式拿当前字段值):
```ts
import { TPL_FULL_RE } from '@/utils/dataset-segments'

function onRegistryMenu(field: IOFieldBinding) {
  const raw = currentFieldValueOf(field)   // onFieldPromote 同款取值;若那边是就地闭包,则这里按挂载点写法取
  const m = TPL_FULL_RE.exec(String(raw ?? ''))
  if (!m) {
    ElMessage.warning('该字段未模板化 — 请先「设为变量」再加入断言管理')
    return
  }
  emit('registryMark', { field, varName: m[1] })
  menuField.value = null   // 收菜单,与既有 toggleMenu 状态同源
}
```
(实施注:若 FieldForm 各挂载点值上下文分散,可改为挂载点行内 `@field-registry="onRegistryMenu(field, <该行值>)"` 传值;核心是复用 fieldPromote 已验证的取值路径,不新造遍历。)

- [x] **Step 5: Canvas 失败测试**(CaseComposerCanvas.test.ts 追加;仿既有断言事件用例的挂载工厂)

```ts
it('REG-MARK: FieldForm registryMark → Canvas 组装 anchor(stepIndex=activeStepIdx)上抛 registryAdd;未模板化不上抛', async () => {
  const w = await mountCanvas()          // 既有工厂;步骤定位到请求体页(stepIdx 使 activeStepIdx=0)
  const ff = w.findComponent(FieldForm)
  ff.vm.$emit('registryMark', { field: { name: 'amount', path: '$.amount' }, varName: 'amount' })
  await flushPromises()
  const emits = w.emitted('registryAdd')
  expect(emits).toBeTruthy()
  expect(emits![0][0]).toEqual({ stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' })
  w.unmount()
})
```

- [x] **Step 6: 跑确认失败后实现 Canvas + CaseComposer**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/CaseComposerCanvas.test.ts -t REG-MARK`
Expected: FAIL — 无 registryAdd emit。

Canvas(script):
```ts
// emits 声明追加:'registryAdd': [anchor: AssertionAnchor]
function onRegistryMark(p: { field: IOFieldBinding; varName: string }) {
  emit('registryAdd', {
    stepIndex: activeStepIdx.value,
    source: 'body',
    jsonpath: p.field.path,
    varName: p.varName,
  })
}
```
模板:request 侧 FieldForm(L232-257)追加 `@registry-mark="onRegistryMark"`(response 侧不挂 — domain='response' 菜单项已藏)。

CaseComposer.vue:
```ts
import type { AssertionAnchor } from '@/types/assertion-registry'
import { genEntryId } from '@/utils/assertion-registry'
import { scenarioAssertionsUrl } from '@/utils/links'

function onRegistryAdd(anchor: AssertionAnchor) {
  const base = definition.value.config?.vars?.[anchor.varName ?? ''] ?? ''
  registry.value.entries.push({
    id: genEntryId(),
    name: `偏离 ${registry.value.entries.length + 1}`,
    anchor,
    injection: anchor.varName ? [{ varName: anchor.varName, value: base }] : [],
    asserts: [],
  })
  ElMessage.success({ message: '已加入断言管理(偏离值默认取基线,请到断言管理编辑)', duration: 4000 })
  touch()   // 与既有编辑同款保存调度;函数名按现场
}
```
Canvas 挂载处接线 `@registry-add="onRegistryAdd"`。

- [x] **Step 7: 全量回归 + 类型**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全绿 + 0 error。(若 FieldForm 用户 WIP 未完成态导致挂载型测试不稳,把受影响断言移到 FieldActionMenu 独立测 + CaseComposer 集成测,并在报告注明。)

- [x] **Step 8: 选择性暂存提交(WIP 纪律)**

FieldActionMenu.vue / FieldForm.vue 常带用户未提交改动 — 本任务只提交新增 hunk:
```bash
git -C d:/Gimbal/Gimbal diff src/gimbal-platform/frontend/src/components/composer/FieldActionMenu.vue | head -100   # 人工审阅:新增行 vs 用户 WIP 行
git -C d:/Gimbal/Gimbal add src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue \
  src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.test.ts \
  src/gimbal-platform/frontend/src/views/CaseComposer.vue \
  src/gimbal-platform/frontend/src/components/composer/__tests__/FieldActionMenu.registry.test.ts
git -C d:/Gimbal/Gimbal add -p src/gimbal-platform/frontend/src/components/composer/FieldActionMenu.vue   # 只选新增 hunk
git -C d:/Gimbal/Gimbal add -p src/gimbal-platform/frontend/src/components/composer/FieldForm.vue
git -C d:/Gimbal/Gimbal commit -m "feat(frontend): 编排器标记入口 — 字段卡「加入断言管理」三级事件链 + anchor 组装(spec v2 §4)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
# 提交后验证:git show --stat 本提交两 WIP 文件的 diff 只含新增行;git diff <file> 剩余 = 用户 WIP 原样
```

---

### Task 5: RunDialog 注入条目多选 + 运行方案透传(spec §5/§10,spec 任务 T4)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunDialog.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/RunDialog.injection.test.ts`(新建)
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts:125-132`(RunScheme TS 加键)
- Modify: `src/gimbal-platform/frontend/src/types/scenario-composer.ts`(若有 RunScheme 类型处)
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:197-206`(RunScheme pydantic 加键)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(传 entries prop + onRunConfirm 透传)

**Interfaces:**
- Consumes: Task 2 `AssertionEntry`;既有 RunDialog props/emits(234-281)、onConfirm(459-480)、watch(selectedScheme)(391-411)、onSaveScheme(487-502)、MAX_TOTAL_RUNS=200(448)。
- Produces(Task 6 消费):`RunRequest.injectionEntryIds: string[]`(前端 confirm opts 键名 `injectionEntryIds`);`RunScheme.injectionEntryIds?: string[]`(两端类型)。

**语义**:注入条目多选(异常组)与数据集多选(正常组)并列;死条目禁选;总量闸 = (Σ数据集行数 + 选中条目数)× nRuns ≤ 200;方案保存/回填/悬空降级同 dataSetIds 模式。

- [x] **Step 1: pydantic RunScheme 加键**(schemas/scenario_composer.py:197-206)

```python
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")
    injection_entry_ids: list[str] = Field(default_factory=list, alias="injectionEntryIds")
```

TS(api/scenario-composer.ts:125-132 RunScheme):
```ts
  injectionEntryIds?: string[]
```

- [x] **Step 2: 写失败测试**(RunDialog.injection.test.ts;挂载工厂仿 VariableDetailPanel.test.ts 模式,RunDialog props 按 234-259 实际形状)

**前置检查**:先 `ls src/gimbal-platform/frontend/src/components/composer/__tests__/ | grep -i run` — 若已有 RunDialog 既有测试文件 pin 了 props 形状/总量文案/confirm 载荷,加 props 与 totalRuns 公式变化可能碰它:先跑一遍确认基线,新测试与既有适配同提交。

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import RunDialog from '../RunDialog.vue'

const ENTRIES = [
  { id: 'inj-1', name: '金额为负', injection: [{ varName: 'amount', value: '-1' }], asserts: [] },
  { id: 'inj-dead', name: '死条目', injection: [{ varName: 'ghost', value: '1' }], asserts: [] },
] as any[]

function mountDialog(over: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: {
      visible: true, scenario: { meta: { scenarioId: 'sc-1', name: 's' } },
      dataSets: [], running: false, schemes: [],
      serviceRows: [], authOptions: [], stepOrchestrationNames: [],
      assertionEntries: ENTRIES,
      ...over,
    } as any,
    global: { plugins: [ElementPlus] },
  })
}

beforeEach(() => setActivePinia(createPinia()))

describe('RunDialog — 注入条目多选(spec v2 §5)', () => {
  it('INJ-1: 条目区渲染 + 死条目禁选', async () => {
    const w = mountDialog()
    await flushPromises()
    const boxes = w.findAll('.rd-injection .el-checkbox')
    expect(boxes.length).toBe(2)
    expect(boxes[1].find('input').attributes('disabled')).toBeDefined()
    w.unmount()
  })
  it('INJ-2: 勾选条目 → confirm 载荷含 injectionEntryIds;总量闸计入条目数', async () => {
    const w = mountDialog()
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    await w.findAll('button').find((b) => b.text().includes('开跑'))!.trigger('click')
    const emitted = w.emitted('confirm')
    expect(emitted).toBeTruthy()
    const [, opts] = emitted![0] as [string[], any]
    expect(opts.injectionEntryIds).toEqual(['inj-1'])
    w.unmount()
  })
})
```
(按钮文案/类名按 RunDialog 实际 footer 对齐;总量闸数值断言按 totalRuns computed 现形状补一条。)

- [x] **Step 3: 跑确认失败 → 实现 RunDialog**

失败后改 RunDialog.vue:
1. props 追加 `assertionEntries?: AssertionEntry[]`(default `[]`);
2. `const injectionIds = ref<string[]>([])`(confirm 后/d dialog 开合重置,与 dataSetIds 同款 watch visible 重置点);
3. 数据集区(43-93)后加注入条目区:
```html
<div v-if="assertionEntries.length" class="rd-sec rd-injection">
  <div class="rd-sec-title">断言注入条目(异常组)— 跑在基线上,与数据集行并列生成 case</div>
  <el-checkbox-group v-model="injectionIds">
    <el-checkbox v-for="e in assertionEntries" :key="e.id" :value="e.id">
      {{ e.name }}
      <span v-if="deadIds.has(e.id)" class="rd-dead-note">悬空 — 不可选</span>
    </el-checkbox>
  </el-checkbox-group>
</div>
```
```ts
const deadIds = computed(() => new Set(/* 死判定:entries 传不传 dead 标记由 CaseComposer 预计算传入
  assertionEntries 携带 __dead?不 — CaseComposer 计算 deadEntries: string[] 作独立 prop 更干净 */))
```
**裁定(计划钉死)**:死判定在 CaseComposer 预计算(`isDeadEntry` 全量算一次),以 `deadEntryIds: string[]` prop 传入 RunDialog,`deadIds = new Set(props.deadEntryIds)`。测试 INJ-1 相应传 `deadEntryIds: ['inj-dead']`。
4. totalRuns(448-457):`ΣrowCount` 后加 `+ injectionIds.value.length`,乘 nRuns 不变;
5. onConfirm(459-480)opts 追加 `injectionEntryIds: [...injectionIds.value]`;
6. watch(selectedScheme)(391-411)回填 `injectionIds.value = scheme.injectionEntryIds ?? []`;
7. onSaveScheme(487-502)写 `injectionEntryIds: [...injectionIds.value]`;
8. schemeDegraded(310-314)追加悬空判定:`(scheme.injectionEntryIds ?? []).some((id) => !allEntryIds.has(id))`。

- [x] **Step 4: CaseComposer 接线**

RunDialog 挂载处传 `:assertion-entries="registry.entries"` 与 `:dead-entry-ids="deadEntryIds"`(`const deadEntryIds = computed(() => registry.value.entries.filter((e) => isDeadEntry(e, stepCount, varNames, assertTargetsOf)).map((e) => e.id))` — 检测喂食函数从 Task 3 编辑器同款内联);onRunConfirm(921-968)构造 RunRequest 追加 `injectionEntryIds: opts.injectionEntryIds`。

- [x] **Step 5: 全量回归 + 类型 + Commit**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit` → 全绿;`cd ../../backend 2>/dev/null || cd src/gimbal-platform/backend; python -m pytest tests -q` → 绿。

```bash
git -C d:/Gimbal/Gimbal add src/gimbal-platform/frontend/src/components/composer/RunDialog.vue \
  src/gimbal-platform/frontend/src/components/composer/__tests__/RunDialog.injection.test.ts \
  src/gimbal-platform/frontend/src/api/scenario-composer.ts src/gimbal-platform/frontend/src/types/scenario-composer.ts \
  src/gimbal-platform/backend/app/schemas/scenario_composer.py \
  src/gimbal-platform/frontend/src/views/CaseComposer.vue
git -C d:/Gimbal/Gimbal commit -m "feat: RunDialog 注入条目多选(异常组)+ 运行方案透传 injectionEntryIds(spec v2 §5)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: backend 物化注入族 + 行可观测(spec §8,spec 任务 T5)

**Files:**
- Create: `src/gimbal-platform/backend/app/services/run_injection.py`(纯函数:compose + 检测)
- Test: `src/gimbal-platform/backend/tests/test_run_injection.py`(新建)
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:229-262`(RunRequest 加键)
- Modify: `src/gimbal-platform/backend/app/schemas/execution.py:30-44`(ExecutionRowOut 加 injection_id)
- Modify: `src/gimbal-platform/backend/app/routers/runs.py:44-79`(载荷透传,若有形状断言处)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(dispatch_run 读 registry → _fanout 注入族 → JSONL/RowState 字段)
- Modify: `src/gimbal-platform/frontend/src/views/Executions.vue:127-188`(行表格注入列)
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`(ExecutionRow TS 加键,若有类型)

**Interfaces:**
- Consumes: Task 2 payload `assertion_registry` 节;Task 5 `RunRequest.injectionEntryIds`;既有 `_compose_scenario`(run_dispatcher.py:1009-1046)、`_fanout`(486-816)、case stem(623-627)、JSONL 行(629-641)、RowState registry(211-234)。
- Produces: `run_injection.compose_injection_scenario(definition: dict, entry: dict) -> dict`、`run_injection.entry_issues(entry, step_count, var_names, assert_targets_of) -> list[dict]`(dispatcher 死条目 skip 用)。

**物化语义(spec §8)**:注入条目 = 深拷贝场景 → 基线 vars + injection 覆写(`vars[varName] = value`,走既有 `_coerce_row_value` 同款类型还原?否 — injection.value 由用户显式编辑,**原样覆写不 coerce**,类型由前端输入态保证)→ asserts patch(override 改 expected / append 加条目;越界与无匹配 skip)。convert 之前的 definition 层完成(与 `_compose_scenario` 同层);`materialize_run_copy` 本体零改动(其后 services/users/carry 照旧)。**执行/导出同源纪律**:导出(ExportOverlay)有意不收 injectionEntryIds(与 dataSetIds 不收同语义,场景级产物),黄金等价测试不动。

- [ ] **Step 1: 纯函数失败测试**(tests/test_run_injection.py)

```python
"""run_injection — 注入条目物化纯函数(spec v2 §8)。"""
import copy

from app.services.run_injection import compose_injection_scenario, entry_issues

DEF = {
    "config": {"vars": {"amount": 100, "bl_no": "BL1"}},
    "steps": [
        {"description": "下单", "request": {"body": {"amount": "${var.amount}"}},
         "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                       "operator": "eq", "expected": "0"}]},
        {"description": "查单", "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
    ],
}


def test_injection_overrides_baseline_vars_without_mutation():
    entry = {"id": "inj-1", "injection": [{"varName": "amount", "value": "-1"}], "asserts": []}
    src = copy.deepcopy(DEF)
    out = compose_injection_scenario(DEF, entry)
    assert out["config"]["vars"]["amount"] == -1 if False else out["config"]["vars"]["amount"] == "-1"
    assert DEF["config"]["vars"]["amount"] == 100          # 源零污染
    assert out["config"]["vars"]["bl_no"] == "BL1"          # 基线保留


def test_override_patches_matching_assert_expected():
    entry = {"id": "inj-1", "injection": [], "asserts": [
        {"stepIndex": 0, "target": "$.response_body.code", "operator": "eq",
         "expected": "400", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    st = out["steps"][0]["strategy"]
    assert len(st) == 1
    assert st[0]["expected"] == "400"


def test_append_adds_new_assertion():
    entry = {"id": "inj-1", "injection": [], "asserts": [
        {"stepIndex": 1, "target": "$.response_body.msg", "operator": "contains",
         "expected": "金额非法", "mode": "append"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][1]["strategy"] == [{"kind": "assertion", "target": "$.response_body.msg",
                                            "operator": "contains", "expected": "金额非法"}]


def test_dangling_step_and_unmatched_override_skipped():
    entry = {"id": "inj-1", "injection": [{"varName": "ghost", "value": "1"}], "asserts": [
        {"stepIndex": 9, "target": "$.x", "operator": "eq", "expected": "1", "mode": "append"},
        {"stepIndex": 0, "target": "$.nope", "operator": "eq", "expected": "1", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "0"   # 无匹配 override 不动
    assert out["steps"][1]["strategy"] == []                     # 越界 append 不落
    issues = entry_issues(entry, 2, {"amount"}, lambda si: {"$.response_body.code"} if si == 0 else set())
    assert {"kind": "step-oob", "stepIndex": 9} in issues
    assert {"kind": "var-unknown", "varName": "ghost"} in issues
    assert {"kind": "override-no-match", "stepIndex": 0, "target": "$.nope"} in issues
```

- [ ] **Step 2: 跑确认失败 → 实现 run_injection.py**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_injection.py -q`
Expected: FAIL — 模块不存在。

```python
"""注入条目物化(spec v2 §8)— 平台层 patch,引擎零改动。

与 run_materialize.py 同纪律:纯函数、深拷贝进深拷贝出、执行链唯一物化语义。
assertion_registry 条目在 plate convert 之前落进 definition(vars 覆写 +
strategy patch),materialize_run_copy 其后照旧(services/users/carry)。
"""
import copy
from typing import Any, Callable


def entry_issues(
    entry: dict[str, Any],
    step_count: int,
    var_names: set[str],
    assert_targets_of: Callable[[int], set[str]],
) -> list[dict[str, Any]]:
    """悬空检测(前端 utils/assertion-registry.ts 的 Python 同构):
    stepIndex 越界 / injection.varName ∉ vars / override 无匹配。"""
    issues: list[dict[str, Any]] = []
    idxs = set()
    anchor = entry.get("anchor")
    if isinstance(anchor, dict) and isinstance(anchor.get("stepIndex"), int):
        idxs.add(anchor["stepIndex"])
    for a in entry.get("asserts") or []:
        if isinstance(a, dict) and isinstance(a.get("stepIndex"), int):
            idxs.add(a["stepIndex"])
    for si in idxs:
        if si < 0 or si >= step_count:
            issues.append({"kind": "step-oob", "stepIndex": si})
    for inj in entry.get("injection") or []:
        if isinstance(inj, dict) and inj.get("varName") not in var_names:
            issues.append({"kind": "var-unknown", "varName": inj.get("varName")})
    for a in entry.get("asserts") or []:
        if (isinstance(a, dict) and a.get("mode") == "override"
                and isinstance(a.get("stepIndex"), int)
                and 0 <= a["stepIndex"] < step_count
                and a.get("target") not in assert_targets_of(a["stepIndex"])):
            issues.append({"kind": "override-no-match",
                           "stepIndex": a["stepIndex"], "target": a.get("target")})
    return issues


def compose_injection_scenario(definition: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """基线 vars + injection 覆写 + asserts patch(override 改 expected /
    append 加条目);悬空项(越界/无匹配)静默跳过 — dispatcher 层已先经
    entry_issues 过滤死条目,此处双保险。"""
    out = copy.deepcopy(definition)
    cfg = out.setdefault("config", {})
    vars_map = dict(cfg.get("vars") or {})
    for inj in entry.get("injection") or []:
        if isinstance(inj, dict) and isinstance(inj.get("varName"), str):
            vars_map[inj["varName"]] = inj.get("value")
    cfg["vars"] = vars_map

    steps = out.get("steps") or []
    for a in entry.get("asserts") or []:
        if not isinstance(a, dict):
            continue
        si = a.get("stepIndex")
        if not isinstance(si, int) or si < 0 or si >= len(steps):
            continue
        strat = steps[si].setdefault("strategy", [])
        if a.get("mode") == "override":
            for st in strat:
                if (isinstance(st, dict) and st.get("kind") == "assertion"
                        and st.get("target") == a.get("target")):
                    st["expected"] = a.get("expected")
        else:
            strat.append({"kind": "assertion", "target": a.get("target", ""),
                          "operator": a.get("operator", "eq"), "expected": a.get("expected")})
    return out
```

- [ ] **Step 3: RunRequest + ExecutionRowOut 加键**

scenario_composer.py RunRequest(229-262)追加:
```python
    injection_entry_ids: list[str] = Field(default_factory=list, alias="injectionEntryIds")
```
execution.py ExecutionRowOut(30-44)追加:
```python
    injection_id: str | None = Field(default=None, alias="injectionId")
```

- [ ] **Step 4: dispatcher 集成失败测试**(tests/test_run_injection.py 追加,仿 test_run_m1_capabilities 的 `_run_payload`/`_patch_launch_capture` 模式)

```python
def test_dispatcher_fans_out_injection_entries(db, client, owner_headers, monkeypatch):
    """选中 2 条目 + 无数据集 → case 数 = 条目数×nRuns;JSONL 带 injectionId;
    case.json 的 vars/asserts 已 patch。"""
    # 场景带 assertion_registry(两条目:一活一死)+ POST /api/runs injectionEntryIds=[活]
    # 断言:_fanout 产物 2 case(nRuns=2);死条目被 skip 且不炸;
    #      case 变量 amount='-1'、断言 expected='400';rows API 回放含 injectionId
    ...按 test_run_m1_capabilities._run_payload 的建场景/发请求/收 JSONL 骨架仿写...
```
(骨架按既有 m1 测试的夹具实际形状补全 — 建场景走 scenarios API 注入 assertion_registry 节,launch 用 monkeypatch 捕获。)

- [ ] **Step 5: 实现 dispatcher 集成**

run_dispatcher.py:
1. `dispatch_run` 读 registry:`registry = (raw or {}).get("assertion_registry") or {}`、`entries = registry.get("entries") or []`(raw 即 payload,definition_from_payload 的兄弟键);
2. 选中 + 死过滤:
```python
from app.services.run_injection import compose_injection_scenario, entry_issues
selected_ids = set(req.injection_entry_ids or [])
selected_entries = []
for e in entries:
    if e.get("id") not in selected_ids:
        continue
    issues = entry_issues(e, len(steps_from_payload(raw) or []),
                          set((definition_config_vars(raw) or {}).keys()),
                          _assert_targets_of(raw))
    if issues:
        logger.warning("injection entry %s dangling (%s) — skipped", e.get("id"), issues)
        continue
    selected_entries.append(e)
```
(`_assert_targets_of(raw)` 小助手:按 steps[si].strategy 投影 target 集 — 文件内新加,与 compose 同语义。)
3. `_fanout`(486-816)加 injections 参数(默认 `()`):entries 与 rep 笛卡尔为注入族 `(injection, rep)`;case stem:`case-{seq:03d}-inj-{entryId}-r{rep}`(datasetId 位);JSONL 行加 `"injectionId": entry_id`;RowState 行记录带 injection_id;总量校验沿用 `MAX_RUNS_PER_EXECUTION`(数据集族 + 注入族合计);
4. `_row` 闭包(677-686):注入族分支走 `converted = plate_client.convert(compose_injection_scenario(definition, entry))` 替代 `_compose_scenario` 的行合并路径(vars 已在 compose 内合并);`materialize_run_copy` 调用不变;
5. `_replay_rows`(245-277):`injection_id = rec.get("injectionId")`(旧 JSONL 缺键 → None,不炸)。

- [ ] **Step 6: Executions.vue 行表格加注入列**(127-188 数据集列旁)

```html
<el-table-column prop="injectionId" label="注入条目" width="130">
  <template #default="{ row }">
    <span v-if="row.injectionId" class="inj-badge">⚠ {{ row.injectionId }}</span>
    <span v-else>—</span>
  </template>
</el-table-column>
```
(数据集列显示逻辑:injectionId 在场时数据集列显示「基线」;ExecutionRow TS 类型若有则加 `injectionId?: string | null`。)

- [ ] **Step 7: 全量双端回归**

**前端适配注**:Executions.vue 加列可能碰既有列数/列序断言(`grep -rn "Executions" src/gimbal-platform/frontend/src --include="*.test.ts" -l` 先找;若有 pin 列的测试,同提交适配)。
Run: `cd src/gimbal-platform/backend && python -m pytest tests -q` → 全绿(含黄金等价测试不动)。
Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit` → 全绿。

- [ ] **Step 8: Commit**

```bash
git -C d:/Gimbal/Gimbal add src/gimbal-platform/backend/app/services/run_injection.py \
  src/gimbal-platform/backend/tests/test_run_injection.py \
  src/gimbal-platform/backend/app/schemas/scenario_composer.py \
  src/gimbal-platform/backend/app/schemas/execution.py \
  src/gimbal-platform/backend/app/routers/runs.py \
  src/gimbal-platform/backend/app/services/run_dispatcher.py \
  src/gimbal-platform/frontend/src/views/Executions.vue
git -C d:/Gimbal/Gimbal commit -m "feat(backend): 注入条目族物化 — 基线+injection 覆写+asserts patch,死条目 skip,行可观测 injectionId(spec v2 §8)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 期望提升链退场 + exp_* 清除(spec §2/§9,spec 任务 T6)

**Files**(全量命中清单来自 2026-09-11 探查,实施时以 grep 复核):
- Modify: `src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue` — 删 L77-101 `.sf-exp-row` 动作行、`expVarName` computed(166-172)、emits `expPromote/expRestore/expNav`(130-135)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue` — 删 `onExpPromote`(1009-1022)、`promptUniqueExpName`(1026-1050)、`applyExpPromote`(1052-1057)、`onExpRestore`(1060-1071)、`onExpNav`(1074-1076)、模板接线 L360-364(`@exp-promote/@exp-restore/@exp-nav`)、`expectVarNameOf` import
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue` — 删模板接线 L159-162 中 `@var-demote`/`@exp-nav`(保留 `@var-promote` — FieldForm fieldPromote 链仍用)、删 `onVarDemote`(501-506)、`onExpNav`(510-513);**`onVarPromote`(492-498)留**
- Modify: `src/gimbal-platform/frontend/src/utils/dataset-segments.ts` — 删 `expectVarNameOf`(151-158)
- Modify: `src/gimbal-platform/frontend/src/components/composer/VarSelectorModal.vue` — 删 L39-44 `exp_` 前缀紫族「期望」标注(变量不再有 exp_* 专属语义)
- Test: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.test.ts` — 删 X1-X5 中提升链用例(2573-2727;提升/撞名改名/还原/VarSelector 标注),保留仍真部分(扰动位不含期望列断言按需改写)
- Delete: `src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.vardemote.test.ts`(vardemote 链整体退场)
- Grep 复核:`grep -rn "expectVarNameOf\|expPromote\|expRestore\|expNav\|promptUniqueExpName\|varDemote" src/gimbal-platform/frontend/src` 零残留;`grep -rn "exp_" src/gimbal-platform/frontend/src --include="*.ts" --include="*.vue"` 仅剩测试夹具变量名(如 `exp_code` 夹具)/ DataSetEditor 期望徽标(见下)。

**Interfaces:**
- Consumes: 无新接口;依赖 Task 2-6 已落(编辑器承接期望偏离的语义位置)。
- Produces: 无(exp_* 提升链生成侧 + 专属 UI 退场)。

**保留裁定(计划钉死,防误删)**:
- **一致性断言引用扫描留**:`deriveSegments` 的 strategy 段(L99-109)、`ExpectColumn`、`gridColumnsOf` source='expect'、DataSetEditor 期望徽标(VAR-3)、VariableDetailPanel 期望引用行 — 这些承载 `${var.x}` 一致性断言(spec §2 合法保留)的引用面,不是 exp_* 提升链;删了会让一致断言变量在数据集隐形。
- **期望徽标文案留**:徽标指「断言 expected 引用」语义仍真;↗ 跳断言卡是通用导航。
- 存量场景的 `${var.exp_*}` 引用与 config.vars exp_* 键 = 用户手工清理(spec §9);数据集行残留 exp_* 行键由既有死键软提示兜底 — 均不建代码。

- [ ] **Step 1: 退场锚定测试先行**(改写而非先删 — 在 CaseComposerCanvas.test.ts 追加一条退场断言,然后实施)

```ts
it('EXP-EXIT: 断言卡无「设为期望变量」动作;expected 模板串不再有提升/还原入口', async () => {
  const w = await mountCanvasWithAssertion()   // 既有工厂:断言卡在场
  expect(w.text()).not.toContain('设为期望变量')
  expect(w.text()).not.toContain('还原为字面量')
  expect(w.text()).not.toContain('期望列')      // sf-exp-badge 一并退场
  w.unmount()
})
```

- [ ] **Step 2: 跑确认失败**(当前有「设为期望变量」按钮)→ 按上面 Files 清单逐文件删除

- [ ] **Step 3: 全量回归 + 类型**

Run: `cd src/gimbal-platform/frontend && npx vitest run && npx vue-tsc --noEmit`
Expected: 全绿 + 0 error(删 export/函数后的未用 import 一并清;DataSetEditor.varview 的 VAR-3/VAR-4c 期望徽标测试**保持绿** — 引用扫描在)。

- [ ] **Step 4: Commit**

```bash
git -C d:/Gimbal/Gimbal add -A src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue \
  src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue \
  src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.test.ts \
  src/gimbal-platform/frontend/src/views/CaseComposer.vue \
  src/gimbal-platform/frontend/src/utils/dataset-segments.ts \
  src/gimbal-platform/frontend/src/components/composer/VarSelectorModal.vue
git -C d:/Gimbal/Gimbal rm src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.vardemote.test.ts 2>/dev/null || git -C d:/Gimbal/Gimbal add src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.vardemote.test.ts
git -C d:/Gimbal/Gimbal commit -m "refactor(frontend): 期望提升链(exp_*)退场 — 提升/还原/导航动作与专属标注清除,一致性断言引用面保留(spec v2 §2/§9)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: 文档标注(spec 任务 T8)

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-dataset-driven-refactor-design.md`(头部 + §8.4)
- Modify: `docs/superpowers/specs/2026-09-11-assertion-registry-field-binding-design.md`(§12 状态列)

- [ ] **Step 1: 2026-09-10 spec 头部加取代注记**

```markdown
> **取代标注(2026-09-11)**:本 spec 的期望行级化(exp_* 提升链)与段网格已被
> `2026-09-11-assertion-registry-field-binding-design.md` 取代 — 期望偏离迁至
> 断言管理注册表(条目自含 injection+asserts),exp_* 提升链已随其 T6 退场;
> 纯值面(置顶基线行/TSV/CSV/行详情/死键提示)继续有效。§8.4 后续项按新 spec §11 协议位重读。
```

- [ ] **Step 2: v2 spec §12 任务表状态更新**(T1-T6/T8 各行补 ✅ + 提交号)

- [ ] **Step 3: Commit**

```bash
git -C d:/Gimbal/Gimbal add docs/superpowers/specs/2026-09-10-dataset-driven-refactor-design.md \
  docs/superpowers/specs/2026-09-11-assertion-registry-field-binding-design.md
git -C d:/Gimbal/Gimbal commit -m "docs(spec): 2026-09-10 spec 取代标注 + v2 §12 任务状态收口

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 自审记录(写完即查)

1. **Spec 覆盖**:§3 条目形状/悬空检测/手工条目 → Task 2/3;§4 fieldPathsOf+标记 → Task 1/4;§5 运行时汇合 → Task 5/6;§6 数据集侧 = T0 已实施(本计划不动 DataSetEditor 值面);§7 编辑器 → Task 3;§8 物化 → Task 6;§9 存量处置(无读兼容/无迁移)→ Task 7 保留裁定;§10 IA 汇总 → Task 3/5;§12 任务号对应各 Task 头注;T8 → Task 8。**无缺口**。
2. **占位符扫描**:Task 6 Step 4 dispatcher 集成测试为骨架 + 指向 `test_run_m1_capabilities._run_payload` 仿写点(既有夹具形状实施者可见);其余步骤均含真实代码/精确 file:line。可接受。
3. **类型一致性**:`AssertionEntry/Anchor/Inject/AssertPatch/Registry` 五类型 Task 2 定义,Task 3/4/5 消费同名;`registryIssues(entry, stepCount, varNames, assertTargetsOf)` 前端签名与 `entry_issues` Python 版参数序一致;`injectionEntryIds` 键名在 RunScheme/RunRequest/RunDialog opts/CaseComposer 四处一致(camelCase,pydantic alias 对应);`assertion_registry` JSON 键全程 snake 原样。已核。

## 已知边界(2026-09-11 执行前影响评估裁定)

- **registry 整体 PUT 覆盖窗口**:registry 写权威只有编辑器的整体 PUT(后端 update 强制保留 runSchemes 存量,但 registry 无同款保护)— 断言管理编辑器与编排器同时编辑时后保存者胜。单用户语境接受(v1);不建窄端点。
- **_warn_dangling_refs 不对称**:方案保存的后端悬空警告只覆盖 dataSetIds;injectionEntryIds 悬空由前端 schemeDegraded 标降级 + dispatcher 运行时 skip 兜底,后端不警。接受。
- **backend 常驻服务**:live 8000 uvicorn 若在跑,T2/T5/T6 的 backend 改动须重启才对手验生效;pytest 用临时 SQLite 不受影响。
