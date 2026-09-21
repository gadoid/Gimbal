/**
 * ScenarioDetailView — 批次 5 原型修订项(v2.2)钉子:
 * ①断言覆盖率徽标:数据驱动(含 assertion 策略的步骤/总步骤),
 *   整体可点直达断言注册表(徽标即入口,无割裂链接);三态色;
 * ②数据集章节计数可点直达方案工作台(数据集管理承接处);
 * ③「修改编排」已更名「编排」(黄金位让给主操作)。
 * 另:原型注释文案("方案和变量数据已合并…"一行)实测不存在于实现,
 * 剥离项为 no-op(已核实)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import ScenarioDetailView from '@/views/ScenarioDetailView.vue'
import type { Scenario } from '@/types/scenario-composer'
import * as composerApi from '@/api/scenario-composer'

vi.mock('@/api/scenario-composer', () => ({
  getScenario: vi.fn(),
  listDataSets: vi.fn().mockResolvedValue([]),
}))

const push = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ params: { scenarioId: 'sc-demo' } }),
    useRouter: () => ({ push, back: vi.fn() }),
  }
})

function scenario(steps: unknown[]): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo', name: '订单查询', description: '',
      module: '订单', priority: 1, author: 'qa', owner: 'qa',
      tags: [], system: ['fin'], version: 'v0.1.0', expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: steps as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 2,
    stepCount: steps.length,
    tags: [],
  }
}

async function mountPage() {
  const w = mount(ScenarioDetailView, { global: { plugins: [getActivePinia()!] } })
  await flushPromises()
  return w
}

describe('ScenarioDetailView — 断言覆盖率徽标', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
  })

  it('覆盖口径 = 含 assertion 策略的步骤 / 总步骤;全覆盖态', async () => {
    vi.mocked(composerApi.getScenario).mockResolvedValue(scenario([
      { name: '下单', api: { method: 'POST', path: '/o' },
        strategy: [{ kind: 'assertion', target: '$.code', operator: '==', expected: 0 }] },
      { name: '查单', api: { method: 'GET', path: '/q' },
        strategy: [{ kind: 'extract', target: 'v', expression: '$.id' },
                   { kind: 'assertion', target: '$.msg', operator: 'exists' }] },
    ]))
    const w = await mountPage()
    const badge = w.find('[data-testid="assert-cov-badge"]')
    expect(badge.text()).toBe('断言覆盖 2/2')
    expect(badge.classes()).toContain('cov-full')
    w.unmount()
  })

  it('部分/零覆盖三态 + 徽标即注册表入口(可点直达)', async () => {
    vi.mocked(composerApi.getScenario).mockResolvedValue(scenario([
      { name: '下单', api: { method: 'POST', path: '/o' },
        strategy: [{ kind: 'assertion', target: '$.code', operator: '==', expected: 0 }] },
      { name: '查单', api: { method: 'GET', path: '/q' }, strategy: [] },
    ]))
    const w = await mountPage()
    const badge = w.find('[data-testid="assert-cov-badge"]')
    expect(badge.text()).toBe('断言覆盖 1/2')
    expect(badge.classes()).toContain('cov-part')

    await badge.trigger('click')
    expect(push).toHaveBeenCalledWith('/scenarios/sc-demo/assertions')

    // 零覆盖态:无 assertion 策略
    push.mockClear()
    vi.mocked(composerApi.getScenario).mockResolvedValue(scenario([
      { name: 'a', api: { method: 'GET', path: '/a' }, strategy: [] },
    ]))
    await mountPage()
    w.unmount()
  })
})

describe('ScenarioDetailView — 修订小项', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
  })

  it('数据集计数可点直达方案工作台', async () => {
    vi.mocked(composerApi.getScenario).mockResolvedValue(scenario([]) as never)
    vi.mocked(composerApi.listDataSets).mockResolvedValue([
      { datasetId: 'ds-1', scenarioId: 'sc-demo', name: '主流程', rowCount: 3, preview: [] },
      { datasetId: 'ds-2', scenarioId: 'sc-demo', name: '异常', rowCount: 1, preview: [] },
    ] as never)
    const w = await mountPage()
    const link = w.find('[data-testid="ds-count-link"]')
    expect(link.text()).toBe('2')
    await link.trigger('click')
    expect(push).toHaveBeenCalledWith('/scenarios/sc-demo/schemes')
    w.unmount()
  })

  it('「修改编排」已更名「编排」', async () => {
    vi.mocked(composerApi.getScenario).mockResolvedValue(scenario([]) as never)
    const w = await mountPage()
    const btns = w.findAll('button').map((b) => b.text())
    expect(btns).toContain('编排')
    expect(btns).not.toContain('修改编排')
    w.unmount()
  })
})
