/**
 * api/shares.ts — 引用/副本分享(权限域二期 P2,
 * 《Suite成员层、引用分享与浏览镜头-设计方案》§7/§9)。
 *
 * 分享 = 属主在弹窗里选模式:引用(live link,只读可执行,可撤销/退订)
 * 或副本(独立拷贝,不可撤回);admin 不可代发(§8.1)。
 * 徽标数据源:direction=in(共享给我的)+ direction=out(我分享出去的)。
 */
import http from './http'
import type { RosterItem } from './handoff'

export interface ShareRefItem {
  id: number
  resourceType: 'scenario' | 'suite'
  scenarioId: string | null
  scenarioName: string | null
  suiteId: number | null
  suiteName: string | null
  memberCount: number | null
  granteeUserId: number
  granteeName: string
  grantedByName: string
  grantedAt: string | null
}

/** 场景引用人(重构方案 D-1:直接 + 经由所属 Suite 的间接,同人合并)。 */
export interface ScenarioReferrer {
  granteeUserId: number
  granteeName: string
  direct: boolean
  viaSuites?: { suiteId: number; suiteName: string }[]
}

export interface ShareCopyResult {
  mode: 'copy'
  scenarioId: string | null
  suiteId: number | null
  suiteName: string | null
  memberCount: number
}

export { type RosterItem }

/** 发起分享(属主;ref 幂等 upsert / copy 深拷贝;409=cap)。 */
export function createShare(body: {
  resourceType: 'scenario' | 'suite'
  resourceId: string
  granteeUserId: number
  mode: 'ref' | 'copy'
}): Promise<ShareRefItem | ShareCopyResult> {
  return http.post('/shares', body).then((r) => r.data)
}

/** 引用清单(direction=in 共享给我的 / out 我分享出去的)。 */
export function listShares(params: {
  direction: 'in' | 'out'
  resourceType?: 'scenario' | 'suite'
  resourceId?: string
}): Promise<ShareRefItem[]> {
  return http.get<ShareRefItem[]>('/shares', { params }).then((r) => r.data)
}

/** 场景的全部引用人(直接 + 经由所属 Suite 的间接;属主/admin 闸)。 */
export function listScenarioReferrers(
  scenarioId: string,
): Promise<{ items: ScenarioReferrer[] }> {
  return http.get<{ items: ScenarioReferrer[] }>('/shares/referrers', {
    params: { scenarioId },
  }).then((r) => r.data)
}

/** 撤销(属主/admin)或退订(被分享人)。 */
export function deleteShare(shareId: number): Promise<void> {
  return http.delete(`/shares/${shareId}`).then(() => undefined)
}

/** 转为副本(被分享人;原引用保留)。 */
export function forkShare(shareId: number): Promise<ShareCopyResult> {
  return http.post<ShareCopyResult>(`/shares/${shareId}/fork`)
    .then((r) => r.data)
}
