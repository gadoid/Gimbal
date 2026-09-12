// utils/assertion-registry.ts
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AssertionEntry, AssertionRegistry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { catalogPaths, toTemplatePath } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

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

/** path 是否可解析(spec v3.1 §2.1):实例形态对齐 body 面、模板形态对齐
 *  契约声明面,二者任一命中即可;或为某路径的容器前缀(`p.` / `p[`
 *  开头 —— 条目可锚在容器上,Assign 整体覆写该容器,spec §2)。 */
export function pathResolvable(jsonpath: string, injectablePaths: ReadonlySet<string>): boolean {
  for (const form of [jsonpath, toTemplatePath(jsonpath)]) {
    if (injectablePaths.has(form)) return true
    // 容器前缀扫描**承重,别当死代码删**:本文件 `injectablePathSetOf` 只放
    // body 叶子与契约声明路径,**不**预展开各级容器前缀(后端
    // `injectable_universe` 走的是另一条路 —— 它把 `_container_prefixes`
    // materialize 进 universe,故后端那边同形的扫描才可省)。这里若照抄删掉
    // 本段,活着的容器路径(`$.items` 之于叶子 `$.items.sku`)会被判成悬空。
    for (const p of injectablePaths) {
      if (p.startsWith(`${form}.`) || p.startsWith(`${form}[`)) return true
    }
  }
  return false
}

/** 悬空检测(spec v3 §2,软提示不阻断):legacy-entry / step-oob /
 *  path-unresolvable / override-no-match。injectablePathsOfStep 与
 *  assertTargetsOf 由调用方从场景 definition 投影(编辑器/编排器同构)。 */
export function registryIssues(
  entry: AssertionEntry | LegacyAssertionEntry,
  stepCount: number,
  injectablePathsOfStep: (stepIndex: number) => ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): RegistryIssue[] {
  if (isLegacyEntry(entry)) return [{ kind: 'legacy-entry' }]
  const issues: RegistryIssue[] = []
  // stepIndex 非整数(手改 JSON:"0")与越界同判 step-oob —— 后端同守卫
  // (`as_step_index`:拒 bool、收整数值浮点 —— 与这里的 `Number.isInteger`
  // 同构),否则前端把它当活条目,chip 宣称一次永不触发的注入。
  const si = entry.path.stepIndex
  // jsonpath 非字符串(手改 JSON / 旧写入方)与越界同判 path-unresolvable —
  // 后端同守卫(`isinstance(jp, str)`,run_injection.py)。**不得**放它进
  // pathResolvable:`toTemplatePath` 是 `path.replace(...)`,非串必抛
  // TypeError,四个消费方(编辑器 deadOf / CaseComposer / CaseDataSetsList
  // / RunPanelHost 的 deadEntryIds)都在渲染期调它 → 整页白屏。守卫前
  // 前端崩、后端判死 = 判定层单向分裂。
  // (RegistryIssue.jsonpath 静态类型是 string:与 EntryPath 一样,对
  //  /draft 这份不可信 JSON 是静态承诺,这里按后端同口径送**原值**。)
  const jp = entry.path.jsonpath as unknown
  if (!Number.isInteger(si) || si < 0 || si >= stepCount) {
    issues.push({ kind: 'step-oob', stepIndex: si })
  } else if (typeof jp !== 'string' || !pathResolvable(jp, injectablePathsOfStep(si))) {
    issues.push({ kind: 'path-unresolvable', stepIndex: si, jsonpath: entry.path.jsonpath })
  }
  // asserts 缺键 / 非数组 → 视作空(后端 `entry.get("asserts") or []`);
  // 单条 assert 非对象或 stepIndex 非整数 → 跳过(后端 `isinstance(a, dict)`
  // 且 `as_step_index(a.get("stepIndex"))` 为 None → continue)。
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
