/**
 * 工作台右侧固定栏:身份卡 + 时间线。
 * 钉住:头像色与用户名一一稳定(与用户管理表同一份 token 调色板)、
 * 计数读场景 store(不另发请求)、时间线按天分组且每行可下钻、
 * member 无适配权限时不显示降级警示、右栏不进 registry(不可删/不可拖)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import UserIdentityCard from '@/components/workbench/UserIdentityCard.vue'
import ActivityTimeline from '@/components/workbench/ActivityTimeline.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'
import { useTimelineColors } from '@/composables/useTimelineColors'
import { useAuthStore } from '@/stores/auth'
import * as composerApi from '@/api/scenario-composer'
import * as executionsApi from '@/api/executions'
import * as adaptationsApi from '@/api/adaptations'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/executions', () => ({ listExecutions: vi.fn() }))
vi.mock('@/api/adaptations', () => ({ listBatches: vi.fn() }))
vi.mock('@/api/constants', () => ({ list: vi.fn().mockResolvedValue([]) }))

const as = (over: Record<string, unknown> = {}) => ({
  id: 3, username: 'alice', display_name: 'Alice Zhang', is_admin: false,
  created_at: '2026-01-05T08:00:00Z', ...over,
})
const scen = (id: string, vis: 'private' | 'public', at: string) => ({
  meta: {
    scenarioId: id, name: `场景 ${id}`, module: 'm', priority: 1, author: 'Alice',
    owner: 'Alice', tags: [], system: [], updateTime: at,
  },
  steps: [], config: { vars: {} }, tags: [], starred: false, visibility: vis,
}) as never

function mountWithRouter(component: object) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:all(.*)', component: { template: '<div/>' } }],
  })
  return mount(component as never, {
    global: {
      plugins: [router],
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })
}

const ago = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString()

describe('UserIdentityCard — 右栏身份卡', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()                      // 用例间不共享取数次数
    vi.mocked(composerApi.listScenarios).mockResolvedValue([] as never)
  })

  it('姓名靠左、头像放大靠右;角色徽标按 is_admin 分档', () => {
    useAuthStore().currentUser = as() as never
    const w = mountWithRouter(UserIdentityCard)
    const avatar = w.find('.avatar')
    expect(avatar.text()).toBe('A')
    expect(avatar.attributes('style')).toContain('var(--avatar-4)')   // id=3 → 第 4 档(1 基)
    // 视觉右置 = 源码里排在文字块之后(不做 flex 反转)
    const kids = Array.from(w.find('.id-hero').element.children)
    expect(kids.indexOf(avatar.element)).toBeGreaterThan(kids.indexOf(w.find('.id-text').element))
    expect(w.find('.id-name').text()).toBe('Alice Zhang')
    expect(w.find('.id-welcome').text()).toMatch(/好，欢迎回到工作台$/)
    expect(w.find('.id-user').text()).toBe('@alice')
    expect(w.find('.id-role').text()).toBe('成员')
    expect(w.find('.id-joined').exists()).toBe(false)                 // 加入时间已撤

    useAuthStore().currentUser = as({ is_admin: true }) as never
    const admin = mountWithRouter(UserIdentityCard)
    expect(admin.find('.id-role').text()).toBe('管理员')
    expect(admin.find('.id-role').classes()).toContain('admin')
  })

  it('计数走 store 同一份取数;store 未加载时显示占位而不是假 0', async () => {
    vi.mocked(composerApi.listScenarios).mockResolvedValue([
      scen('p1', 'private', ago(1)), scen('p2', 'private', ago(2)), scen('pub', 'public', ago(3)),
    ] as never)
    useAuthStore().currentUser = as() as never
    const w = mountWithRouter(UserIdentityCard)
    expect(w.findAll('.id-stat dd').map((d) => d.text())).toEqual(['—', '—'])
    await flushPromises()
    const stats = w.findAll('.id-stat dd').map((d) => d.text())
    expect(stats).toEqual(['2', '0'])              // 私有 2 个(公共不计),关注 0
    expect(composerApi.listScenarios).toHaveBeenCalledTimes(1)
    // 再挂一张卡也不该重复取数(store.ensureScenarios 单飞 + 复用)
    const second = mountWithRouter(UserIdentityCard)
    await flushPromises()
    expect(composerApi.listScenarios).toHaveBeenCalledTimes(1)
    second.unmount()
    w.unmount()
  })

  it('未登录(currentUser 还没到位)→ 整卡不渲染,不出现空壳', () => {
    useAuthStore().currentUser = null
    const w = mountWithRouter(UserIdentityCard)
    expect(w.find('[data-testid="wb-rail-identity"]').exists()).toBe(false)
    w.unmount()
  })
})

describe('ActivityTimeline — 右栏时间线', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useAuthStore().currentUser = as() as never
    useTimelineColors().reset()              // 配色是 module 单例:用例间归零
    vi.mocked(composerApi.listScenarios).mockResolvedValue([] as never)
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue([] as never)
  })

  it('三源合流按天分组,每行深链到自己的详情页', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({
      total: 2,
      items: [
        { id: 12, scenario_id: 'sc-a', status: 'failed', passed: 0, failed: 1, total_runs: 1, started_at: ago(2), finished_at: ago(2), config: {} },
        { id: 11, scenario_id: 'sc-a', status: 'done', passed: 1, failed: 0, total_runs: 1, started_at: ago(30), finished_at: ago(30), config: {} },
      ],
    } as never)
    vi.mocked(composerApi.listScenarios).mockResolvedValue([scen('p1', 'private', ago(5))] as never)
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue([{
      batchId: 'b1', endpointId: 'fin.pay.create', fromVersion: 'v1', toVersion: 'v2',
      status: 'completed', operatorId: 3, createdAt: ago(6), closedAt: ago(6), opCounts: { api: 2 },
    }] as never)

    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()
    expect(w.findAll('.tl-day').map((d) => d.text())).toEqual(['今天', '昨天'])
    const rows = w.findAll('.tl-item')
    expect(rows).toHaveLength(4)
    expect(rows[0].text()).toContain('执行 #12 失败')
    // 圆点/徽标同色:颜色来自「类型→颜色」映射,不是状态色
    expect(rows[0].find('.tl-dot').attributes('style')).toContain('var(--avatar-2)')
    expect(rows[0].find('.tl-time').text()).toContain('h 前')
    expect(rows[0].find('.tl-kind').text()).toBe('执行')
    expect(rows[0].find('.tl-kind').attributes('style')).toContain('var(--avatar-2)')
    expect(rows[0].find('.tl-sub').text()).toContain('sc-a')
    expect(rows[0].find('.tl-body').attributes('href')).toBe('/executions/12')
    expect(rows[1].find('.tl-body').attributes('href')).toContain('/scenarios/p1/detail')
    expect(rows[1].find('.tl-dot').attributes('style')).toContain('var(--avatar-3)')
    expect(rows[2].find('.tl-body').attributes('href')).toBe('/adaptations/batches/b1')
    expect(w.text()).toContain('接口适配 v1 → v2(已完成) · 2 处改写')
    expect(w.find('.tl-note').exists()).toBe(false)     // 三源都成功 → 不该有警示
    // 图例 = 颜色↔类型的说明,三类各一条
    expect(w.findAll('.lg-item').map((i) => i.text())).toEqual(['执行', '场景', '适配'])
    expect(w.find('[data-testid="wb-rail-config"]').exists()).toBe(false)
    w.unmount()
  })

  it('「配色」打开映射面板:改色即时上图例、上圆点,并按用户名存档', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({
      total: 1,
      items: [{ id: 5, scenario_id: 'sc-a', status: 'done', passed: 1, failed: 0, total_runs: 1, started_at: ago(1), finished_at: ago(1), config: {} }],
    } as never)
    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()

    await w.find('.lg-edit').trigger('click')
    const panel = w.find('[data-testid="wb-rail-config"]')
    expect(panel.exists()).toBe(true)
    expect(panel.findAll('.cfg-row')).toHaveLength(3)     // 三类各一行
    expect(panel.findAll('.cfg-sw')).toHaveLength(24)     // 8 色 × 3 类

    // 第一行(执行)选第 5 色 → 圆点与图例同步
    await panel.findAll('.cfg-row')[0]!.findAll('.cfg-sw')[4].trigger('click')
    expect(w.find('.tl-dot').attributes('style')).toContain('var(--avatar-5)')
    expect(w.findAll('.lg-item i')[0]!.attributes('style')).toContain('var(--avatar-5)')
    expect(JSON.parse(localStorage.getItem('gimbal.workbench.timeline-colors:alice')!))
      .toMatchObject({ execution: 'var(--avatar-5)' })

    await w.find('.cfg-reset').trigger('click')
    expect(w.find('.tl-dot').attributes('style')).toContain('var(--avatar-2)')
    w.unmount()
  })

  it('超过 10 条才出「查看更多」,展开后给到池子', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({
      total: 14,
      items: Array.from({ length: 14 }, (_, i) => ({
        id: i + 1, scenario_id: 'sc-a', status: 'done', passed: 1, failed: 0, total_runs: 1,
        started_at: ago(i + 1), finished_at: ago(i + 1), config: {},
      })),
    } as never)
    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()
    expect(w.findAll('.tl-item')).toHaveLength(10)
    const more = w.find('[data-testid="wb-rail-more"]')
    expect(more.text()).toContain('查看更多')
    expect(more.text()).toContain('14')

    await more.trigger('click')
    expect(w.findAll('.tl-item')).toHaveLength(14)
    expect(w.find('[data-testid="wb-rail-more"]').text()).toBe('收起')
    await w.find('[data-testid="wb-rail-more"]').trigger('click')
    expect(w.findAll('.tl-item')).toHaveLength(10)
    w.unmount()
  })

  /** jsdom 不做布局,溢出只能喂假尺寸给 measure() —— 这正是渐隐唯一的判据。 */
  function fakeMetrics(el: HTMLElement, scrollHeight: number, clientHeight: number) {
    Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true })
    Object.defineProperty(el, 'clientHeight', { value: clientHeight, configurable: true })
  }

  it('渐隐只在真还有剩余内容时出现;「查看更多」在滚动区之外', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({
      total: 14,
      items: Array.from({ length: 14 }, (_, i) => ({
        id: i + 1, scenario_id: 'sc-a', status: 'done', passed: 1, failed: 0, total_runs: 1,
        started_at: ago(i + 1), finished_at: ago(i + 1), config: {},
      })),
    } as never)
    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()

    const scroller = w.find('.tl-scroll')
    const el = scroller.element as HTMLElement
    // 出口不跟着内容滚:被截断的那一行下面永远有按钮
    expect(el.contains(w.find('[data-testid="wb-rail-more"]').element)).toBe(false)

    // 装得下 → 两端都不画
    fakeMetrics(el, 300, 420)
    await scroller.trigger('scroll')
    expect(el.classList.contains('fade-head')).toBe(false)
    expect(el.classList.contains('fade-foot')).toBe(false)

    // 顶部有溢出、底部还有内容 → 两端都画
    fakeMetrics(el, 900, 420)
    Object.defineProperty(el, 'scrollTop', { value: 120, configurable: true })
    await scroller.trigger('scroll')
    expect(el.classList).toContain('fade-head')
    expect(el.classList).toContain('fade-foot')

    // 贴到顶/贴到底(±1px 容差)→ 对应那一端收掉
    Object.defineProperty(el, 'scrollTop', { value: 0, configurable: true })
    await scroller.trigger('scroll')
    expect(el.classList.contains('fade-head')).toBe(false)
    Object.defineProperty(el, 'scrollTop', { value: 479, configurable: true })
    await scroller.trigger('scroll')
    expect(el.classList.contains('fade-foot')).toBe(false)
    w.unmount()
  })

  it('member 拿不到适配批次(403)→ 只少一类事件,不标降级', async () => {
    const { ApiError } = await import('@/api/http')
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({
      total: 1,
      items: [{ id: 5, scenario_id: 'sc-a', status: 'done', passed: 1, failed: 0, total_runs: 1, started_at: ago(1), finished_at: ago(1), config: {} }],
    } as never)
    vi.mocked(adaptationsApi.listBatches).mockRejectedValue(new ApiError(403, 403, 'forbidden'))
    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()
    expect(w.findAll('.tl-item')).toHaveLength(1)
    expect(w.find('.tl-note').exists()).toBe(false)
    w.unmount()
  })

  it('没有任何活动 → 空态指引;取数全失败 → 错误态', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({ total: 0, items: [] } as never)
    const empty = mountWithRouter(ActivityTimeline)
    await flushPromises()
    expect(empty.find('.tl-state p').text()).toContain('还没有动态')
    empty.unmount()

    vi.mocked(executionsApi.listExecutions).mockRejectedValue(new Error('boom'))
    vi.mocked(adaptationsApi.listBatches).mockRejectedValue(new Error('boom'))
    const broken = mountWithRouter(ActivityTimeline)
    await flushPromises()
    expect(broken.find('[data-testid="wb-rail-loading"]').exists()).toBe(false)
    expect(broken.text()).toContain('动态读取失败')
    broken.unmount()
  })
})

