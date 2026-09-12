# 断言管理 v3 — path 直补(Assign)与数据集合并执行 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 断言条目重铸为 `{path, value, asserts}` 三元组 — 值注入走引擎 Assign 直补 `$.request_body`(与数据集 vars 注入解耦、正交叠加),执行矩阵改为 逐行 × 条目 交叉,IA 升级「测试数据」同页双区 + 两个执行入口,并清理 v2 旧实现。

**Architecture:** 前端 `types/assertion-registry.ts` 是条目形状唯一权威;后端自由 dict 不建模(`run_injection.py` 纯函数物化:steps[path.stepIndex].strategy 追加 Assign + asserts patch);dispatcher `_fanout` 展开交叉矩阵 R × E;`dataSetSelection` 成为 RunRequest/RunScheme 权威行级选择键(旧 `dataSetIds` 降为兼容读)。plate 与执行核(src/gimbal-plate/**、src/gimbal/**)零改动 — Assign 是 StrategyUnion 既有合法成员。

**Tech Stack:** Vue 3 + TS + Element Plus(vitest/@vue/test-utils)/ FastAPI + Pydantic(pytest)/ plate convert 链不变。

**Spec:** `docs/superpowers/specs/2026-09-12-assertion-registry-v3-merge-injection-design.md`(权威;冲突以 spec 为准)

## Global Constraints

- **分支**: `feat/dataset-driven-refactor`(现有工作分支;勿在 master/main 上实施)。
- **plate/执行核零改动**: `src/gimbal-plate/**`、`export/gimbal.py`、`src/gimbal/**` 一行不动。
- **永不提交/触碰**: `gimbal-tmp/`、`reports/test-report.html`、`probe_ui.js`、`src/gimbal-plate/gimbal_plate/systems/fin/endpoint/order_order_add_demo.py` 及 `endpoint/__init__.py` 的 3 行演示副本改动。
- **用户 WIP 文件**: `FieldActionMenu.vue` / `FieldForm.vue` 只加必要 hunk,不重排不改格式;`FieldActionMenu.vue` 本计划无功能改动。
- **安全**: SUT 凭证(Authorization token/Cookie/加密密码)不回显、不入库、不提交;绝不自动重登录。
- **git**: `git add` 点名文件,不用 `git add -A`;commit message 尾行 `Co-Authored-By: Claude Code <noreply@anthropic.com>`;**不 push**(用户明示才推)。
- **环境命令**(Bash 每次调用自带 `cd /d/Gimbal/Gimbal`;`python` = D:\python\python.exe,后端无 venv):
  - 后端单测: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_injection.py -v`
  - 前端单测: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/assertion-registry.test.ts`
  - 前端类型检查: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run typecheck`
- **中间态申报**: Task 1 重铸 utils 后,`vue-tsc` 对 `AssertionRegistryEditor.vue` / `CaseComposer.vue` / `RunDialog` 旧用例报错属**预期** — Task 6 完成后类型全绿,Task 7 后前端套件全绿,Task 8 后全仓回归绿。各任务验证只跑本任务的测试文件(命令见各任务)。
- **兼容边界**: schemas 不删 `dataSetIds` 键(兼容读保留);v2 的 anchor/varName 消费链**全清、不留读写兼容层**(spec §7);旧形状条目保留原样不删,仅灰显「旧版条目,请重建」(spec §8)。

## 任务切分与 spec §10 映射

| 计划任务 | 内容 | spec §10 |
|---|---|---|
| Task 1 | types + utils 重铸(新形状/悬空三检/legacy 识别) | T1 |
| Task 2 | `run_injection.py` 重铸 + dispatcher 调用点跟随 | T2 |
| Task 3 | schemas `dataSetSelection` + dispatcher 交叉矩阵 + 审计 | T3 |
| Task 4 | AssertionRegistryEditor 三元组重铸 | T4 |
| Task 5 | Canvas/FieldForm 标记 + CaseComposer 装配 | T5 |
| Task 6 | RunDialog 交叉语义 + 预填 + RunPanelHost 抽出 | spec T7(对调:先行供 T7 消费) |
| Task 7 | 测试数据页双区 + 配置签展示化 + DataSetEditor 运行此行 | spec T6 |
| Task 8 | 退场清单清理 + 全量回归 | T8 |

对调原因:测试数据页的「运行」按钮需要 Task 6 产出的 RunPanelHost 组件。

---

### Task 1: types + utils 重铸(前端形状权威)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/assertion-registry.ts`(整体重写)
- Modify: `src/gimbal-platform/frontend/src/utils/assertion-registry.ts`(整体重写)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts`(整体重写)

**Interfaces:**
- Consumes: 无(首任务)。
- Produces(后续任务按此消费,签名逐字):
  - `types/assertion-registry.ts`: `interface EntryPath { stepIndex: number; source: 'body'; jsonpath: string }`; `interface AssertionEntry { id: string; name: string; path: EntryPath; value: unknown; asserts: AssertPatch[] }`; `interface LegacyAssertionEntry { id; name; anchor?; injection?; asserts? }`; `AssertionRegistry { entries: Array<AssertionEntry | LegacyAssertionEntry> }`; `function isLegacyEntry(e): e is LegacyAssertionEntry`(判据 = `path === undefined`)。`AssertionAnchor` / `AssertionInject` 类型**退役删除**。
  - `utils/assertion-registry.ts`: `type RegistryIssue = { kind: 'legacy-entry' } | { kind: 'step-oob'; stepIndex: number } | { kind: 'path-unresolvable'; stepIndex: number; jsonpath: string } | { kind: 'override-no-match'; stepIndex: number; target: string }`; `function bodyPathSetOf(leaves: Array<{ source: string; path: string }>): ReadonlySet<string>`; `function pathResolvable(jsonpath: string, bodyPaths: ReadonlySet<string>): boolean`; `function registryIssues(entry: AssertionEntry | LegacyAssertionEntry, stepCount: number, bodyPathsOfStep: (stepIndex: number) => ReadonlySet<string>, assertTargetsOf: (stepIndex: number) => ReadonlySet<string>): RegistryIssue[]`; `function isDeadEntry(entry, stepCount, bodyPathsOfStep, assertTargetsOf): boolean`; `normalizeRegistry` / `genEntryId` 不变。`var-unknown` 分支与 `varNames` 参数退役。

- [ ] **Step 1: 写失败测试**(整文件重写 `src/utils/__tests__/assertion-registry.test.ts`)

```ts
import { describe, expect, it } from 'vitest'
import { bodyPathSetOf, genEntryId, isDeadEntry, pathResolvable, registryIssues } from '../assertion-registry'
import { isLegacyEntry } from '../../types/assertion-registry'
import type { AssertionEntry, LegacyAssertionEntry } from '../../types/assertion-registry'

const E = (over: Partial<AssertionEntry> = {}): AssertionEntry => ({
  id: 'inj-1', name: 'n',
  path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
  value: -1,
  asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }],
  ...over,
})
const LEGACY: LegacyAssertionEntry = {
  id: 'inj-old', name: '旧条目',
  anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
  injection: [{ varName: 'amount', value: '-1' }],
  asserts: [],
}
const bodyPaths = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])
const targets = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])
const BODY0 = { 0: ['$.amount', '$.bl_no', '$.items[0].sku'] }

describe('registryIssues — 悬空检测(spec v3 §2)', () => {
  it('RG-1: 全匹配零 issue(path 落在 body 字段树 + override 有匹配)', () => {
    expect(registryIssues(E(), 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toEqual([])
    expect(isDeadEntry(E(), 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toBe(false)
  })
  it('RG-2: path/asserts 各自的 stepIndex 越界 → step-oob', () => {
    const e = E({ path: { stepIndex: 5, source: 'body', jsonpath: '$.x' } })
    expect(registryIssues(e, 2, bodyPaths({}), targets({})))
      .toContainEqual({ kind: 'step-oob', stepIndex: 5 })
    const a = E({ asserts: [{ stepIndex: -1, target: '$.y', operator: 'eq', expected: '1', mode: 'append' }] })
    expect(registryIssues(a, 2, bodyPaths(BODY0), targets({})))
      .toContainEqual({ kind: 'step-oob', stepIndex: -1 })
  })
  it('RG-3: jsonpath 不落在该步 body 字段树 → path-unresolvable;容器前缀可解析', () => {
    const e = E({ path: { stepIndex: 0, source: 'body', jsonpath: '$.ghost' } })
    expect(registryIssues(e, 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] })))
      .toContainEqual({ kind: 'path-unresolvable', stepIndex: 0, jsonpath: '$.ghost' })
    // 容器锚点:叶子是它的子路径 → 可解析(Assign 整体覆写该容器)
    const container = E({ path: { stepIndex: 0, source: 'body', jsonpath: '$.items' } })
    expect(registryIssues(container, 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toEqual([])
    expect(pathResolvable('$.items[0]', new Set(['$.items[0].sku']))).toBe(true)
    expect(pathResolvable('$.amount', new Set(['$.amount']))).toBe(true)
    expect(pathResolvable('$.amoun', new Set(['$.amount']))).toBe(false)   // 前缀字符串不算
  })
  it('RG-4: override 匹配不到既有断言 → override-no-match;append 不查匹配', () => {
    const base = { 0: ['$.response_body.other'] }
    expect(registryIssues(E(), 2, bodyPaths(BODY0), targets(base)))
      .toContainEqual({ kind: 'override-no-match', stepIndex: 0, target: '$.response_body.code' })
    const app = E({ asserts: [{ stepIndex: 0, target: '$.new', operator: 'eq', expected: '1', mode: 'append' }] })
    expect(registryIssues(app, 2, bodyPaths(BODY0), targets(base))).toEqual([])
  })
  it('RG-5: v2 旧条目(无 path)→ legacy-entry;isLegacyEntry 守卫', () => {
    expect(isLegacyEntry(LEGACY)).toBe(true)
    expect(isLegacyEntry(E())).toBe(false)
    expect(registryIssues(LEGACY, 2, bodyPaths(BODY0), targets({}))).toEqual([{ kind: 'legacy-entry' }])
    expect(isDeadEntry(LEGACY, 2, bodyPaths(BODY0), targets({}))).toBe(true)
  })
  it('RG-6: genEntryId 不变;bodyPathSetOf 只收 body 源叶子', () => {
    const a = genEntryId()
    expect(a).toMatch(/^inj-[a-z0-9]{9}$/)
    expect(new Set([a, genEntryId(), genEntryId()]).size).toBe(3)
    expect(bodyPathSetOf([
      { source: 'body', path: '$.a' },
      { source: 'headers', path: '$.h' },
    ])).toEqual(new Set(['$.a']))
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/assertion-registry.test.ts`
Expected: FAIL(path/source/value 类型不存在、pathResolvable 未导出、legacy-entry 未定义)。

- [ ] **Step 3: 重写 `types/assertion-registry.ts`**

```ts
// types/assertion-registry.ts
/** 断言管理注册表(spec v3 §2)— 平台侧偏离注入条目,场景级资产,
 *  住场景文档 payload.assertion_registry(与 orchestration 同级,引擎不感知)。 */

/** 定位面:锁定到该元素的地址。jsonpath 根 = 该步请求 body */
export interface EntryPath {
  stepIndex: number
  source: 'body'
  /** jsonpath 风格,$. 前缀(实例路径,数组带 [i]) */
  jsonpath: string
}

/** 期望偏离面:override 覆写既有断言(匹配键 = stepIndex+target)/ append 追加 */
export interface AssertPatch {
  stepIndex: number
  target: string
  operator: string
  expected: unknown
  mode: 'override' | 'append'
}

/** v3 条目三元组:定位 path + 注入值 + 期望配对(spec v3 §2) */
export interface AssertionEntry {
  id: string
  name: string
  path: EntryPath
  /** 注入面:替换该字段的值(字面量,原样覆写不 coerce;
   *  物化 = 引擎 Assign 直补 $.request_body,与 config.vars 零耦合) */
  value: unknown
  asserts: AssertPatch[]
}

/** v2 旧形状(anchor + injection)— 仅识别不编辑(spec v3 §8 灰显);
 *  保留原样不删,不可编辑、不可选中执行 */
export interface LegacyAssertionEntry {
  id: string
  name: string
  anchor?: { stepIndex: number; source: 'body' | 'headers'; jsonpath: string; varName?: string }
  injection?: Array<{ varName: string; value: unknown }>
  asserts?: AssertPatch[]
}

/** 注册表容器:v3 条目与旧条目共存于同一 entries 数组(spec v3 §8) */
export interface AssertionRegistry {
  entries: Array<AssertionEntry | LegacyAssertionEntry>
}

/** v2 旧形状识别(spec v3 §7/§8):无 path 键 = 旧条目。 */
export function isLegacyEntry(e: AssertionEntry | LegacyAssertionEntry): e is LegacyAssertionEntry {
  return (e as AssertionEntry).path === undefined
}
```

- [ ] **Step 4: 重写 `utils/assertion-registry.ts`**

```ts
// utils/assertion-registry.ts
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'

export type RegistryIssue =
  | { kind: 'legacy-entry' }
  | { kind: 'step-oob'; stepIndex: number }
  | { kind: 'path-unresolvable'; stepIndex: number; jsonpath: string }
  | { kind: 'override-no-match'; stepIndex: number; target: string }

/** body 叶子路径投影(spec v3 §2 path-unresolvable 检测输入):
 *  调用方从 fieldPathsOf(step)(utils/dataset-segments)取叶子列表,
 *  这里滤出 body 源(headers 源 v1 不支持 path 注入,spec §1 裁定 9)。 */
export function bodyPathSetOf(
  leaves: Array<{ source: string; path: string }>,
): ReadonlySet<string> {
  return new Set(leaves.filter((l) => l.source === 'body').map((l) => l.path))
}

/** path 是否可解析:等于某叶子,或是某叶子的容器前缀(`p.` / `p[`
 *  开头)— 条目可锚在容器上,Assign 会整体覆写该容器(spec §2)。 */
export function pathResolvable(jsonpath: string, bodyPaths: ReadonlySet<string>): boolean {
  if (bodyPaths.has(jsonpath)) return true
  for (const p of bodyPaths) {
    if (p.startsWith(`${jsonpath}.`) || p.startsWith(`${jsonpath}[`)) return true
  }
  return false
}

/** 悬空检测(spec v3 §2,软提示不阻断):legacy-entry / step-oob /
 *  path-unresolvable / override-no-match。bodyPathsOfStep 与
 *  assertTargetsOf 由调用方从场景 definition 投影(编辑器/编排器同构)。 */
export function registryIssues(
  entry: AssertionEntry | LegacyAssertionEntry,
  stepCount: number,
  bodyPathsOfStep: (stepIndex: number) => ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): RegistryIssue[] {
  if (isLegacyEntry(entry)) return [{ kind: 'legacy-entry' }]
  const issues: RegistryIssue[] = []
  if (entry.path.stepIndex < 0 || entry.path.stepIndex >= stepCount) {
    issues.push({ kind: 'step-oob', stepIndex: entry.path.stepIndex })
  } else if (!pathResolvable(entry.path.jsonpath, bodyPathsOfStep(entry.path.stepIndex))) {
    issues.push({ kind: 'path-unresolvable', stepIndex: entry.path.stepIndex, jsonpath: entry.path.jsonpath })
  }
  for (const a of entry.asserts) {
    if (a.stepIndex < 0 || a.stepIndex >= stepCount) {
      issues.push({ kind: 'step-oob', stepIndex: a.stepIndex })
    } else if (a.mode === 'override' && !assertTargetsOf(a.stepIndex).has(a.target)) {
      issues.push({ kind: 'override-no-match', stepIndex: a.stepIndex, target: a.target })
    }
  }
  return issues
}

export function isDeadEntry(
  entry: AssertionEntry | LegacyAssertionEntry,
  stepCount: number,
  bodyPathsOfStep: (stepIndex: number) => ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): boolean {
  return registryIssues(entry, stepCount, bodyPathsOfStep, assertTargetsOf).length > 0
}

/** 注册表形状归一:服务端来源(draft)不可信 — V2 之前保存的场景无
 *  assertion_registry 键,后端 pydantic default 补成 `{}`(truthy,无
 *  entries)→ `?? { entries: [] }` 只兜 null 挡不住,直灌 registry 会
 *  在 `registry.entries.length` 崩渲染。所有水化入口统一走这里。 */
export function normalizeRegistry(raw: unknown): AssertionRegistry {
  const entries = (raw as AssertionRegistry | undefined | null)?.entries
  return { entries: Array.isArray(entries) ? entries : [] }
}

/** 条目 id:inj-<6位base36时间戳><3位随机>(genScenarioId 同款纪律,无依赖) */
export function genEntryId(): string {
  const ts = Date.now().toString(36).slice(-6)
  const rnd = Math.floor(Math.random() * 36 ** 3).toString(36).padStart(3, '0')
  return `inj-${ts}${rnd}`
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/assertion-registry.test.ts`
Expected: PASS(6 用例)。

- [ ] **Step 6: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/types/assertion-registry.ts src/gimbal-platform/frontend/src/utils/assertion-registry.ts src/gimbal-platform/frontend/src/utils/__tests__/assertion-registry.test.ts && git commit -m "feat(assertion): v3 条目形状重铸 — path/value/asserts 三元组 + 悬空三检 + legacy 识别

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

(注:此提交后 vue-tsc 对编辑器/编排器旧调用报错属预期,Task 4-6 逐个收编 — 见 Global Constraints 中间态申报。)

---

### Task 2: run_injection 重铸(Assign 直补)+ dispatcher 调用点跟随

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_injection.py`(整体重写)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(仅 §2.5 调用点 + `_body_of` helper 新增 + `_definition_vars` 删除;交叉矩阵留给 Task 3)
- Test: `src/gimbal-platform/backend/tests/test_run_injection.py`(整体重写)

**Interfaces:**
- Consumes: Task 1 无关(后端自由 dict)。引擎既有:`jsonpath.exists(data, path) -> bool`(app/services/jsonpath.py:589,JsonPathError → False);Assign 策略 `{kind:"assign", source:<literal>, target:str}`(plate StrategyUnion 合法成员)。
- Produces(Task 3 消费,签名逐字):
  - `entry_issues(entry: dict, step_count: int, body_of: Callable[[int], Any], assert_targets_of: Callable[[int], set[str]]) -> list[dict]` — 无 path 键 → `[{"kind": "legacy-entry"}]`;path stepIndex 越界 → step-oob;`not exists(body_of(si), jsonpath)` → path-unresolvable;override 无匹配 → override-no-match。`var_names` 参数退役。
  - `compose_injection_scenario(definition: dict, entry: dict) -> dict` — **不触碰 config.vars**;`steps[path.stepIndex].strategy` 追加 `{"kind": "assign", "source": entry["value"], "target": "$.request_body" + jsonpath[1:]}`;asserts patch 语义不变(override 改 expected / append 追加)。
  - dispatcher `_body_of(payload) -> Callable[[int], Any]`(steps[si].request.body 投影)。

- [ ] **Step 1: 写失败测试**(整文件重写 `tests/test_run_injection.py` 的纯函数段 + 集成段)

```python
"""run_injection — 注入条目物化纯函数 + 集成(spec v3 §3)。"""
import asyncio

import pytest

from app.services.run_injection import compose_injection_scenario, entry_issues
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)

DEF = {
    "config": {"vars": {"amount": 100, "bl_no": "BL1"}},
    "steps": [
        {"description": "下单", "request": {"body": {"amount": "${var.amount}"}},
         "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                       "operator": "eq", "expected": "0"}]},
        {"description": "查单", "request": {"body": {"bl_no": "${var.bl_no}"}}, "strategy": []},
    ],
}


def _body_of(steps):
    return lambda si: (steps[si].get("request") or {}).get("body")


def _targets_of(steps):
    def _t(si: int) -> set:
        return {st.get("target") for st in (steps[si].get("strategy") or [])
                if isinstance(st, dict) and st.get("kind") == "assertion"}
    return _t


def test_assign_appends_strategy_without_touching_vars():
    """path 直补(spec v3 §3):Assign 追加进 steps[si].strategy,config.vars
    零触碰(与数据集 vars 注入解耦);源 definition 零污染。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
             "value": -1, "asserts": []}
    out = compose_injection_scenario(DEF, entry)
    assert out["config"]["vars"]["amount"] == 100            # vars 不动
    st = out["steps"][0]["strategy"]
    assert st[-1] == {"kind": "assign", "source": -1, "target": "$.request_body.amount"}
    assert DEF["steps"][0]["strategy"] == [{"kind": "assertion", "target": "$.response_body.code",
                                            "operator": "eq", "expected": "0"}]   # 源零污染


def test_assign_value_passthrough_no_coerce():
    """value 原样覆写不 coerce(str/bool/嵌套 dict 都不转形)。"""
    for v in ["-1", True, {"a": [1, 2]}, None]:
        entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
                 "value": v, "asserts": []}
        out = compose_injection_scenario(DEF, entry)
        assert out["steps"][0]["strategy"][-1]["source"] == v


def test_override_and_append_patch_keep_v2_semantics():
    entry = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
             "value": -1, "asserts": [
                 {"stepIndex": 0, "target": "$.response_body.code", "operator": "eq",
                  "expected": "400", "mode": "override"},
                 {"stepIndex": 1, "target": "$.response_body.msg", "operator": "contains",
                  "expected": "金额非法", "mode": "append"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "400"    # override 改 expected
    assert {"kind": "assertion", "target": "$.response_body.msg",
            "operator": "contains", "expected": "金额非法"} in out["steps"][1]["strategy"]


def test_dangling_path_and_unmatched_override_skipped():
    """悬空项静默跳过(dispatcher 已过滤,双保险):越界 stepIndex 不落
    Assign;无匹配 override 不动既有断言。issues 同构断言四种。"""
    entry = {"id": "inj-1", "path": {"stepIndex": 9, "source": "body", "jsonpath": "$.x"},
             "value": 1, "asserts": [
                 {"stepIndex": 0, "target": "$.nope", "operator": "eq", "expected": "1", "mode": "override"}]}
    out = compose_injection_scenario(DEF, entry)
    assert out["steps"][0]["strategy"][0]["expected"] == "0"     # 无匹配 override 不动
    assert all(st.get("kind") != "assign" for s in out["steps"] for st in s["strategy"])
    issues = entry_issues(entry, 2, _body_of(DEF["steps"]), _targets_of(DEF["steps"]))
    assert {"kind": "step-oob", "stepIndex": 9} in issues
    assert {"kind": "override-no-match", "stepIndex": 0, "target": "$.nope"} in issues


def test_entry_issues_path_unresolvable_and_legacy():
    body_of = _body_of(DEF["steps"])
    targets = _targets_of(DEF["steps"])
    ghost = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.ghost"},
             "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.ghost"} in \
        entry_issues(ghost, 2, body_of, targets)
    # 容器前缀可解析:叶子 $.amount 在树上,$. 不在
    ok = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
          "value": 1, "asserts": []}
    assert entry_issues(ok, 2, body_of, targets) == []
    # str body 步骤无可索引字段 → 一律不可解析(spec v3 §2)
    str_body = [{"request": {"body": "raw"}}]
    s = {"id": "inj-1", "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.x"},
         "value": 1, "asserts": []}
    assert {"kind": "path-unresolvable", "stepIndex": 0, "jsonpath": "$.x"} in \
        entry_issues(s, 2, _body_of(str_body), targets)
    # v2 旧形状(无 path)→ legacy-entry 全量 issue(spec v3 §8)
    legacy = {"id": "inj-old", "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
              "injection": [{"varName": "amount", "value": "-1"}], "asserts": []}
    assert entry_issues(legacy, 2, body_of, targets) == [{"kind": "legacy-entry"}]
```

集成段(替换旧 `test_dispatcher_fans_out_injection_entries`;**本任务仍是并集语义** — 交叉矩阵是 Task 3;此处只验证新物化 + 旧/死条目 skip):

```python
# ── dispatcher 集成(spec v3 §3:Assign 直补落 case.json;skip 链)────
# 骨架不变:建场景(assertion_registry 注入)→ POST /api/runs → 断言
# case 数 / case.json patch / rows 回放。

_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """JSONL/case 目录指到 tmp:回放只读本测试写入的行(镜像
    test_execution_rows.py 的做法,理由见其注释)。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


async def test_dispatcher_fans_out_injection_entries(
    client, plate_mock: PlateMock, monkeypatch
):
    """选中 1 活条目(+ 死条目 + 旧版条目)且无数据集 → case 数 = 活条目数
    ×nRuns;死/旧条目 skip 不炸;case.json 的 steps[0].strategy 已追加
    Assign 直补($.request_body.amount)且 vars 未被触碰;rows 回放含
    injectionId。"""
    from .helpers import make_draft as _draft, wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_visibility_and_copy import _member

    bob = await _member(client, "bob")
    draft = _draft(
        steps=[
            {"id": "s1", "request": {"body": {"amount": "${var.amount}"}},
             "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                           "operator": "eq", "expected": "0"}]},
            {"id": "s2", "strategy": []},
        ],
        vars_map={"amount": 100},
    )
    draft["assertion_registry"] = {"entries": [
        # 活条目:Assign 直补(value -1,原样不 coerce)+ override patch('400')
        {"id": "inj-live", "name": "金额非法",
         "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
         "value": -1,
         "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                      "operator": "eq", "expected": "400", "mode": "override"}]},
        # 死条目:path stepIndex 越界 → entry_issues 判死,skip 不炸
        {"id": "inj-dead", "name": "越界死条目",
         "path": {"stepIndex": 9, "source": "body", "jsonpath": "$.x"},
         "value": 1,
         "asserts": [{"stepIndex": 9, "target": "$.x", "operator": "eq",
                      "expected": "1", "mode": "append"}]},
        # 旧版条目(v2 anchor+injection 形状)→ legacy-entry 全量 issue → skip
        {"id": "inj-old", "name": "旧版条目",
         "anchor": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount", "varName": "amount"},
         "injection": [{"varName": "amount", "value": "-1"}], "asserts": []},
    ]}
    r = await client.post("/api/scenarios", headers=bob, json=draft)
    assert r.status_code in (200, 201), r.text

    # echo:converted 原样回灌 → case.json 保留 patched strategy 可断言
    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [],
        "injectionEntryIds": ["inj-live", "inj-dead", "inj-old"], "nRuns": 2,
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 2)
    assert len(cases) == 2                       # 1 活条目 × nRuns=2;死/旧 skip
    for case in cases:
        st = case["steps"][0]["strategy"]
        assert st[0]["expected"] == "400"                          # override patch
        assert {"kind": "assign", "source": -1,
                "target": "$.request_body.amount"} in st           # Assign 直补
        assert case["config"]["vars"]["amount"] == 100             # vars 未触碰

    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 2
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 2
    assert all(row["injectionId"] == "inj-live" for row in rows)
    assert all(row["datasetId"] is None for row in rows)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_injection.py -v`
Expected: FAIL — 纯函数用例因 `entry_issues` 旧签名(body_of 不存在/legacy 分支缺失)与 compose 仍写 vars 而失败;集成用例因条目仍走 vars 覆写(`config.vars.amount == "-1"` 断言错)而失败。

- [ ] **Step 3: 重写 `run_injection.py`**

```python
"""注入条目物化(spec v3 §3)— 平台层 patch,引擎/plate 零改动。

与 run_materialize.py 同纪律:纯函数、深拷贝进深拷贝出、执行链唯一物化语义。
assertion_registry 条目在 plate convert 之前落进 definition(steps[si].strategy
追加 Assign 直补 + asserts patch),materialize_run_copy 其后照旧。
值注入与数据集 vars 注入完全解耦(正交叠加):compose 不触碰 config.vars。
"""
import copy
from typing import Any, Callable

from .jsonpath import exists


def entry_issues(
    entry: dict[str, Any],
    step_count: int,
    body_of: Callable[[int], Any],
    assert_targets_of: Callable[[int], set[str]],
) -> list[dict[str, Any]]:
    """悬空检测(前端 utils/assertion-registry.ts 的 Python 同构,spec v3 §2):
    旧形状条目(无 path)/ stepIndex 越界 / path 不落在该步 request body
    字段树(jsonpath.exists;str body 无可索引字段恒不可解析)/ override
    无匹配。"""
    issues: list[dict[str, Any]] = []
    path = entry.get("path")
    if not isinstance(path, dict):
        # v2 旧形状(anchor+injection)或残缺条目:全量 issue → skip(spec v3 §8)
        return [{"kind": "legacy-entry"}]
    si = path.get("stepIndex")
    jp = path.get("jsonpath")
    if not isinstance(si, int) or si < 0 or si >= step_count:
        issues.append({"kind": "step-oob", "stepIndex": si})
    elif not isinstance(jp, str) or not exists(body_of(si) or {}, jp):
        issues.append({"kind": "path-unresolvable", "stepIndex": si, "jsonpath": jp})
    for a in entry.get("asserts") or []:
        if isinstance(a, dict) and isinstance(a.get("stepIndex"), int):
            asi = a["stepIndex"]
            if asi < 0 or asi >= step_count:
                issues.append({"kind": "step-oob", "stepIndex": asi})
            elif a.get("mode") == "override" and a.get("target") not in assert_targets_of(asi):
                issues.append({"kind": "override-no-match",
                               "stepIndex": asi, "target": a.get("target")})
    return issues


def compose_injection_scenario(definition: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Assign 直补 + asserts patch(spec v3 §3)。config.vars 零触碰 —
    数据集行值合入在 _compose_scenario(与 Assign 正交叠加,偏离最后生效:
    字段恰为模板串时被字面量整体替换,该 case 内行值对此字段不再起效)。
    悬空项静默跳过 — dispatcher 层已先经 entry_issues 过滤,此处双保险。
    value 由用户显式编辑,原样覆写不 coerce(引擎 _resolve_source_value
    对非模板 source 直通)。
    """
    out = copy.deepcopy(definition)
    steps = out.get("steps") or []
    path = entry.get("path")
    if isinstance(path, dict):
        si = path.get("stepIndex")
        jp = path.get("jsonpath")
        if (isinstance(si, int) and 0 <= si < len(steps)
                and isinstance(jp, str) and jp.startswith("$")):
            # $.amount → $.request_body.amount;根 "$" → $.request_body
            target = "$.request_body" + (jp[1:] if jp != "$" else "")
            steps[si].setdefault("strategy", []).append(
                {"kind": "assign", "source": entry.get("value"), "target": target})
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

- [ ] **Step 4: dispatcher 调用点跟随(`run_dispatcher.py` 两处小 hunk)**

hunk A — helpers 段(1071-1075 附近):删除 `_definition_vars`,新增 `_body_of`:

```python
def _body_of(payload: dict | None) -> Callable[[int], Any]:
    """steps[si].request.body 投影(entry_issues 的 path-unresolvable
    检测输入,spec v3 §2;jsonpath.exists 在其上判路径可解析性)。"""
    steps = steps_from_payload(payload)

    def _body(si: int) -> Any:
        if si < 0 or si >= len(steps):
            return None
        return (steps[si].get("request") or {}).get("body")

    return _body
```

hunk B — §2.5 过滤处(395-418 附近)的 `entry_issues(...)` 调用替换:

```python
        issues = entry_issues(
            e,
            len(steps_from_payload(raw_payload) or []),
            _body_of(raw_payload),
            _assert_targets_of(raw_payload),
        )
```

(§2.5 注释块同步改为:「v3 §8:被选中且悬空检测通过的条目 → 注入族;死/旧条目 skip + 告警,绝不炸 dispatch」。其余不动 — 并集 → 交叉在 Task 3。)

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_injection.py -v`
Expected: PASS(5 纯函数 + 1 集成)。
再跑邻近回归: `python -m pytest tests/test_run_m1_capabilities.py tests/test_run_baseline.py -v` → PASS(dispatcher 调用点未破坏既有族)。

- [ ] **Step 6: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/services/run_injection.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_injection.py && git commit -m "feat(run): 注入条目物化重铸 — Assign 直补 request_body,vars 解耦 + legacy/死条目 skip

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: schemas `dataSetSelection` + dispatcher 交叉矩阵 + 审计三定位

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py`(DataSetSelection 新类 + RunRequest/RunScheme 新键 + `__all__`)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(§2 选择合并 / §3 行过滤与交叉 / config_json / `_fanout` entries 重构 / `_row` 组合序与 stem)
- Test: `src/gimbal-platform/backend/tests/test_run_cross_matrix.py`(新建)

**Interfaces:**
- Consumes: Task 2 的 `entry_issues` / `compose_injection_scenario`(签名不变);dispatcher 既有 `_compose_scenario(scenario_payload, row_dict)`、`_find_dataset_by_id`。
- Produces(Task 6/7 前端消费,wire 形状):
  - `dataSetSelection: [{ datasetId: string, rowIndexes: number[] }]`(0-based;缺省/空 = 整库);两键同发时 dataSetSelection 优先、dataSetIds 忽略(兼容读保留,schemas 不删 dataSetIds)。
  - 行越界 → `409 Conflict`,error code `row_index_out_of_range`。
  - case stem 统一 `case-{seq:03d}-{datasetId|baseline}-r{rowIdx}[-inj-{entryId}]-n{rep}`;交叉行 JSONL/RowState 同时记 `datasetId + rowIndex + injectionId`(三字段首次同时有值)。
  - 总量公式:`total_runs = Σ(选中行数) × max(选中条目数, 1) × nRuns`;都不选 = 1 基线 case。

- [ ] **Step 1: 写失败测试**(新建 `tests/test_run_cross_matrix.py`,整文件)

```python
"""dispatcher 交叉矩阵 + dataSetSelection 行级选择(spec v3 §4)。"""
import asyncio

import pytest

from app.schemas.scenario_composer import RunRequest, RunScheme
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)
from .test_scenario_composer_container import _register_and_login  # noqa: F401


# ── 纯函数:schema 键解析 ────────────────────────────────────────────
def test_run_request_parses_data_set_selection():
    req = RunRequest.model_validate({
        "scenarioId": "sc-test",
        "dataSetSelection": [
            {"datasetId": "ds-a", "rowIndexes": [0, 2]},
            {"datasetId": "ds-b"},                       # 缺省 = 整库
        ],
        "dataSetIds": ["ds-c"],                          # 兼容键照收
    })
    assert req.data_set_selection[0].dataset_id == "ds-a"
    assert req.data_set_selection[0].row_indexes == [0, 2]
    assert req.data_set_selection[1].row_indexes == []   # 整库 = 空
    assert req.data_set_ids == ["ds-c"]
    assert RunScheme.model_validate({
        "name": "s", "dataSetSelection": [{"datasetId": "ds-a", "rowIndexes": [1]}],
    }).data_set_selection[0].row_indexes == [1]


# ── 集成:交叉矩阵 ──────────────────────────────────────────────────
_EXEC_FINAL = {"done", "failed", "canceled"}


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)


