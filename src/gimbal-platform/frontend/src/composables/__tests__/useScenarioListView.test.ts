/**
 * useScenarioListView — 场景库两页共用的服务端列表骨架(M1 服务端化)。
 * 钉住新的客户端契约:分桶 → visibility 参数下推、筛选 → 多值 csv 参数、
 * 分页只拉目标页、"筛空 vs 真无"判定、取数失败冒泡一句提示。
 * (客户端分桶/过滤/分页的旧行为已整体迁服务端,由后端
 * tests/test_scenario_list_projection.py 覆盖语义。)
 *
 * 另半段是筛选分组(2026-09-22 改落服务端 user_prefs;同日定稿新语义):
 * chip = 以分组名搜索的开关 —— 存 = 带当前条件的单条写 + 回读(成功后
 * 框/筛选让位)、点名 = 生效 q 用分组名且框不回填、再点 = 取消回全量、
 * 手动面一动即退出分组态、URL q 命中分组名自动还原分组态、
 * 读失败要给重试入口而不是伪装成「一个分组都没有」。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useScenarioListView } from '@/composables/useScenarioListView'
import { toastState } from '@/utils/toast'
import * as composerApi from '@/api/scenario-composer'
import * as groupApi from '@/api/scenario-filter-groups'
import type { FilterGroup } from '@/api/scenario-filter-groups'
import type { ScenarioListItem } from '@/types/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 }),
  fetchScenarioFacets: vi.fn().mockResolvedValue({
    modules: [], systems: [], tags: [], authors: [], priorities: [],
  }),
}))

vi.mock('@/api/scenario-filter-groups', () => ({
  listFilterGroups: vi.fn().mockResolvedValue([]),
  createFilterGroup: vi.fn(),
  deleteFilterGroup: vi.fn().mockResolvedValue(undefined),
}))

/** 路由 query 可变:URL → 分组态还原的用例要往里塞 q。 */
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string> }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: routeState.query }),
    useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  }
})

function item(i: number): ScenarioListItem {
  return {
    meta: {
      scenarioId: `sc-${i}`, name: `场景 ${i}`, description: '', module: '支付',
      priority: 1, author: 'Alice', owner: 'Alice', tags: [`t${i}`], system: ['fin'],
      updateTime: '2026-09-15T15:13:00',
    },
    dataSetCount: 0, schemeCount: 0, stepCount: 1, varCount: 0,
    tags: [`t${i}`], starred: false, visibility: 'private',
  } as unknown as ScenarioListItem
}

function group(over: Partial<FilterGroup> = {}): FilterGroup {
  return {
    id: 'g-1', name: '大促回归', q: '订单',
    filters: {
      modules: ['支付'], tags: [], authors: [], priorities: [],
      systems: ['fin'], updatedWithin: '7d',
    },
    createdAt: '2026-09-22T10:00:00+00:00',
    ...over,
  }
}

function mockEnv(items: ScenarioListItem[], total = items.length) {
  vi.mocked(composerApi.listScenarios).mockResolvedValue(
    { items, total, page: 1, pageSize: 20 } as never,
  )
}

async function lastCallParams(): Promise<Record<string, unknown>> {
  return vi.mocked(composerApi.listScenarios).mock.lastCall?.[0] as Record<string, unknown>
}

