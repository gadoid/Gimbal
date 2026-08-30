/**
 * plate.ts — Plate(结构权威)直连查询层。
 *
 * 为什么用原生 fetch 而非 axios:
 *     plate 走 Vite 的 `/plate` 代理,而项目 axios 实例的 baseURL 是 `/api`,
 *     会拼出 `/api/plate/...` 的错误路径 — 与 CaseComposerCatalog 的先例一致。
 * 鉴权:
 *     统一从 auth store 取 accessToken(repo 约定:不手解析 localStorage)。
 * 映射约定:
 *     plate 输出 snake_case(time_policy/create_time/requirement_ref),
 *     前端视图类型 camelCase — 本模块是这层映射的唯一收敛点,
 *     UserAuthView 例外(其自身即 snake_case,与 plate 直通)。
 */
import { useAuthStore } from '@/stores/auth'
import type { ConfigView, MetaView, ResourceView } from '@/types/plate'

/** plate 信封响应:data.items 为该 dim 的条目列表。 */
interface PlateEnvelope<T> {
  ok: boolean
  data: { items: T[]; total: number }
}

/** 带 Authorization(Bearer)头的 plate GET;失败抛错由调用方决定降级。 */
async function plateFetch<T>(path: string): Promise<PlateEnvelope<T>> {
  const token = useAuthStore().accessToken
  const resp = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!resp.ok) throw new Error(`plate ${path} -> HTTP ${resp.status}`)
  return (await resp.json()) as PlateEnvelope<T>
}

/** GET /plate/api/system → 已注册系统 id 列表(common/fin/C1 注册的…)。 */
export async function fetchPlateSystems(): Promise<string[]> {
  const body = await plateFetch<{ id: string }>('/plate/api/system')
  return body.data.items.map((it) => it.id)
}

/** plate config 条目(snake_case 原样)。 */
interface PlateConfigItem {
  setup?: unknown[]
  teardown?: unknown[]
  services?: Record<string, string>
  users?: Record<string, Record<string, unknown>>
  time_policy?: ConfigView['timePolicy']
  retry?: ConfigView['retry']
  vars?: Record<string, unknown>
}

/** GET /plate/api/systems/{s}/config → ConfigView;无 seed 返回 null。 */
export async function fetchSystemConfig(system: string): Promise<ConfigView | null> {
  const body = await plateFetch<PlateConfigItem>(`/plate/api/systems/${system}/config`)
  const it = body.data.items[0]
  if (!it) return null
  return {
    setup: it.setup ?? [],
    teardown: it.teardown ?? [],
    services: it.services ?? {},
    users: (it.users ?? {}) as ConfigView['users'],
    timePolicy: it.time_policy ?? { kind: 'record' },
    retry: it.retry ?? null,
    vars: it.vars ?? {},
  }
}

/** plate meta 条目(仅列出需要映射的字段,其余同名直通)。 */
interface PlateMetaItem {
  name?: string
  description?: string
  module?: string
  priority?: number
  author?: string
  owner?: string
  tags?: string[]
  version?: string
  create_time?: string
  expire?: boolean
  requirement_ref?: MetaView['requirementRef']
  system?: MetaView['system']
}

/** GET /plate/api/systems/{s}/meta → MetaView;无 seed 返回 null。 */
export async function fetchSystemMeta(system: string): Promise<MetaView | null> {
  const body = await plateFetch<PlateMetaItem>(`/plate/api/systems/${system}/meta`)
  const it = body.data.items[0]
  if (!it) return null
  return {
    name: it.name ?? '',
    description: it.description ?? '',
    module: it.module ?? '',
    priority: it.priority ?? 1,
    author: it.author ?? '',
    owner: it.owner ?? '',
    tags: it.tags ?? [],
    version: it.version ?? '',
    createTime: it.create_time ?? '',
    expire: it.expire ?? false,
    requirementRef: it.requirement_ref ?? [],
    system: it.system ?? [],
  }
}

/** plate resource /full 条目:extra 携带 kind 专属载荷。 */
interface PlateResourceItem {
  name: string
  kind: string
  extra?: {
    image?: string
    config?: Record<string, unknown>
    portMapping?: Record<number, number>
    path?: string
  }
}

/** resource /full 条目 → 前端资源视图;未知 kind(如 *_ref)返回 null 跳过。 */
function toResourceView(it: PlateResourceItem): ResourceView | null {
  if (it.kind === 'mock') {
    return {
      kind: 'mock',
      name: it.name,
      image: it.extra?.image ?? '',
      config: it.extra?.config ?? {},
      portMapping: it.extra?.portMapping ?? {},
    }
  }
  if (it.kind === 'file') {
    return { kind: 'file', name: it.name, path: it.extra?.path ?? '' }
  }
  return null
}

/** GET /plate/api/systems/{s}/resource/full → 按 name 建键的资源集。 */
export async function fetchSystemResources(system: string): Promise<Record<string, ResourceView>> {
  const body = await plateFetch<PlateResourceItem>(`/plate/api/systems/${system}/resource/full`)
  const resources: Record<string, ResourceView> = {}
  for (const it of body.data.items) {
    const view = toResourceView(it)
    if (view) resources[it.name] = view
  }
  return resources
}