describe('右栏是固定区 — 不进 registry 组装', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    useAuthStore().currentUser = as() as never
    vi.mocked(composerApi.listScenarios).mockResolvedValue([] as never)
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({ total: 0, items: [] } as never)
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue([] as never)
  })

  it('时间线不在卡片网格里,也不出现在卡片市场候选中', async () => {
    const w = mount(WorkbenchView, {
      global: {
        plugins: [createRouter({
          history: createMemoryHistory(),
          routes: [{ path: '/:all(.*)', component: { template: '<div/>' } }],
        })],
        stubs: {
          RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
          DropdownMenu: { template: '<div><slot /></div>' },
          DropdownMenuTrigger: { template: '<button><slot /></button>' },
          DropdownMenuContent: { template: '<div><slot /></div>' },
          DropdownMenuItem: { template: '<div><slot /></div>' },
        },
      },
      attachTo: document.body,
    })
    await flushPromises()
    const grid = w.find('[data-testid="wb-grid"]')
    expect(grid.find('[data-testid="wb-rail-timeline"]').exists()).toBe(false)
    expect(w.find('[data-testid="wb-rail-identity"]').exists()).toBe(true)
    // 市场里找不到右栏 → registry 未被动它
    const { workbenchRegistry } = await import('@/components/workbench/registry')
    expect(workbenchRegistry.map((d) => d.id)).not.toContain('timeline')
    expect(workbenchRegistry.map((d) => d.id)).not.toContain('identity')
    w.unmount()
  })
})
