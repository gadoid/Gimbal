/**
 * ScenarioFollows — 关注页契约。
 * 钉住:常驻区只渲染 pinned ∩ 关注集(死席位挂载即回收)、▲▼ 键盘重排
 * (含 move 的「追加末尾」落点)、取消关注失败不得掉席位、方案数/默认方案名
 * 取自信号装配而非列表字段、接口变更信号必须等 ensure() 算完再读(竞态)、
 * 趋势只统计默认方案的执行。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ScenarioFollows from '@/views/ScenarioFollows.vue'
import { useFollowLayout } from '@/composables/useFollowLayout'
import { resetUserPreferencesForTest } from '@/composables/useUserPreferences'
import { useAuthStore } from '@/stores/auth'
import * as composerApi from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

const LS_KEY = 'gimbal.scenario-follows.pinned:alice'
const readPinned = () => JSON.parse(localStorage.getItem(LS_KEY) ?? '[]') as string[]

// 常驻席存档已改走服务端(user_prefs)+ 本地镜像:不打桩的话 pull 会去摸
// 真 axios,首帧断言就看的是网络何时回来了。
vi.mock('@/api/preferences', () => ({
  getPreferences: vi.fn().mockResolvedValue({}),
  putPreference: vi.fn().mockResolvedValue(undefined),
}))

const ensureSpy = vi.hoisted(() => vi.fn().mockResolvedValue(undefined))

vi.mock('@/composables/useInterfaceChange', () => ({
  useInterfaceChange: () => ({
    // hasChange 只在 f-c1 上为真 —— 视图必须等 ensure() 完成再读,否则恒 false
    ensure: ensureSpy,
    hasChange: (id: string) => id === 'f-c1',
  }),
}))

vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 }),
  starScenario: vi.fn().mockResolvedValue(undefined),
  // M5 bulk 信号:一次请求回全部关注对象的 趋势/最近执行/方案面。
  // f-a:默认方案 2 次执行(旧 done → 新 failed)+ 3 个方案(默认=标准回归)。
  fetchScenarioSignals: vi.fn().mockImplementation(async (ids: string[]) => {
    const signals: Record<string, unknown> = {}
    for (const id of ids) {
      signals[id] = id === 'f-a'
        ? {
            trend: ['done', 'failed'],
            lastRun: { status: 'failed', at: '2026-09-18T10:00:00' },
            schemeCount: 3,
            defaultSchemeName: '标准回归',
          }
        : { trend: [], lastRun: null, schemeCount: 0, defaultSchemeName: null }
    }
    return signals
  }),
  // 只有 f-a 有 3 个方案(默认 = 标准回归),其余 0 个
  listRunSchemes: vi.fn().mockImplementation(async (id: string) =>
    id === 'f-a'
      ? [
          { schemeId: 'sch-1', name: '标准回归', isDefault: true, dataSetSelection: [], injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 2, parallel: 1 },
          { schemeId: 'sch-2', name: '边界值', isDefault: false, dataSetSelection: [], injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1 },
          { schemeId: 'sch-3', name: '夜间巡检', isDefault: false, dataSetSelection: [], injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1 },
        ]
      : []),
}))

vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({
    total: 3,
    items: [
      // 新→旧:默认方案 2 次(一次失败)+ 别的方案 1 次 —— 趋势不得跨方案聚合
      { id: 9, scenario_id: 'f-a', status: 'failed', configSummary: { schemeId: 'sch-1' }, started_at: '2026-09-18T09:00:00', finished_at: '2026-09-18T10:00:00' },
      { id: 8, scenario_id: 'f-a', status: 'done', configSummary: { schemeId: 'sch-2' }, started_at: '2026-09-17T09:00:00', finished_at: '2026-09-17T10:00:00' },
      { id: 7, scenario_id: 'f-a', status: 'done', configSummary: { schemeId: 'sch-1' }, started_at: '2026-09-16T09:00:00', finished_at: '2026-09-16T10:00:00' },
    ],
  }),
}))

function followed(id: string): Scenario {
  return {
    meta: {
      scenarioId: id, name: id, description: '', module: 'm', priority: 1,
      author: 'Alice', owner: 'Alice', tags: [], system: ['fin'], updateTime: '2026-09-15T15:13:00',
    },
    steps: [], config: { vars: {} }, dataSetCount: 0, stepCount: 1,
    tags: [], starred: true, visibility: 'private', schemeCount: 0,
  } as unknown as Scenario
}

async function mountPage(scenarios: Scenario[]): Promise<VueWrapper> {
  vi.mocked(composerApi.listScenarios).mockResolvedValue({
    items: scenarios, total: scenarios.length, page: 1, pageSize: 100,
  } as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios/follows', component: { template: '<div/>' } },
      { path: '/scenarios/:scenarioId/schemes', component: { template: '<div/>' } },
    ],
  })
  const w = mount(ScenarioFollows, {
    global: {
      plugins: [router],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        DropdownMenu: { template: '<div><slot /></div>' },
        DropdownMenuTrigger: { template: '<button><slot /></button>' },
        DropdownMenuContent: { template: '<div><slot /></div>' },
        DropdownMenuItem: { template: '<div><slot /></div>' },
      },
    },
  })
  await flushPromises()
  return w
}

const names = (w: VueWrapper) => w.findAll('.fav-name').map((n) => n.text())

/** 按场景名定位常驻卡的 ▲(up)/▼(down) 按钮 —— 不靠可能被复用的节点索引。 */
async function nudge(w: VueWrapper, name: string, dir: 'up' | 'down') {
  const card = w.findAll('.fav-card').find((c) => c.find('.fav-name').text() === name)!
  await card.findAll('.kb-btn')[dir === 'up' ? 0 : 1]!.trigger('click')
  await flushPromises()
}
const nudgeBtn = (w: VueWrapper, name: string, dir: 'up' | 'down') =>
  w.findAll('.fav-card').find((c) => c.find('.fav-name').text() === name)!
    .findAll('.kb-btn')[dir === 'up' ? 0 : 1]!