async def _await_final(client, headers, exec_id: int) -> None:
    for _ in range(200):
        ex = (await client.get(f"/api/executions/{exec_id}", headers=headers)).json()
        if ex["status"] in _EXEC_FINAL:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("execution not final in 10s")


_LIVE_ENTRY = {
    "id": "inj-live", "name": "金额非法",
    "path": {"stepIndex": 0, "source": "body", "jsonpath": "$.amount"},
    "value": -1,
    "asserts": [{"stepIndex": 0, "target": "$.response_body.code",
                 "operator": "eq", "expected": "400", "mode": "override"}],
}


async def _seed(client, headers, *, entries=None, rows=None):
    """建场景(1 步,body.amount 模板 + code 断言)+ 数据集。"""
    from .helpers import make_draft as _draft

    draft = _draft(
        steps=[
            {"id": "s1", "request": {"body": {"amount": "${var.amount}"}},
             "strategy": [{"kind": "assertion", "target": "$.response_body.code",
                           "operator": "eq", "expected": "0"}]},
            {"id": "s2", "strategy": []},
        ],
        vars_map={"amount": 100},
    )
    if entries is not None:
        draft["assertion_registry"] = {"entries": entries}
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code in (200, 201), r.text
    if rows is None:
        return None
    r = await client.post("/api/scenarios/sc-test/data-sets", headers=headers,
                          json={"name": "正负流", "rows": rows})
    assert r.status_code == 201, r.text
    return r.json()["datasetId"]


