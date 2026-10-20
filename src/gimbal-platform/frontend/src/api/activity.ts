/**
 * api/activity.ts — 工作台活动时间线(M5-3 服务端合流)。
 *
 * 三源(我的执行 / 我的场景改动 / 触碰我场景的适配批次)由后端一次
 * 合流,前端只做文案映射与日历分组。sources 报告各源是否取到。
 */
import http from '@/api/http'

export interface ActivityEventIn {
  kind: 'execution' | 'scenario' | 'adaptation' | 'suite' | 'integration'
  at: string
  executionId?: number | null
  status?: string | null
  scenarioId?: string | null
  /** 执行面的用例展示名(快照列;空(历史行)回退 scenarioId)。 */
  scenarioName?: string | null
  name?: string | null
  module?: string | null
  batchId?: string | null
  fromVersion?: string | null
  toVersion?: string | null
  endpointId?: string | null
  opCount?: number | null
  /** F3(2026-09-23):scenario 子动作 edit/rename/save_as/
   * handoff_received;缺省(旧事件)= 按 edit 渲染。 */
  action?: string | null
  /** F3:子动作的结构化数据(oldName/newName/sourceScenarioId/senderName)。 */
  detail?: Record<string, unknown> | null
  /** suite 面(2026-10-20:suite 事件此前只写不读,现并入时间线)。 */
  suiteId?: number | null
  /** integration 面(边沿事件:订阅/暂停/恢复/结论翻转)。 */
  taskId?: number | null
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
