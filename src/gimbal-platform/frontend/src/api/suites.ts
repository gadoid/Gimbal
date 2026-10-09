/**
 * suites.ts — Suite API client(成员层 P1 + 引用分享 P2 + Suite 层重构
 * 第 2 步:composition 整体保存 / 模式分流运行 / 运行记录 / 重跑失败
 * 单元 / 公共复制 / 最近运行摘要)。
 */
import http from '@/api/http'

export type SuiteMode = 'aggregate' | 'chain' | 'fanout' | 'compose'
export type MemberRole = 'main' | 'before' | 'after'

/** 单元设置(mode_config.units.<scenarioId>;编排模式消费)。 */
export interface SuiteUnitConfig {
  ref?: string
  needs?: string[]
  repeat?: number
  nRuns?: number
  schemeId?: string | null
  row?: { datasetId: string; rowIndex: number } | null
  injectionEntryIds?: string[]
  map?: Record<string, string>
}

/** 编排配置(suites.mode_config;draft 标记服务端管理,保存时原样带回)。 */
export interface SuiteModeConfig {
  units?: Record<string, SuiteUnitConfig>
  parallel?: number
  nRuns?: number
  gates?: { metric: string; op: string; value: number }[]
  checks?: { on?: { bracket?: string; refs?: string[] }; strategy?: Record<string, unknown> }[]
  draft?: boolean
  [k: string]: unknown
}

export interface SuiteLatestRun {
  kind: 'suite_graph' | 'batch'
  status?: string
  executionId?: number
  batchId?: string | null
  createdAt?: string | null
  finishedAt?: string | null
  passed?: number
  failed?: number
}

export interface SuiteSummary {
  suiteId: number
  name: string
  description: string
  visibility: string
  mode: string
  memberCount: number
  rev: number
  isDraft: boolean
  createdAt: string | null
  updatedAt: string | null
  latestRun?: SuiteLatestRun | null
}

export interface SuitePage {
  items: SuiteSummary[]
  total: number
  page: number
  pageSize: number
}

export interface SuiteMemberItem {
  scenarioId: string
  name: string
  module: string
  visibility: string
  role: MemberRole
  sort: number
  addedAt: string | null
}

export interface SuiteDetail extends SuiteSummary {
  access: 'owner' | 'admin' | 'ref' | 'public' | null
  canEdit: boolean | null
  canRun: boolean | null
  canShare: boolean | null
  modeConfig: SuiteModeConfig | null
  members: SuiteMemberItem[]
}

/** 聚合模式运行结果(批次通道)。 */
export interface SuiteRunResult {
  batchId: string
  started: number[]
  skipped: { scenarioId: string; reason: string }[]
  dispatchWarnings: {
    scenarioId: string; executionId: number; message: string
  }[]
  totalRuns: number
}

/** 编排模式运行结果(一次编排执行)。 */
export interface SuiteOrchRunResult {
  executionId: number
  batchId: string
  mode: string
  units: number
  estimatedRuns: number
}

export interface CompositionMember {
  scenarioId: string
  role: MemberRole
}

export interface CompositionBody {
  rev: number
  mode: SuiteMode
  members: CompositionMember[]
  modeConfig: SuiteModeConfig
  publishUnpublished?: boolean
}

/** 409 suite_rev_conflict 附最新内容(自动保存冲突合并用)。 */
export interface RevConflict {
  currentRev: number
  latest: SuiteDetail
}

export interface SuiteRunItem {
  executionId?: number
  kind: 'suite_graph' | 'batch' | 'single'
  batchId?: string | null
  mode?: string | null
  status: string
  executions?: number[]
  totalRuns: number
  passed: number
  failed: number
  skipped?: number
  createdAt: string | null
  finishedAt?: string | null
  /** 判定门结论(第 3 步):执行器 gates.evaluated 事件的结构化落账;
   *  {gates: [{metric, op, value, actual, passed}], passed: boolean}。 */
  gatesEvaluated?: {
    gates: { metric: string; op: string; value: number; actual?: number; passed?: boolean }[]
    passed: boolean
  } | null
}

/** 预检条目(第 3 步 /suites/{id}/validate)。 */
export interface ValidateItem {
  level: 'error' | 'warn' | 'ok'
  code: string
  message: string
  units?: string[]
  refs?: string[]
  /** unit = 可直达单元改选;map = 同名输入需改名。 */
  action?: string
}

export interface ValidateOut {
  ok: boolean
  mode: string
  unitCount: number
  estimatedRuns: number
  runCap: number
  gates: number
  degraded: boolean
  inFlight: { batchId: string } | null
  items: ValidateItem[]
}

export interface SuiteLookupItem {
  suiteId: number
  name: string
  memberCount: number
  ownerName: string
}

/** 浏览镜头口径与场景库一致(§5.1):前端默认传 mine。 */
export async function listSuites(params?: {
  scope?: 'mine' | 'all'
  visibility?: 'public'
  page?: number
  page_size?: number
}): Promise<SuitePage> {
  const { data } = await http.get<SuitePage>('/suites', { params })
  return data
}