async def test_cross_matrix_rows_times_entries(
    client, plate_mock: PlateMock, monkeypatch
):
    """双选 = N×M 交叉(spec v3 §4):2 行 × 1 条目 × nRuns=2 = 4 cases;
    每 case 行值合入 vars AND Assign 直补同场(正交叠加);rows 回放
    三定位同记(datasetId + rowIndex + injectionId);stem 带三定位。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_composer_plate_integration import _member_headers

    bob = await _member_headers(client)
    ds_id = await _seed(client, bob, entries=[_LIVE_ENTRY],
                        rows=[{"amount": 10}, {"amount": 20}])

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_id}],
        "injectionEntryIds": ["inj-live"], "nRuns": 2,
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]

    await _wait(lambda: len(cases) >= 4)
    assert len(cases) == 4                          # 2 行 × 1 条目 × 2 rep
    for case in cases:
        assert case["config"]["vars"]["amount"] in (10, 20)     # 行值合入
        st = case["steps"][0]["strategy"]
        assert st[0]["expected"] == "400"                        # asserts patch
        assert {"kind": "assign", "source": -1,
                "target": "$.request_body.amount"} in st         # Assign 直补
    # 交叉完备:两行 × 两 rep 都出现过
    assert {c["config"]["vars"]["amount"] for c in cases} == {10, 20}

    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 4
    await _await_final(client, bob, exec_id)

    rows = (await client.get(f"/api/executions/{exec_id}/rows", headers=bob)
            ).json()["items"]
    assert len(rows) == 4
    assert all(row["datasetId"] == ds_id for row in rows)
    assert all(row["injectionId"] == "inj-live" for row in rows)   # 三定位同记
    assert {row["rowIndex"] for row in rows} == {0, 1}


async def test_row_selection_single_row(
    client, plate_mock: PlateMock, monkeypatch
):
    """dataSetSelection rowIndexes=[1] → 只跑该行(1 case,vars=行值)。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_composer_plate_integration import _member_headers

    bob = await _member_headers(client)
    ds_id = await _seed(client, bob, rows=[{"amount": 10}, {"amount": 20}])

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_id, "rowIndexes": [1]}],
    })
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1
    assert cases[0]["config"]["vars"]["amount"] == 20
    assert all("source" not in st or st.get("kind") != "assign"
               for st in cases[0]["steps"][0]["strategy"])   # 未选条目 = 无注入


async def test_row_index_out_of_range_409(client, plate_mock):
    """rowIndexes 越界 → 409 row_index_out_of_range,不派发任何 case。"""
    from .test_scenario_composer_plate_integration import _member_headers

    bob = await _member_headers(client)
    ds_id = await _seed(client, bob, rows=[{"amount": 10}])
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test",
        "dataSetSelection": [{"datasetId": ds_id, "rowIndexes": [3]}],
    })
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "row_index_out_of_range"


async def test_both_empty_single_baseline(
    client, plate_mock: PlateMock, monkeypatch
):
    """都不选 = 1 基线 case(R={[基线]} × E={[无注入]})。"""
    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture
    from .test_scenario_composer_plate_integration import _member_headers

    bob = await _member_headers(client)
    await _seed(client, bob)

    plate_mock.behaviour = "echo"
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-test", "dataSetIds": [], "injectionEntryIds": [],
    })
    assert r.status_code == 201, r.text
    exec_id = r.json()["executionId"]
    await _wait(lambda: len(cases) >= 1)
    assert len(cases) == 1
    assert cases[0]["config"]["vars"]["amount"] == 100        # 基线 vars
    detail = (await client.get(f"/api/executions/{exec_id}", headers=bob)).json()
    assert detail["total_runs"] == 1
```

(注:`_member_headers` 若在该模块不存在,以 `test_scenario_visibility_and_copy._member` 同款替代 — 建 admin 吃 bootstrap 后拿普通成员 headers;禁止用 admin 直跑。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_cross_matrix.py -v`
Expected: FAIL — schema 用例 `data_set_selection` 属性不存在(AttributeError/ValidationError);集成用例 422(dataSetSelection 键被 pydantic 静默忽略后 ds 未选)或交叉计数断言错(现状并集 = N+M)。

- [ ] **Step 3: schemas 加 DataSetSelection(`scenario_composer.py`)**

在 `RunScheme` 类定义之前(ServiceBinding 之后)插入:

```python
class DataSetSelection(BaseModel):
    """行级数据集选择(spec v3 §4):datasetId + rowIndexes(0-based,
    与编辑器行号一致;缺省/空 = 整库)。RunRequest/RunScheme 的权威
    选择键;旧 dataSetIds 保留为兼容读(两键同发本键优先)。"""
    model_config = _CAMEL

    dataset_id: str = Field(alias="datasetId", min_length=1, max_length=128)
    row_indexes: list[int] = Field(default_factory=list, alias="rowIndexes")
```

`RunScheme` 在 `injection_entry_ids` 字段后加:

```python
    # 行级数据集选择(spec v3 §4)— 权威键;旧方案无此键 = 整库回读。
    data_set_selection: list[DataSetSelection] = Field(
        default_factory=list, alias="dataSetSelection"
    )
```

`RunRequest` 在 `data_set_ids` 字段后加同款字段(注释改「行级数据集选择(spec v3 §4)— 权威键;两键同发时本键优先,dataSetIds 忽略」)。`__all__` 加 `"DataSetSelection"`。

- [ ] **Step 4: dispatcher 交叉矩阵(`run_dispatcher.py` 五处 hunk)**

hunk A — §2 数据集校验(386-393)替换为选择合并 + 单次加载:

```python
    # 行级选择合并(spec v3 §4):dataSetSelection 权威,dataSetIds 兼容
    # 读(映射为整库);同库多段合并行集,行集空 = 整库;某段整库则整库
    # (整库 ⊇ 任意行集,合并取超集)。
    sel_by_ds: dict[str, list[int] | None] = {}
    for sel in req.data_set_selection:
        ds_id = sel.dataset_id
        if ds_id not in sel_by_ds:
            sel_by_ds[ds_id] = list(sel.row_indexes) or None
        elif sel_by_ds[ds_id] is not None and sel.row_indexes:
            sel_by_ds[ds_id] = sorted(
                set(sel_by_ds[ds_id]) | set(sel.row_indexes)
            )
    for ds_id in req.data_set_ids:
        sel_by_ds.setdefault(ds_id, None)

    selected_datasets: list[ComposerDataSet] = []
    for ds_id in sel_by_ds:
        ds = await _find_dataset_by_id(db, ds_id)
        if ds is None or ds.scenario_id != scen.scenario_id:
            raise NotFound(
                "data_set_not_found", f"data set not found: {ds_id}"
            )
        selected_datasets.append(ds)
```

hunk B — §3 fanout 构建 + total_runs(425-439 的 D12/并集块)替换:

```python
    run_id = _new_run_id()
    # 行级过滤(spec v3 §4):rowIndexes 选中行;越界 409。行集为空的
    # 数据集 = 隐式空覆盖行(D12 基线语义);rowIndexes 校验对真实行数。
    fanout_datasets: list[dict] = []
    for ds in selected_datasets:
        rows_raw = list(ds.rows or [])
        sel = sel_by_ds.get(ds.dataset_id)
        if sel is None:
            fanout_datasets.append(
                {"datasetId": ds.dataset_id, "rows": rows_raw or [{}]}
            )
        else:
            for ri in sel:
                if ri < 0 or ri >= len(rows_raw):
                    raise Conflict(
                        "row_index_out_of_range",
                        f"rowIndex={ri} out of range for data set "
                        f"{ds.dataset_id} (0..{len(rows_raw) - 1})",
                    )
            fanout_datasets.append(
                {"datasetId": ds.dataset_id, "rows": [rows_raw[ri] for ri in sel]}
            )
    # 交叉矩阵(spec v3 §4):R(行集合,空={[基线]})× E(选中条目集合,
    # 空={[无注入]})— 每 case = 一行 × 一条目,单一偏离可直接归因;
    # 替代 v2 的 N+M 并集与 `not fanout and not entries` 特判。
    injections = list(selected_entries) or [None]
    if not fanout_datasets:
        fanout_datasets = [{"datasetId": None, "rows": [{}]}]
    # 数据集族 × 注入族合计(rows × entries × nRuns)。
    total_runs = (
        sum(len(d["rows"]) for d in fanout_datasets) * len(injections)
    ) * req.n_runs
```

hunk C — config_json(465-482)在 `"dataSetIds": req.data_set_ids,` 后加一行:

```python
            "dataSetSelection": [
                s.model_dump(by_alias=True) for s in req.data_set_selection
            ],
```

hunk D — `_fanout`:签名 `injections: list[dict] | tuple = ()` 改 `injections: list[dict | None] | tuple = ()`;认证失败分支的 total_rows(585-586)改交叉口径:

```python
        total_rows = (sum(len(ds["rows"]) for ds in datasets)
                      * len(injections or [None])) * n_runs
```

docstring 里「spec v2 §8:``injections`` … 与数据集族并集」段与 entries 构造处注释(844-847)改为交叉表述;entries 列表(848-857)替换为嵌套交叉:

```python
    # (dataset row × injection entry × repeat) 交叉笛卡尔积(spec v3 §4):
    # injections 已含 None 占位(未选条目时 = [None],恰一次无注入组合)。
    # seq 为 case 文件名里的全局序号(与 entries 顺序一致,单测可断言)。
    injections = list(injections) or [None]
    entries = [
        (ds, row_idx, inj, rep)
        for ds in datasets
        for row_idx in range(len(ds["rows"]))
        for inj in injections
        for rep in range(n_runs)
    ]
```

(RowState 初始化与 `asyncio.gather` 段解包顺序同步改为 `(ds, i, inj, r)` 对齐。)

hunk E — `_row` 组合序(670-677)either/or 改叠加,stem(681-686)统一:

```python
            # 交叉组合序(spec v3 §3):行值合入(vars)→ 条目 Assign 直补
            # + asserts patch — 偏离最后生效。基线/无行维度 = 空行字典。
            row_dict = dict(ds["rows"][row_idx] or {}) if ds is not None else {}
            composed = _compose_scenario(scenario_payload, row_dict)
            if injection is not None:
                composed = compose_injection_scenario(composed, injection)
```

```python
            # stem 三定位(spec v3 §4 审计):数据集(或 baseline)+ 行号
            # + 条目 id(无注入省略)+ rep,如 case-003-ds-x-r1-inj-inj-2-n0。
            stem = (
                f"case-{seq:03d}-{ds['datasetId'] or 'baseline'}-r{row_idx}"
                + (f"-inj-{injection_id}" if injection_id else "")
                + f"-n{rep}"
            )
```