describe('useScenarioListView(服务端化)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastState.items.splice(0, toastState.items.length)
    routeState.query = {}
    vi.clearAllMocks()
    mockEnv([])
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([])
    vi.mocked(groupApi.createFilterGroup).mockResolvedValue(group())
    vi.mocked(groupApi.deleteFilterGroup).mockResolvedValue(undefined)
  })

  it('分桶下推:mine → visibility=private,public → visibility=public', async () => {
    mockEnv([item(1)])
    const mine = useScenarioListView('mine')
    await mine.load()
    expect((await lastCallParams()).visibility).toBe('private')

    const pub = useScenarioListView('public')
    await pub.load()
    expect((await lastCallParams()).visibility).toBe('public')
  })

  it('筛选参数下推为 csv;updatedWithin 只在非 all 时带', async () => {
    mockEnv([])
    const v = useScenarioListView('mine')
    v.q.value = '订单'
    v.filters.value = {
      ...v.filters.value,
      systems: ['fin', 'logi'], modules: ['支付'], tags: ['t1'],
      authors: ['Alice'], priorities: [1, 2], updatedWithin: '7d',
    }
    await v.load()
    const p = await lastCallParams()
    expect(p.q).toBe('订单')
    expect(p.system).toBe('fin,logi')
    expect(p.module).toBe('支付')
    expect(p.tag).toBe('t1')
    expect(p.author).toBe('Alice')
    expect(p.priority).toBe('1,2')
    expect(p.updatedWithin).toBe('7d')

    v.filters.value = { ...v.filters.value, updatedWithin: 'all' }
    await v.load()
    expect((await lastCallParams()).updatedWithin).toBeUndefined()
  })

  it('摊平行带上筛选层认得的键,FilterPopover 才能按 module/author/系统取值', async () => {
    mockEnv([item(1)])
    const v = useScenarioListView('mine')
    await v.load()
    const row = v.filterableRows.value[0]!
    expect(row.module).toBe('支付')
    expect(row.author).toBe('Alice')
    expect(row.updated_at).toBe('2026-09-15T15:13:00')
    expect(row.system).toEqual(['fin'])
  })

  it('facets 随列表口径拉取(分桶 visibility + q),失败回落 null 池兜底', async () => {
    const v = useScenarioListView('mine')
    await flushPromises()
    const facetsCall = vi.mocked(composerApi.fetchScenarioFacets).mock.calls[0]
    expect(facetsCall?.[0]).toEqual({ visibility: 'private' })

    v.q.value = '订单'
    await flushPromises()
    expect(
      vi.mocked(composerApi.fetchScenarioFacets).mock.lastCall?.[0],
    ).toEqual({ q: '订单', visibility: 'private' })

    // 请求失败 → facets 置 null(FilterPopover 回落当前页 uniq 池)
    vi.mocked(composerApi.fetchScenarioFacets).mockRejectedValueOnce(new Error('502'))
    v.q.value = '划转'
    await flushPromises()
    expect(v.facets.value).toBeNull()
  })

  it('分页只拉目标页;total 来自信封', async () => {
    mockEnv([item(1)], 25)
    const v = useScenarioListView('mine')
    await v.load()
    expect(v.total.value).toBe(25)
    expect(v.pageCount.value).toBe(2)
    v.setPage(2)
    await flushPromises()
    const p = await lastCallParams()
    expect(p.page).toBe(2)
    expect(p.page_size).toBe(20)
  })

  it('filtering 区分「筛空了」和「本来就什么都没有」', () => {
    const v = useScenarioListView('mine')
    expect(v.filtering.value).toBe(false)
    v.q.value = 'x'
    expect(v.filtering.value).toBe(true)
    v.q.value = ''
    v.filters.value = { ...v.filters.value, modules: ['支付'] }
    expect(v.filtering.value).toBe(true)
  })

  it('取数失败 → 冒泡成「加载场景失败」提示', async () => {
    vi.mocked(composerApi.listScenarios).mockRejectedValueOnce(new Error('502'))
    const v = useScenarioListView('mine')
    await v.load()
    await flushPromises()
    expect(v.store.pageStatus).toBe('error')
    expect(toastState.items.some((t) => t.kind === 'error' && t.message.includes('502'))).toBe(true)
  })

  // ── 筛选分组(服务端持久)──────────────────────────────────────
  it('分组按分桶各读各的(mine/public 不互串)', async () => {
    const mine = useScenarioListView('mine')
    await flushPromises()
    expect(mine.groupsState.value).toBe('ready')
    const pub = useScenarioListView('public')
    await flushPromises()
    expect(vi.mocked(groupApi.listFilterGroups).mock.calls.map((c) => c[0]))
      .toEqual(['mine', 'public'])
  })

  it('存分组 = 带当前 q + 筛选 + 分桶的单条写;成功后条件让位,框与筛选清空', async () => {
    const v = useScenarioListView('mine')
    await flushPromises()
    const g = group()
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([g])
    v.q.value = g.q
    v.filters.value = JSON.parse(JSON.stringify(g.filters))

    await v.saveGroup(g.name)
    expect(groupApi.createFilterGroup).toHaveBeenCalledWith({
      bucket: 'mine', name: g.name, q: g.q, filters: g.filters,
    })
    await flushPromises()
    expect(v.groups.value.map((x) => x.name)).toEqual([g.name])
    expect(v.groupsState.value).toBe('ready')
    // 条件已进分组:搜索框不显示内容、筛选复位、无分组态(想再用点 chip)
    expect(v.searchBox.value).toBe('')
    expect(v.filters.value.systems).toEqual([])
    expect(v.activeGroupId.value).toBe('')
  })

  it('点分组 = 以分组名搜索:生效 q 是分组名,搜索框不回填,筛选整体写入', async () => {
    mockEnv([])
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([group()])
    const v = useScenarioListView('mine')
    await flushPromises()

    v.applyGroup(v.groups.value[0]!)
    expect(v.q.value).toBe('')                       // 存的 q(订单)不进框
    expect(v.searchBox.value).toBe('')
    expect(v.filters.value.systems).toEqual(['fin'])
    expect(v.filters.value.updatedWithin).toBe('7d')
    expect(v.activeGroupId.value).toBe('g-1')

    await v.load()
    const p = await lastCallParams()
    expect(p.q).toBe('大促回归')                      // 生效词 = 分组名
    expect(p.updatedWithin).toBe('7d')
  })

  it('再点同一个分组 = 取消搜索:回全量(词/筛选/分组态全清)', async () => {
    mockEnv([])
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([group()])
    const v = useScenarioListView('mine')
    await flushPromises()
    v.applyGroup(v.groups.value[0]!)

    v.applyGroup(v.groups.value[0]!)
    expect(v.q.value).toBe('')
    expect(v.searchBox.value).toBe('')
    expect(v.filters.value.systems).toEqual([])
    expect(v.activeGroupId.value).toBe('')

    await v.load()
    expect((await lastCallParams()).q).toBeUndefined()
  })

  it('手动面一动即退出分组态:输入框敲字 / FilterPopover 改筛选,高亮熄灭', async () => {
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([group()])
    const v = useScenarioListView('mine')
    await flushPromises()
    v.applyGroup(v.groups.value[0]!)
    expect(v.activeGroupId.value).toBe('g-1')

    v.writeSearch('手动搜')
    expect(v.activeGroupId.value).toBe('')
    expect(v.searchBox.value).toBe('手动搜')

    v.applyGroup(v.groups.value[0]!)
    await flushPromises()
    v.filters.value = { ...v.filters.value, systems: ['wms'] }   // popover 改筛选
    await flushPromises()
    expect(v.activeGroupId.value).toBe('')
    expect(v.filters.value.systems).toEqual(['wms'])              // 改动保留
  })

  it('URL q 命中分组名 → 自动进分组态(刷新不破相:框仍空、chip 高亮)', async () => {
    mockEnv([])
    routeState.query = { q: '大促回归' }
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([group()])
    const v = useScenarioListView('mine')
    await flushPromises()
    expect(v.activeGroupId.value).toBe('g-1')
    expect(v.searchBox.value).toBe('')
    await v.load()
    expect((await lastCallParams()).q).toBe('大促回归')
  })

  it('分组读失败 → error 态 + 可重试,不伪装成「一个分组都没有」', async () => {
    vi.mocked(groupApi.listFilterGroups).mockRejectedValueOnce(new Error('502'))
    const v = useScenarioListView('mine')
    await flushPromises()
    expect(v.groupsState.value).toBe('error')
    expect(v.groups.value).toEqual([])

    await v.loadGroups()
    expect(v.groupsState.value).toBe('ready')
  })

  it('删掉正在高亮的分组 → 高亮跟着清空', async () => {
    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([group()])
    const v = useScenarioListView('mine')
    await flushPromises()
    v.applyGroup(v.groups.value[0]!)
    expect(v.activeGroupId.value).toBe('g-1')

    vi.mocked(groupApi.listFilterGroups).mockResolvedValue([])
    await v.removeGroup('g-1')
    await flushPromises()
    expect(groupApi.deleteFilterGroup).toHaveBeenCalledWith('mine', 'g-1')
    expect(v.groups.value).toEqual([])
    expect(v.activeGroupId.value).toBe('')
  })
})
