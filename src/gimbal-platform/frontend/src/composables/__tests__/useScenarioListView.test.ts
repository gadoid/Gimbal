/**
 * useScenarioListView — 场景库两页共用的服务端列表骨架(M1 服务端化)。
 * 钉住新的客户端契约:分桶 → visibility 参数下推、筛选 → 多值 csv 参数、
 * 分页只拉目标页、"筛空 vs 真无"判定、取数失败冒泡一句提示。
 * (客户端分桶/过滤/分页的旧行为已整体迁服务端,由后端
 * tests/test_scenario_list_projection.py 覆盖语义。)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { useScenarioListView } from '@/composables/useScenarioListView'
import { toastState } from '@/utils/toast'
import * as composerApi from '@/api/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 }),
  fetchScenarioFacets: vi.fn().mockResolvedValue({
    modules: [], systems: [], tags: [], authors: [], priorities: [],
  }),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: {} as Record<string, string> }),
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
    vi.clearAllMocks()
    mockEnv([])
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
})