(§2.5 注释块、`_row` docstring 首行的「or (injection entry × repeat)」措辞同步改为交叉表述。)

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest tests/test_run_cross_matrix.py tests/test_run_injection.py -v`
Expected: PASS(交叉 4 + Task 2 回归 6 — Task 2 集成在新公式下同为 2 cases:1 活条目 × [基线] × nRuns=2)。
再跑邻近回归: `python -m pytest tests/test_run_m1_capabilities.py tests/test_run_baseline.py tests/test_run_cancel.py -v` → PASS(dataSetIds 旧路径走 setdefault 整库,行为不变)。

- [ ] **Step 6: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/backend/app/schemas/scenario_composer.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_cross_matrix.py && git commit -m "feat(run): dataSetSelection 行级选择 + 执行矩阵改 R×E 交叉(逐行×条目,审计三定位)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: AssertionRegistryEditor 三元组重铸

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue`(整体重写)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts`(整体重写)

**Interfaces:**
- Consumes: Task 1 的 `AssertionEntry` / `LegacyAssertionEntry` / `isLegacyEntry` / `isDeadEntry` / `registryIssues` / `normalizeRegistry` / `genEntryId` / `bodyPathSetOf`;`fieldPathsOf(step)`(utils/dataset-segments,`SegmentStepShape | null | undefined → FieldLeaf[]`)。
- Produces(Task 7 消费):编辑器路由与整体 PUT 保存行为不变(只动 `assertion_registry` 键);条目落盘形状 = Task 1 `AssertionEntry`。

- [ ] **Step 1: 写失败测试**(整文件重写 `src/views/__tests__/AssertionRegistryEditor.test.ts`)

```ts
/**
 * AssertionRegistryEditor — 断言管理编辑器(spec v3 §5):
 * 条目列表(path 徽标/值摘要/期望数/死条目灰/旧版条目灰不可选)+
 * 详情(path 只读跳编排器 / value 类型化编辑 / asserts 编辑)+
 * 手工新建(步骤 + jsonpath)+ 整体 PUT(只动 assertion_registry 键)。
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
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
      value: -1,
      asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }] },
    { id: 'inj-dead', name: '悬空条目',
      path: { stepIndex: 9, source: 'body', jsonpath: '$.x' },
      value: 1, asserts: [] },
    { id: 'inj-legacy', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
      injection: [{ varName: 'amount', value: '-1' }], asserts: [] },
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

it('ARE-1: 列表渲染条目(名称/path 徽标/值摘要/期望数)', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(3)
  expect(rows[0].text()).toContain('金额为负')
  expect(rows[0].text()).toContain('步骤1 · $.amount')        // path 徽标
  expect(rows[0].text()).toContain('-1')                      // value 摘要
  expect(rows[0].text()).toContain('1 期望')                  // asserts 数
  w.unmount()
})

it('ARE-2: 悬空条目灰(stepIndex 越界)+ 旧版条目灰且不可选;活条目不灰', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows[1].classes()).toContain('are-dead')
  expect(rows[2].classes()).toContain('are-legacy')
  expect(rows[0].classes()).not.toContain('are-dead')
  // 旧版条目点击不进详情(不可编辑,spec v3 §8)
  await rows[2].trigger('click')
  await flushPromises()
  expect(w.find('.are-detail').exists()).toBe(false)
  w.unmount()
})

it('ARE-3: path ↗ 跳编排器(focusStep query)', async () => {
  const w = await mountEditor()
  await w.findAll('.are-anchor-jump')[0].trigger('click')
  expect(routerMock.push).toHaveBeenCalledWith({
    path: '/composer/sc-rg',
    query: { step: '4', focusStep: '0' },
  })
  w.unmount()
})

it('ARE-4: 手工新建(步骤+jsonpath)+ value num 类型化编辑 + 保存只动 assertion_registry', async () => {
  const w = await mountEditor()
  // 手工新建:pendingPath 填 $.bl_no → 新建条目
  ;(w.vm as any).pendingPath.jsonpath = '$.bl_no'
  await w.findAll('button').find((b) => b.text().includes('新建条目'))!.trigger('click')
  await flushPromises()
  expect(w.findAll('.are-row').length).toBe(4)
  const rows = w.findAll('.are-row')
  await rows[3].trigger('click')
  await flushPromises()
  const detail = w.find('.are-detail')
  expect(detail.exists()).toBe(true)
  // value 类型化编辑:num 类 '-7' → 落条目为 number -7(原样不 coerce 串)
  ;(w.vm as any).valueDraft.kind = 'num'
  ;(w.vm as any).valueDraft.text = '-7'
  ;(w.vm as any).applyValue()
  await w.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
  await flushPromises()
  expect(api.updateScenario).toHaveBeenCalledTimes(1)
  const payload = vi.mocked(api.updateScenario).mock.calls[0][1] as any
  expect(payload.definition).toEqual(DEF)                        // definition 原样
  const e3 = payload.assertion_registry.entries[3]
  expect(e3.path).toEqual({ stepIndex: 0, source: 'body', jsonpath: '$.bl_no' })
  expect(e3.value).toBe(-7)
  expect(e3.asserts).toEqual([])
  w.unmount()
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: FAIL — 旧编辑器读 `e.injection`(v3 条目无此键 → TypeError)/ `deadOf` 旧签名(第 3 参 varNames)/ legacy 行渲染崩。

- [ ] **Step 3: 重写 `AssertionRegistryEditor.vue`**

```vue
<!--
  AssertionRegistryEditor.vue — 断言管理编辑器(spec v3 §5/§8)

     场景级注册表的独立编辑视图(路由 /scenarios/:scenarioId/assertions):
       - 条目列表:名称 / path 徽标(步骤N · jsonpath + ↗ 跳编排器)/
         值摘要 / 期望数;悬空条目(step-oob / path-unresolvable /
         override-no-match,registryIssues)标灰;v2 旧条目(无 path)灰显
         「旧版条目,请重建」,不可选不可编辑(保留原样不删)
       - 条目详情:path 只读 + 跳编排器;value 类型化编辑
         (str/num/bool/json,按字段当前字面量类型还原);
         asserts 编辑(步骤/target/操作符/期望值/mode,继承 v2)
       - 手工新建 = 步骤下拉 + jsonpath 输入(path 是注入地址,不预设
         模板化);整体 PUT 保存 — 只动 assertion_registry 键
-->
<template>
  <section class="are-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title">断言管理(偏离注入)</h2>
        <p>
          场景 <strong class="scenario-name">{{ scenarioName }}</strong>
          <code class="sid">{{ scenarioId }}</code>
          · {{ registry.entries.length }} 条目 · 悬空 {{ deadCount }} 条
        </p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(composerUrl(scenarioId, 1))">返回编排器</el-button>
        <el-button type="primary" plain :loading="saving" :disabled="!draft" @click="save">保存</el-button>
      </div>
    </header>

    <p class="are-lead">
      每条 = 一次偏离注入:定位 path(引擎 Assign 直补 request_body,与数据集 vars 解耦)
      + 注入值 + 期望配对(override 覆写既有断言 / append 追加),执行时与数据集行
      交叉(spec v3 §3/§4)。悬空条目标灰只提示,不阻断编辑。
    </p>

    <!-- 手工新建:步骤 + jsonpath(path 即注入地址) -->
    <div class="are-new-bar">
      <el-select
        :model-value="pendingPath.stepIndex"
        size="small"
        class="are-step-select"
        @update:model-value="(v: any) => (pendingPath.stepIndex = Number(v))"
      >
        <el-option v-for="(label, i) in stepLabels" :key="`np:${i}`" :value="i" :label="label" />
      </el-select>
      <el-input v-model="pendingPath.jsonpath" size="small" class="are-path-input" placeholder="jsonpath($.amount)" />
      <el-button size="small" :disabled="!draft" @click="addEntry">新建条目</el-button>
    </div>

    <!-- 条目列表:path 徽标 / 值摘要 / 期望数 / 死条目灰 / 旧版条目灰 -->
    <div class="are-list-card">
      <div
        v-for="e in registry.entries"
        :key="e.id"
        class="are-row"
        :class="{ 'are-dead': deadOf(e), 'are-legacy': isLegacyEntry(e), 'are-active': selectedId === e.id }"
        :title="isLegacyEntry(e) ? '旧版条目,请重建' : deadOf(e) ? `悬空:${issueSummary(e)}` : ''"
        @click="selectEntry(e)"
      >
        <span class="are-name">{{ e.name }}</span>
        <span v-if="!isLegacyEntry(e)" class="are-anchor">
          步骤{{ e.path.stepIndex + 1 }} · {{ e.path.jsonpath }}
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click.stop="jumpToAnchor(e.path.stepIndex)"
          >↗</button>
        </span>
        <span v-else class="are-anchor are-anchor-none">旧版条目,请重建</span>
        <span class="are-inject" :title="valueSummary(e)">{{ valueSummary(e) }}</span>
        <span class="are-count">{{ e.asserts?.length ?? 0 }} 期望</span>
        <span v-if="isLegacyEntry(e)" class="are-legacy-mark">旧版</span>
        <span v-else-if="deadOf(e)" class="are-dead-mark" :title="`悬空:${issueSummary(e)}`">悬空</span>
        <button type="button" class="are-del" title="删除条目" @click.stop="removeEntry(e.id)">×</button>
      </div>
      <div v-if="!registry.entries.length" class="are-empty">
        还没有偏离注入条目 — 上方手工建,或在编排器字段菜单「加入断言管理」自动带来
      </div>
    </div>

    <!-- 详情:path 只读 + value 类型化编辑 / asserts 编辑 -->
    <div v-if="selected && !isLegacyEntry(selected)" class="are-detail">
      <div class="are-detail-head">
        <el-input v-model="selected.name" class="are-name-input" size="small" placeholder="条目名称" />
        <span class="are-anchor">
          锚点:步骤{{ selected.path.stepIndex + 1 }} · {{ selected.path.source }} · {{ selected.path.jsonpath }}
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click="jumpToAnchor(selected.path.stepIndex)"
          >↗</button>
        </span>
      </div>

      <!-- 注入值(value)— 类型化编辑 -->
      <div class="are-sec">
        <h4>注入值(value)<span class="are-sec-hint">物化 = 引擎 Assign 直补 request_body(spec v3 §3);原样覆写不 coerce</span></h4>
        <div class="are-value-edit">
          <el-select v-model="valueDraft.kind" size="small" class="are-kind-select" @change="onKindChange">
            <el-option value="str" label="str" />
            <el-option value="num" label="num" />
            <el-option value="bool" label="bool" />
            <el-option value="json" label="json" />
          </el-select>
          <el-checkbox
            v-if="valueDraft.kind === 'bool'"
            v-model="valueDraft.bool"
            @change="applyValue"
          >true</el-checkbox>
          <el-input
            v-else
            v-model="valueDraft.text"
            size="small"
            class="are-val-input"
            placeholder="偏离值(例:-1 / "中文" / {"a":1})"
            @change="applyValue"
          />
          <code class="are-val-preview" :title="fmtVal(selected.value)">→ {{ fmtVal(selected.value) }}</code>
        </div>
      </div>

      <!-- 期望配对(asserts)— 继承 v2 段 -->
      <div class="are-sec">
        <h4>期望配对(asserts)<span class="are-sec-hint">override 覆写既有断言(匹配键 = 步骤+target)/ append 追加</span></h4>
        <div v-if="!selected.asserts.length" class="are-empty">没有期望配对</div>
        <table v-else class="are-asserts">
          <thead>
            <tr><th>步骤</th><th>target</th><th>op</th><th>expected</th><th>mode</th><th /></tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in selected.asserts" :key="`${a.stepIndex}:${a.target}:${i}`">
              <td>{{ stepLabels[a.stepIndex] ?? `步骤${a.stepIndex + 1}` }}</td>
              <td><code>{{ a.target }}</code></td>
              <td>{{ a.operator }}</td>
              <td><code class="are-val">{{ fmtVal(a.expected) }}</code></td>
              <td><span class="are-mode" :class="`m-${a.mode}`">{{ a.mode }}</span></td>
              <td><button type="button" class="are-del" title="删除期望" @click="selected.asserts.splice(i, 1)">×</button></td>
            </tr>
          </tbody>
        </table>
        <div class="are-pending are-pending-assert">
          <el-select
            :model-value="pendingAssert.stepIndex"
            size="small"
            class="are-step-select"
            @update:model-value="(v: any) => (pendingAssert.stepIndex = Number(v))"
          >
            <el-option v-for="(label, i) in stepLabels" :key="`sa:${i}`" :value="i" :label="label" />
          </el-select>
          <el-input v-model="pendingAssert.target" size="small" class="are-target-input" placeholder="target($.response_body.code)" />
          <el-select v-model="pendingAssert.operator" size="small" class="are-op-select" filterable allow-create>
            <el-option v-for="op in OPERATORS" :key="op" :value="op" :label="op" />
          </el-select>
          <el-input v-model="pendingAssert.expected" size="small" class="are-exp-input" placeholder="期望值" />
          <el-select v-model="pendingAssert.mode" size="small" class="are-mode-select">
            <el-option value="override" label="override" />
            <el-option value="append" label="append" />
          </el-select>
          <button type="button" class="are-add-assert" @click="addAssert">+ 添加期望</button>
        </div>
      </div>
    </div>
    <div v-else-if="selected && isLegacyEntry(selected)" class="are-empty are-select-hint">旧版条目(v2 形状)— 不可编辑,请在编排器重新标记创建</div>
    <div v-else-if="draft" class="are-empty are-select-hint">点击上方条目查看详情</div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionEntry, AssertionRegistry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { bodyPathSetOf, genEntryId, isDeadEntry, normalizeRegistry, registryIssues } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { composerUrl } from '@/utils/links'
import { showError } from '@/utils/errorFallback'

const route = useRoute()
const router = useRouter()
const scenarioId = route.params.scenarioId as string

const draft = ref<ScenarioDraft | null>(null)
const registry = ref<AssertionRegistry>({ entries: [] })
const selectedId = ref<string | null>(null)
const selected = computed(() => registry.value.entries.find((e) => e.id === selectedId.value) ?? null)
const stepCount = computed(() => draft.value?.definition.steps?.length ?? 0)
const steps = computed(() => (draft.value?.definition.steps ?? []) as Array<Record<string, unknown>>)
const stepLabels = computed(() =>
  steps.value.map((s, i) => `${i + 1}·${(s as any)?.description || `Step ${i + 1}`}`),
)
const scenarioName = computed(() => draft.value?.definition?.meta?.name || scenarioId)

/** steps[si].request.body 叶子集合(悬空检测 path 维度,spec v3 §2) */
function bodyPathsOfStep(si: number): ReadonlySet<string> {
  return bodyPathSetOf(fieldPathsOf(steps.value[si] as any))
}
/** steps[si].strategy 的 assertion target 集合(悬空检测 override 维度) */
function assertTargetsOf(si: number): ReadonlySet<string> {
  const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
  return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadOf = (e: AssertionEntry | LegacyAssertionEntry) =>
  isDeadEntry(e, stepCount.value, bodyPathsOfStep, assertTargetsOf)
const deadCount = computed(() => registry.value.entries.filter(deadOf).length)

/** 旧版条目不可选(不可编辑,spec v3 §8) */
function selectEntry(e: AssertionEntry | LegacyAssertionEntry) {
  if (isLegacyEntry(e)) return
  selectedId.value = e.id
}

/** 悬空原因摘要(title 展示):registryIssues 人话投影 */
function issueSummary(e: AssertionEntry | LegacyAssertionEntry): string {
  if (isLegacyEntry(e)) return '旧版条目(v2 形状),请在编排器重新标记创建'
  return registryIssues(e, stepCount.value, bodyPathsOfStep, assertTargetsOf)
    .map((iss) => {
      if (iss.kind === 'step-oob') return `步骤${iss.stepIndex + 1} 越界(场景共 ${stepCount.value} 步)`
      if (iss.kind === 'path-unresolvable') return `步骤${iss.stepIndex + 1} body 无字段 ${iss.jsonpath}`
      return `步骤${iss.stepIndex + 1} 无既有断言 ${iss.target}(override 无匹配)`
    })
    .join('; ')
}

/** 值摘要(列表展示) */
function valueSummary(e: AssertionEntry | LegacyAssertionEntry): string {
  if (isLegacyEntry(e)) return '—'
  return fmtVal(e.value) || '—'
}
function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}

// ── value 类型化编辑(str/num/bool/json,spec v3 §2)─────────────────
type ValKind = 'str' | 'num' | 'bool' | 'json'
/** 按字段当前字面量类型还原编辑形态 */
function kindOf(v: unknown): ValKind {
  if (typeof v === 'number') return 'num'
  if (typeof v === 'boolean') return 'bool'
  if (v !== null && typeof v === 'object') return 'json'
  return 'str'
}
function tryJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}
const valueDraft = ref<{ kind: ValKind; text: string; bool: boolean }>({ kind: 'str', text: '', bool: false })
watch(selectedId, () => {
  const e = selected.value
  if (!e || isLegacyEntry(e)) return
  valueDraft.value = { kind: kindOf(e.value), text: fmtVal(e.value), bool: e.value === true }
})
/** 落回条目:str 原样 / num Number(非数回落原串)/ bool 直取 / json parse 失败回落原串 */
function applyValue() {
  const e = selected.value
  if (!e || isLegacyEntry(e)) return
  const d = valueDraft.value
  e.value = d.kind === 'num'
    ? (Number.isFinite(Number(d.text)) ? Number(d.text) : d.text)
    : d.kind === 'bool' ? d.bool
    : d.kind === 'json' ? tryJson(d.text)
    : d.text
}
/** 切类型立即按新形态落值(编辑器随时可切回原类型) */
function onKindChange() {
  applyValue()
}

/** 手工新建暂存:步骤 + jsonpath(path 是注入地址,不预设模板化) */
const pendingPath = ref({ stepIndex: 0, jsonpath: '' })
/** asserts 行编辑暂存(mode 字符串形态,入条目时收窄) */
const pendingAssert = ref({ stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'override' as string })
const OPERATORS = ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains', 'exists']

const saving = ref(false)

onMounted(async () => {
  try {
    draft.value = await getScenarioDraft(scenarioId)
    // 归一:旧场景 draft 该键经后端 default 补成 {}(truthy,?? 兜不住)
    registry.value = normalizeRegistry(draft.value.assertion_registry)
  } catch (e) {
    showError('加载', e)
  }
})

