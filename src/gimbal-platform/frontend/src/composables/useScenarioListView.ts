/**
 * useScenarioListView.ts — 场景库列表视图的共用骨架(M1 服务端化改版)。
 *
 * 「我的场景」与「公共场景」是**同一个服务端列表的两种分桶**:检索/
 * 筛选/分页全部下推到 GET /api/scenarios(Page 信封),前端只渲染当前页
 * ——不再从 store 拿全量场景做客户端过滤(那是 store 退位前的形态,
 * PG迁移方案 §4.3)。搜索词与页码写回地址栏,刷新/分享/返回不丢状态。
 *
 * M3:FilterPopover 的维度可选值改由 GET /scenarios/facets(GROUP BY
 * 聚合)供给 —— 不再依赖当前页 uniq 池(分页后可选值会残缺)。facets
 * 请求失败时置 null,FilterPopover 自动回落当前页池兜底。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useServerList } from '@/composables/useServerList'
import { emptyFilters, isFiltering, type ScenarioFilters } from '@/utils/filters'
import { fetchScenarioFacets, type ScenarioFacets } from '@/api/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'

export type ScenarioListRow = ScenarioListItem

export const LIST_PAGE_SIZE = 20

/** 分桶 → 服务端 visibility 参数:mine=private(自己的;admin=全员私有,
 *  与旧「非 public」谓词同口径),public=public。 */
type Bucket = 'mine' | 'public'

export function useScenarioListView(bucket: Bucket) {
  const store = useScenarioComposerStore()
  const route = useRoute()

  // 初始 q 从地址栏读回(在 useServerList 创建前赋值,不触发首拉)。
  const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
  const filters = ref<ScenarioFilters>(emptyFilters())

  const params = () => ({
    q: q.value.trim() || undefined,
    visibility: (bucket === 'mine' ? 'private' : 'public') as 'private' | 'public',
    system: filters.value.systems.join(',') || undefined,
    module: filters.value.modules.join(',') || undefined,
    tag: filters.value.tags.join(',') || undefined,
    author: filters.value.authors.join(',') || undefined,
    priority: filters.value.priorities.join(',') || undefined,
    updatedWithin:
      filters.value.updatedWithin !== 'all' ? filters.value.updatedWithin : undefined,
  })

  const initialPage = (() => {
    const p = Number.parseInt(String(route.query.page ?? '1'), 10)
    return Number.isFinite(p) && p >= 1 ? p : 1
  })()

  const list = useServerList<ScenarioListItem, ReturnType<typeof params>>({
    fetch: (p) => store.fetchPage(p),
    params,
    pageSize: LIST_PAGE_SIZE,
    syncUrl: true,
    initialPage,
  })

  // FilterPopover 按摊平键取值,所以先把 meta.* 抄到顶层(池 = 当前页,
  // 仅作 facets 请求失败时的兜底)。
  const filterableRows = computed(() =>
    list.items.value.map((s) => ({
      ...s,
      module: s.meta.module,
      author: s.meta.author || s.meta.owner,
      priority: s.meta.priority,
      updated_at: s.meta.updateTime,
      system: s.meta.system,
      tags: s.meta.tags,
    })),
  )

  // ── facets(M3):FilterPopover 可选值的服务端数据源 ─────────────
  // 与列表同口径下推 q + 分桶 visibility;静默失败(置 null 即回落池)。
  const facets = ref<ScenarioFacets | null>(null)
  const visibility = (bucket === 'mine' ? 'private' : 'public') as 'private' | 'public'

  async function loadFacets(): Promise<void> {
    try {
      facets.value = await fetchScenarioFacets({
        q: q.value.trim() || undefined,
        visibility,
      })
    } catch {
      facets.value = null
    }
  }

  watch(q, () => void loadFacets())
  void loadFacets()

  const filtering = computed(() => isFiltering(filters.value, q.value))

  async function load(): Promise<void> {
    await list.reload()
  }

  return {
    store,
    q, filters,
    page: list.page,
    items: list.items,
    /** 兼容旧消费面:rows/paged 均为当前页(服务端已分页)。 */
    rows: list.items,
    paged: list.items,
    total: list.total,
    pageCount: list.pageCount,
    loading: list.loading,
    filtering, filterableRows, facets, loadFacets,
    pageSize: LIST_PAGE_SIZE,
    load, reload: list.reload, setPage: list.setPage,
  }
}
