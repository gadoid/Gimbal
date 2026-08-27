/**
 * catalog-services.ts — plate 目录服务名加载器(共享,模块级缓存)
 *
 * 目录服务名全串集合 = 别名派生(deriveBase)的唯一外部输入。数据源与
 * CaseComposerCatalog 相同:plate /api/endpoint?per_page=500 的 items[].service
 * (必须用原生 fetch — axios baseURL=/api 会把 /plate 拼成 /api/plate,
 * 绕过 Vite 的 /plate 代理)。消费方:Canvas 别名下拉 / Config 归属列 /
 * CaseComposer.checkSystemMismatch;失败静默降级为空集合(裸声明黄警)。
 */
import { useAuthStore } from '@/stores/auth'

let cached: Promise<string[]> | null = null

export function loadCatalogServiceNames(): Promise<string[]> {
  if (cached) return cached
  const p: Promise<string[]> = (async () => {
    const token = useAuthStore().accessToken || ''
    const r = await fetch('/plate/api/endpoint?per_page=500', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!r.ok) throw new Error(`catalog endpoint list HTTP ${r.status}`)
    const data: any = await r.json()
    const items = data?.data?.items || data?.items || (Array.isArray(data) ? data : [])
    const names: string[] = items.map((e: any) => e.service).filter(Boolean)
    return [...new Set(names)]
  })().catch((e) => {
    cached = null          // 失败不缓存,下次可重试
    throw e
  })
  cached = p
  return p
}