describe('ScenarioFollows — 关注页', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    // 常驻席存档按用户名分键:未登录时 whenReady() 不 resolve,页面会
    // 停在「等身份」上 —— 这正是要钉的行为,所以用例必须带身份进。
    useAuthStore().currentUser = { id: 1, username: 'alice', display_name: 'Alice', is_admin: false } as never
    // 常驻席是 module 作用域单例:不清零会带着上一条用例的顺序进下一条,
    // 播种/回收断言就看的是别人的状态了。
    resetUserPreferencesForTest()
    useFollowLayout().pinned.value = []
    vi.mocked(composerApi.starScenario).mockResolvedValue(undefined)
  })

  it('首访以前 PINNED_MAX 条播种常驻席,其余进堆叠区', async () => {
    const w = await mountPage(Array.from({ length: 7 }, (_, i) => followed(`f-${i}`)))
    expect(names(w)).toEqual(['f-0', 'f-1', 'f-2', 'f-3', 'f-4'])
    expect(w.findAll('.stack-card')).toHaveLength(2)
    expect(readPinned()).toEqual(['f-0', 'f-1', 'f-2', 'f-3', 'f-4'])
    w.unmount()
  })

  it('挂载即回收死席位:存档里不再关注的 id 不得继续占 5 席预算', async () => {
    // 直接摆出「客户端存档里留着两个已取消关注的 id」这个状态
    useFollowLayout().pinned.value = ['gone-1', 'gone-2', 'f-a', 'f-b']
    const w = await mountPage([followed('f-a'), followed('f-b'), followed('f-c')])
    expect(names(w)).toEqual(['f-a', 'f-b'])
    expect(readPinned()).toEqual(['f-a', 'f-b'])
    // 剪完就补得上位:死 id 没有把 5 席预算堵死
    await w.findAll('.pin-link')[0]!.trigger('click')
    expect(names(w)).toEqual(['f-a', 'f-b', 'f-c'])
    w.unmount()
  })

  it('▲▼ 键盘重排:边界按钮禁用,下移到末尾走 move(id,null)', async () => {
    const w = await mountPage([followed('f-1'), followed('f-2'), followed('f-3')])
    expect((nudgeBtn(w, 'f-1', 'up').element as HTMLButtonElement).disabled).toBe(true)
    expect((nudgeBtn(w, 'f-3', 'down').element as HTMLButtonElement).disabled).toBe(true)
    expect(nudgeBtn(w, 'f-1', 'down').attributes('aria-label')).toContain('下移')

    await nudge(w, 'f-1', 'down')
    expect(names(w)).toEqual(['f-2', 'f-1', 'f-3'])     // 与拖拽同一条 move 通道
    expect(readPinned()).toEqual(['f-2', 'f-1', 'f-3']) // 顺序落盘

    await nudge(w, 'f-1', 'down')
    expect(names(w)).toEqual(['f-2', 'f-3', 'f-1'])     // 越过末尾 → 追加最后一席

    await nudge(w, 'f-1', 'up')
    expect(names(w)).toEqual(['f-2', 'f-1', 'f-3'])
    w.unmount()
  })

  it('取消关注失败 → 常驻席不得被顺手摘掉(先落库再动席位)', async () => {
    vi.mocked(composerApi.starScenario).mockRejectedValueOnce(new Error('boom'))
    const w = await mountPage([followed('f-a'), followed('f-b')])
    expect(names(w)).toEqual(['f-a', 'f-b'])
    await w.find('.fav-card .star-btn').trigger('click')
    await flushPromises()
    expect(names(w)).toEqual(['f-a', 'f-b'])
    expect(readPinned()).toEqual(['f-a', 'f-b'])
    w.unmount()
  })

  it('方案数 + 默认方案名来自信号装配;>1 才给「+N 更多」入口', async () => {
    const w = await mountPage([followed('f-a'), followed('f-c1')])
    const links = w.findAll('.more-link')
    expect(links).toHaveLength(1)                       // f-c1 无方案 → 不出现
    expect(links[0]!.text()).toContain('+2 更多')
    expect(links[0]!.attributes('href')).toContain('/scenarios/f-a/schemes')
    expect(w.findAll('.fav-scheme .nm')[0]!.text()).toBe('标准回归')
    w.unmount()
  })

  it('趋势只统计默认方案的执行(不跨方案聚合),旧→新', async () => {
    const w = await mountPage([followed('f-a')])
    const dots = w.findAll('.signal-dots i')
    expect(dots).toHaveLength(2)                        // id=8 属 sch-2,不计入
    expect(dots.map((d) => d.classes().join(' '))).toEqual(['ok', 'bad'])
    // 默认方案最近一次 = failed → 单点状态与趋势同一口径
    expect(w.find('.status-dot-sm').classes()).toContain('bad')
    w.unmount()
  })

  it('接口变更信号先等 ensure() 再装配(此前恒读到空集)', async () => {
    const w = await mountPage([followed('f-a'), followed('f-c1')])
    expect(ensureSpy).toHaveBeenCalled()
    const badges = w.findAll('.change-badge')
    expect(badges).toHaveLength(1)
    expect(badges[0]!.text()).toContain('接口有变更')
    w.unmount()
  })

  it('无关注 → 空态指出去哪儿关注,而不是「常驻席为空」', async () => {
    const w = await mountPage([])
    expect(w.find('.slib-empty').text()).toContain('还没有关注任何场景')
    w.unmount()
  })

  it('刷新首帧身份还没到 → 不写匿名键;身份到位后播种落对键', async () => {
    useAuthStore().currentUser = null
    vi.mocked(composerApi.listScenarios).mockResolvedValue({
      items: [followed('f-a'), followed('f-b')], total: 2, page: 1, pageSize: 100,
    } as never)
    const w = mount(ScenarioFollows, {
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
    })
    await flushPromises()
    // 场景已经加载完,但存档一步都没动过 —— 既没有匿名键,也没有假播种
    expect(localStorage.getItem('gimbal.scenario-follows.pinned:')).toBeNull()
    expect(w.findAll('.fav-card')).toHaveLength(0)

    useAuthStore().currentUser = { id: 1, username: 'alice', display_name: 'Alice', is_admin: false } as never
    await flushPromises()
    expect(readPinned()).toEqual(['f-a', 'f-b'])
    expect(w.findAll('.fav-name').map((n) => n.text())).toEqual(['f-a', 'f-b'])
    w.unmount()
  })
})
