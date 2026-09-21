/**
 * notifications.ts — 通知中心 API(P1b/M2.5,权限方案 §3.3)。
 * 三接口 + 按 type 偏好 + 公告;铃铛 30s 轮询 unread-count。
 */
import http from './http'

export type Role = 'member' | 'operator' | 'admin'

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

export const NOTIFICATION_TYPE_LABELS: Record<SwitchableType, string> = {
  execution_finished: '执行完成',
  adaptation_applied: '适配应用',
  announcement: '平台公告',
  scenario_unpublished: '场景下架',
  role_changed: '角色变更',
  resource_transferred: '资源转让',
}

export function list(params?: { unreadOnly?: boolean; limit?: number }) {
  return http
    .get<NotificationList>('/notifications', { params })
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
