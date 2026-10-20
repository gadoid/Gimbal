/** integration.ts — 外部系统集成 P1(功能/模板 + 批量卡片 + 平台凭证)。 */
import http from '@/api/http'

export interface IntegrationInstance {
  state: 'idle' | 'running' | 'paused' | 'none' | 'removed'
  enabled: boolean
  lastRunAt: string | null
  lastError: string
  pausedReason: string
  nextRunAt: string | null
  failStreak: number
  /** 集成线 v2(I2 双出过渡):运行状态 × 检查结论分立 */
  runStatus: string
  checkStatus: string
  checkMessage: string
  checkChangedAt: string | null
  /** W0b④:缺失别名全集(与执行期暂停判定同口径 = 任一缺失即列) */
  missingCredentials?: string[]
}

export interface IntegrationTaskItem {
  id: number
  name: string
  ownerId: number
  mine: boolean
  canManage: boolean
  visibility: string
  identityMode: string
  targetType: string
  scenarioId: string | null
  suiteId: number | null
  schemeId: string | null
  targetSystem: string
  triggerCron: string
  cronText: string
  resultPolicy: string
  cardTemplate: string
  removed: boolean
  instance: IntegrationInstance | null
  /** W0b④:消费面字段(创建/列表/订阅回显) */
  authAliases?: string[]
  subscribed?: boolean
}

export interface FunctionCardData {
  id: string
  name?: string
  state?: string
  enabled?: boolean
  lastRunAt?: string | null
  lastError?: string
  cronText?: string
  identityMode?: string
  stale?: boolean
  /** Y4:卡片输出投影(output_mapping 投影/空 mapping = 全量;已脱敏) */
  outputs?: Record<string, unknown>
  /** Y4:模板(status|kv|counter|list;缺省 status) */
  cardTemplate?: string
  /** 集成线 v2(I2):run/check 分立出参 */
  runStatus?: string
  checkStatus?: string
  checkMessage?: string
  checkChangedAt?: string | null
  /** 暂停原因(D13 角标:auth_failed/missing_credential;
   * W2:template_changed/made_private/manual;W4:fail_streak) */
  pausedReason?: string
  /** W4:连续失败计数(fail_streak 暂停门面显示「N 次」) */
  failStreak?: number
  /** W4:当前用户可管理该模板(owner;平台模式含 admin)—— 平台卡
   * fail_streak/manual 门面的「启动」仅对管理者渲染 */
  canManage?: boolean
  /** W0b④/W3:缺失别名全集(角标跳转「我的凭证」定位用) */
  missingCredentials?: string[]
}

/** ── 集成线 v2(I3,方案 §2.5):run/check 人话映射(卡片与集成中心共用)── */

/** 运行状态角标文案;ok = 无角标(主结论直接呈现) */
export const RUN_BADGE_TEXT: Record<string, string> = {
  ok: '运行正常',
  auth: '凭证失效',
  timeout: '超时',
  transport: '网络异常',
  contract: '契约不符',
  channel: '通道故障',
}

/** 检查结论文案(主状态灯:pass 绿 / fail 红 / none 无灯 / unknown 灰) */
export const CHECK_TEXT: Record<string, string> = {
  pass: '检查通过',
  fail: '检查不通过',
  none: '无断言',
  unknown: '结论未知',
}

/** run ≠ ok 即运行异常(主结论置灰 + 角标 + lastError 摘要) */
export function runAbnormalOf(runStatus?: string | null): boolean {
  return !!runStatus && runStatus !== 'ok'
}

export async function listIntegrationTasks(): Promise<IntegrationTaskItem[]> {
  const { data } = await http.get<{ items: IntegrationTaskItem[] }>(
    '/integration/tasks')
  return data.items
}

export async function createIntegrationTask(body: {
  name: string
  scenarioId: string
  schemeId?: string | null
  identityMode?: string
  triggerCron?: string
  resultPolicy?: string
  visibility?: string
  targetSystem?: string
}): Promise<IntegrationTaskItem> {
  const { data } = await http.post<IntegrationTaskItem>(
    '/integration/tasks', body)
  return data
}

export async function patchIntegrationTask(
  id: number, body: Record<string, unknown>,
): Promise<IntegrationTaskItem> {
  const { data } = await http.patch<IntegrationTaskItem>(
    `/integration/tasks/${id}`, body)
  return data
}

export async function deleteIntegrationTask(id: number): Promise<void> {
  await http.delete(`/integration/tasks/${id}`)
}

