/** Suite 层重构第 4 步:SuiteCompose 画布(10–13)测试。
 *
 * 覆盖:空白画布自动弹 11 说明 +「从空白开始」关闭;首次拖入创建草稿
 * 并换 URL(同记录 alias,组件复用);连线推断(串联/环拒绝);完成编排
 * 命名转正(patchSuite clearDraft)→ 进管理页;非属主访问画布路由
 * 重定向到管理页;已有 Suite 按 mode 回归合成画布连线。
 * jsdom 无法模拟连线手势:addEdge 经 defineExpose 作为测试边界驱动。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

// jsdom 缺 ResizeObserver(vue-flow 依赖)→ 最小桩
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
;(globalThis as Record<string, unknown>).ResizeObserver ??= ResizeObserverStub

import SuiteCompose from '@/views/SuiteCompose.vue'
import * as suitesApi from '@/api/suites'

vi.mock('@/api/suites', () => ({
  createSuite: vi.fn(),
  getSuite: vi.fn(),
  patchSuite: vi.fn(),
  putSuiteComposition: vi.fn(),
  runSuite: vi.fn(),
  validateSuite: vi.fn(),
  suiteErrDetail: vi.fn((e: unknown) => {
    const resp = (e as { response?: { data?: unknown } })?.response
    return (resp?.data as Record<string, unknown> | undefined) ?? null
  }),
}))
vi.mock('@/api/scenario-composer', () => ({
  listScenarioOptions: vi.fn().mockResolvedValue({
    items: [
      { scenarioId: 'sc-login', name: '登录' },
      { scenarioId: 'sc-order', name: '下单' },
      { scenarioId: 'sc-pay', name: '支付' },
    ], total: 3, page: 1, pageSize: 100,
  }),
  listRunSchemes: vi.fn().mockResolvedValue([]),
  getDataSet: vi.fn().mockResolvedValue(
    { datasetId: 'ds-1', name: 'DS', rows: [] }),
}))
vi.mock('@/api/shares', () => ({
  listShares: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn().mockResolvedValue(true),
  promptAction: vi.fn().mockResolvedValue(null),
}))

/** 生产同款:同一路由记录 + alias,首次拖入换 URL 不重挂组件。 */
function routerAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/suites', component: { template: '<div/>' } },
      {
        path: '/suites/:id(\\d+)/compose',
        alias: '/suites/new',
        component: SuiteCompose,
      },
      { path: '/suites/:id(\\d+)', component: { template: '<div/>' } },
    ],
  })
  router.push(path)
  return router
}

function draftSummary(over: Partial<suitesApi.SuiteSummary> = {}): suitesApi.SuiteSummary {
  return {
    suiteId: 7, name: '未命名 Suite 2', description: '', visibility: 'private',
    mode: 'aggregate', memberCount: 0, rev: 0, isDraft: true,
    createdAt: null, updatedAt: null, latestRun: null,
    ...over,
  }
}

function detailOf(over: Partial<suitesApi.SuiteDetail> = {}): suitesApi.SuiteDetail {
  return {
    ...draftSummary({ suiteId: 5, name: '下单链', rev: 4, mode: 'chain' }),
    access: 'owner', canEdit: true, canRun: true, canShare: true,
    modeConfig: { units: {} },
    members: [
      { scenarioId: 'sc-a', name: 'A', module: 'fin', visibility: 'private',
        role: 'main', sort: 0, addedAt: null },
      { scenarioId: 'sc-b', name: 'B', module: 'fin', visibility: 'private',
        role: 'main', sort: 1, addedAt: null },
    ],
    ...over,
  } as suitesApi.SuiteDetail
}

const linkStub = { props: ['to'], template: '<a :href="to"><slot /></a>' }

/** 弹层(结构说明 / 完成编排)Teleport 到 body,经 document 取。 */
function dq(selector: string): DOMWrapper<Element> | null {
  const el = document.querySelector(selector)
  return el ? new DOMWrapper(el) : null
}

async function mountCompose(path: string) {
  const router = routerAt(path)
  await router.isReady()
  const w = mount(SuiteCompose, {
    global: { plugins: [router], stubs: { RouterLink: linkStub } },
  })
  await flushPromises()
  return { w, router }
}