/** name 省略 = 创建草稿(服务端生成不重名草稿名,画布首次拖入口径)。 */
export async function createSuite(body: {
  name?: string
  description?: string
}): Promise<SuiteSummary> {
  const { data } = await http.post<SuiteSummary>('/suites', body)
  return data
}

export async function getSuite(suiteId: number): Promise<SuiteDetail> {
  const { data } = await http.get<SuiteDetail>(`/suites/${suiteId}`)
  return data
}

export async function patchSuite(
  suiteId: number, body: { name?: string; description?: string; clearDraft?: boolean },
): Promise<SuiteSummary> {
  const { data } = await http.patch<SuiteSummary>(`/suites/${suiteId}`, body)
  return data
}

export async function deleteSuite(suiteId: number): Promise<void> {
  await http.delete(`/suites/${suiteId}`)
}

/** 整体保存(重构方案):模式、成员及顺序、编排配置一次落库;rev 乐观锁。 */
export async function putSuiteComposition(
  suiteId: number, body: CompositionBody,
): Promise<SuiteDetail> {
  const { data } = await http.put<SuiteDetail>(
    `/suites/${suiteId}/composition`, body)
  return data
}

export async function addSuiteMembers(
  suiteId: number, scenarioIds: string[], publishUnpublished = false,
): Promise<SuiteDetail> {
  const { data } = await http.post<SuiteDetail>(
    `/suites/${suiteId}/members`,
    { scenarioIds, publishUnpublished })
  return data
}

export async function reorderSuiteMembers(
  suiteId: number, scenarioIds: string[],
): Promise<SuiteDetail> {
  const { data } = await http.patch<SuiteDetail>(
    `/suites/${suiteId}/members/order`, { scenarioIds })
  return data
}

export async function removeSuiteMember(
  suiteId: number, scenarioId: string,
): Promise<void> {
  await http.delete(`/suites/${suiteId}/members/${encodeURIComponent(scenarioId)}`)
}

/** 运行(模式分流):聚合 → SuiteRunResult(批次);编排 → SuiteOrchRunResult。
 *  control:only = 试跑选中段(单元 ref);toNode = 串联只跑到某一步。 */
export async function runSuite(
  suiteId: number, control?: { only?: string[]; toNode?: string },
): Promise<SuiteRunResult | SuiteOrchRunResult> {
  const { data } = await http.post<SuiteRunResult | SuiteOrchRunResult>(
    `/suites/${suiteId}/run`, control ?? {})
  return data
}

/** 该 Suite 的历次运行(只含本人发起,不变量 2):聚合按批次归并、编排逐条。 */
export async function listSuiteRuns(suiteId: number): Promise<SuiteRunItem[]> {
  const { data } = await http.get<{ items: SuiteRunItem[]; total: number }>(
    `/suites/${suiteId}/runs`)
  return data.items
}

/** 只重跑某次编排执行里失败的单元(control.only 指向失败单元)。 */
export async function rerunFailedUnits(
  suiteId: number, executionId: number,
): Promise<SuiteOrchRunResult> {
  const { data } = await http.post<SuiteOrchRunResult>(
    `/suites/${suiteId}/runs/${executionId}/rerun-failed`)
  return data
}

/** 不入队的预检(第 3 步):服务端权威结论(执行器编译 + 逐成员
 * _precheck_one + 认证别名 + 在途)。 */
export async function validateSuite(suiteId: number): Promise<ValidateOut> {
  const { data } = await http.post<ValidateOut>(`/suites/${suiteId}/validate`)
  return data
}

/** 公共读者「复制到我的」:深拷贝为私有 Suite(含编排配置重映射)。 */
export async function forkPublicSuite(
  suiteId: number,
): Promise<{ suiteId: number; suiteName: string; memberCount: number; mode: string }> {
  const { data } = await http.post(`/suites/${suiteId}/fork`)
  return data
}

/** 场景反查所属 suite(§9)。 */
export async function suitesOfScenario(
  scenarioId: string,
): Promise<SuiteLookupItem[]> {
  const { data } = await http.get<SuiteLookupItem[]>(
    `/scenarios/${encodeURIComponent(scenarioId)}/suites`)
  return data
}

/** P2 §7.9:suite 发布(级联发布未发布成员,回执 publishedMembers)。 */
export async function postSuitePublish(
  suiteId: number,
): Promise<SuiteSummary & { publishedMembers?: string[] }> {
  const { data } = await http.post(`/suites/${suiteId}/publish`)
  return data
}

/** P2 §7.9:suite 下架(成员 public 状态独立保留)。 */
export async function deleteSuitePublish(
  suiteId: number,
): Promise<SuiteSummary> {
  const { data } = await http.delete(`/suites/${suiteId}/publish`)
  return data
}

/** 从 axios 错误里取 409 detail(冲突/在途/上限/发布确认的机器面)。 */
export function suiteErrDetail(e: unknown): {
  code?: string; message?: string; [k: string]: unknown
} | null {
  const resp = (e as { response?: { status?: number; data?: unknown } })
    ?.response
  if (resp && typeof resp.data === 'object' && resp.data !== null) {
    return resp.data as Record<string, unknown>
  }
  return null
}
