/** integration.ts — 外部系统集成 P1(功能/模板 + 批量卡片 + 平台凭证)。 */
import http from '@/api/http'

export interface IntegrationInstance {
  state: 'idle' | 'running' | 'paused' | 'none' | 'removed'
  enabled: boolean
  lastStatus: string
  lastRunAt: string | null
  lastError: string
  pausedReason: string
  nextRunAt: string | null
  failStreak: number
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
}

export interface FunctionCardData {
  id: string
  name?: string
  state?: string
  enabled?: boolean
  lastStatus?: string
  lastRunAt?: string | null
  lastError?: string
  cronText?: string
  identityMode?: string
  stale?: boolean
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

/** 409/422 detail 提取(集成路由统一 {code, message} 信封)。 */
export function integrationErr(e: unknown): string {
  const resp = (e as { response?: { data?: unknown } })?.response
  const det = resp?.data as { detail?: { message?: string } | string } | undefined
  if (typeof det?.detail === 'string') return det.detail
  return det?.detail?.message || (e as Error).message
}