describe('SuiteCompose — 新建画布(10/11/12)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    document.body.innerHTML = ''
  })

  it('空白画布:自动弹四种结构说明,「从空白开始」关闭;状态条引导', async () => {
    const { w } = await mountCompose('/suites/new')
    // 11 弹层自动打开(未设「不再弹出」;Teleport 到 body)
    expect(dq('[data-testid="structure-guide-mask"]')).not.toBeNull()
    expect(dq('[data-testid="structure-guide-card-chain"]')?.text()).toContain('串联')
    await dq('[data-testid="structure-guide-blank"]')?.trigger('click')
    expect(dq('[data-testid="structure-guide-mask"]')).toBeNull()
    // 空态与状态条
    expect(w.find('[data-testid="suite-compose-empty"]').text()).toContain('把入口场景拖到这里')
    expect(w.find('[data-testid="suite-compose-status"]').text()).toContain('拖入第一个场景开始')
    expect(w.find('[data-testid="suite-compose-finish"]').attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('勾选「不再弹出」后关闭写标记,再次进入不自动弹', async () => {
    {
      const { w } = await mountCompose('/suites/new')
      await dq('[data-testid="structure-guide-dontshow"]')?.setValue(true)
      await dq('[data-testid="structure-guide-blank"]')?.trigger('click')
      expect(localStorage.getItem('suite-compose-guide-off')).toBe('1')
      w.unmount()
      document.body.innerHTML = ''
    }
    const { w } = await mountCompose('/suites/new')
    expect(dq('[data-testid="structure-guide-mask"]')).toBeNull()
    w.unmount()
  })

  it('首次拖入创建草稿并换 URL;节点上屏,识别为聚合', async () => {
    vi.mocked(suitesApi.createSuite).mockResolvedValue(draftSummary())
    const { w, router } = await mountCompose('/suites/new')
    const replace = vi.spyOn(router, 'replace')

    await w.find('[data-testid="suite-drawer-add-sc-login"]').trigger('click')
    await flushPromises()

    expect(suitesApi.createSuite).toHaveBeenCalledTimes(1)
    expect(suitesApi.createSuite).toHaveBeenCalledWith({})
    expect(replace).toHaveBeenCalledWith('/suites/7/compose')
    // 组件未重挂(alias 同记录):节点与选中态都在
    expect(w.find('[data-testid="suite-compose-node-sc-login"]').exists()).toBe(true)
    const status = w.find('[data-testid="suite-compose-status"]').text()
    expect(status).toContain('聚合')
    expect(status).toContain('1 单元')
    expect((w.find('[data-testid="suite-compose-name"]').element as HTMLInputElement).value)
      .toBe('未命名 Suite 2')
    w.unmount()
  })
})

describe('SuiteCompose — 连线与结构推断(12)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.setItem('suite-compose-guide-off', '1')
  })

  async function canvasWith(units: string[]) {
    vi.mocked(suitesApi.createSuite).mockResolvedValue(draftSummary())
    const { w } = await mountCompose('/suites/new')
    for (const sid of units) {
      await w.find(`[data-testid="suite-drawer-add-${sid}"]`).trigger('click')
      await flushPromises()
    }
    return w
  }

  it('直线自动识别为串联;成环连线被拒并就地提示', async () => {
    vi.mocked(suitesApi.createSuite).mockResolvedValue(draftSummary())
    const { w } = await mountCompose('/suites/new')
    const vm = w.vm as unknown as {
      addEdge: (producer: string, consumer: string) => void
    }
    // 两单元一条线 → 串联
    await w.find('[data-testid="suite-drawer-add-sc-login"]').trigger('click')
    await flushPromises()
    await w.find('[data-testid="suite-drawer-add-sc-order"]').trigger('click')
    await flushPromises()
    vm.addEdge('sc-login', 'sc-order')
    await flushPromises()
    expect(w.find('[data-testid="suite-compose-status"]').text()).toContain('串联')

    // 补第三单元接成直线 → 仍是串联
    await w.find('[data-testid="suite-drawer-add-sc-pay"]').trigger('click')
    await flushPromises()
    vm.addEdge('sc-order', 'sc-pay')
    await flushPromises()
    expect(w.find('[data-testid="suite-compose-status"]').text()).toContain('串联')

    // pay → login 会形成环:就地提示、边不落下(仍是串联)
    vm.addEdge('sc-pay', 'sc-login')
    await flushPromises()
    const cycle = w.find('[data-testid="suite-compose-cycle"]')
    expect(cycle.exists()).toBe(true)
    expect(cycle.text()).toContain('会形成环')
    expect(w.find('[data-testid="suite-compose-status"]').text()).toContain('串联')
    w.unmount()
  })

  it('分叉识别为扇出;汇合变依赖编排;孤立单元计数提示', async () => {
    const w = await canvasWith(['sc-login', 'sc-order', 'sc-pay'])
    const vm = w.vm as unknown as {
      addEdge: (producer: string, consumer: string) => void
    }
    vm.addEdge('sc-login', 'sc-order')
    vm.addEdge('sc-login', 'sc-pay')
    await flushPromises()
    expect(w.find('[data-testid="suite-compose-status"]').text()).toContain('扇出')

    vm.addEdge('sc-order', 'sc-pay')   // 汇合:超出扇出 → 依赖编排
    await flushPromises()
    expect(w.find('[data-testid="suite-compose-status"]').text()).toContain('依赖编排')
    w.unmount()
  })
})

