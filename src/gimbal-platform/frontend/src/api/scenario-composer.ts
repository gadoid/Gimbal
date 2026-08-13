/**
 * api/scenario-composer.ts — 场景编排 API client
 *
 * 与现有 cases.ts 同等级别，提供 scenarios / cases / data-sets 三个领域
 * 的 REST 调用。请求路径对齐 Plate V3.2 的资源命名（snake_case + s 复数）。
 */
import { http } from '@/utils/http'
import type {
  Scenario, Case, DataSet, DataSetSummary,
  ScenarioDraft, DataSetDraft, RunEnv,
} from '@/types/scenario-composer'

// ── scenarios ────────────────────────────────────────────────
export async function listScenarios(params: {
  q?: string; system?: string; module?: string; priority?: number;
}): Promise<Scenario[]> {
  const { data } = await http.get<Scenario[]>('/scenarios', { params })
  return data
}

export async function getScenario(scenarioId: string): Promise<Scenario> {
  const { data } = await http.get<Scenario>(`/scenarios/${scenarioId}`)
  return data
}

export async function getScenarioDraft(scenarioId: string): Promise<ScenarioDraft> {
  const { data } = await http.get<ScenarioDraft>(`/scenarios/${scenarioId}/draft`)
  return data
}

export async function createScenario(draft: ScenarioDraft): Promise<Scenario> {
  const { data } = await http.post<Scenario>('/scenarios', draft)
  return data
}

export async function updateScenario(
  scenarioId: string, draft: ScenarioDraft,
): Promise<Scenario> {
  const { data } = await http.put<Scenario>(`/scenarios/${scenarioId}`, draft)
  return data
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  await http.delete(`/scenarios/${scenarioId}`)
}

export async function starScenario(
  scenarioId: string, starred: boolean,
): Promise<void> {
  await http.post(`/scenarios/${scenarioId}/star`, { starred })
}

// ── cases ──────────────────────────────────────────────────────
export async function listCases(params: {
  scenarioId?: string; q?: string; system?: string; module?: string;
}): Promise<Case[]> {
  const { data } = await http.get<Case[]>('/cases', { params })
  return data
}

export async function getCase(caseId: string): Promise<Case> {
  const { data } = await http.get<Case>(`/cases/${caseId}`)
  return data
}

export async function createCase(draft: Case): Promise<Case> {
  const { data } = await http.post<Case>('/cases', draft)
  return data
}

export async function updateCase(
  caseId: string, patch: Partial<Case>,
): Promise<Case> {
  const { data } = await http.patch<Case>(`/cases/${caseId}`, patch)
  return data
}

export async function deleteCase(caseId: string): Promise<void> {
  await http.delete(`/cases/${caseId}`)
}

// ── data-sets ─────────────────────────────────────────────────
export async function listDataSets(params: {
  caseId?: string;
}): Promise<DataSetSummary[]> {
  const { data } = await http.get<DataSetSummary[]>('/data-sets', { params })
  return data
}

export async function getDataSet(datasetId: string): Promise<DataSet> {
  const { data } = await http.get<DataSet>(`/data-sets/${datasetId}`)
  return data
}

export async function createDataSet(
  caseId: string, draft: DataSetDraft,
): Promise<DataSet> {
  const { data } = await http.post<DataSet>(`/cases/${caseId}/data-sets`, draft)
  return data
}

export async function updateDataSet(
  datasetId: string, draft: DataSetDraft,
): Promise<DataSet> {
  const { data } = await http.put<DataSet>(`/data-sets/${datasetId}`, draft)
  return data
}

export async function deleteDataSet(datasetId: string): Promise<void> {
  await http.delete(`/data-sets/${datasetId}`)
}

// ── run ────────────────────────────────────────────────────────
export interface RunRequest {
  caseId: string
  dataSetIds: string[]
  env: RunEnv
  auth?: string
  retry?: { maxAttempts: number; intervalMs: number }
}

export async function runCase(req: RunRequest): Promise<{ runId: string }> {
  const { data } = await http.post<{ runId: string }>('/runs', req)
  return data
}

export async function listEnvs(): Promise<RunEnv[]> {
  const { data } = await http.get<RunEnv[]>('/envs')
  return data
}

// ── plate /convert 预校验 + 导出 ─────────────────────────────────
export interface PreviewPlateResult {
  ok: boolean
  errors?: Array<{ path: string; message: string }>
  /** Plate /convert  转换后的"可执行"场景结构,导出时直接用它 */
  converted?: Record<string, any> | null
}

export async function previewPlateDraft(draft: ScenarioDraft): Promise<PreviewPlateResult> {
  const { data } = await http.post<PreviewPlateResult>(
    '/scenarios/preview-plate', draft,
  )
  return data
}

// ── endpoint catalog (proxy → Plate /api/endpoint/{id}/full) ────────
export interface IOFieldBinding {
  name: string
  path: string
  required: boolean
  default: any
  example: any
  description: string
  enum: any[] | null
  ui_kind: 'text' | 'number' | 'boolean' | 'select' | 'textarea' | 'json' | 'file' | 'binary' | 'unknown'
  source_kind: 'independent' | 'lookup' | 'generated'
}

export interface EndpointFull {
  id: string
  system: string
  service: string
  name: string
  description: string
  api: {
    service: string
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
    path: string
    headers: Record<string, string>
    timeout_seconds: number
    auth: string
    produces: string[]
    consumes: string[]
  }
  request: {
    body_type: 'none' | 'json' | 'form' | 'multipart' | 'raw' | 'binary'
    fields: IOFieldBinding[]
  }
  responses: Record<string, {
    status: number
    description: string
    fields: IOFieldBinding[]
    assertable_fields: string[]
  }>
  metadata: {
    module: string
    tags: string[]
    owner: string
    preconditions: string[]
    success_criteria: string
    failed_criteria: string[]
    business_notes: string
  }
  version: string
}

export async function getFullEndpoint(endpointId: string): Promise<EndpointFull> {
  const { data } = await http.get<EndpointFull>(`/endpoint-catalog/${encodeURIComponent(endpointId)}/full`)
  return data
}
