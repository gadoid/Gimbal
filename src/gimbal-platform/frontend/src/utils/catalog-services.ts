/**
 * catalog-services.ts — 服务目录加载器(共享,模块级缓存)
 *
 * M5(债 11)起数据源 = 平台后端聚合端点 GET /api/catalog/services
 * (后端代理 plate /api/endpoint 全量 + 聚合 + 30s TTL)—— 浏览器不再
 * 直连 plate /api/endpoint?per_page=500(超 500 静默丢 + 每浏览器一份
 * 全量拉取的旧形态退役)。
 * 消费方:Canvas 别名下拉 / Config 归属列 / CaseComposer.checkSystemMismatch;
 * 失败静默降级为空集合(裸声明黄警)。
 *
 * 多个 loader 共享同一次拉取(单一 cached promise):
 *   - loadCatalogServiceNames:去重服务名集合(别名派生输入)
 *   - loadCatalogSystemByService:service → system 权威映射
 *   - loadCatalogServiceRows:服务级聚合行(画像页/工作台卡,口径唯一)
 */
import http from '@/api/http'

/** 目录 endpoint 条目中派生所需的字段(id 供 endpoint→service 映射,
 *  如适配中心待适配卡跳接口线索板;个别脏行可缺)。 */
interface CatalogServiceEntry {
  service: string
  system: string
  id?: string
}

/** GET /api/catalog/services 响应形状(M5 聚合端点)。 */
interface CatalogServicesEnvelope {
  services: { name: string; system: string; endpointCount: number }[]
  endpoints: { id: string; service: string }[]
  plateReachable: boolean
}

let cached: Promise<CatalogServicesEnvelope> | null = null

function fetchCatalogServices(): Promise<CatalogServicesEnvelope> {
  return http.get<CatalogServicesEnvelope>('/catalog/services')
    .then((r) => r.data)
}

/**
 * 目录条目全集(service×system,每 endpoint 一行 —— 由聚合端点的
 * services × endpoints 复原,消费方形状不变)。
 */
export function loadCatalogEntries(): Promise<CatalogServiceEntry[]> {
  if (!cached) {
    cached = fetchCatalogServices().catch((e) => {
      cached = null // 失败不缓存,下次可重试
      throw e
    })
  }
  return cached.then((env) =>
    env.endpoints.map((ep) => ({
      service: ep.service,
      system: env.services.find((s) => s.name === ep.service)?.system ?? '',
      id: ep.id,
    })).filter((e) => e.service && e.system))
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
  // 聚合端点已按服务聚好 —— 直接取,不再前端重算(口径唯一,债 11 消除)
  return loadCatalogEntries().then(() => (cached ? cached : fetchCatalogServices()))
    .then((env) => env.services.map((s) => ({ ...s })))
}
