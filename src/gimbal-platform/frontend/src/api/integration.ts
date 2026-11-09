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
  /** authz M2a S8:实例凭证来源('project' = 项目凭证;personal = 持有人) */
  credentialSource?: string
}

export interface IntegrationTaskItem {
  id: number
  name: string
  ownerId: number
  mine: boolean
  canManage: boolean
  visibility: string
  /** S7.0:所属项目 id(public = 公共项目 / 普通项目;null = 私有) */
  projectId?: number | null
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
  /** webhook v4:注册令牌(管理者视角;公共模板对非属主隐藏) */
  tokenId?: number | null
  tokenName?: string | null
  tokenKind?: string | null
  clientRef?: string | null
  /** authz M2a S8:普通项目模板可选凭证来源(项目 / 个人) */
  projectCredentialsAvailable?: boolean
}

export interface FunctionCardData {
  id: string
  name?: string
  state?: string
  enabled?: boolean
  lastRunAt?: string | null
  lastError?: string
  cronText?: string
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
  /** 暂停原因(§3.3 全集):auth_failed/missing_credential/
   * template_changed/made_private/manual/fail_streak/scope_denied/
   * token_revoked/token_invalidated/token_expired/
   * token_owner_ineligible/resource_not_allowed —— 令牌类暂停各有
   * 专属恢复路径(续期/重新生成自动恢复;吊销先解绑)。 */
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

/** S7.0:?projectId = 项目详情「集成任务」页签(可见性按成员收口)。 */
export async function listIntegrationTasks(
  projectId?: number,
): Promise<IntegrationTaskItem[]> {
  const { data } = await http.get<{ items: IntegrationTaskItem[] }>(
    '/integration/tasks', { params: projectId != null ? { projectId } : undefined })
  return data.items
}

/** 集成详情(webhook v4 §8 原型 IntegrationDetail):GET /tasks/{id}
 *  出参与列表行同构(_tpl_out_full),含 instance/authAliases/
 *  missingCredentials/tokenId/tokenName。 */
export async function getIntegrationTask(
  id: number | string,
): Promise<IntegrationTaskItem> {
  const { data } = await http.get<IntegrationTaskItem>(`/integration/tasks/${id}`)
  return data
}

export async function createIntegrationTask(body: {
  name: string
  scenarioId: string
  schemeId?: string | null
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
  /** 场景+方案所需凭证槽位(${auth.*} 扫描 ∪ 生效别名声明槽位;S6) */
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
  /** authz M2a S8:凭证来源(仅普通项目模板可选 project —— 项目集成
   * 默认用项目凭证;personal = 持有人个人凭证;缺省 = 建新实例按模板
   * 缺省,已有实例不变) */
  credentialSource?: 'personal' | 'project',
): Promise<IntegrationTaskItem> {
  const { data } = await http.post<IntegrationTaskItem>(
    `/integration/tasks/${id}/subscribe`,
    credentialSource ? { fingerprint, credentialSource } : { fingerprint })
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
