/**
 * api/admin.ts — admin 查询面(P2-3 审计日志)。
 */
import http from '@/api/http'

export interface AuditLogRow {
  id: number
  actorId: number | null
  actorName: string
  action: string
  resourceType: string | null
  resourceId: string | null
  detail: Record<string, unknown>
  createdAt: string
}

export interface AuditLogPage {
  items: AuditLogRow[]
  total: number
  page: number
  pageSize: number
  actions: string[]
}

export function listAuditLogs(params?: {
  action?: string
  page?: number
  page_size?: number
}): Promise<AuditLogPage> {
  return http
    .get<AuditLogPage>('/admin/audit-logs', { params })
    .then((r) => r.data)
}

// ── 凭证治理阶段 3:清账向导盘点(admin 只读)────────────────────
/** 带未登记身份引用的场景行(保存/导入闸同一提取器口径)。 */
export interface CleanupUnregisteredRow {
  scenarioId: string
  name: string
  owner: string
  projectId: number | null
  refs: string[]
}

/** 明文快照场景行(键名 only —— 值不出任何面);referencedKeys =
 *  被步骤引用的键,须先登记同名条目再清快照。 */
export interface CleanupSnapshotRow {
  scenarioId: string
  name: string
  owner: string
  keys: string[]
  referencedKeys: string[]
}

/** 绑定换用目标未登记的运行方案行。 */
export interface CleanupBindingRow {
  schemeId: string
  scenarioId: string
  name: string
  unregisteredTargets: string[]
}

/** 清账向导盘点(三面全空 = 可切 enforce;拍板:清账完成即切)。 */
export interface CleanupSurvey {
  gateMode: 'off' | 'audit' | 'enforce'
  registrySize: number
  unregistered: CleanupUnregisteredRow[]
  snapshots: CleanupSnapshotRow[]
  bindings: CleanupBindingRow[]
}

/** GET /admin/cleanup-survey(阶段 3;零写面 —— 登记走 /service-aliases,
 *  清快照走属主保存链,W3 admin 无旁路)。 */
export function fetchCleanupSurvey(): Promise<CleanupSurvey> {
  return http.get<CleanupSurvey>('/admin/cleanup-survey').then((r) => r.data)
}
