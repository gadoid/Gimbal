/**
 * api/adaptations.ts —— 适配中心 API client(P5)。
 *
 * 契约照后端 app/schemas/adaptations.py(camelCase 显式 alias);
 * 错误形状为 http.ts 归一后的 ApiError { status, code }:文案在 Error 继承的
 * .message 上(运行时不赋 .msg)。
 */
import http, { ApiError } from '@/api/http'

export interface PendingChange {
  endpointId: string
  fromVersion: string
  toVersion: string
}

export interface CatalogAnomaly {
  endpointId: string
  reason: string
  detail: string
}

export interface CatalogDiffReport {
  pending: PendingChange[]
  anomalies: CatalogAnomaly[]
  baselinedNow: number
}

export interface ImpactItem {
  scenarioId: string
  stepIndex: number
  source: 'body' | 'headers' | 'query'
  field: string
  viaVar: string | null
  datasetId: string | null
  datasetColumn: string | null
}

export interface OpOut {
  id: number
  batchId: string
  scenarioId: string
  datasetId: string | null
  opType: string
  payload: Record<string, unknown>
  status: 'pending' | 'applied' | 'conflict' | 'skipped'
  appliedAt: string | null
  note: string | null
}

export interface SnapshotRef {
  entityType: string
  entityId: string
}

export interface BatchOut {
  batchId: string
  endpointId: string
  fromVersion: string
  toVersion: string
  status: 'open' | 'applying' | 'completed' | 'rolled_back'
  operatorId: number
  createdAt: string
  closedAt: string | null
  opCounts: Record<string, number>
}

export interface BatchDetail extends BatchOut {
  ops: OpOut[]
  snapshots: SnapshotRef[]
}

export interface RestoredEntity {
  entityType: string
  entityId: string
}

export interface RollbackConflictItem extends RestoredEntity {
  note: string
}

export interface RollbackReport {
  batchId: string
  status: string
  restored: RestoredEntity[]
  conflicts: RollbackConflictItem[]
}

export interface UnindexedStep {
  scenarioId: string
  stepIndex: number
  reason: string
}

export interface OpCreateIn {
  opType: string
  scenarioId: string
  datasetId?: string | null
  payload: Record<string, unknown>
}

/** remove+add 同 step 合并为 renameField 的预填种子(纯前端交互,§6.3)。 */
export interface MergeSeed {
  step: number
  from: string
  to: string
}

/** ApiError → 展示文案:文案在 Error 继承的 .message(运行时不赋 .msg);plate 502 等场景的兜底。 */
export function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message || fallback
  const msg = (e as { msg?: string } | null)?.msg
  return msg || fallback
}

export async function catalogDiff(): Promise<CatalogDiffReport> {
  const { data } = await http.post<CatalogDiffReport>('/adaptations/catalog/diff')
  return data
}

export async function impact(endpointId: string, field?: string): Promise<ImpactItem[]> {
  const { data } = await http.get<ImpactItem[]>('/adaptations/impact', {
    params: { endpointId, field: field || undefined },
  })
  return data
}

export async function unindexedSteps(): Promise<UnindexedStep[]> {
  const { data } = await http.get<UnindexedStep[]>('/adaptations/unindexed-steps')
  return data
}

export async function listBatches(scope?: 'mine'): Promise<BatchOut[]> {
  const { data } = await http.get<BatchOut[]>('/adaptations/batches', {
    params: scope ? { scope } : {},
  })
  return data
}

export async function getBatch(batchId: string): Promise<BatchDetail> {
  const { data } = await http.get<BatchDetail>(
    `/adaptations/batches/${encodeURIComponent(batchId)}`)
  return data
}

export async function openBatch(endpointId: string): Promise<BatchDetail> {
  const { data } = await http.post<BatchDetail>('/adaptations/batches', {
    endpointId,
  })
  return data
}

export async function createOp(batchId: string, input: OpCreateIn): Promise<OpOut> {
  const { data } = await http.post<OpOut>(
    `/adaptations/batches/${encodeURIComponent(batchId)}/ops`, input)
  return data
}

export async function applyOp(opId: number): Promise<OpOut> {
  const { data } = await http.post<OpOut>(`/adaptations/ops/${opId}/apply`)
  return data
}

export async function skipOp(opId: number): Promise<OpOut> {
  const { data } = await http.post<OpOut>(`/adaptations/ops/${opId}/skip`)
  return data
}

export async function patchOp(
  opId: number, payload: Record<string, unknown>,
): Promise<OpOut> {
  const { data } = await http.patch<OpOut>(`/adaptations/ops/${opId}`, {
    payload,
  })
  return data
}

export async function rollbackBatch(batchId: string): Promise<RollbackReport> {
  const { data } = await http.post<RollbackReport>(
    `/adaptations/batches/${encodeURIComponent(batchId)}/rollback`)
  return data
}