function addEntry() {
  if (!pendingPath.value.jsonpath.startsWith('$')) {
    ElMessage.warning('jsonpath 需以 $ 开头(例:$.amount)')
    return
  }
  const e: AssertionEntry = {
    id: genEntryId(),
    name: `偏离 ${registry.value.entries.length + 1}`,
    path: {
      stepIndex: pendingPath.value.stepIndex,
      source: 'body',
      jsonpath: pendingPath.value.jsonpath,
    },
    value: '',
    asserts: [],
  }
  registry.value.entries.push(e)
  selectedId.value = e.id
  pendingPath.value = { stepIndex: pendingPath.value.stepIndex, jsonpath: '' }
}
function removeEntry(id: string) {
  registry.value.entries = registry.value.entries.filter((e) => e.id !== id)
  if (selectedId.value === id) selectedId.value = null
}
function addAssert() {
  if (!selected.value || isLegacyEntry(selected.value) || !pendingAssert.value.target) return
  selected.value.asserts.push({
    stepIndex: pendingAssert.value.stepIndex,
    target: pendingAssert.value.target,
    operator: pendingAssert.value.operator,
    expected: pendingAssert.value.expected,
    mode: pendingAssert.value.mode === 'append' ? 'append' : 'override',
  })
}
/** path ↗:跳编排器画布聚焦该步骤(与 DataSetEditor jumpToRef 同契约) */
function jumpToAnchor(si: number) {
  router.push({ path: `/composer/${encodeURIComponent(scenarioId)}`, query: { step: '4', focusStep: String(si) } })
}
/** 整体 PUT — 只动 assertion_registry 键,definition/orchestration 原样透传 */
async function save() {
  if (!draft.value || saving.value) return
  saving.value = true
  try {
    await updateScenario(scenarioId, { ...draft.value, assertion_registry: registry.value })
    ElMessage.success('断言管理已保存')
  } catch (e) {
    showError('保存', e)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* ── v2 样式基座全量继承(类名未变),新增三类 ── */
.are-new-bar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
}
.are-path-input { width: 260px; }
.are-legacy-mark {
  font-size: 10px; font-weight: 700; color: #64748b;
  background: #f1f5f9; border-radius: 3px; padding: 1px 5px;
}
.are-row.are-legacy { opacity: .55; }
.are-value-edit { display: flex; align-items: center; gap: 8px; }
.are-kind-select { width: 90px; }
.are-val-preview {
  font-family: var(--font-mono); font-size: 11px; color: #4338ca;
  background: #eef2ff; border-radius: 3px; padding: 1px 6px;
}
</style>
```

(注:v2 的其余样式类 `.are-editor/.page-header/.are-list-card/.are-row/.are-anchor/.are-dead-mark/.are-asserts/.are-mode` 等原样保留在 style 块中 — 上块为「新增」,实施时与 v2 样式合并为同一 scoped style,勿删既有类。)

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: PASS(4 用例)。

- [ ] **Step 5: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/views/AssertionRegistryEditor.vue src/gimbal-platform/frontend/src/views/__tests__/AssertionRegistryEditor.test.ts && git commit -m "feat(assertion): 编辑器重铸 — path/value/asserts 三元组 + value 类型化编辑 + 旧版条目灰显不可选

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: Canvas/FieldForm 标记改造 + CaseComposer 装配

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`(用户 WIP — 只加必要 hunk:emit 类型 + onRegistryMenu 去 guard + TPL_FULL_RE import 删)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(import / emit 类型 / onRegistryMark 三 hunk)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(dead 计算 body 维度 + onRegistryAdd 落 v3 条目)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.registry.test.ts`(整体重写 — ANCHOR → MARK,断言 v3 落条目形状)

**Interfaces:**
- Consumes: Task 1 `EntryPath`、`isDeadEntry(e, stepCount, bodyPathsOfStep, assertTargetsOf)`、`bodyPathSetOf`、`genEntryId`;`fieldPathsOf(step)`(utils/dataset-segments)。
- Produces(Task 6/7 消费):Canvas emit 形状 `'registryAdd': [mark: EntryPath & { value: unknown }]`;CaseComposer `deadEntryIds: computed<string[]>`(含 legacy — `isDeadEntry` 对 legacy 恒 true);registry 条目落盘形状 = `AssertionEntry`。

- [ ] **Step 1: 写失败测试**(整文件重写 `src/views/__tests__/CaseComposer.registry.test.ts` — 仅改 MARK 载荷与断言形状,其余 mock 面/骨架逐字保留 v2 版)

文件头注释改为:

```ts
/**
 * CaseComposer — registryAdd 落条目通路(spec v3 §5/Task 5):Canvas
 * emit('registryAdd', mark) → onRegistryAdd 落 registry.entries(path 直取
 * 标记载荷 + value 预填字段当前字面量)+ 显式保存调度(registry 不在
 * dirty watch 源 → 防抖自动 PUT 须携带 assertion_registry,标记不丢)。
 *
 * 终审 F2:loadScenario 的 GET /draft 失败(注册表未水化)→ 本地空
 * registry 不可信 — 保存前重试拉取合并;重试仍失败则中止保存,
 * 绝不带空 assertion_registry 整包 PUT(会把存量条目永久冲掉)。
 */
```

mock 面(vi.mock × executions/auth_sessions/constants/carry/catalog-services/query-views)、`sampleScenario()`、`mountPage()`、beforeEach/afterEach **逐字保留**。改动点:

```ts
describe('CaseComposer — registryAdd 落条目 + 保存调度(spec v3 §5)', () => {
  const MARK = { stepIndex: 0, source: 'body' as const, jsonpath: '$.base_url', value: 'http://x' }

  it('registryAdd → registry.entries 落偏离条目(path/value 直取载荷)→ draft store 同步', async () => {
    const w = await mountPage()
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.exists()).toBe(true)
    canvas.vm.$emit('registryAdd', MARK)
    await nextTick()
    await flushPromises()
    const reg = (useScenarioDraftStore().draft as any).assertion_registry
    expect(reg.entries).toHaveLength(1)
    expect(reg.entries[0].id).toMatch(/^inj-/)
    expect(reg.entries[0].name).toBe('偏离 1')
    expect(reg.entries[0].path).toEqual({ stepIndex: 0, source: 'body', jsonpath: '$.base_url' })
    expect(reg.entries[0].value).toBe('http://x')      // 字段当前字面量预填
    expect(reg.entries[0].asserts).toEqual([])
    w.unmount()
  })

  it('registryAdd 触发防抖自动保存 — PUT 携带 assertion_registry(v3 形状)', async () => {
    const w = await mountPage()
    ;(api.updateScenario as any).mockClear()   // 隔离挂载期噪音
    const canvas = w.findComponent(CaseComposerCanvas)
    canvas.vm.$emit('registryAdd', MARK)
    await nextTick()
    await flushPromises()
    expect(api.updateScenario).not.toHaveBeenCalled()   // 防抖未到不发
    vi.advanceTimersByTime(2500)
    await flushPromises()
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(1)
    const draft = (api.updateScenario as any).mock.calls[0][1]
    expect(draft.assertion_registry.entries).toHaveLength(1)
    expect(draft.assertion_registry.entries[0].path).toEqual({
      stepIndex: 0, source: 'body', jsonpath: '$.base_url',
    })
    expect(draft.assertion_registry.entries[0].value).toBe('http://x')
    w.unmount()
  })
})
```

「存量空注册表形状归一」describe **逐字保留**(配置签入口卡本任务不动 — Task 7 改);「注册表水化失败防擦除(终审 F2)」describe 仅把两处 `ANCHOR` 常量与 `$emit('registryAdd', ANCHOR)` 改为 `MARK`(server 存量条目 fixture 保持 v2 形状不动 — 水化合并按 id 并集,形状无关)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/views/__tests__/CaseComposer.registry.test.ts`
Expected: FAIL — 落条目断言 `path`/`value` 键不存在(旧 onRegistryAdd 产 anchor/injection 形状)。

- [ ] **Step 3: FieldForm 两 hunk(WIP 文件,最小改动)**

hunk A — emit 类型(1021-1026):

```ts
  /**
   * 加入断言管理(spec v3 §5):FAM fieldRegistry 上抛,载荷带字段当前
   * 字面量 value(任意字段可偏离 — path 即地址,不预设模板化,varName
   * 不再采集)。stepIndex 由 Canvas 补。
   */
  'registryMark': [payload: { field: IOFieldBinding; value: unknown }]
```

hunk B — onRegistryMenu 去 guard(1326-1339 替换):

```ts
/**
 * 菜单「加入断言管理」(spec v3 §5):无守卫直通 — 任意字段可偏离
 * (path 即注入地址,与模板化解耦);取值与 onFieldPromote 同源
 * (getValue,body 寻址)作 value 预填。Canvas 组装 path。
 */
function onRegistryMenu(field: IOFieldBinding) {
  emit('registryMark', { field, value: getValue(field) })
  menuField.value = null
}
```

同时删除 `import { TPL_FULL_RE } from '@/utils/dataset-segments'`(920 行,该文件仅 onRegistryMenu 消费;`ElMessage` 若仅此函数使用则同步删 import,先 grep 确认)。`FieldActionMenu.vue` 本任务**零改动**。

- [ ] **Step 4: Canvas 三 hunk**

hunk A — import(582):`import type { AssertionAnchor } from '@/types/assertion-registry'` 改 `import type { EntryPath } from '@/types/assertion-registry'`。

hunk B — emit 类型(600-602):

```ts
  /** 加入断言管理标记(spec v3 §5):FieldForm registryMark → path 组装
   *  (+ 字段当前字面量 value 预填)上抛,CaseComposer 落 registry.entries
   *  (registry 住在编排器层) */
  'registryAdd': [mark: EntryPath & { value: unknown }]
```

hunk C — onRegistryMark(976-988 替换):

```ts
/**
 * 菜单"加入断言管理"(spec v3 §5):FieldForm registryMark — stepIndex
 * 由本层补(FieldForm 无步骤上下文),jsonpath = 字段实例路径;value =
 * 字段当前字面量(条目 value 预填,编辑器可改)。v1 请求体标记只产
 * source='body'(headers = 协议位,spec v3 §1 裁定 9)。
 */
function onRegistryMark(p: { field: IOFieldBinding; value: unknown }) {
  emit('registryAdd', {
    stepIndex: activeStepIdx.value,
    source: 'body',
    jsonpath: p.field.path,
    value: p.value,
  })
}
```

- [ ] **Step 5: CaseComposer 两 hunk**

hunk A — dead 计算(507-518 替换;import 加 `import { fieldPathsOf } from '@/utils/dataset-segments'`,`AssertionAnchor` 类型引用改 `EntryPath`):

```ts
/** 死条目(悬空)id 集(spec v3 §2):bodyPathsOfStep 与编辑器同构
 *  (AssertionRegistryEditor)— RunDialog 注入区据此禁选;legacy 条目
 *  isDeadEntry 恒 true,一并计入。 */
function registryBodyPathsOf(si: number): ReadonlySet<string> {
  return bodyPathSetOf(fieldPathsOf(steps.value[si] as any))
}
function registryAssertTargetsOf(si: number): ReadonlySet<string> {
  const st = steps.value[si]?.strategy ?? []
  return new Set(st.filter((x) => x.kind === 'assertion').map((x) => x.target))
}
const deadEntryIds = computed(() =>
  registry.value.entries
    .filter((e) => isDeadEntry(e, steps.value.length, registryBodyPathsOf, registryAssertTargetsOf))
    .map((e) => e.id))
```

(`registryVarNames` computed 删除 — 唯一消费方即旧 dead 计算;spec §7 退场项。)

hunk B — onRegistryAdd(529-553 替换):

```ts
/**
 * Canvas「加入断言管理」标记(spec v3 §5):落 registry 条目 — path 直取
 * 标记载荷,value 预填字段当前字面量,asserts 留空由编辑器补。registry
 * 不在 dirty watch 源(watch [definition, orchestration])→ 显式走与
 * 单字段编辑同款保存调度:置 dirty + 防抖自动保存,标记不丢。
 */
function onRegistryAdd(mark: EntryPath & { value: unknown }) {
  registry.value.entries.push({
    id: genEntryId(),
    name: `偏离 ${registry.value.entries.length + 1}`,
    path: { stepIndex: mark.stepIndex, source: mark.source, jsonpath: mark.jsonpath },
    value: mark.value,
    asserts: [],
  })
  ElMessage.success({ message: '已加入断言管理(偏离值预填字段当前值,请到断言管理编辑)', duration: 4000 })
  // 与 watch([definition, orchestration]) 体同款(dirty 标记 + 防抖调度)
  dirty.value = true
  if (saveState.value === 'saving') {
    editsDuringSave = true
  } else {
    saveState.value = 'dirty'
  }
  scheduleAutoSave()
}
```

(Config 挂载点 `:assertion-count="registry.entries.length"` 本任务不动 — Task 7 改展示列表。)