export async function runIntegrationTask(id: number): Promise<{
  result: { status: string; durationMs: number; error: string }
  instance: IntegrationInstance
}> {
  const { data } = await http.post(`/integration/tasks/${id}/run`)
  return data
}

export async function fetchFunctionCards(
  ids: string[],
): Promise<FunctionCardData[]> {
  const { data } = await http.post<{ items: FunctionCardData[] }>(
    '/integration/cards', { ids })
  return data.items
}

// ── W1(个人侧方案 §2):创建前置预览 ────────────────────────────
export interface ScenarioPreview {
  /** 场景+方案所需凭证别名(方案 authAlias ∪ ${auth.*}) */
  authAliases: string[]
  /** 当前用户「我的凭证」中缺失的别名(任一缺失即列) */
  missingCredentials: string[]
  /** 场景声明 working(预览执行)—— 集成任务会拒绝触发 */
  workingPreview: boolean
}

export async function fetchScenarioPreview(
  scenarioId: string, schemeId?: string | null,
): Promise<ScenarioPreview> {
  const { data } = await http.get<ScenarioPreview>(
    '/integration/scenario-preview',
    { params: { scenarioId, ...(schemeId ? { schemeId } : {}) } })
  return data
}

// ── 平台凭证(admin)────────────────────────────────────────────
export interface PlatformCredential {
  id: number
  alias: string
  url: string
  username: string
  tokenType: string
  expiresIn: number
}

export async function listPlatformCredentials(): Promise<PlatformCredential[]> {
  const { data } = await http.get<{ items: PlatformCredential[] }>(
    '/integration/platform-credentials')
  return data.items
}

export async function createPlatformCredential(body: {
  alias: string; url?: string; username: string; password: string
  tokenType?: string; expiresIn?: number
}): Promise<{ id: number; alias: string }> {
  const { data } = await http.post(
    '/integration/platform-credentials', body)
  return data
}

export async function deletePlatformCredential(id: number): Promise<void> {
  await http.delete(`/integration/platform-credentials/${id}`)
}

// ── W2(个人侧方案 §2):订阅 / 自管 ─────────────────────────────

export interface SubscriptionSummary {
  fingerprint: string
  steps: {
    service: string
    method: string
    path: string
    endpoint: string | null
    readonly: boolean
  }[]
  authAliases: string[]
  baseUrls: Record<string, string>
  datasetName: string | null
  cron: string
}

export async function fetchSubscriptionSummary(
  id: number,
): Promise<SubscriptionSummary> {
  const { data } = await http.get<SubscriptionSummary>(
    `/integration/tasks/${id}/subscription-summary`)
  return data
}

export async function subscribeIntegrationTask(
  id: number,
  /** P2.2:摘要返回的 fingerprint(必填)—— 服务端与当前内容比对,
   * 不一致 409 consent_stale(确认的必须是看到的那份内容);
   * 不带指纹的订阅没有「知情」凭据,服务端 422。 */
  fingerprint: string,
): Promise<IntegrationTaskItem> {
  const { data } = await http.post<IntegrationTaskItem>(
    `/integration/tasks/${id}/subscribe`, { fingerprint })
  return data
}

export async function unsubscribeIntegrationTask(id: number): Promise<void> {
  await http.delete(`/integration/tasks/${id}/subscription`)
}

export async function pauseMySubscription(
  id: number,
): Promise<IntegrationTaskItem> {
  const { data } = await http.post<IntegrationTaskItem>(
    `/integration/tasks/${id}/subscription/pause`)
  return data
}

export async function resumeMySubscription(
  id: number,
): Promise<IntegrationTaskItem> {
  const { data } = await http.post<IntegrationTaskItem>(
    `/integration/tasks/${id}/subscription/resume`)
  return data
}

/** 409/422 detail 提取(集成路由统一 {code, message} 信封)。 */
export function integrationErr(e: unknown): string {
  const resp = (e as { response?: { data?: unknown } })?.response
  const det = resp?.data as { detail?: { message?: string } | string } | undefined
  if (typeof det?.detail === 'string') return det.detail
  return det?.detail?.message || (e as Error).message
}

/** detail.code 提取(P2.2 订阅 409 consent_stale 分支处理用)。 */
export function integrationErrCode(e: unknown): string | undefined {
  const resp = (e as { response?: { data?: unknown } })?.response
  const det = resp?.data as { detail?: { code?: string } | string } | undefined
  return typeof det?.detail === 'object' ? det.detail?.code : undefined
}
