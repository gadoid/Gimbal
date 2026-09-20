/**
 * 工作台补登的功能页卡 —— 服务画像 / 认证管理 / 适配中心 / 执行器,
 * 以及三张 adminOnly 卡(服务信息管理 / 默认值 / 用户管理)。
 * 钉住 §7 的三条契约:
 * - 每张卡复用完整页的取数与判定谓词,不另开口子、不另算一套计数;
 * - adminOnly 卡对 member 完全不出现;
 * - 取数失败只落本卡空态,网格其余部分照常在。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'
import { useAuthStore } from '@/stores/auth'
import * as composerApi from '@/api/scenario-composer'
import * as executionsApi from '@/api/executions'
import * as adaptationsApi from '@/api/adaptations'
import * as authSessionsApi from '@/api/auth_sessions'
import * as catalogServices from '@/utils/catalog-services'

vi.mock('@/api/constants', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/api/scenario-composer', () => ({ listScenarios: vi.fn() }))
vi.mock('@/api/adaptations', () => ({
  listBatches: vi.fn().mockResolvedValue([]),
  catalogDiff: vi.fn().mockResolvedValue({ pending: [], anomalies: [] }),
  errMsg: (_e: unknown, d: string) => d,
}))
vi.mock('@/api/auth_sessions', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/service-aliases', () => ({ listAliases: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/carry', () => ({ getDefaults: vi.fn().mockResolvedValue({}) }))
vi.mock('@/api/users', () => ({ list: vi.fn().mockResolvedValue([]) }))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceRows: vi.fn().mockResolvedValue([]),
  loadCatalogEntries: vi.fn().mockResolvedValue([]),
}))

function setAuth(isAdmin: boolean): void {
  useAuthStore().currentUser = { id: 1, username: 'alice', display_name: 'A', is_admin: isAdmin } as never
}

function mountPage() {
  return mount(WorkbenchView, {
    global: {
      plugins: [getActivePinia()!],
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
    attachTo: document.body,
  })
}

/** 等某张卡的异步组件落地 */
async function waitCard(w: ReturnType<typeof mountPage>, id: string) {
  await vi.waitFor(() => {
    expect(w.find(`[data-testid="wb-card-${id}"]`).exists()).toBe(true)
  })
}

const scen = (id: string, schemeCount: number, visibility = 'private') => ({
  meta: { scenarioId: id, name: `场景 ${id}`, module: '订单', priority: 1, author: 'A', owner: 'A', tags: [], system: [], updateTime: '2026-09-19T10:00:00Z' },
  steps: [], config: { vars: {} }, tags: [], starred: false, visibility, schemeCount,
}) as never

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
  setAuth(false)
  vi.mocked(composerApi.listScenarios).mockResolvedValue([] as never)
  vi.mocked(adaptationsApi.listBatches).mockResolvedValue([])
  vi.mocked(authSessionsApi.list).mockResolvedValue([] as never)
  vi.mocked(catalogServices.loadCatalogServiceRows).mockResolvedValue([])
})

afterEach(() => { document.body.innerHTML = '' })

describe('功能页卡登记(§7 第 2 条:registry 集中注册)', () => {
  it('member:四张公共卡进网格,三张 adminOnly 卡完全不出现', async () => {
    const w = mountPage()
    await waitCard(w, 'services')
    for (const id of ['services', 'auths', 'adaptations', 'runner']) {
      expect(w.find(`[data-testid="wb-slot-${id}"]`).exists()).toBe(true)
    }
    for (const id of ['service-aliases', 'carry', 'users']) {
      expect(w.find(`[data-testid="wb-slot-${id}"]`).exists()).toBe(false)
    }
    w.unmount()
  })

  it('admin:三张 adminOnly 卡进网格', async () => {
    setAuth(true)
    const w = mountPage()
    await waitCard(w, 'users')
    for (const id of ['service-aliases', 'carry', 'users']) {
      expect(w.find(`[data-testid="wb-slot-${id}"]`).exists()).toBe(true)
    }
    w.unmount()
  })
})

