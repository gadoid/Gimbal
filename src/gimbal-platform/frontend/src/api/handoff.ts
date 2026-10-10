/**
 * api/handoff.ts — 分享配套查询(原 F1 资源分发批次遗留)。
 *
 * 「分发给…」入口已并入 ShareDialog 的副本模式(POST /shares,后端同一深拷贝);
 * 这里只留两个查询:成员选择器 roster、「来自 X 的分享」未读标签。
 */
import http from './http'

export interface RosterItem {
  id: number
  username: string
  display_name: string
}

export interface HandoffUnreadItem {
  id: number
  resourceId: string
  senderName: string | null
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
