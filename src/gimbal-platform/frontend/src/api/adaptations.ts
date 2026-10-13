/**
 * api/adaptations.ts —— 变更适配 API client(P5)。
 *
 * 契约照后端 app/schemas/adaptations.py(camelCase 显式 alias);
 * 错误形状为 http.ts 归一后的 ApiError { status, code }:文案在 Error 继承的
 * .message 上(运行时不赋 .msg)。
 *
 * A-6 清理(2026-10-12):catalogDiff / impact / impactBulk /
 * impactSummary / openBatch(POST /batches 旧流程)已随旧读面删除。
 */
import http, { ApiError } from '@/api/http'

export interface OpOut {
  id: number
  batchId: string
  /** CARRY_OPS 免场景落点(D1)→ null;场景 op 恒有值。 */
  scenarioId: string | null
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
  /** 场景 op 必填;CARRY_OPS 免(后端 OpCreateIn 已可空)—— carry 请求体不带该键。 */
  scenarioId?: string | null
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

export async function unindexedSteps(): Promise<UnindexedStep[]> {
  const { data } = await http.get<UnindexedStep[]>('/adaptations/unindexed-steps')
  return data
}

/** M4 Page 信封(§6.3):status 精确 + 分页。 */
export interface BatchPage {
  items: BatchOut[]
  total: number
  page: number
  pageSize: number
}

export async function listBatches(params?: {
  scope?: 'mine'
  status?: string
  page?: number
  page_size?: number
}): Promise<BatchPage> {
  const { data } = await http.get<BatchPage>('/adaptations/batches', {
    params: params ?? {},
  })
  return data
}

export async function getBatch(batchId: string): Promise<BatchDetail> {
  const { data } = await http.get<BatchDetail>(
    `/adaptations/batches/${encodeURIComponent(batchId)}`)
  return data
}

/** 开 carry 值表批(漂移面板入口,spec §7);service=null → 全局默认表面。 */
export async function openCarryBatch(
  service: string | null,
): Promise<BatchDetail> {
  const { data } = await http.post<BatchDetail>('/adaptations/carry-batches', {
    service,
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