describe('服务画像卡', () => {
  it('计数与行都来自 loadCatalogServiceRows,行深链到服务画像', async () => {
    vi.mocked(catalogServices.loadCatalogServiceRows).mockResolvedValue([
      { name: 'fin', system: '财务', endpointCount: 12 },
      { name: 'ord', system: '交易', endpointCount: 3 },
    ])
    const w = mountPage()
    await waitCard(w, 'services')
    const card = w.find('[data-testid="wb-card-services"]')
    expect(card.find('.chead-count').text()).toBe('2')
    expect(card.find('[data-testid="wb-svc-row-fin"]').text()).toContain('12 端点')
    expect(card.find('[data-testid="wb-svc-row-fin"]').attributes('href')).toBe('/services/fin')
    w.unmount()
  })

  it('plate 不可达只落本卡空态,其余卡照常渲染', async () => {
    vi.mocked(catalogServices.loadCatalogServiceRows).mockRejectedValue(new Error('plate down'))
    const w = mountPage()
    await waitCard(w, 'auths')
    const card = w.find('[data-testid="wb-card-services"]')
    expect(card.find('.card-empty').text()).toContain('Plate 目录不可达')
    expect(w.find('[data-testid="wb-slot-services"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-services-error"]').exists()).toBe(false)
    w.unmount()
  })
})

describe('认证管理卡', () => {
  it('未被引用 = alias_ref_count 与 scenario_ref_count 都空', async () => {
    vi.mocked(authSessionsApi.list).mockResolvedValue([
      { id: 1, alias: 'codfish', token_type: 'Bearer', url: 'u', username: 'x', updated_at: '', alias_ref_count: 0, scenario_ref_count: 0 },
      { id: 2, alias: 'svc-bot', token_type: 'Basic', url: 'u', username: 'y', updated_at: '', alias_ref_count: 0, scenario_ref_count: 2 },
    ] as never)
    const w = mountPage()
    await waitCard(w, 'auths')
    const card = w.find('[data-testid="wb-card-auths"]')
    expect(card.find('.chead-count').text()).toBe('2')
    expect(card.find('[data-testid="wb-ar-row-codfish"]').text()).toContain('未被引用')
    expect(card.find('[data-testid="wb-ar-row-svc-bot"]').text()).toContain('2 处引用')
    w.unmount()
  })
})

describe('适配中心卡', () => {
  it('member 只发 listBatches("mine"),不触发 admin 的 catalogDiff', async () => {
    const w = mountPage()
    await waitCard(w, 'adaptations')
    expect(adaptationsApi.listBatches).toHaveBeenCalledWith('mine')
    expect(adaptationsApi.catalogDiff).not.toHaveBeenCalled()
    w.unmount()
  })

  it('批次行走 BATCH_LABEL 文案并深链批次详情', async () => {
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue([{
      batchId: 'b1', endpointId: 'fin.pay.create', fromVersion: 'v1', toVersion: 'v2',
      status: 'open', operatorId: 1, createdAt: '2026-09-19T10:00:00Z', opCounts: { api: 2 },
    }] as never)
    setAuth(true)
    const w = mountPage()
    await waitCard(w, 'adaptations')
    const row = w.find('[data-testid="wb-ad-row-b1"]')
    expect(row.text()).toContain('待处理')
    expect(row.text()).toContain('v1→v2')
    expect(row.attributes('href')).toBe('/adaptations/batches/b1')
    // admin 侧徽章走 store 的单飞合流,卡上不会重复拉
    await flushPromises()
    expect(adaptationsApi.catalogDiff).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})

describe('执行器卡', () => {
  it('缺方案的私有场景进行里,可执行数只算有方案的', async () => {
    vi.mocked(composerApi.listScenarios).mockResolvedValue([
      scen('p1', 0), scen('p2', 2), scen('pub', 1, 'public'),
    ] as never)
    const w = mountPage()
    await waitCard(w, 'runner')
    const card = w.find('[data-testid="wb-card-runner"]')
    expect(card.find('.chead-count').text()).toBe('1 可跑')
    expect(card.find('[data-testid="wb-rn-row-p1"]').exists()).toBe(true)
    expect(card.find('[data-testid="wb-rn-row-p2"]').exists()).toBe(false)
    expect(card.find('[data-testid="wb-rn-row-p1"]').attributes('href'))
      .toBe('/scenarios/p1/schemes')
    w.unmount()
  })
})
