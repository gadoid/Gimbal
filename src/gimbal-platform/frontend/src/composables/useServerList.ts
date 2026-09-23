/**
 * useServerList.ts — 「服务端列表页」统一范式(M1 三件套之一,PG迁移方案 §6.1)。
 *
 * 入参:fetch 函数(收「筛选参数 + page/page_size」,回 Page 信封
 * {items,total,page,pageSize})+ 响应式筛选参数源;产出 items/total/
 * loading/error/page/setPage/pageCount/reload。
 *
 * 行为契约:
 *  - 筛选参数变化(含查询词)→ 300ms 防抖重拉(utils/debounce,全站
 *    第一个公共防抖)+ 页码自动重置 1;
 *  - 翻页只拉目标页,翻页后 scrollTo(0);
 *  - 结果集变小后停在越界页 → 自动回拉末页;
 *  - ``syncUrl`` 开启时 q/page 写回 router.replace(不进历史;防抖生效,
 *    打字不逐字 replace),刷新/分享/返回不丢状态;其余既有 query
 *    (?batch_id 等)原样保留,``readQuery()`` 提供初始态读回。
 *
 * 约束:本 composable 不持有筛选参数 —— 筛选状态归调用方(各列表页
 * 有自己的 FilterPopover/URL 形态),这里只观察 ``params`` getter 的
 * 「参数签名」判断变化。
 */
import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { debounce } from '@/utils/debounce'
import { showError } from '@/utils/errorFallback'
import { usePagerSize } from './usePagerSize'

export interface PageEnvelope<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export type ServerListParams = Record<string, string | number | boolean | undefined>

export interface UseServerListOptions<T, P extends ServerListParams> {
  /** 拉取函数:参数 = 筛选参数 + 分页(page/page_size 由本体注入)。 */
  fetch: (params: P & { page: number; page_size: number }) => Promise<PageEnvelope<T>>
  /** 响应式筛选参数(getter 形态,变更即触发重置页码 + 防抖重拉)。 */
  params: () => P
  pageSize?: number
  debounceMs?: number
  /** q/page 写回 URL query(router.replace,不进历史)。默认 false。 */
  syncUrl?: boolean
  /** 每页行数存用户偏好(pager.sizes 键,服务端+镜像;2026-09-23 批次)。 */
  pagerKey?: string
  /** 初始页码(syncUrl 深链恢复;在 watch 注册前生效,不触发首拉)。 */
  initialPage?: number
  /** 翻页后 scrollTo(0)。默认 true。 */
  scroll?: boolean
  /** 报错通道(默认走 showError 全局提示)。 */
  onError?: (e: unknown) => void
}

/** 参数里 undefined/空串剔除后的签名(浅比较足够:筛选值都是标量)。 */
function signature(p: ServerListParams): string {
  const parts: string[] = []
  for (const k of Object.keys(p).sort()) {
    const v = p[k]
    if (v === undefined || v === '') continue
    parts.push(`${k}=${String(v)}`)
  }
  return parts.join('&')
}

export function useServerList<T, P extends ServerListParams>(
  opts: UseServerListOptions<T, P>,
) {
  // 2026-09-23 分页批次:pageSize 从定值改 ref,配合 Pagination 的每页行数
  // 选择器;改尺寸 → 回页 1 重拉(见 watch)。给了 pagerKey 则初始值/持久
  // 化交给用户偏好层(镜像管首帧,服务端管跨设备)。
  const pageSize = opts.pagerKey
    ? usePagerSize(opts.pagerKey, opts.pageSize ?? 20).pageSize
    : ref(opts.pageSize ?? 20)

  const items = ref<T[]>([]) as Ref<T[]>
  const total = ref(0)
  const page = ref(opts.initialPage ?? 1)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const route = opts.syncUrl ? useRoute() : null
  const router = opts.syncUrl ? useRouter() : null

  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  let seq = 0
  async function load(): Promise<void> {
    const mine = ++seq
    loading.value = true
    error.value = null
    const extra = opts.params()
    try {
      const env = await opts.fetch({ ...extra, page: page.value, page_size: pageSize.value })
      if (mine !== seq) return // 过期响应(参数又变了),丢弃
      items.value = env.items
      total.value = env.total
      if (env.items.length === 0 && page.value > 1) {
        // 结果集变小(删除/筛选收紧)后停在越界页 → 回拉到末页重取一次。
        page.value = Math.max(1, Math.ceil(env.total / pageSize.value))
        await load()
        return
      }
      syncUrl(page.value, extra)
    } catch (e) {
      if (mine !== seq) return
      error.value = e instanceof Error ? e.message : String(e)
      ;(opts.onError ?? ((e2: unknown) => showError('加载列表', e2)))(e)
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  const debouncedLoad = debounce(() => { void load() }, opts.debounceMs ?? 300)

  /** q/page 写回地址栏(replace 不进历史);其余既有 query 原样保留。 */
  function syncUrl(p: number, extra: ServerListParams): void {
    if (!route || !router) return
    const next: Record<string, string> = {}
    for (const [k, v] of Object.entries(route.query)) {
      if (k === 'q' || k === 'page') continue
      if (typeof v === 'string') next[k] = v
    }
    const q = extra.q
    if (typeof q === 'string' && q) next.q = q
    if (p > 1) next.page = String(p)
    router.replace({ query: next })
  }

  // 筛选参数变化 → 页码重置;页码本来就非 1 时由 page watch 立即拉,
  // 否则防抖拉(打字不逐请求)。
  watch(
    () => signature(opts.params()),
    () => {
      if (page.value !== 1) page.value = 1
      else debouncedLoad()
    },
  )
  watch(page, (p) => {
    void load()
    if (opts.scroll !== false) window.scrollTo(0, 0)
  })
  // 每页行数变化 → 回页 1(页码 watch 立即拉;本来就在页 1 则主动拉一次)。
  watch(pageSize, () => {
    if (page.value !== 1) page.value = 1
    else void load()
  })

  onBeforeUnmount(() => debouncedLoad.cancel())

  return {
    items, total, page, pageCount, loading, error,
    pageSize,
    setPage(p: number): void {
      const clamped = Math.min(Math.max(p, 1), pageCount.value)
      if (clamped !== page.value) page.value = clamped
    },
    setPageSize(n: number): void {
      const clamped = Math.max(1, Math.floor(n))
      if (clamped !== pageSize.value) pageSize.value = clamped
    },
    reload: load,
    /** syncUrl 时的初始态读回:深链/刷新恢复 q 与 page。 */
    readQuery(): { q: string; page: number } {
      const q = typeof route?.query.q === 'string' ? route.query.q : ''
      const raw = Number.parseInt(String(route?.query.page ?? '1'), 10)
      return { q, page: Number.isFinite(raw) && raw >= 1 ? raw : 1 }
    },
  }
}

export type UseServerList = ReturnType<typeof useServerList>
