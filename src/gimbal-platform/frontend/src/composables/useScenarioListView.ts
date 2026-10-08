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
 *
 * 筛选分组也住在这里:两页对分组做的事一字不差(存/应用/删),而应用
 * 要写的 q + filters 正是本骨架的私有状态 —— 拆成独立 composable
 * 只会让两页各抄一遍接线。分组语义(2026-09-22 定稿):chip = 以分组名
 * 搜索的开关 —— 点名 → 生效 q = 分组名(搜索框不回填,chip 高亮即
 * "正在搜什么");再点 → 取消回全量;手动输入/改筛选即退出分组态。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { useAuthStore } from '@/stores/auth'
import { useServerList } from '@/composables/useServerList'
import { emptyFilters, isFiltering, type ScenarioFilters } from '@/utils/filters'
import { fetchScenarioFacets, type ScenarioFacets } from '@/api/scenario-composer'
import {
  createFilterGroup, deleteFilterGroup, listFilterGroups, type FilterGroup,
} from '@/api/scenario-filter-groups'
import { toast } from '@/utils/toast'
import type { ScenarioListItem } from '@/types/scenario-composer'

export type ScenarioListRow = ScenarioListItem

export const LIST_PAGE_SIZE = 20

/** 分桶:mine = 「我的场景」页(浏览镜头,scope=mine——自己创建的全部
 *  含已发布;admin 默认同样只见自己的,「全员视角」是显式开关),public
 *  = 公共页(visibility=public,口径不变)。
 *  此前 mine 桶下推 visibility=private——admin 查 private = 全员私有,
 *  是「admin 场景库被淹没」的根源;且自己的已发布场景从「我的」页消失。 */
type Bucket = 'mine' | 'public'

/** 浏览镜头的本地偏好键(仅 admin 的全员视角开关用;镜头不进权限)。 */
const LENS_KEY = 'scenarios-mine-lens'