- [ ] **Step 6: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/views/__tests__/CaseComposer.registry.test.ts`
Expected: PASS(4 用例:落条目 / 自动保存 / 空注册表归一 / F2 ×2)。

- [ ] **Step 7: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/components/composer/FieldForm.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.registry.test.ts && git commit -m "feat(assertion): 编排标记去模板化守卫 — path+value 载荷直落 v3 条目,dead 计算改 body 字段树维度

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: RunDialog 交叉语义 + dataSetSelection + 预填 + RunPanelHost 抽出(spec T7)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`(ServiceBinding 后加 DataSetSelection/RunPreset;RunScheme/RunRequest 加键)
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunDialog.vue`(selection 状态机/交叉总量/confirm 载荷/preset 预填/legacy 禁选)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(preset 管道 + onRunConfirm 签名跟随)
- Create: `src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/RunDialog.injection.test.ts`(整体重写)+ `src/gimbal-platform/frontend/src/components/composer/__tests__/RunPanelHost.test.ts`(新建)

**Interfaces:**
- Consumes: Task 1 `isLegacyEntry`/`isDeadEntry`/`bodyPathSetOf`/`normalizeRegistry`;Task 3 的 wire 键 `dataSetSelection: [{datasetId, rowIndexes?}]`;`fieldPathsOf(step)`(utils/dataset-segments)。
- Produces(Task 7 消费,签名逐字):
  - `api/scenario-composer.ts`: `interface DataSetSelection { datasetId: string; rowIndexes?: number[] }`;`interface RunPreset { dataSetSelection?: DataSetSelection[]; injectionEntryIds?: string[] }`;`RunScheme.dataSetSelection?: DataSetSelection[]`;`RunRequest.dataSetSelection?: DataSetSelection[]`。
  - `RunDialog.vue` emits: `confirm: [dataSetSelection: DataSetSelection[], opts: {...原五键}]`;props 加 `preset?: RunPreset | null`;props `assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>`。
  - `RunPanelHost.vue`: props `{ scenarioId: string; preset?: RunPreset | null }`,emits `{ close: [] }` — 自取数装配 RunDialog,confirm → `runScenario` → `router.push(executionUrl(resp.executionId))`。

- [ ] **Step 1: 写失败测试**(整文件重写 `RunDialog.injection.test.ts`)

```ts
/**
 * RunDialog — 注入条目 × 数据集交叉选择(spec v3 §4/§6)
 *
 * - INJ-1 条目区渲染:悬空禁选「悬空 — 不可选」;旧版条目(v2 形状)
 *   禁选「旧版条目 — 不可选」(isLegacyEntry)
 * - INJ-2 交叉总量:基线 × 1 条目 = 1(条目空 = [无注入] 单元,不叠基线);
 *   confirm 首参 = dataSetSelection(空选 = [])
 *   INJ-2b 数据集分支:3 行 × 1 条目 = 3(交叉,非并集 4)
 *   INJ-2c 合并态:(2+3 行)× 2 条目 × nRuns=2 = 20
 * - INJ-3 方案回填链:saveScheme 快照携带 dataSetSelection + injectionEntryIds
 *   → 重选方案 → selection/injectionIds 回填;INJ-3b/3c 降级 + 过滤
 * - INJ-4 preset 预填(spec v3 §6):dataSetSelection 行级段 + 条目预勾
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import RunDialog from '../RunDialog.vue'
import type { RunScheme } from '@/api/scenario-composer'

const ENTRIES = [
  { id: 'inj-1', name: '金额为负',
    path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
  { id: 'inj-dead', name: '死条目',
    path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
  { id: 'inj-old', name: '旧版条目',
    anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
] as any[]

function mountDialog(over: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: {
      visible: true, scenario: { meta: { scenarioId: 'sc-1', name: 's' }, stepCount: 0 },
      dataSets: [], running: false, schemes: [],
      lastRunOverlay: null,
      serviceRows: [], authOptions: [], stepOrchestrationNames: [],
      assertionEntries: ENTRIES,
      deadEntryIds: ['inj-dead', 'inj-old'],
      ...over,
    } as any,
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

beforeEach(() => setActivePinia(createPinia()))

describe('RunDialog — 注入条目 × 数据集交叉(spec v3 §4/§6)', () => {
  it('INJ-1: 条目区渲染 + 悬空/旧版条目禁选', async () => {
    const w = mountDialog()
    await flushPromises()
    const boxes = w.findAll('.rd-injection .el-checkbox')
    expect(boxes.length).toBe(3)
    expect(boxes[1].find('input').attributes('disabled')).toBeDefined()   // 悬空
    expect(boxes[2].find('input').attributes('disabled')).toBeDefined()   // 旧版(v2 形状)
    expect(boxes[2].text()).toContain('旧版条目 — 不可选')
    w.unmount()
  })

  it('INJ-2: 勾选条目 → confirm 首参 dataSetSelection + 载荷含 injectionEntryIds;交叉总量', async () => {
    const w = mountDialog()
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    // 无数据集 = R={[基线]} × E={inj-1} = 1 case(交叉:条目空缺不叠基线)
    expect(w.find('.summary-chip.total').text()).toBe('1 次运行')
    expect(w.text()).not.toContain('基线 ×1')
    await w.findAll('button').find((b) => b.text().includes('发起运行'))!.trigger('click')
    const emitted = w.emitted('confirm')
    expect(emitted).toBeTruthy()
    const [selection, opts] = emitted![0] as [any[], any]
    expect(selection).toEqual([])                              // 空选 = 基线(dataSetSelection 空)
    expect(opts.injectionEntryIds).toEqual(['inj-1'])
    w.unmount()
  })

  it('INJ-3: 存方案快照携带 dataSetSelection/injectionEntryIds → 重选回填', async () => {
    // 半程:默认全选 ds-1 + 勾 inj-1 存方案
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 2, preview: [] }],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    ;(w.vm as any).schemeNameDraft = '异常回归'
    await flushPromises()
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const saved = w.emitted('saveScheme')
    expect(saved).toBeTruthy()
    const scheme = saved![0][0] as RunScheme
    expect(scheme.injectionEntryIds).toEqual(['inj-1'])
    expect(scheme.dataSetSelection).toEqual([{ datasetId: 'ds-1' }])
    expect(scheme.dataSetIds).toEqual(['ds-1'])                 // 兼容键同存(旧读方)
    w.unmount()

    // 回程:重挂载 → 选中该方案 → selection/injectionIds 回填
    const w2 = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 2, preview: [] }],
      schemes: [scheme],
    })
    await flushPromises()
    ;(w2.vm as any).selectedScheme = '异常回归'
    await flushPromises()
    expect((w2.vm as any).injectionIds).toEqual(['inj-1'])
    expect((w2.vm as any).selectedDatasetIds).toEqual(['ds-1'])
    w2.unmount()
  })

  it('INJ-3b: 方案引用已删条目 → 标注配置已失效 + 回填静默跳过', async () => {
    const dangling = {
      name: '旧方案', dataSetIds: [], injectionEntryIds: ['inj-1', 'inj-gone'],
      serviceBindings: {},
    } as RunScheme
    const w = mountDialog({ schemes: [dangling] })
    await flushPromises()
    expect(w.text()).toContain('旧方案 · 配置已失效')
    ;(w.vm as any).selectedScheme = '旧方案'
    await flushPromises()
    expect((w.vm as any).injectionIds).toEqual(['inj-1'])   // 已删项静默跳过,不报废
    w.unmount()
  })

  it('INJ-3c: 方案引用死而现存条目 → 同样降级标注 + 回填被过滤', async () => {
    const deadRef = {
      name: '悬空方案', dataSetIds: [], injectionEntryIds: ['inj-1', 'inj-dead'],
      serviceBindings: {},
    } as RunScheme
    const w = mountDialog({ schemes: [deadRef] })
    await flushPromises()
    expect(w.text()).toContain('悬空方案 · 配置已失效')
    ;(w.vm as any).selectedScheme = '悬空方案'
    await flushPromises()
    expect((w.vm as any).injectionIds).toEqual(['inj-1'])   // 死条目不可回填勾选
    w.unmount()
  })

  it('INJ-2b: 交叉总量数据集分支 = Σrows × 条目数 × nRuns', async () => {
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 3, preview: [] }],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    // 3 行 × 1 条目 × nRuns=1 = 3(交叉,非 v2 并集的 3+1=4)
    expect(w.find('.summary-chip.total').text()).toBe('3 次运行')
    w.unmount()
  })

  it('INJ-2c: 合并态 (Σrows) × 条目数 × nRuns>1,无基线加算', async () => {
    const w = mountDialog({
      dataSets: [
        { datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 2, preview: [] },
        { datasetId: 'ds-2', scenarioId: 'sc-1', name: 'B', rowCount: 3, preview: [] },
      ],
      assertionEntries: [
        { id: 'inj-a', name: '金额为负', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
        { id: 'inj-b', name: '超时偏离', path: { stepIndex: 0, source: 'body', jsonpath: '$.timeout' }, value: 0, asserts: [] },
      ] as any[],
      deadEntryIds: [],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-a', 'inj-b']
    await w.findAll('input[type="number"]')[0].setValue('2')
    await flushPromises()
    // (2+3) 行 × 2 条目 × nRuns=2 = 20(交叉矩阵)
    expect(w.find('.summary-chip.total').text()).toBe('20 次运行')
    expect(w.text()).not.toContain('基线 ×1')
    w.unmount()
  })

  it('INJ-4: preset 预填 — 行级段 + 条目预勾(数据集入口/「加入本次执行」)', async () => {
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 3, preview: [] }],
      preset: {
        dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }],
        injectionEntryIds: ['inj-1'],
      },
    })
    await flushPromises()
    expect((w.vm as any).selectedDatasetIds).toEqual(['ds-1'])
    expect((w.vm as any).selection).toEqual([{ datasetId: 'ds-1', rowIndexes: [1] }])
    expect((w.vm as any).injectionIds).toEqual(['inj-1'])
    // 1 行 × 1 条目 × nRuns=1 = 1
    expect(w.find('.summary-chip.total').text()).toBe('1 次运行')
    w.unmount()
  })
})
```

- [ ] **Step 2: 写失败测试**(新建 `RunPanelHost.test.ts`)

```ts
/**
 * RunPanelHost — 运行面板宿主(spec v3 §6):两个执行入口共用的装配层。
 * - RH-1 自取数装配:getScenario + getScenarioDraft + listDataSets → RunDialog
 *   挂载,assertionEntries/deadEntryIds(含 legacy)透传
 * - RH-2 confirm → runScenario(dataSetIds 派生 + dataSetSelection 权威键)
 *   → 跳执行详情
 * - RH-3 saveScheme → putRunSchemes(scenarioId, 整表)
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock.push }),
  useRoute: () => ({ params: { scenarioId: 'sc-host' } }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))
vi.mock('@/api/auth_sessions', () => ({ list: async () => [{ alias: 'owner-1' }] }))

import * as api from '@/api/scenario-composer'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import RunDialog from '@/components/composer/RunDialog.vue'
import { executionUrl } from '@/utils/links'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-host', meta: { name: 'host' },
  config: { vars: { amount: 100 }, services: { 'fin.test': 'http://fin' }, users: {} },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {} },
      request: { kind: 'request', body: {} }, strategy: [] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-live', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
  ],
}
const DRAFT = {
  definition: DEF,
  orchestration: { steps: [{ name: '下单', enabled: true }, { name: '查单', enabled: true }], resourceMeta: {}, runSchemes: [] },
  assertion_registry: REG,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenario').mockResolvedValue(
    { meta: { scenarioId: 'sc-host', name: 'host' }, steps: DEF.steps, stepCount: 2 } as any)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'listDataSets').mockResolvedValue([
    { datasetId: 'ds-1', scenarioId: 'sc-host', name: 'A', rowCount: 2, preview: [] }] as any)
  vi.spyOn(api, 'runScenario').mockResolvedValue({ runId: 'r-1', executionId: 7 } as any)
  vi.spyOn(api, 'putRunSchemes').mockResolvedValue([] as any)
  pushMock.push.mockReset()
})
afterEach(() => { vi.restoreAllMocks() })

async function mountHost(props: Record<string, unknown> = {}) {
  const w = mount(RunPanelHost, {
    props: { scenarioId: 'sc-host', ...props } as any,
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
  await flushPromises()
  return w
}

it('RH-1: 自取数装配 — RunDialog 挂载 + 条目/死条目透传(legacy 入 deadEntryIds)', async () => {
  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(dlg.exists()).toBe(true)
  expect(dlg.props('assertionEntries')).toHaveLength(2)
  expect(dlg.props('deadEntryIds')).toEqual(['inj-old'])   // legacy 恒死(isDeadEntry)
  expect(dlg.props('preset')).toBeNull()
  expect(dlg.props('serviceRows')).toEqual([{ service: 'fin.test', declaredUrl: 'http://fin' }])
  expect(dlg.props('stepOrchestrationNames')).toEqual(['下单', '查单'])
  w.unmount()
})

it('RH-2: confirm → runScenario 携带 dataSetSelection 权威键 → 跳执行详情', async () => {
  const w = await mountHost({
    preset: { dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }], injectionEntryIds: ['inj-live'] },
  })
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('preset')).toEqual({
    dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }],
    injectionEntryIds: ['inj-live'],
  })
  dlg.vm.$emit('confirm', [{ datasetId: 'ds-1', rowIndexes: [1] }], { injectionEntryIds: ['inj-live'] })
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.scenarioId).toBe('sc-host')
  expect(body.dataSetIds).toEqual(['ds-1'])
  expect(body.dataSetSelection).toEqual([{ datasetId: 'ds-1', rowIndexes: [1] }])
  expect(body.injectionEntryIds).toEqual(['inj-live'])
  expect(w.emitted('close')).toBeTruthy()
  expect(pushMock.push).toHaveBeenCalledWith(executionUrl(7))
  w.unmount()
})

it('RH-3: saveScheme → putRunSchemes(scenarioId, 整表含新方案)', async () => {
  const w = await mountHost()
  const scheme = { name: '回归', dataSetIds: [], dataSetSelection: [], injectionEntryIds: ['inj-live'], serviceBindings: {} }
  w.findComponent(RunDialog).vm.$emit('saveScheme', scheme)
  await flushPromises()
  expect(api.putRunSchemes).toHaveBeenCalledWith('sc-host', [scheme])
  w.unmount()
})
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/RunDialog.injection.test.ts src/components/composer/__tests__/RunPanelHost.test.ts`
Expected: FAIL — RunDialog.injection(旧 v2 形状断言/无 preset prop/并集总量 4 与 14);RunPanelHost(组件不存在,import 报错)。

- [ ] **Step 4: api 类型键(`api/scenario-composer.ts`)**

在 `ServiceBinding` 接口(118-121)之后插入:

```ts
/** 行级数据集选择(spec v3 §4):datasetId + rowIndexes(0-based,与编辑器
 *  行号一致;缺省/空 = 整库)。RunRequest/RunScheme 的权威选择键;
 *  旧 dataSetIds 保留为兼容读(两键同发本键优先)。 */
export interface DataSetSelection {
  datasetId: string
  rowIndexes?: number[]
}

/** 运行面板预填(spec v3 §6):数据集入口(整库/单行)与配置签「加入本次
 *  执行」传入;RunDialog 挂载时按此预勾(已删/悬空条目静默过滤)。 */
export interface RunPreset {
  dataSetSelection?: DataSetSelection[]
  injectionEntryIds?: string[]
}
```

`RunScheme` 的 `injectionEntryIds?: string[]` 字段后加:

```ts
  /** 行级数据集选择快照(spec v3 §4)— 权威键;dataSetIds 同存供旧读方 */
  dataSetSelection?: DataSetSelection[]
```

`RunRequest` 的 `dataSetIds: string[]` 字段后加:

```ts
  /** 行级数据集选择(spec v3 §4)— 权威键;两键同发时本键优先,
   *  dataSetIds 忽略(兼容读保留) */
  dataSetSelection?: DataSetSelection[]
