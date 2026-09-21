/**
 * 工作台右侧固定栏:身份卡 + 时间线。
 * 钉住:头像色与用户名一一稳定(与用户管理表同一份 token 调色板)、
 * 计数读场景 store(不另发请求)、时间线按天分组且每行可下钻、
 * 卡头圆点按颜色筛流、滚动渐隐只在真有剩余内容时出现、
 * member 无适配权限时不显示降级警示、右栏不进 registry(不可删/不可拖)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
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
import * as activityApi from '@/api/activity'

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 }),
}))
vi.mock('@/api/executions', () => ({ listExecutions: vi.fn() }))
vi.mock('@/api/activity', () => ({ getActivity: vi.fn() }))
vi.mock('@/api/adaptations', () => ({ listBatches: vi.fn() }))
vi.mock('@/api/constants', () => ({ list: vi.fn().mockResolvedValue([]) }))
// 新增的 registry 卡(认证管理 / 服务画像)同样不能打真网络
vi.mock('@/api/auth_sessions', () => ({ list: vi.fn().mockResolvedValue([]), listAll: vi.fn().mockResolvedValue([]) }))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceRows: vi.fn().mockResolvedValue([]),
  loadCatalogEntries: vi.fn().mockResolvedValue([]),
}))

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
    vi.mocked(composerApi.listScenarios).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 } as never)
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
    vi.mocked(composerApi.listScenarios).mockResolvedValue({
      items: [scen('p1', 'private', ago(1)), scen('p2', 'private', ago(2)), scen('pub', 'public', ago(3))] as never[],
      total: 3, page: 1, pageSize: 100,
    } as never)
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
    // 钉住时钟在午后:ago() 偏移的历日归属不随真实运行时刻漂 ——
    // 凌晨跑时 2h 前落「昨天」,按天分组断言就是颗时间炸弹。
    vi.setSystemTime(new Date('2026-09-20T15:00:00'))
    setActivePinia(createPinia())
    localStorage.clear()
    useAuthStore().currentUser = as() as never
    useTimelineColors().reset()              // 配色是 module 单例:用例间归零
    vi.mocked(composerApi.listScenarios).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 } as never)
    vi.mocked(adaptationsApi.listBatches).mockResolvedValue([] as never)
    // M5-3:时间线一次合流;默认空报告(各用例按需覆写)
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [], sources: { executions: true, scenarios: true, adaptations: true },
    } as never)
  })
  afterEach(() => {
    vi.useRealTimers()                        // 还原 setSystemTime 的 Date  mock
  })

  it('三源合流按天分组,每行深链到自己的详情页', async () => {
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [
        { kind: 'execution', at: ago(2), executionId: 12, status: 'failed', scenarioId: 'sc-a' },
        { kind: 'scenario', at: ago(5), scenarioId: 'p1', name: '场景 p1', module: 'm' },
        { kind: 'adaptation', at: ago(6), batchId: 'b1', fromVersion: 'v1', toVersion: 'v2',
           status: 'completed', endpointId: 'fin.pay.create', opCount: 2 },
        { kind: 'execution', at: ago(30), executionId: 11, status: 'done', scenarioId: 'sc-a' },
      ],
      sources: { executions: true, scenarios: true, adaptations: true },
    } as never)

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
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [
        { kind: 'execution', at: ago(1), executionId: 5, status: 'done', scenarioId: 'sc-a' },
      ],
      sources: { executions: true, scenarios: true, adaptations: true },
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
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: Array.from({ length: 14 }, (_, i) => ({
        kind: 'execution', at: ago(i + 1), executionId: i + 1, status: 'done', scenarioId: 'sc-a',
      })),
      sources: { executions: true, scenarios: true, adaptations: true },
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
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: Array.from({ length: 14 }, (_, i) => ({
        kind: 'execution', at: ago(i + 1), executionId: i + 1, status: 'done', scenarioId: 'sc-a',
      })),
      sources: { executions: true, scenarios: true, adaptations: true },
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

  it('卡头圆点即筛流:点一颗只剩那一类、再点还原;池里没有的那类不给点', async () => {
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [
        { kind: 'execution', at: ago(2), executionId: 12, status: 'failed', scenarioId: 'sc-a' },
        { kind: 'scenario', at: ago(5), scenarioId: 'p1', name: '场景 p1', module: 'm' },
        { kind: 'execution', at: ago(3), executionId: 11, status: 'done', scenarioId: 'sc-a' },
      ],
      sources: { executions: true, scenarios: true, adaptations: true },
    } as never)   // 适配一类为空
    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()

    const chips = w.findAll('[data-testid="wb-rail-filter"]')
    expect(chips).toHaveLength(3)
    // 点色跟着「配色」映射走,不是写死的
    expect(chips[0]!.attributes('style')).toContain('var(--avatar-2)')
    expect(chips[2]!.attributes('disabled')).toBeDefined()
    expect(w.find('.chead-count').text()).toBe('3')

    await chips[0]!.trigger('click')
    const rows = w.findAll('.tl-item')
    expect(rows).toHaveLength(2)
    expect(rows.every((r) => r.attributes('data-testid') === 'wb-tl-execution')).toBe(true)
    expect(w.find('.chead-count').text()).toBe('2')                 // 计数说的是"当前这条轴"
    expect(w.findAll('.lg-item')[2]!.classes()).toContain('dim')     // 图例同步压暗
    expect(chips[0]!.attributes('aria-pressed')).toBe('true')

    await chips[0]!.trigger('click')
    expect(w.findAll('.tl-item')).toHaveLength(3)
    expect(w.findAll('.lg-item.dim')).toHaveLength(0)
    w.unmount()
  })

  it('member 拿不到适配批次(403)→ 只少一类事件,不标降级', async () => {
    // M5-3:member 的 403 在服务端折算(适配源 owner 视图可读)——
    // sources 报告即「确定性答案」口径,不算降级
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [
        { kind: 'execution', at: ago(1), executionId: 5, status: 'done', scenarioId: 'sc-a' },
      ],
      sources: { executions: true, scenarios: true, adaptations: true },
    } as never)
    const w = mountWithRouter(ActivityTimeline)
    await flushPromises()
    expect(w.findAll('.tl-item')).toHaveLength(1)
    expect(w.find('.tl-note').exists()).toBe(false)
    w.unmount()
  })

  it('没有任何活动 → 空态指引;取数全失败 → 错误态', async () => {
    const empty = mountWithRouter(ActivityTimeline)   // 默认空报告(beforeEach)
    await flushPromises()
    expect(empty.find('.tl-state p').text()).toContain('还没有动态')
    empty.unmount()

    // 三源全挂(sources 全 false 且无事件)→ 错误态
    vi.mocked(activityApi.getActivity).mockResolvedValue({
      events: [],
      sources: { executions: false, scenarios: false, adaptations: false },
    } as never)
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
    vi.mocked(composerApi.listScenarios).mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 } as never)
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
