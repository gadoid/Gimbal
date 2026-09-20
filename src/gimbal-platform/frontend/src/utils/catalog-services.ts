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

/** 目录 endpoint 条目中派生所需的字段(id 供 endpoint→service 映射,
 *  如适配中心待适配卡跳接口线索板;个别脏行可缺)。 */
interface CatalogServiceEntry {
  service: string
  system: string
  id?: string
}

let cached: Promise<CatalogServiceEntry[]> | null = null

/**
 * 目录条目全集(service×system,每 endpoint 一行)。
 * 消费方:服务画像落地页按服务聚合计数(2026-09-20 起);
 * 与另两个 loader 共享同一次缓存拉取。
 */
export function loadCatalogEntries(): Promise<CatalogServiceEntry[]> {
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
      .map((e: any) => ({ service: e.service, system: e.system, id: e.id }))
      .filter((e: CatalogServiceEntry) => e.service && e.system)
  })().catch((e) => {
    cached = null          // 失败不缓存,下次可重试
    throw e
  })
  cached = p
  return p
}

/** endpoint_id → service 映射(适配中心「看影响面」跳线索板要用;
 *  与其他 loader 共享同一次缓存拉取)。 */
export function loadCatalogEndpointServiceMap(): Promise<Map<string, string>> {
  return loadCatalogEntries().then(
    (es) => new Map(es.filter((e) => e.id).map((e) => [e.id!, e.service])))
}

export function loadCatalogServiceNames(): Promise<string[]> {
  return loadCatalogEntries().then((es) => [...new Set(es.map((e) => e.service))])
}

export function loadCatalogSystemByService(): Promise<Map<string, string>> {
  return loadCatalogEntries().then((es) => new Map(es.map((e) => [e.service, e.system])))
}

/** 按服务聚合的一行。服务画像落地页与工作台「服务画像」卡共用 ——
 *  §7 第 6 条:卡上的服务数/端点数必须与点进完整页看到的一致,
 *  所以聚合只能有一份。 */
export interface CatalogServiceRow {
  name: string
  system: string
  endpointCount: number
}

export function loadCatalogServiceRows(): Promise<CatalogServiceRow[]> {
  return loadCatalogEntries().then((entries) => {
    const byName = new Map<string, CatalogServiceRow>()
    for (const e of entries) {
      const row = byName.get(e.service)
      if (row) row.endpointCount += 1
      else byName.set(e.service, { name: e.service, system: e.system, endpointCount: 1 })
    }
    return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name))
  })
}
