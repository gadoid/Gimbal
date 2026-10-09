/**
 * suites.ts — suite 成员层 API client(权限域二期 P1,
 * 《Suite成员层、引用分享与浏览镜头-设计方案》§9 的 P1 子集:
 * CRUD + 成员管理 + 聚合模式运行 + 反查;publish/分享随 P2)。
 */
import http from '@/api/http'

export interface SuiteSummary {
  suiteId: number
  name: string
  description: string
  visibility: string
  mode: string
  memberCount: number
  createdAt: string | null
  updatedAt: string | null
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
  sort: number
  addedAt: string | null
}

export interface SuiteDetail extends SuiteSummary {
  members: SuiteMemberItem[]
}

export interface SuiteRunResult {
  batchId: string
  started: number[]
  skipped: { scenarioId: string; reason: string }[]
  dispatchWarnings: {
    scenarioId: string; executionId: number; message: string
  }[]
  totalRuns: number
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
  page?: number
  page_size?: number
}): Promise<SuitePage> {
  const { data } = await http.get<SuitePage>('/suites', { params })
  return data
}

export async function createSuite(body: {
  name: string
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
  suiteId: number, body: { name?: string; description?: string },
): Promise<SuiteSummary> {
  const { data } = await http.patch<SuiteSummary>(`/suites/${suiteId}`, body)
  return data
}

export async function deleteSuite(suiteId: number): Promise<void> {
  await http.delete(`/suites/${suiteId}`)
}

export async function addSuiteMembers(
  suiteId: number, scenarioIds: string[],
): Promise<SuiteDetail> {
  const { data } = await http.post<SuiteDetail>(
    `/suites/${suiteId}/members`, { scenarioIds })
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

/** 聚合模式运行(§6.6):循环分发 + batch_id 归并;409 附在途批次。 */
export async function runSuite(suiteId: number): Promise<SuiteRunResult> {
  const { data } = await http.post<SuiteRunResult>(`/suites/${suiteId}/run`, {})
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
