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
  ScenarioDraft, DataSetDraft,
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

export async function deleteDataSet(datasetId: string): Promise<void> {
  await http.delete(`/data-sets/${enc(datasetId)}`)
}

// ── run ────────────────────────────────────────────────────────
/** service → {authAlias?, url?} 绑定(spec §3.1/§5),与后端 ServiceBinding 同形 */
export interface ServiceBinding {
  authAlias?: string
  url?: string
}

/** 场景级运行方案(orchestration sidecar,plate 零感知,spec §3.1;
 *  envId 已随 D2 退役) */
export interface RunScheme {
  name: string
  dataSetIds: string[]
  serviceBindings: Record<string, ServiceBinding>
  /** 预埋(gimbal 就绪前 no-op) */
  plugins?: unknown
  logSub?: unknown
}

/** 运行方案覆盖层:RunDialog 上次运行回填 / 按方案导出共用(spec §8;
 *  envId 已随 D2 退役) */
export interface RunOverlay {
  dataSetIds?: string[]
  serviceBindings?: Record<string, ServiceBinding>
}

/** 执行配方(recipe):Case 层解散后 RunRequest 即配方本身,直接挂 scenario */
export interface RunRequest {
  scenarioId: string
  /** D12:空数组合法 = 基线执行(一个隐式空覆盖行);非空 = 选中数据集 */
  dataSetIds: string[]
  /** service → {authAlias?, url?} 绑定:注入清单 = 模板扫描(steps 里的
   * ${auth.*} 引用)∪ 绑定 authAlias;绑定 url 物化进 services(显式绑定
   * 最优先)。旧 auths/injectCredentials/prefix/mergePolicy 已退役(spec §6) */
  serviceBindings?: Record<string, ServiceBinding>
  /** V1 能力移植:0-based 含端点,透传引擎 halt_at,在该步后停 */
  stepTo?: number
  /** M1 执行能力:每行数据的重复执行次数(total = Σrows × nRuns) */
  nRuns?: number
  /** M1 执行能力:fan-out 并发度(1–200) */
  parallel?: number
}

export interface RunScenarioResult {
  runId: string
  /** Numeric Execution row — the only id with a detail route. */
  executionId?: number
}

export async function runScenario(req: RunRequest): Promise<RunScenarioResult> {
  const { data } = await http.post<RunScenarioResult>('/runs', req)
  return data
}

/** PUT 场景级运行方案(整表替换);返回落库后的完整列表 */
export async function putRunSchemes(scenarioId: string, schemes: RunScheme[]): Promise<RunScheme[]> {
  const { data } = await http.put<RunScheme[]>(`/scenarios/${enc(scenarioId)}/run-schemes`, { schemes })
  return data
}

// ── plate /convert 预校验 + 导出 ─────────────────────────────────
export interface PreviewPlateResult {
  ok: boolean
  errors?: Array<{ path: string; message: string }>
  /** Plate /convert  转换后的"可执行"场景结构,导出时直接用它 */
  converted?: Record<string, any> | null
}

/** 预校验/导出转换;overlay(按方案导出,spec §8)不传 → 凭证/服务绑定
 *  零注入,carry 物化无条件(spec §4.3 勘误) */
export async function previewPlateDraft(
  draft: ScenarioDraft, overlay?: RunOverlay,
): Promise<PreviewPlateResult> {
  const { data } = await http.post<PreviewPlateResult>(
    '/scenarios/preview-plate',
    overlay ? { ...draft, overlay } : draft,
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

/** B1 路径推断候选(plate resolve-paths: 响应样本 → JSONPath,数组出下标) */
export interface ResponsePathCandidate {
  path: string
  depth: number
  extracted_by_default: boolean
}

/** 响应样本 → 候选 JSONPath(plate 域 `$.…`)— 策略路径字段点选用 */
export async function resolveResponsePaths(sample: unknown): Promise<ResponsePathCandidate[]> {
  const { data } = await http.post<ResponsePathCandidate[]>(
    '/endpoint-catalog/resolve-paths',
    { response_body_sample: sample },
  )
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
