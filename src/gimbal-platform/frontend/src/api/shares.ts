/**
 * api/shares.ts — 副本分享(引用模式退场后仅剩 copy,ADR-0003 #20)。
 *
 * 分享 = 属主把场景/用例集深拷贝给接收人(独立副本,不可撤回);
 * admin 不可代发(§8.1)。历史引用分享(share_refs)已一次性转为
 * 被分享人私有副本(ADR-0003 #20);徽标/「共享给我的」入口随之退场。
 */
import http from './http'
import type { RosterItem } from './handoff'

export interface ShareCopyResult {
  mode: 'copy'
  scenarioId: string | null
  suiteId: number | null
  suiteName: string | null
  memberCount: number
}

export { type RosterItem }

/** 发起副本分享(属主;深拷贝跨属主剥内置凭证与敏感列)。 */
export function createShare(body: {
  resourceType: 'scenario' | 'suite'
  resourceId: string
  granteeUserId: number
  mode?: 'copy'
}): Promise<ShareCopyResult> {
  return http.post('/shares', body).then((r) => r.data)
}
