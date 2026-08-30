/**
 * catalog-services.ts — plate 目录服务名加载器(共享,模块级缓存)
 *
 * 目录服务名全串集合 = 别名派生(deriveBase)的唯一外部输入。数据源与
 * CaseComposerCatalog 相同:plate /api/endpoint?per_page=500 的
 * items[].service / items[].system(必须用原生 fetch — axios baseURL=/api
 * 会把 /plate 拼成 /api/plate,绕过 Vite 的 /plate 代理)。
 * 消费方:Canvas 别名下拉 / Config 归属列 / CaseComposer.checkSystemMismatch;
 * 失败静默降级为空集合(裸声明黄警)。
 *
 * 两个视图共享同一次拉取(单一 cached promise):
 *   - loadCatalogServiceNames:去重服务名集合(别名派生输入)
 *   - loadCatalogSystemByService:service → system 权威映射
 *     (endpoint 条目自带 system 字段 — 系统黄警不再靠字符串猜测)
 */
import { useAuthStore } from '@/stores/auth'

/** 目录 endpoint 条目中派生所需的两个字段。 */
interface CatalogServiceEntry {
  service: string
  system: string
}

let cached: Promise<CatalogServiceEntry[]> | null = null

function loadCatalogEntries(): Promise<CatalogServiceEntry[]> {
  if (cached) return cached
  const p: Promise<CatalogServiceEntry[]> = (async () => {
    const token = useAuthStore().accessToken || ''
    const r = await fetch('/plate/api/endpoint?per_page=500', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!r.ok) throw new Error(`catalog endpoint list HTTP ${r.status}`)
    const data: any = await r.json()
    const items = data?.data?.items || data?.items || (Array.isArray(data) ? data : [])
    return items
      .map((e: any) => ({ service: e.service, system: e.system }))
      .filter((e: CatalogServiceEntry) => e.service && e.system)
  })().catch((e) => {
    cached = null          // 失败不缓存,下次可重试
    throw e
  })
  cached = p
  return p
}

export function loadCatalogServiceNames(): Promise<string[]> {
  return loadCatalogEntries().then((es) => [...new Set(es.map((e) => e.service))])
}

export function loadCatalogSystemByService(): Promise<Map<string, string>> {
  return loadCatalogEntries().then((es) => new Map(es.map((e) => [e.service, e.system])))
}
