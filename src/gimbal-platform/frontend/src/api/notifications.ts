/**
 * notifications.ts — 通知中心 API(P1b/M2.5,权限方案 §3.3)。
 * 三接口 + 按 type 偏好 + 公告;铃铛 30s 轮询 unread-count。
 */
import http from './http'

export type Role = 'user' | 'admin' | 'super_admin'

export interface NotificationItem {
  id: number
  type: string
  title: string
  body: string
  link: string | null
  batchId: string | null
  createdAt: string
  readAt: string | null
}

export interface NotificationList {
  items: NotificationItem[]
  unread: number
  /** 2026-09-23 分页批次:后端 list 升级 page/pageSize/total 信封 */
  total: number
  page: number
  pageSize: number
}

export interface UnreadCount {
  count: number
  /** 角色版本(users.updated_at ISO):与本地快照不同 → refetch me */
  roleVersion: string | null
}

export type SwitchableType =
  | 'execution_finished'
  | 'adaptation_applied'
  | 'announcement'
  | 'scenario_unpublished'
  | 'role_changed'
  | 'resource_transferred'
  // F1(2026-09-23):分发接收提醒(悬浮标签同一数据源;关 = 标签同步消失)。
  // resource_transferred(资源转让)= 所有权转移,留给离职处置线,语义不同。
  | 'resource_handoff'
  // 2026-10-20 横向件补全:以下类型此前已在发射但没进开关清单 ——
  // 集成任务的高频告警(连续失败/自动暂停)此前用户无法关闭。
  | 'scenario.version_change'
  | 'integration'
  // S7.4 引用分享退役:一次性转换回执(历史 share_ref_* 行照常展示,
  // 标签保留在下方 LABELS)
  | 'share_ref_converted'
  // M2a S7.2:提升流程(加入申请审批)
  | 'project_promotion.pending'
  | 'project_promotion.approved'
  | 'project_promotion.rejected'
  // M2a S7.6:公共层 carry 改动被项目层覆盖遮住 → 项目管理员提醒
  | 'carry.shadowed'

export const NOTIFICATION_TYPE_LABELS: Record<string, string> = {
  execution_finished: '执行完成',
  adaptation_applied: '适配应用',
  announcement: '平台公告',
  scenario_unpublished: '场景下架',
  role_changed: '角色变更',
  resource_transferred: '资源转让',
  resource_handoff: '收到分享',
  'scenario.version_change': '场景版本变更',
  integration: '集成任务',
  'share_ref_received': '收到引用分享',
  'share_ref_revoked': '引用分享撤销',
  'share_ref_resource_deleted': '引用资源删除',
  'share_ref_owner_changed': '引用属主变更',
  'share_ref_converted': '引用转副本',
  'project_promotion.pending': '加入申请待审批',
  'project_promotion.approved': '加入申请已批准',
  'project_promotion.rejected': '加入申请被驳回',
  'carry.shadowed': '公共层 carry 变更',
}

export function list(params?: {
  unreadOnly?: boolean
  page?: number
  pageSize?: number
}) {
  // 后端分页参读 snake_case(page_size);此前直传 camelCase 被忽略,
  // 落默认 50 —— 「每页 10 实显 13」的根因。与 executions/users 的
  // 映射同款,响应信封仍 camelCase。
  return http
    .get<NotificationList>('/notifications', {
      params: {
        ...(params?.unreadOnly ? { unread_only: true } : {}),
        ...(params?.page != null ? { page: params.page } : {}),
        ...(params?.pageSize != null ? { page_size: params.pageSize } : {}),
      },
    })
    .then((r) => r.data)
}

export function markRead(ids: number[] | null) {
  return http
    .post<{ marked: number }>('/notifications/read', { ids })
    .then((r) => r.data)
}

export function unreadCount() {
  return http.get<UnreadCount>('/notifications/unread-count').then((r) => r.data)
}

export function getPreferences() {
  return http.get<{ off: SwitchableType[] }>('/notifications/preferences')
    .then((r) => r.data)
}

export function putPreferences(off: SwitchableType[]) {
  return http.put<{ off: SwitchableType[] }>('/notifications/preferences', { off })
    .then((r) => r.data)
}

export function postAnnouncement(body: { title: string; body: string; hours: number }) {
  return http
    .post<{ delivered: number }>('/notifications/announcements', body)
    .then((r) => r.data)
}
