/**
 * api/scenario-composer.ts — 场景编排 API client
 *
 * 提供 scenarios / data-sets 两个领域的 REST 调用。
 * 请求路径对齐 Plate V3.2 的资源命名（snake_case + s 复数）。
 * Case 层已解散 — RunRequest 即执行配方,直接挂 scenario。
 */
import http from '@/api/http'
import type {
  Scenario, DataSet, DataSetSummary,
  ScenarioDraft, DataSetDraft, RunEnv,
} from '@/types/scenario-composer'
import type {
  EndpointFullView, StrategyKindView, StrategyKindDetailView,
} from '@/types/plate'

// ── scenarios ────────────────────────────────────────────────
export async function listScenarios(params: {
  q?: string; system?: string; module?: string; priority?: number;
  /** P1 读侧收紧后的分桶过滤:public=仅公共;private=仅私有(自己的) */
  visibility?: 'public' | 'private';
}): Promise<Scenario[]> {
  const { data } = await http.get<Scenario[]>('/scenarios', { params })
  return data
}

export async function getScenario(scenarioId: string): Promise<Scenario> {
  const { data } = await http.get<Scenario>(`/scenarios/${enc(scenarioId)}`)
  return data
}

// ── URL encoding policy ──────────────────────────────────────────
// ids ride real path segments, so encodeURI (keeps "/") —
// raw interpolation breaks on spaces / non-ASCII ids.
function enc(id: string): string {
  return encodeURI(id)
}

export async function getScenarioDraft(scenarioId: string): Promise<ScenarioDraft> {
  const { data } = await http.get<ScenarioDraft>(`/scenarios/${enc(scenarioId)}/draft`)
  return data
}

export async function createScenario(draft: ScenarioDraft): Promise<Scenario> {
  const { data } = await http.post<Scenario>('/scenarios', draft)
  return data
}

export async function updateScenario(
  scenarioId: string, draft: ScenarioDraft,
): Promise<Scenario> {
  const { data } = await http.put<Scenario>(`/scenarios/${enc(scenarioId)}`, draft)
  return data
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  await http.delete(`/scenarios/${enc(scenarioId)}`)
}

export async function starScenario(
  scenarioId: string, starred: boolean,
): Promise<void> {
  await http.post(`/scenarios/${enc(scenarioId)}/star`, { starred })
}

// ── 发布 / 下架 / 复制(P1:取代 V1 公共库能力)─────────────────
export async function publishScenario(scenarioId: string): Promise<Scenario> {
  const { data } = await http.post<Scenario>(`/scenarios/${enc(scenarioId)}/publish`)
  return data
}

export async function unpublishScenario(scenarioId: string): Promise<Scenario> {
  const { data } = await http.post<Scenario>(`/scenarios/${enc(scenarioId)}/unpublish`)
  return data
}

/** 深拷贝场景+数据集到自己名下(新 id,恒 private) */
export async function copyScenario(scenarioId: string): Promise<Scenario> {
  const { data } = await http.post<Scenario>(`/scenarios/${enc(scenarioId)}/copy`)
  return data
}

// ── data-sets ─────────────────────────────────────────────────
export async function listDataSets(params: {
  scenarioId?: string;
}): Promise<DataSetSummary[]> {
  const { data } = await http.get<DataSetSummary[]>('/data-sets', { params })
  return data
}

export async function getDataSet(datasetId: string): Promise<DataSet> {
  const { data } = await http.get<DataSet>(`/data-sets/${enc(datasetId)}`)
  return data
}

export async function createDataSet(
  scenarioId: string, draft: DataSetDraft,
): Promise<DataSet> {
  const { data } = await http.post<DataSet>(`/scenarios/${enc(scenarioId)}/data-sets`, draft)
  return data
}

export async function updateDataSet(
  datasetId: string, draft: DataSetDraft,
): Promise<DataSet> {
  const { data } = await http.put<DataSet>(`/data-sets/${enc(datasetId)}`, draft)
  return data
}

// ── run ────────────────────────────────────────────────────────
/** 执行配方(recipe):Case 层解散后 RunRequest 即配方本身,直接挂 scenario */
export interface RunRequest {
  scenarioId: string
  dataSetIds: string[]
  env: RunEnv
  /** 执行用认证 alias 多选(原 auth 单选已废);dispatcher 解密注入 Config.users */
  auths?: string[]
  retry?: { maxAttempts: number; intervalMs: number }
  /** V1 能力移植:0-based 含端点,透传引擎 halt_at,在该步后停 */
  stepTo?: number
  /** V1 能力移植:false = 跳过执行凭证解析/注入 */
  injectCredentials?: boolean
  /** M1 执行能力:每行数据的重复执行次数(total = Σrows × nRuns) */
  nRuns?: number
  /** M1 执行能力:fan-out 并发度(1–200) */
  parallel?: number
  /** M1 执行能力:提单号前缀,注入 vars.order_no / order_no_prefix / seq */
  prefix?: string
  /** M1 执行能力:执行认证合并策略(override|merge|append) */
  mergePolicy?: 'override' | 'merge' | 'append'
}

export interface RunCaseResult {
  runId: string
  /** Numeric Execution row — the only id with a detail route. */
  executionId?: number
}

export async function runScenario(req: RunRequest): Promise<RunCaseResult> {
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