```

- [ ] **Step 5: RunDialog 改造(七处 hunk)**

hunk A — imports(249-251):

```ts
import type { DataSetSelection, RunPreset, ServiceBinding, RunScheme, RunOverlay } from '@/api/scenario-composer'
import type { Scenario, DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
```

hunk B — props(274-277 断言段 + defaults):`assertionEntries?: AssertionEntry[]` 改 `assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>`;追加 prop 与默认值:

```ts
  /** 运行面板预填(spec v3 §6):数据集入口/「加入本次执行」传入;
   *  挂载时按此预勾(已删/悬空条目静默过滤),null = 无预填 */
  preset?: RunPreset | null
```

(defaults 对象加 `preset: null`。)emits `confirm` 首参类型 `dataSetIds: string[]` 改 `dataSetSelection: DataSetSelection[]`。

hunk C — 数据集状态机(314-334 整段替换):

```ts
// ── 数据集行级选择(spec v3 §4):dataSetSelection 权威形状 ──────────
const selection = ref<DataSetSelection[]>([])
/** 勾选态数据集 id 集(同库多段去重;整库切换见 toggleDataset) */
const selectedDatasetIds = computed(() => [...new Set(selection.value.map((s) => s.datasetId))])
/** 初始选择:preset 携带选择时按现存数据集过滤收窄;否则全选(整库) */
function defaultSelection(): DataSetSelection[] {
  if (props.preset?.dataSetSelection?.length) {
    const exists = new Set(props.dataSets.map((d) => d.datasetId))
    return props.preset.dataSetSelection.filter((s) => exists.has(s.datasetId))
  }
  return props.dataSets.map((d) => ({ datasetId: d.datasetId }))
}
/** 勾/取消一库(整库段,不带 rowIndexes;行级选择由 preset 预填) */
function toggleDataset(id: string, on: boolean) {
  selection.value = on
    ? [...selection.value, { datasetId: id }]
    : selection.value.filter((s) => s.datasetId !== id)
}
/** 基线 ↔ 数据集互斥(D12):有任一库勾选 = 非基线;全空 = 基线 */
function toggleBaseline() {
  selection.value = selectedDatasetIds.value.length ? [] : defaultSelection()
}
```

(原 `watch(() => props.dataSets, ...)` 与 `watch(selectedDatasets, ...)` 两段删除 — 时机并入下方合并 watch。)

hunk D — 注入段之后(`liveEntryIds` computed 之后)插合并 immediate watch(**必须在 injectionIds/liveEntryIds 声明之后** — immediate:true 在 setup 期即执行,前置会 TDZ):

```ts
// dataSets/preset 首达(spec v3 §6):选择与注入预填一次成型。RunDialog
// 每次 v-if 重挂载,无中途 preset 变更场景;watch 双源只覆盖异步取数
// 先后(dataSets 晚于 preset 到达时按 preset 收窄)。
watch([() => props.dataSets, () => props.preset], () => {
  selection.value = (props.dataSets.length || props.preset?.dataSetSelection?.length)
    ? defaultSelection()
    : []
  injectionIds.value = (props.preset?.injectionEntryIds ?? [])
    .filter((id) => liveEntryIds.value.has(id))
}, { immediate: true })
```

hunk E — 模板数据集区(50 与 71-93):

```html
              <label class="ds-tile baseline" :class="{ active: selectedDatasetIds.length === 0 }">
                <input
                  type="checkbox"
                  data-test="baseline"
                  :checked="selectedDatasetIds.length === 0"
                  @change="toggleBaseline"
                />
```

```html
              <label
                v-for="ds in dataSets"
                :key="ds.datasetId"
                class="ds-tile"
                :class="{ active: selectedDatasetIds.includes(ds.datasetId) }"
              >
                <input
                  type="checkbox"
                  :value="ds.datasetId"
                  :checked="selectedDatasetIds.includes(ds.datasetId)"
                  @change="toggleDataset(ds.datasetId, ($event.target as HTMLInputElement).checked)"
                />
```

注入区(96-106)el-checkbox 改:

```html
              <el-checkbox v-for="e in assertionEntries" :key="e.id" :value="e.id"
                :disabled="isLegacyEntry(e) || deadIds.has(e.id)">
                {{ e.name }}
                <span v-if="isLegacyEntry(e)" class="rd-dead-note">旧版条目 — 不可选</span>
                <span v-else-if="deadIds.has(e.id)" class="rd-dead-note">悬空 — 不可选</span>
              </el-checkbox>
```

(段注释改「断言注入条目(spec v3 §4 异常组):与数据集行交叉生成 case(N 行 × M 条目);悬空/旧版条目禁选 — 死判定由宿主预计算经 deadEntryIds 传入」。)

footer chips(205-214):

```html
            <span
              v-if="selectedDatasetIds.length === 0 && !injectionIds.length"
              class="summary-chip"
            >基线 ×1</span>
            <span v-if="selectedDatasetIds.length" class="summary-chip">
              {{ selectedDatasetIds.length }} 数据集
            </span>
```

hunk F — 方案链:356-361 `schemeDegraded` 的 `s.dataSetIds.some(...)` 前加 helper 并替换:

```ts
/** 方案引用的数据集 id 集 = dataSetSelection ∪ 兼容 dataSetIds(spec v3 §4 双键) */
function schemeIdsOf(s: RunScheme): string[] {
  return [...new Set([...(s.dataSetSelection ?? []).map((x) => x.datasetId), ...s.dataSetIds])]
}
```

(`.filter((s) => schemeIdsOf(s).some((id) => !props.dataSets.some((d) => d.datasetId === id)) || ...)`)

watch(selectedScheme) 回填(457-458)替换:

```ts
  // 选择回填(spec v3 §4):dataSetSelection 优先;旧方案无此键回落
  // dataSetIds 兼容读(映射为整库段)。已删数据集静默跳过 = 降级不报废。
  const selFromSrc = (src as { dataSetSelection?: DataSetSelection[] } | undefined | null)?.dataSetSelection
  selection.value = selFromSrc?.length
    ? selFromSrc
        .filter((s) => props.dataSets.some((d) => d.datasetId === s.datasetId))
        .map((s) => ({ ...s }))
    : (src?.dataSetIds ?? []).filter((id) =>
        props.dataSets.some((d) => d.datasetId === id)).map((id) => ({ datasetId: id }))
```

totalRuns(505-519)整段替换:

```ts
const totalRuns = computed(() => {
  // 交叉矩阵(spec v3 §4):Σ(选中行数) × max(选中条目数, 1) × nRuns —
  // 与后端 dispatch 同公式。行数:段带 rowIndexes 按段计,缺省段 = 整库
  // (空库按 1 隐式行);全空(基线)= 1。条目空 = [无注入] 单元,不叠基线。
  const rows = selection.value.length
    ? selection.value.reduce((sum, s) => {
        if (s.rowIndexes?.length) return sum + s.rowIndexes.length
        const ds = props.dataSets.find((d) => d.datasetId === s.datasetId)
        return sum + Math.max(ds?.rowCount ?? 0, 1)
      }, 0)
    : 1
  return rows * Math.max(injectionIds.value.length, 1) * (nRuns.value || 1)
})
```

hunk G — onConfirm(536)与 onSaveScheme(556-563):

```ts
  emit('confirm', selection.value.map((s) => ({ ...s })), {
```

```ts
  emit('saveScheme', {
    name,
    dataSetIds: [...selectedDatasetIds.value],
    dataSetSelection: selection.value.map((s) => ({ ...s })),
    injectionEntryIds: [...injectionIds.value],
    serviceBindings: explicitServiceBindings(),
    plugins: null,
    logSub: null,
  })
```

- [ ] **Step 6: 新建 `RunPanelHost.vue`**

```vue
<!--
  RunPanelHost.vue — 运行面板宿主(spec v3 §6)

  两个执行入口共用的装配层:数据集入口(测试数据页「运行」/「运行此行」)
  与场景入口同款 RunDialog,场景加载不绑死 CaseComposer。自取数:
  getScenario(展示名/步数)+ getScenarioDraft(definition/
  orchestration.runSchemes/assertion_registry)+ listDataSets + 凭证池。
  dead 计算与 CaseComposer 同构(bodyPathSetOf(fieldPathsOf)维度)。
-->
<template>
  <RunDialog
    :visible="true"
    :scenario="scenario"
    :data-sets="dataSets"
    :running="dispatching"
    :last-run-id="null"
    :last-run-error="lastRunError"
    :schemes="schemes"
    :last-run-overlay="null"
    :service-rows="serviceRows"
    :auth-options="authOptions"
    :step-orchestration-names="stepNames"
    :assertion-entries="registry.entries"
    :dead-entry-ids="deadEntryIds"
    :preset="preset"
    @close="emit('close')"
    @confirm="onConfirm"
    @save-scheme="onSaveScheme"
    @delete-scheme="onDeleteScheme"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import RunDialog from './RunDialog.vue'
import {
  getScenario, getScenarioDraft, listDataSets, putRunSchemes, runScenario,
} from '@/api/scenario-composer'
import type {
  DataSetSelection, RunPreset, RunScheme, ServiceBinding,
} from '@/api/scenario-composer'
import type { DataSetSummary, Scenario } from '@/types/scenario-composer'
import type { AssertionRegistry } from '@/types/assertion-registry'
import { bodyPathSetOf, isDeadEntry, normalizeRegistry } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { list as listAuthSessions } from '@/api/auth_sessions'
import { showError } from '@/utils/errorFallback'
import { executionUrl } from '@/utils/links'

const props = defineProps<{
  /** 目标场景(路由级组件 prop,非响应式路由参数 — 宿主页已持有) */
  scenarioId: string
  /** 预填(spec v3 §6):数据集入口(整库/单行)或「加入本次执行」条目 */
  preset?: RunPreset | null
}>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()

const scenario = ref<Scenario | null>(null)
const draft = ref<Awaited<ReturnType<typeof getScenarioDraft>> | null>(null)
const dataSets = ref<DataSetSummary[]>([])
const authAliases = ref<string[]>([])
const schemes = ref<RunScheme[]>([])
const registry = ref<AssertionRegistry>({ entries: [] })
const dispatching = ref(false)
const lastRunError = ref<string | null>(null)

const steps = computed(() => ((draft.value?.definition.steps ?? []) as any[]))
/** 展示名:平台编排态 orchestration.steps[i].name(plate Step 无 name) */
const stepNames = computed(() =>
  ((draft.value?.orchestration as any)?.steps ?? []).map((s: { name?: string }) => s.name ?? ''))
/** 绑定行 = 声明 ∪ 引用并集(spec D3,与 CaseComposer 同构) */
const serviceRows = computed(() => {
  const declared = (draft.value?.definition.config as { services?: Record<string, unknown> } | undefined)?.services ?? {}
  const rows = new Map<string, string | null>()
  for (const [k, v] of Object.entries(declared)) rows.set(k, typeof v === 'string' ? v : null)
  for (const st of steps.value) {
    const svc = (st as { api?: { service?: string } })?.api?.service
    if (svc && !rows.has(svc)) rows.set(svc, null)
  }
  return [...rows].map(([service, declaredUrl]) => ({ service, declaredUrl }))
})
/** 凭证选项:owner 凭证池 ∪ 场景内置 users 别名(与 CaseComposer 同构) */
const authOptions = computed(() => {
  const users = Object.keys(
    ((draft.value?.definition.config as any)?.users ?? {}) as Record<string, unknown>)
  return [...new Set([...authAliases.value, ...users])]
})
/** dead 计算(spec v3 §2,与 CaseComposer 同构):body 字段树维度 */
function bodyPathsOfStep(si: number): ReadonlySet<string> {
  return bodyPathSetOf(fieldPathsOf(steps.value[si] as any))
}
function assertTargetsOf(si: number): ReadonlySet<string> {
  const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
  return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadEntryIds = computed(() =>
  registry.value.entries
    .filter((e) => isDeadEntry(e, steps.value.length, bodyPathsOfStep, assertTargetsOf))
    .map((e) => e.id))

onMounted(async () => {
  try {
    const [sc, dr, dss] = await Promise.all([
      getScenario(props.scenarioId),
      getScenarioDraft(props.scenarioId),
      listDataSets({ scenarioId: props.scenarioId }),
    ])
    scenario.value = sc
    draft.value = dr
    dataSets.value = dss
    registry.value = normalizeRegistry(dr.assertion_registry)
    schemes.value = ((dr.orchestration as any)?.runSchemes ?? []) as RunScheme[]
  } catch (e) {
    showError('加载运行面板', e)
    return
  }
  try {
    authAliases.value = (await listAuthSessions()).map((s) => s.alias)
  } catch { /* 凭证池不可达不阻塞运行 */ }
})

/** confirm → runScenario(dataSetSelection 权威键)→ 跳执行详情 */
async function onConfirm(
  dataSetSelection: DataSetSelection[],
  opts?: {
    stepTo?: number
    nRuns?: number
    parallel?: number
    serviceBindings?: Record<string, ServiceBinding>
    injectionEntryIds?: string[]
  },
) {
  if (dispatching.value) return
  dispatching.value = true
  lastRunError.value = null
  try {
    const resp = await runScenario({
      scenarioId: props.scenarioId,
      dataSetIds: dataSetSelection.map((s) => s.datasetId),
      ...(dataSetSelection.length ? { dataSetSelection } : {}),
      ...(opts?.stepTo != null ? { stepTo: opts.stepTo } : {}),
      ...(opts?.nRuns && opts.nRuns !== 1 ? { nRuns: opts.nRuns } : {}),
      ...(opts?.parallel && opts.parallel !== 1 ? { parallel: opts.parallel } : {}),
      ...(opts?.serviceBindings && Object.keys(opts.serviceBindings).length
        ? { serviceBindings: opts.serviceBindings } : {}),
      ...(opts?.injectionEntryIds?.length
        ? { injectionEntryIds: opts.injectionEntryIds } : {}),
    })
    ElMessage.success(`运行已发起: ${resp.runId}`)
    emit('close')
    if (resp.executionId != null) router.push(executionUrl(resp.executionId))
    else router.push('/executions')
  } catch (e) {
    lastRunError.value = (e as Error).message
    showError('运行', e)
  } finally {
    dispatching.value = false
  }
}

/** 存/删方案:整表 PUT(Task 10 窄端点),本地 schemes 同步收缩 */
async function onSaveScheme(scheme: RunScheme) {
  try {
    const next = [...schemes.value.filter((s) => s.name !== scheme.name), scheme]
      .sort((a, b) => a.name.localeCompare(b.name))
    await putRunSchemes(props.scenarioId, next)
    schemes.value = next
    ElMessage.success(`方案「${scheme.name}」已保存`)
  } catch (e) {
    showError('保存方案', e)
  }
}
async function onDeleteScheme(name: string) {
  try {
    const next = schemes.value.filter((s) => s.name !== name)
    await putRunSchemes(props.scenarioId, next)
    schemes.value = next
    ElMessage.success(`方案「${name}」已删除`)
  } catch (e) {
    showError('删除方案', e)
  }
}
</script>
```

- [ ] **Step 7: CaseComposer 跟随(三处 hunk)**

hunk A — import(281-283 的 api type import 列表)加 `DataSetSelection, RunPreset`;287 行 `AssertionAnchor` 类型引用已随 Task 5 改 `EntryPath`(若 Task 5 未及此行,此处一并改)。

hunk B — Run 段状态(398 `runDialogOpen` 后)加:

```ts
/** 运行面板预填(spec v3 §6):配置签「加入本次执行」置入;Task 7 消费 */
const runPreset = ref<RunPreset | null>(null)
function closeRunDialog() {
  runDialogOpen.value = false
  runPreset.value = null
}
```

RunDialog 挂载(232-250)加 `:preset="runPreset"`,`@close="runDialogOpen = false"` 改 `@close="closeRunDialog"`。

hunk C — onRunConfirm 签名(1002-1011)与 body(1024):

```ts
async function onRunConfirm(
  dataSetSelection: DataSetSelection[],
  opts?: {
    stepTo?: number
    nRuns?: number
    parallel?: number
    serviceBindings?: Record<string, ServiceBinding>
    injectionEntryIds?: string[]
  },
) {
```

```ts
    const body: RunRequest = {
      scenarioId: scenario.value.meta.scenarioId,
      dataSetIds: dataSetSelection.map((s) => s.datasetId),
      ...(dataSetSelection.length ? { dataSetSelection } : {}),
```

- [ ] **Step 8: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/RunDialog.injection.test.ts src/components/composer/__tests__/RunPanelHost.test.ts`
Expected: PASS(8 + 3 用例)。
再跑邻近回归: `npx vitest run src/views/__tests__/CaseComposer.registry.test.ts` → PASS(Task 5 用例未受 preset 管道影响)。

- [ ] **Step 9: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/api/scenario-composer.ts src/gimbal-platform/frontend/src/components/composer/RunDialog.vue src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/__tests__/RunDialog.injection.test.ts src/gimbal-platform/frontend/src/components/composer/__tests__/RunPanelHost.test.ts && git commit -m "feat(run): RunDialog 交叉语义 + dataSetSelection 行级选择 + preset 预填 — RunPanelHost 抽出供双入口复用

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 测试数据页双区 + 配置签展示化 + DataSetEditor「运行此行」(spec T6)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue`(升级「测试数据」同页双区)
- Modify: `src/gimbal-platform/frontend/src/views/DataSetEditor.vue`(行工具栏「运行此行」)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue`(断言管理卡 → 纯展示列表)
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(Config 装配 + onRunEntry)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/CaseDataSetsList.test.ts`(新建)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerConfig.test.ts`(新增 describe)

**Interfaces:**
- Consumes: Task 6 `RunPanelHost`(props `{scenarioId, preset?}` / emits close)、`RunPreset`、`DataSetSelection`;Task 1 `isLegacyEntry`/`isDeadEntry`/`bodyPathSetOf`/`normalizeRegistry`;`fieldPathsOf(step)`;`scenarioDataSetsUrl`/`scenarioAssertionsUrl`/`composerUrl`(utils/links)。
- Produces(Task 8 消费):`CaseComposerConfig` props `assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>` + `deadEntryIds?: string[]`,emits `'runEntry': [id: string]`(旧 `assertionCount` prop 退役);CaseDataSetsList 页面标题「测试数据」,数据集卡「运行」与 DataSetEditor「运行此行」均经 RunPanelHost preset 落地。

- [ ] **Step 1: 写失败测试**(新建 `src/views/__tests__/CaseDataSetsList.test.ts`)

```ts
/**
 * CaseDataSetsList — 测试数据页双区(spec v3 §5):
 * - DSL-1 同页双区:数据集卡片网格(store)与断言条目卡片网格
 *   (getScenarioDraft + normalizeRegistry)同屏;v3 条目带 path 徽标,
 *   悬空灰;旧版条目灰显「旧版条目,请重建」不可执行
 * - DSL-2 数据集卡「运行」→ RunPanelHost 挂载且 preset = 整库单选
 * - DSL-3 条目卡点击 → 跳断言管理编辑器(编辑入口搬家至测试数据页)
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-td' } }),
  useRouter: () => ({ push: pushMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import CaseDataSetsList from '@/views/CaseDataSetsList.vue'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import { scenarioAssertionsUrl } from '@/utils/links'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-td', meta: { name: 'td' },
  config: { vars: { amount: 100 } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-1', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-dead', name: '悬空',
      path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
  ],
}

const storeMock = vi.hoisted(() => ({
  dataSetsStatus: 'idle',
  dataSetsOfScenario: () => [
    { datasetId: 'ds-1', scenarioId: 'sc-td', name: '正负流', rowCount: 2, preview: [] },
  ],
  fetchDataSets: vi.fn(async () => {}),
  removeDataSet: vi.fn(async () => {}),
}))
vi.mock('@/stores/scenario-composer', () => ({
  useScenarioComposerStore: () => storeMock,
}))

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.push.mockReset()
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG } as any)
})
afterEach(() => { vi.restoreAllMocks() })

async function mountList() {
  const w = mount(CaseDataSetsList, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

it('DSL-1: 测试数据页双区 — 数据集网格 + 断言条目网格(path 徽标/悬空灰/旧版灰)', async () => {
  const w = await mountList()
  expect(w.find('.page-title').text()).toContain('测试数据')
  expect(w.findAll('.card:not(.add-card):not(.td-entry)')).toHaveLength(1)   // 数据集区(条目区排除)
  const entryCards = w.findAll('.td-entry')
  expect(entryCards).toHaveLength(3)
  expect(entryCards[0].text()).toContain('金额为负')
  expect(entryCards[0].text()).toContain('步骤1 · $.amount')          // path 徽标
  expect(entryCards[1].classes()).toContain('is-dead')                // 悬空灰
  expect(entryCards[2].classes()).toContain('is-dead')                // 旧版灰
  expect(entryCards[2].text()).toContain('旧版条目,请重建')
  w.unmount()
})

it('DSL-2: 数据集卡「运行」→ RunPanelHost 挂载且 preset = 整库单选', async () => {
  const w = await mountList()
  expect(w.findComponent(RunPanelHost).exists()).toBe(false)
  await w.findAll('button').find((b) => b.text() === '运行')!.trigger('click')
  await flushPromises()
  const panel = w.findComponent(RunPanelHost)
  expect(panel.exists()).toBe(true)
  expect(panel.props('scenarioId')).toBe('sc-td')
  expect(panel.props('preset')).toEqual({ dataSetSelection: [{ datasetId: 'ds-1' }] })
  w.unmount()
})

it('DSL-3: 条目卡点击 → 跳断言管理编辑器', async () => {
  const w = await mountList()
  await w.findAll('.td-entry')[0].trigger('click')
  expect(pushMock.push).toHaveBeenCalledWith(scenarioAssertionsUrl('sc-td'))
  w.unmount()
})
```

- [ ] **Step 2: 写失败测试**(`CaseComposerConfig.test.ts` 追加 describe;沿用该文件既有 mock 面(vi.mock catalog-services),本 describe 自带局部 mount 辅助 — 既有 `mountWithParent` 不传展示列表 props)

```ts
describe('断言管理纯展示列表(spec v3 §5)', () => {
  const ENTRIES = [
    { id: 'inj-1', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
  ] as any[]

  /** 生产用法镜像(同 mountWithParent)+ 展示列表 props + runEntry 监听 */
  function mountAreList(props: Record<string, unknown> = {}) {
    const config = ref<ConfigView>(makeConfig())
    const runEntry = vi.fn()
    const Parent = defineComponent({
      setup() {
        return () => h(CaseComposerConfig, {
          modelValue: config.value,
          'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
          assertionEntries: ENTRIES,
          ...props,
          onRunEntry: runEntry,
        })
      },
    })
    return { w: mount(Parent, { global: { plugins: [ElementPlus] } }), runEntry }
  }

  it('CFG-ARE-1: 列表渲染(path 徽标/期望数)+ 旧版条目灰显不可执行', async () => {
    const { w } = mountAreList({ deadEntryIds: ['inj-old'] })
    const rows = w.findAll('.are-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('步骤1 · $.amount')
    expect(rows[1].classes()).toContain('is-dead')
    expect(rows[1].text()).toContain('旧版条目,请重建')
    expect(rows[1].find('.are-run').exists()).toBe(false)   // 旧版无「加入本次执行」
  })

  it('CFG-ARE-2: 活条目「加入本次执行」→ emit runEntry(id)', async () => {
    const { w, runEntry } = mountAreList({ deadEntryIds: [] })
    await w.find('.are-run').trigger('click')
    expect(runEntry).toHaveBeenCalledWith('inj-1')
  })
})
```

(注:emits 经 h() props 监听器断言,不用 `w.emitted` — 包装在 Parent 内;`makeConfig`/`ConfigView`/`h`/`defineComponent`/`ref`/`vi` 均为该文件既有导入。)

- [ ] **Step 3: 跑测试确认失败**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/views/__tests__/CaseDataSetsList.test.ts src/components/composer/__tests__/CaseComposerConfig.test.ts`
Expected: FAIL — CaseDataSetsList(无 .td-entry 区/无 RunPanelHost);CaseComposerConfig(无 assertionEntries prop/.are-row 渲染)。

- [ ] **Step 4: CaseDataSetsList 双区改造**

模板:标题行(9)`数据集列表` 改 `测试数据`;副行(10)改 `场景 {{ scenarioId }} · {{ dataSets.length }} 数据集 · {{ registry.entries.length }} 断言条目`;数据集卡「单条」按钮(41)改「运行」并换 handler:

```html
            <el-button size="small" type="primary" plain @click="runDataset(d)"><el-icon style="margin-right:3px"><VideoPlay /></el-icon>运行</el-button>
```

数据集 grid 之后(el-empty 之前)插入断言条目区:

```html
    <!-- 断言条目网格(spec v3 §5):同页双区第二区 — 编辑入口(点击跳
         断言管理编辑器);旧版条目灰显不可执行(保留原样不删) -->
    <section class="td-entries">
      <header class="page-header">
        <div>
          <h2 class="page-title sub">断言条目(偏离注入)</h2>
          <p>{{ registry.entries.length }} 条 · 定位 path + 偏离值 + 期望配对 · 与数据集行交叉执行</p>
        </div>
        <div class="header-actions">
          <el-button :icon="Back" @click="router.push(scenarioAssertionsUrl(scenarioId))">管理断言</el-button>
        </div>
      </header>
      <div class="grid">
        <article
          v-for="e in registry.entries"
          :key="e.id"
          class="card td-entry"
          :class="{ 'is-dead': isLegacyEntry(e) || deadOf(e) }"
          :title="isLegacyEntry(e) ? '旧版条目,请重建' : deadOf(e) ? '悬空条目 — 不可执行' : '点击编辑'"
          @click="openEntryEditor()"
        >
          <header class="card-head">
            <div class="title">
              <h3>{{ e.name }}</h3>
              <span v-if="!isLegacyEntry(e)" class="row-count">步骤{{ e.path.stepIndex + 1 }} · {{ e.path.jsonpath }}</span>
              <span v-else class="row-count">旧版条目,请重建</span>
            </div>
          </header>
          <p class="preview">{{ valueSummary(e) }}</p>
          <footer class="card-foot">
            <div class="ops" @click.stop>
              <span class="row-count">{{ e.asserts?.length ?? 0 }} 期望</span>
              <span v-if="isLegacyEntry(e)" class="row-count">旧版</span>
              <span v-else-if="deadOf(e)" class="row-count">悬空</span>
            </div>
          </footer>
        </article>
        <article class="card add-card" @click="openEntryEditor()">
          <div class="add-icon">+</div>
          <div class="add-text">新建断言条目</div>
        </article>
      </div>
    </section>

    <!-- 运行面板宿主(spec v3 §6 数据集入口):整库/单行预填 -->
    <RunPanelHost v-if="panelOpen" :scenario-id="scenarioId" :preset="panelPreset" @close="panelOpen = false" />
```

脚本(61-123)追加 import 与状态(vue import 行 62 改 `import { computed, onMounted, ref } from 'vue'`):

```ts
import { getScenarioDraft } from '@/api/scenario-composer'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import type { RunPreset } from '@/api/scenario-composer'
import type { AssertionRegistry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { bodyPathSetOf, isDeadEntry, normalizeRegistry } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
import { scenarioAssertionsUrl } from '@/utils/links'
```

(links import 行合并:`scenarioDataSetUrl, composerUrl, scenarioAssertionsUrl`。)

```ts
// ── 断言条目区(spec v3 §5):draft 自取数(与编辑器同源)────────────
const registry = ref<AssertionRegistry>({ entries: [] })
const steps = ref<any[]>([])
function bodyPathsOfStep(si: number): ReadonlySet<string> {
  return bodyPathSetOf(fieldPathsOf(steps.value[si] as any))
}
function assertTargetsOf(si: number): ReadonlySet<string> {
  const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
  return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadOf = (e: AssertionRegistry['entries'][number]) =>
  isDeadEntry(e, steps.value.length, bodyPathsOfStep, assertTargetsOf)
function valueSummary(e: AssertionRegistry['entries'][number]): string {
  if (isLegacyEntry(e)) return '—'
  const v = (e as { value: unknown }).value
  if (v === null || v === undefined) return '—'
  return typeof v === 'string' ? v : JSON.stringify(v)
}

// ── 运行面板(spec v3 §6 数据集入口):preset 预填 ──────────────────
const panelOpen = ref(false)
const panelPreset = ref<RunPreset | null>(null)

/** 数据集卡「运行」:整库单选预填(行级在 DataSetEditor「运行此行」)*/
function runDataset(d: DataSetSummary) {
  panelPreset.value = { dataSetSelection: [{ datasetId: d.datasetId }] }
  panelOpen.value = true
}
function openEntryEditor() {
  router.push(scenarioAssertionsUrl(scenarioId))
}
```

onMounted 追加 draft 拉取(fetchDataSets 之后):

```ts
  try {
    const draft = await getScenarioDraft(scenarioId)
    registry.value = normalizeRegistry(draft.assertion_registry)
    steps.value = (draft.definition.steps ?? []) as any[]
  } catch (e) {
    showError('加载断言条目', e)
  }
```

(旧 `runOne` 函数删除 — 「单条」按钮被「运行」取代;样式追加 `.td-entries { margin-top: 28px; }` 与 `.card.td-entry.is-dead { opacity: .55; }`、`.page-title.sub { font-size: 16px; }`。)

- [ ] **Step 5: DataSetEditor「运行此行」(最小 hunk)**

行工具栏(236-239)加按钮(icons import 行 280 加 `VideoPlay`):

```html
            <td class="td-action">
              <el-button size="small" text :icon="VideoPlay" :aria-label="`运行第 ${i + 1} 行`" @click="runRow(i)" />
              <el-button size="small" text @click="cloneRow(i)">复制</el-button>
              <el-button size="small" text :icon="Delete" :aria-label="`删除数据 ${i + 1}`" @click="removeRow(i)" />
            </td>
```

模板末尾(`</section>` 前)挂宿主;脚本 import `RunPanelHost` 与 `RunPreset` 类型,状态与 handler:

```ts
/** 运行此行(spec v3 §6 数据集入口):行级 rowIndexes 预填(0-based = 行号) */
const panelOpen = ref(false)
const panelPreset = ref<RunPreset | null>(null)
function runRow(i: number) {
  panelPreset.value = { dataSetSelection: [{ datasetId, rowIndexes: [i] }] }
  panelOpen.value = true
}
```

(注:`datasetId` 是 305 行 `const datasetId = route.params.datasetId as string` — 非 ref,直接用原值;挂载点 `<RunPanelHost v-if="panelOpen" :scenario-id="scenarioId" :preset="panelPreset" @close="panelOpen = false" />`。)

- [ ] **Step 6: CaseComposerConfig 纯展示列表(243-252 替换)**

```html
    <!-- 断言管理(偏离注入)纯展示列表(spec v3 §5)— 编辑入口搬家至
         测试数据页;每条「加入本次执行」预勾运行面板(Task 6 preset) -->
    <div class="c-card are-entry-card">
      <div class="c-card-head">
        <div>
          <h3>断言管理</h3>
          <p class="c-head-desc">偏离注入条目({{ assertionEntries?.length ?? 0 }})— 定位 path + 偏离值 + 期望配对</p>
        </div>
        <button class="c-add" @click="goTestData">测试数据 →</button>
      </div>
      <div v-if="!assertionEntries?.length" class="c-empty">
        <p>还没有偏离注入条目</p>
      </div>
      <ul v-else class="are-list">
        <li
          v-for="e in assertionEntries"
          :key="e.id"
          class="are-row"
          :class="{ 'is-dead': isLegacyEntry(e) || deadEntryIds?.includes(e.id) }"
        >
          <span class="are-name">{{ e.name }}</span>
          <span v-if="!isLegacyEntry(e)" class="are-path">步骤{{ e.path.stepIndex + 1 }} · {{ e.path.jsonpath }}</span>
          <span v-else class="are-path">旧版条目,请重建</span>
          <span class="are-count">{{ e.asserts?.length ?? 0 }} 期望</span>
          <button
            v-if="!isLegacyEntry(e) && !deadEntryIds?.includes(e.id)"
            class="are-run"
            @click="emit('runEntry', e.id)"
          >加入本次执行</button>
        </li>
      </ul>
    </div>
```

脚本:props(289)`assertionCount?: number` 替换为 `assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>` + `deadEntryIds?: string[]`;emits 加 `'runEntry': [id: string]`;import 改:

```ts
import { scenarioDataSetsUrl } from '@/utils/links'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
```

`goAssertions` 改 `goTestData`(scenarioAssertionsUrl → scenarioDataSetsUrl,「请先保存场景」守卫保留);样式追加:

```css
.are-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.are-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--c-bg-secondary); border-radius: 6px;
  font-size: 12px;
}
.are-row.is-dead { opacity: .55; }
.are-name { font-weight: 600; min-width: 96px; }
.are-path { font-family: var(--font-mono); font-size: 11px; color: var(--c-text-secondary); flex: 1; }
.are-count { color: var(--c-text-tertiary); font-size: 11px; }
.are-run {
  background: transparent; border: none; color: var(--c-accent);
  font-size: 12px; cursor: pointer; padding: 0;
}
.are-run:hover { text-decoration: underline; }
```

- [ ] **Step 7: CaseComposer 装配(148 替换)**

```html
              :assertion-entries="registry.entries"
              :dead-entry-ids="deadEntryIds"
              @run-entry="onRunEntry"
```

脚本(Task 6 runPreset 旁)加:

```ts
/** 配置签「加入本次执行」(spec v3 §5):预勾该条目打开运行面板 */
function onRunEntry(id: string) {
  runPreset.value = { injectionEntryIds: [id] }
  openRunDialog()
}
```

(openRunDialog 为既有函数(约 412 行,dirty 时先 flush);只追加调用不改其体。)

- [ ] **Step 8: 跑测试确认通过**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run src/views/__tests__/CaseDataSetsList.test.ts src/components/composer/__tests__/CaseComposerConfig.test.ts src/views/__tests__/CaseComposer.registry.test.ts src/views/__tests__/AssertionRegistryEditor.test.ts`
Expected: PASS(新增 3 + 2;回归 — registry.test 的「断言管理」文案断言仍中(卡片标题保留),AssertionRegistryEditor 不受影响)。
DataSetEditor 无新测试(按钮接线由 typecheck + 既有套件守门 — RunPanelHost 行为已由 RH-* 锁定,此处只做 preset 接线,决策记录于任务注)。

- [ ] **Step 9: Commit**

```bash
cd /d/Gimbal/Gimbal && git add src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue src/gimbal-platform/frontend/src/views/DataSetEditor.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/views/__tests__/CaseDataSetsList.test.ts src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerConfig.test.ts && git commit -m "feat(data): 测试数据页双区 + 配置签纯展示 + 运行此行 — 数据集入口经 RunPanelHost preset 预填

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: 退场清单清理(spec §7)+ 全量回归

**Files:**
- Modify: 按 grep 扫描结果定点(spec §7 前端 6 行 + 后端 3 行;预期绝大多数已随 Task 1-7 的整体重写消亡,本任务做残留确认而非再改)
- Verify: v2 spec 取代标注已在 43bd1ce 落库(spec §7 文档行 — 只读确认)

**Interfaces:**
- Consumes: Task 1-7 全部产出。
- Produces: 全仓无 `AssertionAnchor`/`AssertionInject`/`var-unknown`/`_definition_vars`/`registryVarNames` 残留;plate/执行核零改动得到 `git diff --stat` 守卫确认;全量后端 + 前端套件绿。

- [ ] **Step 1: 退役名残留扫描**(前端 + 后端 + 测试)

```bash
cd /d/Gimbal/Gimbal && grep -rn -E "AssertionAnchor|AssertionInject|var-unknown|_definition_vars|registryVarNames" src/gimbal-platform/frontend/src src/gimbal-platform/backend/app src/gimbal-platform/backend/tests || echo "CLEAN"
```

Expected: `CLEAN`(或仅注释/历史文档提及 — 代码零残留)。若命中:`var-unknown` 应只存在于 Task 1/2 注释(「退役」说明);`AssertionAnchor` 若在 Canvas/FieldForm 残留(Task 5 hunk 未及的次要引用),逐处改 `EntryPath`;`registryVarNames` 若在 CaseComposer 残留,确认 Task 5 hunk A 已删该 computed。

再扫 anchor 载荷残留(varName 采集链,spec §7「Canvas/FieldActionMenu anchor 载荷」行):

```bash
cd /d/Gimbal/Gimbal && grep -rn "registryMark" src/gimbal-platform/frontend/src | grep -v "__tests__" && grep -rn "varName" src/gimbal-platform/frontend/src/components/composer/FieldForm.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue || echo "CLEAN"
```

Expected: registryMark 两处定义/消费(FieldForm emit + Canvas handler),载荷形状 = `{ field, value }`(无 varName)。

- [ ] **Step 2: plate/执行核零改动守卫**

```bash
cd /d/Gimbal/Gimbal && git diff --stat feat/dataset-driven-refactor@{u}...HEAD 2>/dev/null | grep -E "src/gimbal-plate/|src/gimbal/|export/gimbal.py" && echo "VIOLATION" || echo "CLEAN"
```

(若分支无 upstream,以本计划起始 commit 为基:`git diff --stat <base>...HEAD | grep ...`。基线 commit = 实施开始前的 HEAD,执行者记录于 ledger。)
Expected: `CLEAN` — `src/gimbal-plate/**`、`src/gimbal/**`、`export/gimbal.py` 零改动。

- [ ] **Step 3: v2 spec 取代标注确认**(只读)

```bash
cd /d/Gimbal/Gimbal && head -5 docs/superpowers/specs/2026-09-11-assertion-registry-field-binding-design.md
```

Expected: 头部含「**已被 `2026-09-12-assertion-registry-v3-merge-injection-design.md`(spec v3)取代**」(43bd1ce 已落库;若缺失则补该行并随 Step 6 提交 — 正常不应发生)。

- [ ] **Step 4: 后端全量回归**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/backend && python -m pytest -v`
Expected: PASS(全量;重点观察 test_run_injection/test_run_cross_matrix/test_run_m1_capabilities/test_run_baseline/test_run_cancel/test_scenario_composer_plate_integration — 交叉矩阵改写后 dataSetIds 旧路径走 setdefault 整库,行为不变)。

- [ ] **Step 5: 前端全量回归 + 类型检查**

Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npx vitest run`
Expected: PASS(全量 — Task 1 中间态申报的全部预期红在此收口)。
Run: `cd /d/Gimbal/Gimbal/src/gimbal-platform/frontend && npm run typecheck`
Expected: PASS(vue-tsc 零错误 — Task 4-7 的 Interfaces 签名一致性最终验证)。

- [ ] **Step 6: Commit(如有扫描修正;全绿则无本步)**

```bash
cd /d/Gimbal/Gimbal && git add <扫描修正点名文件> && git commit -m "chore(assertion): v2 实现退场残留清理 + 全量回归收口

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 验收对照(spec §10 ↔ 计划任务)

| spec 条目 | 落点 |
|---|---|
| §1 裁定 1-3(三元组/任意字段/解耦)| Task 1 形状 + Task 2 Assign 直补 |
| §1 裁定 4(交叉矩阵)| Task 3 dispatcher + Task 6 RunDialog 总量 |
| §1 裁定 5(同页双区)| Task 7 CaseDataSetsList |
| §1 裁定 6(两个执行入口)| Task 6 RunPanelHost + Task 7 两处挂载 |
| §1 裁定 7(配置签纯展示)| Task 7 CaseComposerConfig |
| §1 裁定 8(清理旧实现)| Task 1-7 逐任务退场 + Task 8 扫描确认 |
| §1 裁定 9(headers 协议位)| Task 1 `source: 'body'` 单值 + Canvas hunk 注释 |
| §2 悬空三检 + legacy | Task 1 RG-1..6 + Task 2 entry_issues |
| §3 物化链(Assign 直补)| Task 2 compose_injection_scenario |
| §4 dataSetSelection + 409 + 审计三定位 | Task 3 schemas + dispatcher + stem |
| §5 IA(测试数据页/编辑器/配置签/标记)| Task 4 编辑器 + Task 5 标记 + Task 7 页面 |
| §6 运行面板复用 | Task 6 RunPanelHost + preset |
| §7 退场清单 | 各任务 hunk 内嵌退场 + Task 8 grep 确认 |
| §8 存量处置(灰显不可执行)| Task 4 ARE-2 + Task 6 INJ-1 + Task 7 DSL-1/CFG-ARE-1 |
| §9 协议位(不实现)| 无任务(边界外) |
