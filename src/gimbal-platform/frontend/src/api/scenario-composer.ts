/**
 * api/scenario-composer.ts — 场景编排 API client
 *
 * 提供 scenarios / data-sets 两个领域的 REST 调用。
 * 请求路径对齐 Plate V3.2 的资源命名（snake_case + s 复数）。
 * Case 层已解散 — RunRequest 即执行配方,直接挂 scenario。
 */
import http from '@/api/http'
import { sanitizeEndpointFull } from '@/utils/declarations'
import type {
  Scenario, ScenarioOptionsPage, ScenarioPage,
  ScenarioDraft, DataSet, DataSetDraft, DataSetSummary,
} from '@/types/scenario-composer'
import type {
  EndpointFullView, StrategyKindView, StrategyKindDetailView,
} from '@/types/plate'

// ── scenarios ────────────────────────────────────────────────
/** 列表筛选参数(M1 服务端化):多值维度收逗号联合字符串(与后端口径
 *  一致:system/tag=OR 携带,module/author/priority=精确命中其一)。 */
export interface ScenarioListParams {
  q?: string
  system?: string
  module?: string
  priority?: string
  tag?: string
  author?: string
  visibility?: 'public' | 'private'
  updatedWithin?: '24h' | '7d' | '30d'
  /** 关注页/关注卡数据源(store 退位后 ?starred=true 服务端过滤)。 */
  starred?: boolean
  page?: number
  page_size?: number
}

export async function listScenarios(
  params: ScenarioListParams,
): Promise<ScenarioPage> {
  const { data } = await http.get<ScenarioPage>('/scenarios', { params })
  return data
}

// ── facets(五维可选值+计数,M3)─────────────────────────────────
/** priorities 的 value 是数字,其余维度是字符串。 */
export type ScenarioFacetValue = { value: string | number; count: number }
export interface ScenarioFacets {
  modules: ScenarioFacetValue[]
  systems: ScenarioFacetValue[]
  tags: ScenarioFacetValue[]
  authors: ScenarioFacetValue[]
  priorities: ScenarioFacetValue[]
}

/** M5 bulk 信号(债 12):关注页每对象 2 请求的 N+1 消除。 */
export interface ScenarioSignal {
  trend: string[]
  lastRun: { status: string; at: string | null } | null
  schemeCount: number
  defaultSchemeName: string | null
}

export async function fetchScenarioSignals(ids: string[]): Promise<
  Record<string, ScenarioSignal>
> {
  const { data } = await http.get<{ signals: Record<string, ScenarioSignal> }>(
    '/scenarios/signals', { params: { ids: ids.join(',') } })
  return data.signals
}

/** GET /scenarios/facets — FilterPopover 维度可选值的服务端数据源
 *  (GROUP BY 聚合,替代「当前页 uniq 池」的 M1 过渡形态)。 */
export async function fetchScenarioFacets(params: {
  q?: string
  visibility?: 'public' | 'private'
}): Promise<ScenarioFacets> {
  const { data } = await http.get<ScenarioFacets>('/scenarios/facets', { params })
  return data
}

/** ``?fields=options`` 轻量形态:选择器与名称映射(Runner picker /
 *  OpConstructDialog / 台账场景名),砍掉「为拿名字拉全量场景表」。 */
