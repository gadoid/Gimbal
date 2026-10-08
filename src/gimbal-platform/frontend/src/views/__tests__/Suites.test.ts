/** 权限域二期 P1:用例组管理页测试(列表渲染/新建 API 接线/详情运行跳批次)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import SuiteLibrary from '@/views/SuiteLibrary.vue'
import SuiteDetail from '@/views/SuiteDetail.vue'
import * as suitesApi from '@/api/suites'

vi.mock('@/api/suites', () => ({
  listSuites: vi.fn(),
  createSuite: vi.fn(),
  getSuite: vi.fn(),
  patchSuite: vi.fn(),
  deleteSuite: vi.fn(),
  addSuiteMembers: vi.fn(),
  reorderSuiteMembers: vi.fn(),
  removeSuiteMember: vi.fn(),
  runSuite: vi.fn(),
  suitesOfScenario: vi.fn(),
}))
vi.mock('@/api/scenario-composer', () => ({
  listScenarioOptions: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 }),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

function routerWith(routes: Array<{ path: string; component?: unknown }>) {
  return createRouter({
    history: createMemoryHistory(),
    routes: routes.map((r) => ({
      path: r.path,
      component: r.component ?? { template: '<div/>' },
    })),
  })
}

describe('SuiteLibrary — 用例组列表', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('渲染我的用例组(镜头 mine);空态有引导', async () => {
    vi.mocked(suitesApi.listSuites).mockResolvedValue({
      items: [
        { suiteId: 1, name: '冒烟集', description: '上线前', visibility: 'private',
          mode: 'aggregate', memberCount: 5, createdAt: null, updatedAt: null },
        { suiteId: 2, name: '回归集', description: '', visibility: 'private',
          mode: 'aggregate', memberCount: 12, createdAt: null, updatedAt: null },
      ],
      total: 2, page: 1, pageSize: 100,
    } as never)
    const router = routerWith([
      { path: '/suites' }, { path: '/suites/:id' },
    ])
    const w = mount(SuiteLibrary, {
      global: { plugins: [router], stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    })
    await flushPromises()
    expect(suitesApi.listSuites).toHaveBeenCalledWith(
      expect.objectContaining({ scope: 'mine' }))
    expect(w.find('[data-testid="suite-row-1"]').text()).toContain('冒烟集')
    expect(w.find('[data-testid="suite-row-2"]').text()).toContain('12 个场景')
    expect(w.text()).toContain('共 2 个用例组')
    w.unmount()
  })

  it('空列表给引导文案', async () => {
    vi.mocked(suitesApi.listSuites).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 100,
    } as never)
    const router = routerWith([{ path: '/suites' }])
    const w = mount(SuiteLibrary, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('还没有用例组')
    w.unmount()
  })
})

describe('SuiteDetail — 成员与运行', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const detail = {
    suiteId: 7, name: '回归集', description: '', visibility: 'private',
    mode: 'aggregate', memberCount: 2,
    createdAt: '2026-10-09T01:00:00Z', updatedAt: '2026-10-09T01:00:00Z',
    members: [
      { scenarioId: 'sc-a', name: '下单', module: 'order',
        visibility: 'private', sort: 0, addedAt: null },
      { scenarioId: 'sc-b', name: '撤单', module: 'order',
        visibility: 'public', sort: 1, addedAt: null },
    ],
  }

  it('渲染成员表(含公共徽标);运行后跳批次归并视图', async () => {
    vi.mocked(suitesApi.getSuite).mockResolvedValue(detail as never)
    vi.mocked(suitesApi.runSuite).mockResolvedValue({
      batchId: 'suite-7-1-abc123def456', started: [11, 12], skipped: [],
      dispatchWarnings: [], totalRuns: 2,
    } as never)
    const router = routerWith([
      { path: '/suites/:id' }, { path: '/executions' },
    ])
    await router.push('/suites/7')
    const w = mount(SuiteDetail, {
      global: { plugins: [router], stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } },
    })
    await flushPromises()

    expect(w.find('[data-testid="suite-member-sc-a"]').text()).toContain('下单')
    expect(w.find('[data-testid="suite-member-sc-b"]').text()).toContain('公共')

    await w.find('[data-testid="suite-run"]').trigger('click')
    await flushPromises()
    expect(suitesApi.runSuite).toHaveBeenCalledWith(7)
    // 跳批次归并视图(§6.6:batch_id 归并键是批次视图/通知聚合的面)
    expect(router.currentRoute.value.fullPath).toBe(
      '/executions?batch_id=suite-7-1-abc123def456')
    w.unmount()
  })
})