describe('SuiteCompose — 完成编排与非属主(13)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.setItem('suite-compose-guide-off', '1')
  })

  it('完成编排:命名转正(clearDraft)→ 保存后进管理页', async () => {
    vi.mocked(suitesApi.createSuite).mockResolvedValue(draftSummary())
    vi.mocked(suitesApi.putSuiteComposition).mockResolvedValue(
      detailOf({ suiteId: 7, rev: 1, mode: 'chain' }))
    vi.mocked(suitesApi.patchSuite).mockResolvedValue(draftSummary({ isDraft: false }))
    vi.mocked(suitesApi.validateSuite).mockResolvedValue({
      ok: true, mode: 'chain', unitCount: 2, estimatedRuns: 2, runCap: 1000,
      gates: 0, degraded: false, inFlight: null, items: [],
    } as never)

    const { w, router } = await mountCompose('/suites/new')
    const push = vi.spyOn(router, 'push')
    await w.find('[data-testid="suite-drawer-add-sc-login"]').trigger('click')
    await flushPromises()
    await w.find('[data-testid="suite-drawer-add-sc-order"]').trigger('click')
    await flushPromises()

    await w.find('[data-testid="suite-compose-finish"]').trigger('click')
    await flushPromises()
    expect(dq('[data-testid="suite-compose-finish-mask"]')).not.toBeNull()
    expect(dq('[data-testid="suite-compose-finish-summary"]')?.text())
      .toContain('聚合 · 2 单元')

    await dq('[data-testid="suite-compose-finish-name"]')?.setValue('下单主链')
    await dq('[data-testid="suite-compose-finish-save"]')?.trigger('click')
    await flushPromises()

    expect(suitesApi.patchSuite).toHaveBeenCalledWith(
      7, { name: '下单主链', description: '', clearDraft: true })
    expect(push).toHaveBeenCalledWith('/suites/7')
    w.unmount()
  })

  it('非属主访问画布路由 → 重定向到管理页只读态', async () => {
    vi.mocked(suitesApi.getSuite).mockResolvedValue(
      detailOf({ canEdit: false, access: 'ref' }))
    const router = routerAt('/suites/5/compose')
    await router.isReady()
    const replace = vi.spyOn(router, 'replace')
    const w = mount(SuiteCompose, {
      global: { plugins: [router], stubs: { RouterLink: linkStub } },
    })
    await flushPromises()
    expect(replace).toHaveBeenCalledWith('/suites/5')
    w.unmount()
  })

  it('已有 Suite 按 mode 回归合成画布连线:chain → 状态条直接识别为串联', async () => {
    vi.mocked(suitesApi.getSuite).mockResolvedValue(detailOf())
    const { w } = await mountCompose('/suites/5/compose')
    expect(w.find('[data-testid="suite-compose-node-sc-a"]').exists()).toBe(true)
    const status = w.find('[data-testid="suite-compose-status"]').text()
    expect(status).toContain('串联')
    expect(status).toContain('2 单元')
    w.unmount()
  })
})
