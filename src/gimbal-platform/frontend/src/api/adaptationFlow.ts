/**
 * api/adaptationFlow.ts —— RS4a 适配中心新流程 API（Release v4.4 §5）。
 *
 * 流程：比较 → 影响 → 方案 → 保存检查 → 提交
 * 两种适配：跨版本线（cross_line）与线内修正（correction）
 */
import http from '@/api/http'

// ── 类型 ──────────────────────────────────────────────────────────

/** 版本线信息（plate /api/system/{id}/lines） */
export interface SystemLine {
  line: string
  revisions: number
  latest: string
  line_scheme: string | null
}

/** 对比结果（plate /api/system/{id}/diff/{a}/{b}） */
export interface DiffResult {
  from: string
  to: string
  added: string[]
  removed: string[]
  changed: Record<string, { type: string; parts?: Record<string, unknown> }>
}

/** 保存检查结果 */
export interface SaveCheckResult {
  ok: boolean
  error?: string
  code?: string
  convert_result?: unknown
}

/** 提交结果 */
export interface SubmitResult {
  success: boolean
  scenario_id?: string
  new_scenario_id?: string     // 保存为副本时
  save_mode: 'direct' | 'copy'
  message?: string
}

// ── API 调用 ──────────────────────────────────────────────────────

/** 获取系统版本线列表 */
export async function fetchLines(systemId: string): Promise<SystemLine[]> {
  const { data } = await http.get<{ items: SystemLine[] }>(
    `/endpoint-catalog/${encodeURIComponent(systemId)}/lines`)
  return data.items
}

/** 比较：两个修订间的差异（走 plate diff） */
export async function compareRevisions(
  systemId: string, fromRef: string, toRef: string,
): Promise<DiffResult> {
  const { data } = await http.get<{ item: DiffResult }>(
    `/adaptations/compare`,
    { params: { system: systemId, from: fromRef, to: toRef } })
  return data.item
}

/** 保存检查：目标修订试算 */
export async function saveCheck(
  scenarioId: string, targetRevision: string,
): Promise<SaveCheckResult> {
  const { data } = await http.post<SaveCheckResult>(
    `/adaptations/save-check`, { scenarioId, targetRevision })
  return data
}

/** 提交适配（直接保存或保存为副本） */
export async function submitAdaptation(
  scenarioId: string,
  ops: Array<Record<string, unknown>>,
  targetRevision: string,
  saveMode: 'direct' | 'copy',
): Promise<SubmitResult> {
  const { data } = await http.post<SubmitResult>(
    `/adaptations/submit`, {
      scenarioId, ops, targetRevision, saveMode,
    })
  return data
}

/** 陈旧清单：有待处理提示的场景列表 */
export async function fetchStaleScenarios(): Promise<
  Array<{ scenario_id: string; name: string; reasons: string[] }>
> {
  const { data } = await http.get('/adaptations/stale')
  return data.items ?? []
}
