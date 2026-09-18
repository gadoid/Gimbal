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
    listScenarios: vi.fn().mockResolvedValue([]),
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
    total: 3,
    items: [
      { id: 5, scenario_id: 'sc-a', status: 'done', total_runs: 1, passed: 1, failed: 0, started_at: '2026-09-18T09:00:00', finished_at: '2026-09-18T10:00:00', has_scenario_snapshot: true, config: { schemeId: 's1' } },
      { id: 4, scenario_id: 'sc-a', status: 'done', total_runs: 1, passed: 1, failed: 0, started_at: '2026-09-17T09:00:00', finished_at: '2026-09-17T10:00:00', has_scenario_snapshot: true, config: { schemeId: 's3' } },
      { id: 3, scenario_id: 'sc-a', status: 'failed', total_runs: 1, passed: 0, failed: 1, started_at: '2026-09-16T09:00:00', finished_at: '2026-09-16T10:00:00', has_scenario_snapshot: true, config: { schemeId: 's2' } },
    ],
  }),
}))

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
  vi.mocked(composerApi.listScenarios).mockResolvedValue(scenarios)
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
})
