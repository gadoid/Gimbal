import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/scenario-composer'
import SchemeWorkbench from '@/views/SchemeWorkbench.vue'

const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-wb' }, query: {} }),
  useRouter: () => ({ push }),
}))
vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const SCHEME_DEFAULT = {
  schemeId: 'rs-001', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}
const SCHEME_A = {
  schemeId: 'rs-002', name: '冒烟', isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-001', rowIndexes: [0] }],
  injectionEntryIds: [], serviceBindings: {}, stepTo: null,
  nRuns: 2, parallel: 1, plugins: null, logSub: null,
}

describe('SchemeWorkbench', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'listRunSchemes').mockResolvedValue([SCHEME_DEFAULT, SCHEME_A])
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      definition: { steps: [], config: { vars: {}, services: {} } },
      orchestration: { steps: [], resourceMeta: {} },
      assertionRegistry: { entries: [] },
    } as never)
    vi.spyOn(api, 'listDataSets').mockResolvedValue([])
    push.mockClear()
  })
  afterEach(() => vi.restoreAllMocks())

  async function mountWb() {
    const w = mount(SchemeWorkbench, { global: { plugins: [] } })
    await flushPromises()
    return w
  }

  it('左栏渲染方案,默认方案置顶并带系统徽标', async () => {
    const w = await mountWb()
    const items = w.findAll('.scheme-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('默认方案')
    expect(items[0].find('.tag-default').exists()).toBe(true)
    expect(items[1].text()).toContain('冒烟')
    // 壳 refresh() 自动选中置顶的默认方案(?scheme= 深链优先)—
    // 简报原文此处为 .not.toContain,与其自带的壳代码/Step 2「2 passed」预期矛盾,按意图修正
    expect(items[0].classes()).toContain('selected')
  })

  it('点击方案项选中', async () => {
    const w = await mountWb()
    await w.findAll('.scheme-item')[1].trigger('click')
    expect(w.find('.scheme-item.selected').text()).toContain('冒烟')
  })
})
