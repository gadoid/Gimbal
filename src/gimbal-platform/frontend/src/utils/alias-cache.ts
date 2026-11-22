/**
 * alias-cache.ts — 服务条目懒加载**单源**(复核收口 2026-11-22)。
 *
 * ServiceAdmin(矩阵网格)与 ExecConfigsView(换用槽位)此前各持一份
 * ensureAliases —— 缓存/加载态/错误态形状互异、互不可见,网络面却
 * 完全同构(listAliases({base, page_size:200}))。本模块提供模块级
 * 单例缓存(同一服务两视图共享同一镜像),FE-02 契约:失败 = error
 * 态(≠空表),force 可重拉。
 */
import { reactive } from 'vue'
import { listAliases } from '@/api/service-aliases'
import type { ServiceAliasRow } from '@/api/service-aliases'

export type AliasLoadState = 'idle' | 'loading' | 'done' | 'error'

export interface AliasCacheEntry {
  items: ServiceAliasRow[]
  total: number
  status: AliasLoadState
}

const entries = reactive<Record<string, AliasCacheEntry>>({})

export function useAliasCache() {
  /** 懒装载:done/loading 短路(除非 force);失败 = error 态可重试。 */
  async function ensure(service: string, force = false): Promise<void> {
    if (!service) return
    const cur = entries[service]
    if (!force && cur
        && (cur.status === 'loading' || cur.status === 'done')) return
    entries[service] = {
      items: cur?.items ?? [], total: cur?.total ?? 0, status: 'loading',
    }
    try {
      const page = await listAliases({ base: service, page_size: 200 })
      entries[service] = { items: page.items, total: page.total,
                           status: 'done' }
    } catch {
      // FE-02:失败≠空表 —— error 态保留旧行(如有),下次 ensure 重试
      entries[service] = { items: cur?.items ?? [], total: cur?.total ?? 0,
                           status: 'error' }
    }
  }
  function itemsOf(service: string): ServiceAliasRow[] {
    return entries[service]?.items ?? []
  }
  function totalOf(service: string): number {
    return entries[service]?.total ?? 0
  }
  function statusOf(service: string): AliasLoadState {
    return entries[service]?.status ?? 'idle'
  }
  /** 删除某服务的缓存行(服务/条目注销后失效)。 */
  function invalidate(service: string): void {
    delete entries[service]
  }
  return { entries, ensure, itemsOf, totalOf, statusOf, invalidate }
}

/** 测试隔离钩子:模块级单例缓存跨用例共享 —— 测试 beforeEach 清空
 *  (与 canvas 测试的 _resetEndpointFullCacheForTest 同模式)。 */
export function _resetAliasCacheForTest(): void {
  for (const k of Object.keys(entries)) delete entries[k]
}
