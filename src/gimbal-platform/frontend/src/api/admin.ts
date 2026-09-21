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