export async function listScenarioOptions(params?: {
  page?: number
  page_size?: number
  /** G2:选择器检索下推(场景过百后第 101 条仍可选到;吃 trgm)。 */
  q?: string
}): Promise<ScenarioOptionsPage> {
  const { data } = await http.get<ScenarioOptionsPage>('/scenarios', {
    params: { ...(params ?? {}), fields: 'options' },
  })
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

/** 深拷贝场景+数据集到自己名下(新 id,恒 private)。
 * F2(2026-09-23)另存为:带 name = 自定义副本名,与本人已有场景重名 →
 * 409 code='name_taken',ApiError.detail.suggestion 为计数后缀建议;
 * 不传 name = 旧「(副本)」后缀行为。 */
export async function copyScenario(
  scenarioId: string, name?: string,
): Promise<Scenario> {
  const { data } = await http.post<Scenario>(
    `/scenarios/${enc(scenarioId)}/copy`, name ? { name } : undefined)
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
/** service → {authAlias?, url?} 绑定(spec §3.1/§5),与后端 ServiceBinding 同形。
 *  查询凭证唯一来源 = config.users 首键(查询身份 = 执行身份),
 *  与运行方案无关(退场记录见 docs/adr/0003)。 */
export interface ServiceBinding {
  authAlias?: string
  url?: string
}

/** 行级数据集选择(spec v3 §4):datasetId + rowIndexes(0-based,与编辑器
 *  行号一致;缺省/空 = 整库)。RunRequest/SchemeV2 的权威选择键;
 *  旧 dataSetIds 保留为兼容读(两键同发本键优先)。 */
export interface DataSetSelection {
  datasetId: string
  rowIndexes?: number[]
}

/** 运行方案覆盖层:按方案导出(spec §8)— POST /scenarios/preview-plate
 *  的 overlay wire 形状,与后端 ExportOverlay 同形。仅 serviceBindings:
 *  dataSetIds 有意不收(导出是场景级产物,行级展开是非目标)。 */
export interface RunOverlay {
  serviceBindings?: Record<string, ServiceBinding>
}

/** 执行配方(recipe):Case 层解散后 RunRequest 即配方本身,直接挂 scenario */
export interface RunRequest {
  scenarioId: string
  /** 溯源(方案工作台阶段③,Task 1 后端已接受):本次执行按哪个方案发起 —
   *  默认/自建两态都带(wire camelCase) */
  schemeId?: string
  schemeName?: string
  /** D12:空数组合法 = 基线执行(一个隐式空覆盖行);非空 = 选中数据集 */
  dataSetIds: string[]
  /** 行级数据集选择(spec v3 §4)— 权威键;两键同发时本键优先,
   *  dataSetIds 忽略(兼容读保留) */
  dataSetSelection?: DataSetSelection[]
  /** 断言注入条目(spec v2 §5):异常组 — 跑在基线上,与数据集行并列生成
   *  case;缺省 = 不注入。引擎侧展开由后续任务接入。 */
  injectionEntryIds?: string[]
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
  /** 批次键(执行设计 §1.2):执行器队列逐条顺序发起时共用;纯归并键,
   *  不参与分发语义 — 每条仍是独立 execution。单条发起不传。 */
  batchId?: string
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

// ── run schemes(工作台新 CRUD,方案唯一读写面)──────────────────
// 旧 PUT /scenarios/{id}/run-schemes 整表替换端点与 orchestration.runSchemes
// sidecar 已随阶段④清理下线(2026-09)。

/** 方案 wire 形状(阶段② 新 CRUD;阶段③ RunDialog 切换后统一) */
export interface SchemeV2 {
  schemeId: string
  name: string
  isDefault: boolean
  dataSetIds?: string[]
  dataSetSelection: { datasetId: string; rowIndexes?: number[] }[]
  injectionEntryIds: string[]
  serviceBindings: Record<string, ServiceBinding>
  stepTo: number | null
  nRuns: number
  parallel: number
  plugins?: unknown
  logSub?: unknown
}

/** 方案 → 执行配方:把方案锁定的选择/绑定/次数/并发物化成 RunRequest,
 *  供列表页「▶ 执行」直跑(与 RunDialog 装配同源字段,不丢溯源)。 */
export function schemeToRunRequest(scheme: SchemeV2, scenarioId: string): RunRequest {
  return {
    scenarioId,
    schemeId: scheme.schemeId,
    schemeName: scheme.name,
    dataSetIds: scheme.dataSetIds ?? scheme.dataSetSelection.map((d) => d.datasetId),
    dataSetSelection: scheme.dataSetSelection,
    injectionEntryIds: scheme.injectionEntryIds,
    serviceBindings: scheme.serviceBindings,
    stepTo: scheme.stepTo ?? undefined,
    nRuns: scheme.nRuns,
    parallel: scheme.parallel,
  }
}

export async function listRunSchemes(scenarioId: string): Promise<SchemeV2[]> {
  const { data } = await http.get<SchemeV2[]>(`/scenarios/${enc(scenarioId)}/run-schemes`)
  return data
}
export async function createRunScheme(
  scenarioId: string, body: Omit<SchemeV2, 'schemeId' | 'isDefault'>,
): Promise<SchemeV2> {
  const { data } = await http.post<SchemeV2>(
    `/scenarios/${enc(scenarioId)}/run-schemes`, body)
  return data
}
export async function updateRunScheme(
  scenarioId: string, schemeId: string,
  body: Omit<SchemeV2, 'schemeId' | 'isDefault'>,
): Promise<SchemeV2> {
  const { data } = await http.put<SchemeV2>(
    `/scenarios/${enc(scenarioId)}/run-schemes/${enc(schemeId)}`, body)
  return data
}
export async function deleteRunScheme(
  scenarioId: string, schemeId: string,
): Promise<void> {
  await http.delete(`/scenarios/${enc(scenarioId)}/run-schemes/${enc(schemeId)}`)
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

/** plate `/full` 取数 —— **出口消毒**(裁定 C8b):`/full` 是不可信来源,
 *  `request` 与每个 `response` 的 declarations 在此一次消毒 ⇒ **每一个**消费方
 *  (含不经共享缓存的 `CaseComposerCatalog` 浏览面板)按构造拿到**路径可用性**
 *  干净的声明树(保证范围与边界见 `sanitizeDeclarations`;`children` 形状未归一)。
 *  容器内未发生改动时返回原对象(对干净响应零扰动)。 */
export async function getFullEndpoint(endpointId: string): Promise<EndpointFullView> {
  const { data } = await http.get<EndpointFullView>(`/endpoint-catalog/${encodeURIComponent(endpointId)}/full`)
  return sanitizeEndpointFull(data)
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

// ── 字段状态目录:配置编辑校验(2026-09-05 spec §3.5)───────────────

/** 校验裁决:errors 非空 = 拒(合成态树一致性);warnings 仅提示 */
export interface FieldStatesVerdict {
  errors: Array<{ code: string; path: string; message: string }>
  warnings: Array<{ code: string; path: string; message: string }>
}

/**
 * step.field_states 增量 × plate 目录 → 合成态裁决(§3.5)。
 * 编辑器在改字段状态时调用:errors 非空 → 前端门禁拒绝该次写入;
 * warnings(required 落 carry / 备注族进 form / 目录外 stale path)
 * 仅提示。plate 不可达 → 抛错由调用方降级(不阻塞编辑)。
 */
export async function validateEndpointFieldStates(
  endpointId: string,
  fieldStates: Record<string, string>,
): Promise<FieldStatesVerdict> {
  const { data } = await http.post<FieldStatesVerdict>(
    `/endpoint-catalog/${encodeURIComponent(endpointId)}/field-states/validate`,
    { field_states: fieldStates },
  )
  return data
}

// ── strategy catalog (proxy → Plate /api/strategy 语法 dim) ────────
//
// 策略语法(M6 第 8 dim)的引用数据:哪些 kind、每个 kind 哪些字段。
// 只用于"添加策略"的结构渲染,不进 draft —— 策略实例是 StepView.strategy。

// ── 执行器预检(执行设计 §1.6)────────────────────────────────
/** 「这条用例 × 这个方案」预检入参 */
export interface PrecheckItem {
  scenarioId: string
  schemeId: string
}

/** 单条预检结论 — 全部是「这条方案配置」的事实,不是用例状态(§1.4) */
export interface PrecheckResult {
  scenarioId: string
  schemeId: string
  /** false = 场景不可读/不存在(不泄露存在性);此时其余字段无意义 */
  found: boolean
  /** 方案本体存在(被删 → 不可跑,去工作台重建) */
  schemeFound: boolean
  /** 「这个方案跑不了,换一个方案就能跑」— 不是用例禁跑 */
  schemeValid: boolean
  /** 方案引用但已删的数据集 */
  deadDatasetIds: string[]
  /** dispatch 侧同口径判死的注入条目 id(执行时会被跳过) */
  danglingEntryIds: string[]
  /** steps 引用了、但声明 URL 与绑定 URL 双缺的 service */
  unboundServices: string[]
}

/** 批量预检:队列 N 条一次发回判定面(失效判定的服务端唯一实现,§1.6) */
export async function precheckRun(items: PrecheckItem[]): Promise<PrecheckResult[]> {
  const { data } = await http.post<PrecheckResult[]>('/run/precheck', items)
  return data
}

export async function listStrategyKinds(): Promise<StrategyKindView[]> {
  const { data } = await http.get<StrategyKindView[]>('/strategy-catalog')
  return data
}

export async function getStrategyKindFull(kind: string): Promise<StrategyKindDetailView> {
  const { data } = await http.get<StrategyKindDetailView>(`/strategy-catalog/${encodeURIComponent(kind)}/full`)
  return data
}
