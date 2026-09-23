/**
 * api/handoff.ts — 资源分发(F1,2026-09-23 批次)。
 *
 * 分发 = Fork(副本):接收后归接收方,发送方零控制权、不支持撤回;
 * 凭据引用不迁移(副本执行按接收方本人凭证池解析)。
 * 悬浮标签数据源 = GET /notifications/handoff-unread(未读 resource_handoff)。
 */
import http from './http'

export interface RosterItem {
  id: number
  username: string
  display_name: string
}

export interface HandoffResult {
  status: string
  new_resource_id: string
  new_name: string
  renamed: boolean
}

export interface HandoffUnreadItem {
  id: number
  resourceId: string
  senderName: string | null
}

/** 把场景副本分发给目标用户(仅 owner/admin;后端 403/404/422 分流)。 */
export function postHandoff(
  resourceId: string, targetUserId: number,
): Promise<HandoffResult> {
  return http.post<HandoffResult>('/handoff', {
    resource_type: 'scenario',
    resource_id: resourceId,
    target_user_id: targetUserId,
  }).then((r) => r.data)
}

/** 成员选择器数据(CurrentUser;仅 is_active、已排除自己)。 */
export function getRoster(): Promise<{ items: RosterItem[] }> {
  return http.get<{ items: RosterItem[] }>('/users/roster').then((r) => r.data)
}

/** 未读分享列表(悬浮标签数据源;销账走 notifications.markRead 按 id)。 */
export function getHandoffUnread(): Promise<{ items: HandoffUnreadItem[] }> {
  return http
    .get<{ items: HandoffUnreadItem[] }>('/notifications/handoff-unread')
    .then((r) => r.data)
}
