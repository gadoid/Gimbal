/**
 * api/scenario-composer.ts — 场景编排 API client
 *
 * 与现有 cases.ts 同等级别，提供 scenarios / cases / data-sets 三个领域
 * 的 REST 调用。请求路径对齐 Plate V3.2 的资源命名（snake_case + s 复数）。
 */
import http from '@/api/http'
import type {
  Scenario, Case, DataSet, DataSetSummary,
  ScenarioDraft, DataSetDraft, RunEnv,
} from '@/types/scenario-composer'
import type {
  EndpointFullView, StrategyKindView, StrategyKindDetailView,
} from '@/types/plate'

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
  /** 执行用认证 alias 多选(原 auth 单选已废);dispatcher 解密注入 Config.users */
  auths?: string[]
  retry?: { maxAttempts: number; intervalMs: number }
}

export interface RunCaseResult {
  runId: string
  /** Numeric Execution row — the only id with a detail route. */
  executionId?: number
}

export async function runCase(req: RunRequest): Promise<RunCaseResult> {
  const { data } = await http.post<RunCaseResult>('/runs', req)
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
//
// 端点契约类型(EndpointFullView / IOFieldBinding / ...)已收敛到 @/types/plate,
// 它是 plate 对外契约的前端完整结构表述;本文件不再重复声明。
// 详见 @/types/plate.ts 头注释。

export async function getFullEndpoint(endpointId: string): Promise<EndpointFullView> {
  const { data } = await http.get<EndpointFullView>(`/endpoint-catalog/${encodeURIComponent(endpointId)}/full`)
  return data
}

// ── strategy catalog (proxy → Plate /api/strategy 语法 dim) ────────
//
// 策略语法(M6 第 8 dim)的引用数据:哪些 kind、每个 kind 哪些字段。
// 只用于"添加策略"的结构渲染,不进 draft —— 策略实例是 StepView.strategy。

export async function listStrategyKinds(): Promise<StrategyKindView[]> {
  const { data } = await http.get<StrategyKindView[]>('/strategy-catalog')
  return data
}

export async function getStrategyKindFull(kind: string): Promise<StrategyKindDetailView> {
  const { data } = await http.get<StrategyKindDetailView>(`/strategy-catalog/${encodeURIComponent(kind)}/full`)
  return data
}