export function useScenarioListView(bucket: Bucket) {
  const store = useScenarioComposerStore()
  const route = useRoute()
  const auth = useAuthStore()

  // ── 浏览镜头(《Suite成员层、引用分享与浏览镜头-设计方案》§5.1)──
  // 仅 mine 桶、仅 admin:默认「我的」(scope=mine),显式切「全员视角」
  // (scope=all)。偏好记本地;镜头是查询偏好,不进权限判定——scope=all
  // 拿到的集合与可见性上限严格一致。
  const lensAll = ref(
    bucket === 'mine'
      && auth.isAdmin
      && window.localStorage.getItem(LENS_KEY) === 'all',
  )

  function toggleLens(): void {
    lensAll.value = !lensAll.value
    window.localStorage.setItem(LENS_KEY, lensAll.value ? 'all' : 'mine')
  }

  function lensScope(): 'mine' | 'all' {
    return lensAll.value ? 'all' : 'mine'
  }

  // 初始 q 从地址栏读回(在 useServerList 创建前赋值,不触发首拉)。
  const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
  const filters = ref<ScenarioFilters>(emptyFilters())

  // ── 分组态(2026-09-22 定稿)───────────────────────────────────
  // chip 是"以分组名搜索"的开关:生效 q = 分组名,搜索框(searchBox)
  // 刻意不回填 —— 高亮的 chip 自己说明在搜什么;手动面(输入框/
  // FilterPopover)一动即退出分组态。groups 提前声明供 effQ 闭包取。
  const appliedGroupId = ref('')
  const groups = ref<FilterGroup[]>([])

  /** 生效搜索词:分组态 = 分组名;手动态 = 搜索框文本。 */
  function effQ(): string {
    const g = groups.value.find((x) => x.id === appliedGroupId.value)
    return ((g ? g.name : q.value) || '').trim()
  }

  const params = () => ({
    q: effQ() || undefined,
    // 分桶下推:mine 桶走 scope(镜头),public 桶维持 visibility=public。
    ...(bucket === 'mine'
      ? { scope: lensScope() }
      : { visibility: 'public' as const }),
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
    pagerKey: bucket === 'mine' ? 'scenarios-mine' : 'scenarios-public',
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
  // 与列表同口径下推 q + 分桶参数(镜头切换同步刷新);静默失败(置 null
  // 即回落池)。
  const facets = ref<ScenarioFacets | null>(null)

  async function loadFacets(): Promise<void> {
    try {
      facets.value = await fetchScenarioFacets(bucket === 'mine'
        ? { q: effQ() || undefined, scope: lensScope() }
        : { q: effQ() || undefined, visibility: 'public' as const })
    } catch {
      facets.value = null
    }
  }

  watch([q, appliedGroupId], () => void loadFacets())
  // 镜头切换:params 签名变化已触发列表重拉,这里补 facets。
  watch(lensAll, () => void loadFacets())
  void loadFacets()

  /** 生效口径:分组态下搜索框虽空,列表确实在筛。 */
  const filtering = computed(() => isFiltering(filters.value, effQ()))

  // ── 筛选分组(命名的条件快照;服务端 user_prefs,换设备不丢)──────
  /** 三态而非 loading 布尔:失败要和「一个分组都没有」区分开 —— 前者得给
   *  重试入口,后者是给引导文案。 */
  const groupsState = ref<'loading' | 'ready' | 'error'>('loading')
  const savingGroup = ref(false)

  /** 首次读回后做一次 URL → 分组态还原:?q= 分组名(syncUrl 写下的
   *  生效词)命中分组 → 直接进分组态,搜索框保持空,刷新不破相。 */
  let urlRestoreDone = false

  async function loadGroups(): Promise<void> {
    groupsState.value = 'loading'
    try {
      groups.value = await listFilterGroups(bucket)
      groupsState.value = 'ready'
      if (!urlRestoreDone) {
        urlRestoreDone = true
        const fromUrl = q.value.trim()
        const hit = fromUrl ? groups.value.find((g) => g.name === fromUrl) : undefined
        if (hit) applyGroup(hit)
      }
    } catch {
      groups.value = []
      groupsState.value = 'error'
    }
  }
  void loadGroups()

  /** 应用分组自身写 filters 时不该被当成"手动改筛选"而退出分组态。 */
  let applyingGroup = false

  /** 点分组名 = 以分组名搜索的开关:生效 q 换成分组名、筛选整体写入、
   *  搜索框留空;再点同一个 = 取消搜索,回全量。 */
  function applyGroup(g: FilterGroup): void {
    applyingGroup = true
    if (appliedGroupId.value === g.id) {
      appliedGroupId.value = ''
      q.value = ''
      filters.value = emptyFilters()
    } else {
      appliedGroupId.value = g.id
      q.value = ''
      filters.value = JSON.parse(JSON.stringify(g.filters)) as ScenarioFilters
    }
    void nextTick(() => { applyingGroup = false })
  }

  /** 手动改筛选(FilterPopover)→ 退出分组态,改动保留为手动条件。 */
  watch(filters, () => {
    if (applyingGroup) return
    appliedGroupId.value = ''
  }, { deep: true })

  /** 手动输入搜索词 → 退出分组态。searchBox = 展示值(分组态恒空)。 */
  function writeSearch(v: string): void {
    appliedGroupId.value = ''
    q.value = v
  }
  const searchBox = computed(() => (appliedGroupId.value ? '' : q.value))

  /** 存分组 = 服务端按名覆盖后整表回读:本地不演算"覆盖谁",两标签页
   *  各自存过的结果以服务端为准(写请求本身是单条粒度,不会冲掉别人的)。
   *  成功后条件已进分组,搜索框与筛选让位回全量 —— 想再用点 chip。 */
  async function saveGroup(name: string): Promise<void> {
    if (savingGroup.value) return
    savingGroup.value = true
    try {
      await createFilterGroup({
        bucket, name, q: q.value, filters: filters.value,
      })
      appliedGroupId.value = ''
      applyingGroup = true
      q.value = ''
      filters.value = emptyFilters()
      void nextTick(() => { applyingGroup = false })
      await loadGroups()
      toast.success(`已存为分组「${name}」`)
    } catch (e) {
      toast.error(`存分组失败:${(e as Error).message}`)
    } finally {
      savingGroup.value = false
    }
  }

  /** 删的若是正在应用的分组 → 一并退出分组态(名称搜索源没了,回全量)。 */
  async function removeGroup(id: string): Promise<void> {
    try {
      await deleteFilterGroup(bucket, id)
      if (appliedGroupId.value === id) {
        appliedGroupId.value = ''
        applyingGroup = true
        q.value = ''
        filters.value = emptyFilters()
        void nextTick(() => { applyingGroup = false })
      }
      await loadGroups()
      toast.success('分组已删除')
    } catch (e) {
      toast.error(`删除分组失败:${(e as Error).message}`)
    }
  }

  // 高亮 = 分组开关态本身(点过且未退出);不再做条件反推 —— 生效词
  // 是分组名而分组里存的是当时的 q,条件比对在新语义下恒不相等。
  const activeGroupId = computed(() => appliedGroupId.value)
  /** 分组态没有"当前手动条件"可存 → 存分组钮在分组态置灰。 */
  const canSaveGroup = computed(() => !appliedGroupId.value && filtering.value)

  async function load(): Promise<void> {
    await list.reload()
  }

  return {
    store,
    q, filters,
    // 浏览镜头(mine 桶):admin 显式「全员视角」开关。
    lensAll, lensAvailable: bucket === 'mine' && auth.isAdmin, toggleLens,
    page: list.page,
    items: list.items,
    /** 兼容旧消费面:rows/paged 均为当前页(服务端已分页)。 */
    rows: list.items,
    paged: list.items,
    total: list.total,
    pageCount: list.pageCount,
    loading: list.loading,
    filtering, filterableRows, facets, loadFacets,
    // 2026-09-23 分页批次:每页行数可变(原为 LIST_PAGE_SIZE 定值直传)。
    pageSize: list.pageSize,
    setPageSize: list.setPageSize,
    load, reload: list.reload, setPage: list.setPage,
    searchBox, writeSearch,
    groups, groupsState, savingGroup, activeGroupId, canSaveGroup,
    loadGroups, applyGroup, saveGroup, removeGroup,
  }
}
