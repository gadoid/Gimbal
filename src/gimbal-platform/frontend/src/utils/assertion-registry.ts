// utils/assertion-registry.ts
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AssertionEntry, AssertionRegistry, LegacyAssertionEntry } from '@/types/assertion-registry'

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
  // stepIndex 非整数(手改 JSON:"0")与越界同判 step-oob —— 后端同守卫
  // (`isinstance(si, int)`),否则前端把它当活条目,chip 宣称一次永不
  // 触发的注入。
  const si = entry.path.stepIndex
  if (!Number.isInteger(si) || si < 0 || si >= stepCount) {
    issues.push({ kind: 'step-oob', stepIndex: si })
  } else if (!pathResolvable(entry.path.jsonpath, bodyPathsOfStep(si))) {
    issues.push({ kind: 'path-unresolvable', stepIndex: si, jsonpath: entry.path.jsonpath })
  }
  // asserts 缺键 / 非数组 → 视作空(后端 `entry.get("asserts") or []`);
  // 单条 assert 非对象或 stepIndex 非整数 → 跳过(后端 `isinstance(a, dict)
  // and isinstance(a.get("stepIndex"), int)`)。
  const asserts = Array.isArray(entry.asserts) ? entry.asserts : []
  for (const a of asserts) {
    if (!a || typeof a !== 'object' || !Number.isInteger(a.stepIndex)) continue
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
 *  在 `registry.entries.length` 崩渲染。所有水化入口统一走这里。
 *
 *  逐条形状修复(与后端 run_injection.entry_issues 的容忍面看齐):
 *  * 非对象条目(标量 / 数组 / null)→ 丢弃:模板渲染 `e.id` 先于任何
 *    判定就 TypeError;后端对这些条目本就 500(entry.get),不可用;
 *  * `asserts` 缺键或非数组 → 补 `[]`(后端 `entry.get("asserts") or []`):
 *    否则编辑器详情 `selected.asserts.length` / `v-for` 崩渲染。
 *  path 形状不在此处改(判据归 isLegacyEntry,与后端同构)。 */
export function normalizeRegistry(raw: unknown): AssertionRegistry {
  const rawEntries = (raw as { entries?: unknown } | undefined | null)?.entries
  if (!Array.isArray(rawEntries)) return { entries: [] }
  const entries: Array<AssertionEntry | LegacyAssertionEntry> = []
  for (const e of rawEntries) {
    if (typeof e !== 'object' || e === null || Array.isArray(e)) continue
    const entry = e as AssertionEntry | LegacyAssertionEntry
    entries.push(
      Array.isArray((entry as { asserts?: unknown }).asserts)
        ? entry
        : ({ ...(entry as unknown as Record<string, unknown>), asserts: [] } as unknown as
            AssertionEntry | LegacyAssertionEntry),
    )
  }
  return { entries }
}

/** 条目 id:inj-<6位base36时间戳><3位随机>(genScenarioId 同款纪律,无依赖) */
export function genEntryId(): string {
  const ts = Date.now().toString(36).slice(-6)
  const rnd = Math.floor(Math.random() * 36 ** 3).toString(36).padStart(3, '0')
  return `inj-${ts}${rnd}`
}
