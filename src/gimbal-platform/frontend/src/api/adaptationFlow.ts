/**
 * api/adaptationFlow.ts —— RS4a 适配中心新流程 API（Release v4.4 §5）。
 *
 * 流程：比较 → 保存检查 → 提交；两种适配：跨版本线（cross_line）
 * 与线内修正（correction）。后端实现见 routers/adaptations.py 的
 * /compare /save-check /submit /stale 四端点。
 */
import http from '@/api/http'

// ── 类型 ──────────────────────────────────────────────────────────

/** 版本线信息（GET /endpoint-catalog/{system}/lines → plate lines） */
export interface SystemLine {
  line: string
  revisions: number
  latest: string
  line_scheme: string | null
}

/** 声明字段级差异（R7，plate diff 的 field_diff） */
export interface FieldDiff {
  added: string[]
  removed: string[]
  changed: Record<string, { from: Record<string, unknown>;
                            to: Record<string, unknown> }>
}

/** plate 对象级差异 */
export interface DiffResult {
  from: string
  to: string
  added: string[]
  removed: string[]
  changed: Record<string, { type: string;
    parts?: Record<string, unknown> & {
      request?: { field_diff?: FieldDiff }
      responses?: { field_diff?: Record<string, FieldDiff> } } }>
}

/** 三组影响判定（§5.3） */
export interface ImpactGroups {
  direct: Array<{ step: number; endpoint: string; reason: string }>
  field: Array<{ step: number; endpoint: string;
                 parts?: Record<string, unknown> }>
  structure: Array<{ step: number; endpoint: string; reason: string }>
}

/** 比较结果（GET /adaptations/compare） */
export interface CompareResult {
  scenario_id: string
  system: string
  from: string
  to: string
  diff: DiffResult
  groups: ImpactGroups
}

/** 保存检查结果（POST /adaptations/save-check） */
export interface SaveCheckResult {
  ok: boolean
  blocking_issues: Array<{ code: string; message: string;
                           step?: number; field?: string }>
  review_items: Array<{ entry: string; step: number; jsonpath: string;
                        reason: string; message: string }>
  references: { own: ReferenceItem[]; others: ReferenceItem[] }
  recommendation: 'direct' | 'copy'
  from: string
  to: string
  system: string
  convert_result?: unknown
}

export interface ReferenceItem {
  type: 'suite' | 'integration'
  id: number
  name: string
  owner_id: number | null
}

/** 提交结果（POST /adaptations/submit） */
export interface SubmitResult {
  success: boolean
  scenario_id?: string
  new_scenario_id?: string     // 保存为副本时
  save_mode: 'direct' | 'copy'
  batch_id?: string
  message?: string
}

// ── API 调用 ──────────────────────────────────────────────────────

/** 获取系统版本线列表 */
export async function fetchLines(systemId: string): Promise<SystemLine[]> {
  const { data } = await http.get<{ items: SystemLine[] }>(
    `/endpoint-catalog/${encodeURIComponent(systemId)}/lines`)
  return data.items
}

/** 比较：场景起点修订 vs 目标修订（差异 + 三组影响） */
export async function compareScenario(
  scenarioId: string, target: string, system?: string,
): Promise<CompareResult> {
  const { data } = await http.get<{ item: CompareResult }>(
    `/adaptations/compare`, {
      params: { scenarioId, target, ...(system ? { system } : {}) },
    })
  return data.item
}

/** 保存检查：目标修订试算 + 引用检查 + 保存方式推荐 */
export async function saveCheck(
  scenarioId: string, targetRevision: string, system?: string,
): Promise<SaveCheckResult> {
  const { data } = await http.post<SaveCheckResult>(
    `/adaptations/save-check`, {
      scenarioId, targetRevision, ...(system ? { system } : {}),
    })
  return data
}

/** 提交适配（直接保存或保存为副本；R14 评审项须确认） */
export async function submitAdaptation(
  scenarioId: string,
  ops: Array<Record<string, unknown>>,
  targetRevision: string,
  saveMode: 'direct' | 'copy',
  reviewConfirmed = false,
  system?: string,
): Promise<SubmitResult> {
  const { data } = await http.post<SubmitResult>(
    `/adaptations/submit`, {
      scenarioId, ops, targetRevision, saveMode,
      reviewConfirmed, ...(system ? { system } : {}),
    })
  return data
}

/** 陈旧清单：有待处理提示的场景列表 */
export async function fetchStaleScenarios(scope?: 'mine'): Promise<
  Array<{ scenario_id: string; name: string; reasons: string[] }>
> {
  const { data } = await http.get('/adaptations/stale', {
    params: scope ? { scope } : {},
  })
  return data.items ?? []
}
