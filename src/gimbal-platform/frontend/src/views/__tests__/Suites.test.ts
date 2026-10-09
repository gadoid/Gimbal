/** Suite 层重构第 2 步:SuiteLibrary(02)与 SuiteManage(20/21/30)测试。
 *
 * 覆盖:列表渲染(模式/成员/最近运行/草稿标记)+ 新建草稿直进管理页 +
 * 共享分区;管理页模式条与自动保存(composition 接线)、只读态(ref)
 * 隐藏编辑面、运行入口开预检、切模式确认丢弃 needs。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import SuiteLibrary from '@/views/SuiteLibrary.vue'
import SuiteManage from '@/views/SuiteManage.vue'
import * as suitesApi from '@/api/suites'
import * as sharesApi from '@/api/shares'

vi.mock('@/api/suites', () => ({
  listSuites: vi.fn(),
  createSuite: vi.fn(),
  getSuite: vi.fn(),
  patchSuite: vi.fn(),
  deleteSuite: vi.fn(),
  addSuiteMembers: vi.fn(),
  reorderSuiteMembers: vi.fn(),
  removeSuiteMember: vi.fn(),
  putSuiteComposition: vi.fn(),
  runSuite: vi.fn(),
  listSuiteRuns: vi.fn(),
  rerunFailedUnits: vi.fn(),
  forkPublicSuite: vi.fn(),
  suitesOfScenario: vi.fn(),
  validateSuite: vi.fn(),
  suiteErrDetail: vi.fn((e: unknown) => {
    const resp = (e as { response?: { data?: unknown } })?.response
    return (resp?.data as Record<string, unknown> | undefined) ?? null
  }),
}))
vi.mock('@/api/scenario-composer', () => ({
  listScenarioOptions: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 }),
  listRunSchemes: vi.fn().mockResolvedValue([]),
  getDataSet: vi.fn().mockResolvedValue({ datasetId: 'ds-1', name: 'DS', rowCount: 1, rows: [] }),
}))
vi.mock('@/api/shares', () => ({
  listShares: vi.fn().mockResolvedValue([]),
  deleteShare: vi.fn(),
  forkShare: vi.fn(),
  listScenarioReferrers: vi.fn().mockResolvedValue({ items: [] }),
}))
vi.mock('@/api/executions', () => ({
  getExecutionRows: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 500 }),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn().mockResolvedValue(true),
  promptAction: vi.fn().mockResolvedValue(null),
}))

function routerWith() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/suites', component: { template: '<div/>' } },
      { path: '/suites/:id', component: SuiteManage },
      { path: '/suites/:id/compose', component: { template: '<div/>' } },
      { path: '/executions/:id(\\d+)', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } },
    ],
  })
}

function suiteItem(over: Partial<suitesApi.SuiteSummary> = {}): suitesApi.SuiteSummary {
  return {
    suiteId: 1, name: '冒烟集', description: '上线前', visibility: 'private',
    mode: 'aggregate', memberCount: 5, rev: 3, isDraft: false,
    createdAt: null, updatedAt: null, latestRun: null,
    ...over,
  }
}

function suiteDetail(over: Partial<suitesApi.SuiteDetail> = {}): suitesApi.SuiteDetail {
  return {
    ...suiteItem({ suiteId: 9, memberCount: 2, mode: 'aggregate' }),
    access: 'owner', canEdit: true, canRun: true, canShare: true,
    modeConfig: { units: {} },
    members: [
      { scenarioId: 'sc-login', name: '登录', module: 'fin', visibility: 'private',
        role: 'main', sort: 0, addedAt: null },
      { scenarioId: 'sc-order', name: '下单', module: 'fin', visibility: 'private',
        role: 'main', sort: 1, addedAt: null },
    ],
    ...over,
  } as suitesApi.SuiteDetail
}

const linkStub = { props: ['to'], template: '<a :href="to"><slot /></a>' }

describe('SuiteLibrary — 列表(02)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('渲染模式/草稿/最近运行;本人最近一次运行失败 → 行点击进 21', async () => {
    vi.mocked(suitesApi.listSuites).mockResolvedValue({
      items: [
        suiteItem({ suiteId: 1, name: '冒烟集', mode: 'aggregate', memberCount: 5 }),
        suiteItem({ suiteId: 2, name: '下单链路', mode: 'chain', memberCount: 3,
          isDraft: true, latestRun: { kind: 'batch', status: 'failed', batchId: 'b-1' } }),
      ],
      total: 2, page: 1, pageSize: 100,
    } as never)
    const router = routerWith()
    const push = vi.spyOn(router, 'push')
    const w = mount(SuiteLibrary, {
      global: { plugins: [router], stubs: { RouterLink: linkStub } },
    })
    await flushPromises()

    expect(w.find('[data-testid="suite-row-1"]').text()).toContain('聚合')
    expect(w.find('[data-testid="suite-row-2"]').text()).toContain('串联')
    expect(w.find('[data-testid="suite-row-2"]').text()).toContain('草稿')
    await w.find('[data-testid="suite-row-2"]').trigger('click')
    expect(push).toHaveBeenCalledWith('/suites/2?tab=runs')
    w.unmount()
  })

  it('模式筛选过滤;「+ 新建 Suite」建草稿并跳管理页', async () => {
    vi.mocked(suitesApi.listSuites).mockResolvedValue({
      items: [
        suiteItem({ suiteId: 1, mode: 'aggregate' }),
        suiteItem({ suiteId: 2, mode: 'chain' }),
      ],
      total: 2, page: 1, pageSize: 100,
    } as never)
    vi.mocked(suitesApi.createSuite).mockResolvedValue(
      suiteItem({ suiteId: 7, name: '未命名 Suite', isDraft: true }))
    const router = routerWith()
    const push = vi.spyOn(router, 'push')
    const w = mount(SuiteLibrary, {
      global: { plugins: [router], stubs: { RouterLink: linkStub } },
    })
    await flushPromises()

    await w.find('[data-testid="suite-filter-chain"]').trigger('click')
    expect(w.findAll('tr[data-testid^="suite-row-"]').length).toBe(1)

    await w.find('[data-testid="suite-create"]').trigger('click')
    await flushPromises()
    expect(suitesApi.createSuite).toHaveBeenCalledWith({})
    expect(push).toHaveBeenCalledWith('/suites/7')
    w.unmount()
  })

  it('「共享给我的」分区渲染并退订', async () => {
    vi.mocked(suitesApi.listSuites).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 100,
    } as never)
    vi.mocked(sharesApi.listShares).mockImplementation((() => Promise.resolve([
      { id: 11, resourceType: 'suite', scenarioId: null, scenarioName: null,
        suiteId: 5, suiteName: '引用集', memberCount: 4, granteeUserId: 1,
        granteeName: 'me', grantedByName: 'alice', grantedAt: null },
    ])) as never)
    vi.mocked(sharesApi.deleteShare).mockResolvedValue(undefined as never)
    const router = routerWith()
    const w = mount(SuiteLibrary, {
      global: { plugins: [router], stubs: { RouterLink: linkStub } },
    })
    await flushPromises()

    expect(w.find('[data-testid="shared-in-suites"]').text()).toContain('引用集')
    expect(w.find('[data-testid="shared-in-suites"]').text()).toContain('alice')
    await w.find('[data-testid="shared-suite-unsub-5"]').trigger('click')
    await flushPromises()
    expect(sharesApi.deleteShare).toHaveBeenCalledWith(11)
    expect(w.find('[data-testid="shared-suite-5"]').exists()).toBe(false)
    w.unmount()
  })
})

describe('SuiteManage — 管理页(20/21/30)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(suitesApi.listSuiteRuns).mockResolvedValue([])
  })

  function mountManage(detail: suitesApi.SuiteDetail) {
    vi.mocked(suitesApi.getSuite).mockResolvedValue(detail)
    const router = routerWith()
    void router.push('/suites/9')
    // attachTo body:reka Dialog teleport 目标(document.querySelector 检索,
    // AddToSuiteDialog.test 同款惯例)
    const w = mount(SuiteManage, {
      attachTo: document.body,
      global: { plugins: [router], stubs: { RouterLink: linkStub } },
    })
    return { w, router }
  }

  it('渲染页头 + 模式条 + 成员;抽屉加入成员触发 composition 自动保存', async () => {
    const detail = suiteDetail()
    const { listScenarioOptions } = await import('@/api/scenario-composer')
    vi.mocked(listScenarioOptions).mockResolvedValue({
      items: [{ scenarioId: 'sc-pay', name: '支付' }],
    } as never)
    const { w } = mountManage(detail)
    await flushPromises()

    expect(w.find('[data-testid="suite-manage-name"]').text()).toContain('冒烟集')
    expect(w.find('[data-testid="suite-mode-aggregate"]').classes()).toContain('on')
    expect(w.findAll('[data-testid^="suite-member-row-"]').length).toBe(2)

    vi.useFakeTimers()
    vi.mocked(suitesApi.putSuiteComposition).mockResolvedValue(
      suiteDetail({ rev: 4, members: [
        ...detail.members,
        { scenarioId: 'sc-pay', name: '支付', module: 'fin', visibility: 'private',
          role: 'main', sort: 2, addedAt: null },
      ] }))
    await w.find('[data-testid="suite-drawer-add-sc-pay"]').trigger('click')
    vi.advanceTimersByTime(900)
    await flushPromises()
    expect(suitesApi.putSuiteComposition).toHaveBeenCalledTimes(1)
    const body = vi.mocked(suitesApi.putSuiteComposition).mock.calls[0][1]
    expect(body.members.map((m) => m.scenarioId)).toContain('sc-pay')
    expect(body.rev).toBe(3)
    vi.useRealTimers()
    w.unmount()
    document.body.innerHTML = ''
  }, 15000)

  it('只读态(ref):隐藏抽屉与模式切换,横幅说明来源,保留运行', async () => {
    const detail = suiteDetail({
      access: 'ref', canEdit: false, canRun: true, canShare: false,
    })
    const { w } = mountManage(detail)
    await flushPromises()

    expect(w.find('[data-testid="suite-scenario-drawer"]').exists()).toBe(false)
    expect(w.find('[data-testid="suite-mode-aggregate"]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-testid="suite-readonly-banner"]').text()).toContain('引用分享')
    expect(w.find('[data-testid="suite-manage-run"]').exists()).toBe(true)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('「运行」先开预检(30):结论取服务端 validate(摘要+条目)', async () => {
    const detail = suiteDetail({
      mode: 'compose',
      modeConfig: { units: {
        'sc-login': {}, 'sc-order': { needs: ['sc-login'] },
      }, gates: [{ metric: 'pass_rate', op: 'gte', value: 1 }] },
    })
    vi.mocked(suitesApi.validateSuite).mockResolvedValue({
      ok: true, mode: 'compose', unitCount: 2, estimatedRuns: 2,
      runCap: 1000, gates: 1, degraded: false, inFlight: null,
      items: [
        { level: 'ok', code: 'pass', message: '预检通过:成员方案有效、依赖图完整' },
      ],
    })
    const { w } = mountManage(detail)
    await flushPromises()

    await w.find('[data-testid="suite-manage-run"]').trigger('click')
    await flushPromises()
    // Dialog teleport 到 body;reka 的 attr fallthrough 不落容器 testid,
    // 以摘要行为准(AddToSuiteDialog.test 同款 body 检索惯例)
    expect(suitesApi.validateSuite).toHaveBeenCalledWith(9)
    const summary = document.querySelector('[data-testid="suite-preflight-summary"]')
    expect(summary?.textContent).toContain('2 个单元')
    expect(summary?.textContent).toContain('判定门 1 条')
    expect(document.querySelector('[data-testid="suite-preflight-item-0"]')
      ?.textContent).toContain('预检通过')
    expect(document.querySelector('[data-testid="suite-preflight-run"]')).toBeTruthy()
    w.unmount()
    document.body.innerHTML = ''
  })

  it('预检 error 条目(如 CYCLE)禁用「开始运行」', async () => {
    const detail = suiteDetail({ mode: 'compose' })
    vi.mocked(suitesApi.validateSuite).mockResolvedValue({
      ok: false, mode: 'compose', unitCount: 2, estimatedRuns: 2,
      runCap: 1000, gates: 0, degraded: false, inFlight: null,
      items: [
        { level: 'error', code: 'CYCLE', message: '依赖存在循环(含 a)',
          units: ['sc-login'] },
      ],
    })
    const { w } = mountManage(detail)
    await flushPromises()
    await w.find('[data-testid="suite-manage-run"]').trigger('click')
    await flushPromises()
    const runBtn = document.querySelector(
      '[data-testid="suite-preflight-run"]') as HTMLButtonElement | null
    expect(runBtn).toBeTruthy()
    expect(runBtn?.disabled).toBe(true)
    expect(document.querySelector('[data-testid="suite-preflight-item-0"]')
      ?.textContent).toContain('依赖存在循环')
    w.unmount()
    document.body.innerHTML = ''
  })

  it('切到聚合丢弃 needs 前弹确认;确认后保存清空 needs', async () => {
    const detail = suiteDetail({
      mode: 'compose',
      modeConfig: { units: { 'sc-order': { needs: ['sc-login'] } } },
    })
    const { w } = mountManage(detail)
    await flushPromises()

    vi.useFakeTimers()
    vi.mocked(suitesApi.putSuiteComposition).mockResolvedValue(
      suiteDetail({ rev: 4, mode: 'aggregate', modeConfig: { units: { 'sc-order': {} } } }))
    const { confirmAction } = await import('@/utils/confirmAction')
    vi.mocked(confirmAction).mockResolvedValue(true)
    await w.find('[data-testid="suite-mode-aggregate"]').trigger('click')
    vi.advanceTimersByTime(900)
    await flushPromises()
    expect(confirmAction).toHaveBeenCalled()
    const body = vi.mocked(suitesApi.putSuiteComposition).mock.calls[0][1]
    expect(body.mode).toBe('aggregate')
    expect(body.modeConfig.units?.['sc-order']?.needs ?? []).toEqual([])
    vi.useRealTimers()
    w.unmount()
    document.body.innerHTML = ''
  })
})
