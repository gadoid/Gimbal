/**
 * api/activity.ts — 工作台活动时间线(M5-3 服务端合流)。
 *
 * 三源(我的执行 / 我的场景改动 / 触碰我场景的适配批次)由后端一次
 * 合流,前端只做文案映射与日历分组。sources 报告各源是否取到。
 */
import http from '@/api/http'

export interface ActivityEventIn {
  kind: 'execution' | 'scenario' | 'adaptation'
  at: string
  executionId?: number | null
  status?: string | null
  scenarioId?: string | null
  name?: string | null
  module?: string | null
  batchId?: string | null
  fromVersion?: string | null
  toVersion?: string | null
  endpointId?: string | null
  opCount?: number | null
}

export interface ActivityReport {
  events: ActivityEventIn[]
  sources: Record<string, boolean>
}

export function getActivity(limit = 40): Promise<ActivityReport> {
  return http
    .get<ActivityReport>('/activity', { params: { limit } })
    .then((r) => r.data)
}
