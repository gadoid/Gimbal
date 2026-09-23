/**
 * ScenariosMine — 我的场景页数据接线回归。
 * 钉住:私有分桶、方案内联预览(≤3 卡 + 溢出 tile)、默认徽章与最近执行
 * 状态、次数/并发内联编辑落 updateRunScheme、▶ 执行落 runScenario。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ScenariosMine from '@/views/ScenariosMine.vue'
import * as composerApi from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

vi.mock('@/api/scenario-composer', () => {
  const sch = (id: string, name: string, isDefault: boolean) => ({
    schemeId: id, name, isDefault, dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1,
  })
  return {
    listScenarios: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 }),
    fetchScenarioFacets: vi.fn().mockResolvedValue({ modules: [], systems: [], tags: [], authors: [], priorities: [] }),
    listRunSchemes: vi.fn().mockResolvedValue([
      sch('s1', '标准回归', true), sch('s2', '边界值压测', false), sch('s3', '大促压测', false),
      sch('s4', '夜间巡检', false), sch('s5', '冒烟', false),
    ]),
    updateRunScheme: vi.fn().mockResolvedValue({}),
    runScenario: vi.fn().mockResolvedValue({ runId: 'run-1' }),
    getScenarioDraft: vi.fn(),
    schemeToRunRequest: (s: { schemeId: string; name: string; nRuns: number; parallel: number }, id: string) => ({
      scenarioId: id, schemeId: s.schemeId, schemeName: s.name, nRuns: s.nRuns, parallel: s.parallel,
    }),
  }
})

vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({
    total: 3, page: 1, pageSize: 200,
    items: [
      { id: 5, scenario_id: 'sc-a', status: 'done', total_runs: 1, passed: 1, failed: 0, started_at: '2026-09-18T09:00:00', finished_at: '2026-09-18T10:00:00', has_scenario_snapshot: true, configSummary: { schemeId: 's1' } },
      { id: 4, scenario_id: 'sc-a', status: 'done', total_runs: 1, passed: 1, failed: 0, started_at: '2026-09-17T09:00:00', finished_at: '2026-09-17T10:00:00', has_scenario_snapshot: true, configSummary: { schemeId: 's3' } },
      { id: 3, scenario_id: 'sc-a', status: 'failed', total_runs: 1, passed: 0, failed: 1, started_at: '2026-09-16T09:00:00', finished_at: '2026-09-16T10:00:00', has_scenario_snapshot: true, configSummary: { schemeId: 's2' } },
    ],
  }),
}))

// 按方案导出走 plate /convert(经 scenario-draft store),单测不打真接口;
// 下载工具依赖 URL.createObjectURL(jsdom 无),一并 mock。
vi.mock('@/stores/scenario-draft', () => ({
  convertDraftToExecutable: vi.fn().mockResolvedValue({ converted: true }),
  schemeToOverlay: (s: { serviceBindings: Record<string, unknown> }) => ({ serviceBindings: s.serviceBindings }),
}))
vi.mock('@/utils/download', () => ({ downloadFile: vi.fn() }))
// F1(2026-09-23):分发徽标/销账走独立 api —— mock 掉避免测试环境发真请求
vi.mock('@/api/handoff', () => ({
  getHandoffUnread: vi.fn().mockResolvedValue({ items: [] }),
  getRoster: vi.fn().mockResolvedValue({ items: [] }),
  postHandoff: vi.fn(),
}))
vi.mock('@/api/notifications', () => ({ markRead: vi.fn().mockResolvedValue({ marked: 0 }) }))

function scen(id: string, vis: 'private' | 'public', schemeCount: number): Scenario {
  return {
    meta: {
      scenarioId: id, name: id, description: '', module: 'm', priority: 1,
      author: 'Alice', owner: 'Alice', tags: [], system: ['fin'], updateTime: '2026-09-15T15:13:00',
    },
    steps: [], config: { vars: {} }, dataSetCount: 0, stepCount: 1, schemeCount,
    tags: [], starred: false, visibility: vis,
  } as unknown as Scenario
}

function mountPage(scenarios: Scenario[] = []) {
  // 服务端分桶:mock 尊重 visibility 参数(页面不再做客户端桶过滤)。
  vi.mocked(composerApi.listScenarios).mockImplementation(async (params) => {
    const items = params?.visibility
      ? scenarios.filter((s) => s.visibility === params.visibility)
      : scenarios
    return { items, total: items.length, page: params?.page ?? 1, pageSize: params?.page_size ?? 20 } as never
  })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios/mine', component: { template: '<div/>' } },
      { path: '/composer/:scenarioId', component: { template: '<div/>' } },
      { path: '/scenarios/:scenarioId/schemes', component: { template: '<div/>' } },
    ],
  })
  return mount(ScenariosMine, {
    global: {
      plugins: [router],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        DropdownMenu: { template: '<div><slot /></div>' },
        DropdownMenuTrigger: { template: '<button><slot /></button>' },
        DropdownMenuContent: { template: '<div><slot /></div>' },
        DropdownMenuItem: { template: '<div><slot /></div>' },
        DropdownMenuSub: { template: '<div><slot /></div>' },
        DropdownMenuSubTrigger: { template: '<div><slot /></div>' },
        DropdownMenuSubContent: { template: '<div><slot /></div>' },
        FilterPopover: { template: '<div/>' },
      },
    },
  })
}

describe('ScenariosMine — 拆分后的我的场景页', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('只列私有场景;无方案行显示虚线「+ 创建方案」', async () => {
    const w = mountPage([scen('sc-a', 'private', 5), scen('sc-hello', 'private', 0), scen('sc-p1', 'public', 0)])
    await flushPromises()
    expect(w.text()).toContain('sc-a')
    expect(w.text()).toContain('sc-hello')
    expect(w.text()).not.toContain('sc-p1')
    expect(w.find('.schemes-chip').text()).toContain('5 个方案')
    expect(w.find('.create-scheme-chip').exists()).toBe(true)
    w.unmount()
  })

  it('展开方案面板:≤3 卡 + 溢出 tile;默认徽章与最近执行状态', async () => {
    const w = mountPage([scen('sc-a', 'private', 5)])
    await flushPromises()
    await w.find('.schemes-chip').trigger('click')
    await flushPromises()
    const cards = w.findAll('.scheme-card')
    expect(cards.length).toBe(3)
    expect(cards[0].text()).toContain('默认')
    expect(cards[0].text()).toContain('完成')
    expect(cards[0].classes()).toContain('st-ok')
    expect(cards[1].text()).toContain('失败')
    expect(cards[1].classes()).toContain('st-bad')
    expect(w.find('.scheme-manage-tile').text()).toContain('还有 2 个')
    w.unmount()
  })

  it('并发内联编辑落 updateRunScheme', async () => {
    const w = mountPage([scen('sc-a', 'private', 5)])
    await flushPromises()
    await w.find('.schemes-chip').trigger('click')
    await flushPromises()
    const badge = w.findAll('.mini-badge').find((b) => b.text().includes('并发'))!
    await badge.trigger('click')
    const input = w.find('.mini-badge.editing input')
    await input.setValue('4')
    await input.trigger('blur')
    await flushPromises()
    expect(composerApi.updateRunScheme).toHaveBeenCalledWith('sc-a', 's1', expect.objectContaining({ parallel: 4 }))
    w.unmount()
  })

  it('▶ 执行按方案物化 RunRequest 发起', async () => {
    const w = mountPage([scen('sc-a', 'private', 5)])
    await flushPromises()
    await w.find('.schemes-chip').trigger('click')
    await flushPromises()
    await w.find('.run-link').trigger('click')
    await flushPromises()
    expect(composerApi.runScenario).toHaveBeenCalledWith(
      expect.objectContaining({ scenarioId: 'sc-a', schemeId: 's1' }),
    )
    w.unmount()
  })

  it('并发越界被拦下,不落 updateRunScheme', async () => {
    const w = mountPage([scen('sc-a', 'private', 5)])
    await flushPromises()
    await w.find('.schemes-chip').trigger('click')
    await flushPromises()
    const badge = w.findAll('.mini-badge').find((b) => b.text().includes('并发'))!
    await badge.trigger('click')
    const input = w.find('.mini-badge.editing input')
    // 本文件 beforeEach 不清 mock 史 → 断言"调用数不增加"而非 not.toHaveBeenCalled
    const put = vi.mocked(composerApi.updateRunScheme)
    const before = put.mock.calls.length
    await input.setValue('9999')      // 上限 200;input 的 max 只是装饰
    await input.trigger('blur')
    await flushPromises()
    expect(put.mock.calls.length).toBe(before)
    w.unmount()
  })

  it('按方案导出走行菜单子菜单 —— 同名方案以 schemeId 区分不串台', async () => {
    vi.mocked(composerApi.listRunSchemes).mockResolvedValueOnce([
      { schemeId: 'sX', name: '同名方案', isDefault: true, dataSetSelection: [],
        injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1 },
      { schemeId: 'sY', name: '同名方案', isDefault: false, dataSetSelection: [],
        injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 2, parallel: 3 },
    ] as never)
    const { downloadFile } = await import('@/utils/download')
    const w = mountPage([scen('sc-a', 'private', 2)])
    await flushPromises()
    // 打开行菜单 → 预取方案 → 子菜单项按 schemeId 渲染
    await w.find('.more-btn').trigger('click')
    await flushPromises()
    const items = w.findAll('[data-testid^="export-scheme-"]')
    const keys = items.map((i) => i.attributes('data-testid'))
    // 以 name 为键时这里会是两个一模一样的 '同名方案' → 点第二个仍拿第一个
    expect(keys).toContain('export-scheme-sX')
    expect(keys).toContain('export-scheme-sY')
    expect(new Set(keys).size).toBe(keys.length)
    await items.find((i) => i.attributes('data-testid') === 'export-scheme-sY')!.trigger('click')
    await flushPromises()
    expect(downloadFile).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('管理员看到的列表含他人私有 → 副标题不得自称"你的"', async () => {
    const { useAuthStore } = await import('@/stores/auth')
    useAuthStore().currentUser = { id: 1, username: 'root', display_name: 'root', is_admin: true } as never
    const w = mountPage([scen('sc-a', 'private', 1)])
    await flushPromises()
    expect(w.find('.slib-sub').text()).toContain('管理员可见全员私有编排')
    expect(w.find('.slib-sub').text()).not.toContain('你创建或拥有的')
    w.unmount()
  })

  it('再次展开强刷执行状态:「执行中」旧照在执行完成后不得残留', async () => {
    // 复现 2026-09-23 缺陷:发起执行时缓存里是 running;执行早已完成、
    // 执行记录页也翻篇了,回到本页再展开若不强刷,卡面仍钉在「执行中」。
    const { listExecutions } = await import('@/api/executions')
    const mk = (status: string, extra: Record<string, unknown> = {}) => ({
      id: 9, scenario_id: 'sc-a', status, total_runs: 1, passed: 0, failed: 0,
      started_at: '2026-09-23T09:00:00', finished_at: null,
      has_scenario_snapshot: true, configSummary: { schemeId: 's1' }, ...extra,
    })
    vi.mocked(listExecutions).mockResolvedValue({
      total: 1, page: 1, pageSize: 200, items: [mk('running')],
    } as never)
    const w = mountPage([scen('sc-a', 'private', 5)])
    await flushPromises()
    await w.find('.schemes-chip').trigger('click')
    await flushPromises()
    expect(w.find('.scheme-card').text()).toContain('执行中')
    // 服务端已终态(此时执行记录页能看到「已完成」)
    vi.mocked(listExecutions).mockResolvedValue({
      total: 1, page: 1, pageSize: 200,
      items: [mk('done', { passed: 1, finished_at: '2026-09-23T09:01:00' })],
    } as never)
    await w.find('.schemes-chip').trigger('click')   // 收起
    await w.find('.schemes-chip').trigger('click')   // 再展开 → 强刷拿新状态
    await flushPromises()
    const card = w.find('.scheme-card')
    expect(card.text()).toContain('完成')
    expect(card.classes()).toContain('st-ok')
    w.unmount()
  })

  it('F1:未读分享徽标渲染,进入场景即销账', async () => {
    const { getHandoffUnread } = await import('@/api/handoff')
    const { markRead } = await import('@/api/notifications')
    vi.mocked(getHandoffUnread).mockResolvedValue({
      items: [{ id: 7, resourceId: 'sc-a', senderName: 'Alice' }],
    })
    const w = mountPage([scen('sc-a', 'private', 1)])
    await flushPromises()
    const badge = w.find('[data-testid="handoff-badge-sc-a"]')
    expect(badge.exists()).toBe(true)
    expect(badge.attributes('title')).toContain('来自 Alice 的分享')

    // 点名进入场景 → 乐观摘牌 + 按通知 id 标读
    await w.find('.sl-name button.nm').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="handoff-badge-sc-a"]').exists()).toBe(false)
    expect(markRead).toHaveBeenCalledWith([7])
    w.unmount()
  })
})
