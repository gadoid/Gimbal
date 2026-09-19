/**
 * 工作台组装(Jira 看板式 + v3 设计文档)— 添加 / 删除 / 布局持久化 /
 * 尺寸系统 / 新卡渲染。拖拽落点的换序纯函数在 layout.test 已钉;
 * 此处验证视图接线(draggable 渲染按 orderedIds 顺序,removable 门控,
 * 市场已添加置灰,⤢ 单钮循环切换三档密度 S→M→L)。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'
import { workbenchRegistry } from '@/components/workbench/registry'
import * as constantsApi from '@/api/constants'
import * as executionsApi from '@/api/executions'
import * as scenarioApi from '@/api/scenario-composer'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/constants', () => ({
  list: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
// 右栏时间线会读适配批次 —— 不 mock 就打真网络,用例变慢且不稳定
vi.mock('@/api/adaptations', () => ({
  listBatches: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue([]),
}))

function q(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
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

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
  useAuthStore().currentUser = { id: 1, username: 'alice', is_admin: false } as never
  vi.mocked(constantsApi.list).mockResolvedValue([] as never)
  vi.mocked(executionsApi.listExecutions).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(scenarioApi.listScenarios).mockResolvedValue([] as never)
})

afterEach(() => { document.body.innerHTML = '' })

async function waitCards(w: ReturnType<typeof mountPage>, n: number) {
  await vi.waitFor(() => {
    expect(w.findAll('[data-testid^="wb-slot-"]').length).toBeGreaterThanOrEqual(n)
  })
}

describe('工作台组装 — draggable 接线(卡死根因防回归)', () => {
  it('itemKey 必须是函数(静态字符串会让所有 key=undefined → 拖拽死循环)', () => {
    const w = mountPage()
    const drag = w.findComponent({ name: 'draggable' })
    expect(drag.exists()).toBe(true)
    expect(drag.props('itemKey')).toBeTypeOf('function')
    const keyFn = drag.props('itemKey') as (el: string) => string
    expect(keyFn('constants')).toBe('constants')
    w.unmount()
  })
})

describe('工作台组装 — 添加卡片(网格末尾添加条 + 市场置灰)', () => {
  it('默认渲染全部注册卡;添加条常驻网格末尾,打开市场 = 全类型清单(已添加置灰)', async () => {
    const w = mountPage()
    await waitCards(w, workbenchRegistry.length)
    expect(w.find('[data-testid="wb-slot-constants"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-recent-executions"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-my-scenarios"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-public-scenarios"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(true)

    await w.find('[data-testid="wb-add-card"]').trigger('click')
    await flushPromises()
    // 全部已启用 → 五项都在清单里且置灰(不隐藏)
    expect(q('[data-testid="gal-added-constants"]').exists()).toBe(true)
    expect(q('[data-testid="gal-added-recent-executions"]').exists()).toBe(true)
    expect(q('[data-testid="gal-added-my-scenarios"]').exists()).toBe(true)
    expect(q('[data-testid="gal-added-public-scenarios"]').exists()).toBe(true)
    expect(q('[data-testid="gal-added-starred-scenarios"]').exists()).toBe(true)
    // q() 对"不存在"会抛 — 负断言直接查 DOM
    expect(document.body.querySelector('[data-testid="gal-add-constants"]')).toBeNull()
    // 卸载前等内容 resolve:开着的 Dialog + pending Suspense 一起整页
    // 卸载会把 vitest 模块运行器卡死(后续动态 import 返回空模块)
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-card-constants"]').exists()).toBe(true)
    })
    w.unmount()
  })

  it('移除后市场出现该卡;点「+ 添加」→ 卡片回到工作台且持久化(v2 键)', async () => {
    const w = mountPage()
    await waitCards(w, 3)

    await w.find('[data-testid="wb-remove-recent-executions"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="wb-slot-recent-executions"]').exists()).toBe(false)
    const stored = JSON.parse(localStorage.getItem('workbench.layout.v2:alice')!)
    expect(stored.order).not.toContain('recent-executions')

    await w.find('[data-testid="wb-add-card"]').trigger('click')
    await flushPromises()
    const addBtn = q('[data-testid="gal-add-recent-executions"]')
    await addBtn.trigger('click')
    // 等"内容"而非仅卡槽:加回的卡重新 pending,若卸载时仍有 pending
    // 异步卡 + 开着的市场 Dialog,vitest 模块运行器会被卡死
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-card-recent-executions"]').exists()).toBe(true)
    })
    const after = JSON.parse(localStorage.getItem('workbench.layout.v2:alice')!)
    expect(after.order[after.order.length - 1]).toBe('recent-executions')
    w.unmount()
  })

  it('重挂载(刷新模拟)按存档渲染;「重置布局」回默认', async () => {
    let w = mountPage()
    await waitCards(w, 3)
    await w.find('[data-testid="wb-remove-starred-scenarios"]').trigger('click')
    await flushPromises()
    w.unmount()
    document.body.innerHTML = ''

    w = mountPage()
    await waitCards(w, 2)
    expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(false)

    await w.find('[data-testid="wb-reset"]').trigger('click')
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(true)
    })
    w.unmount()
  })

  it('最后一张卡不可移除(防空工作台;✕ 徽标同步隐藏)', async () => {
    const w = mountPage()
    await waitCards(w, workbenchRegistry.length)
    // 删到只剩 constants —— 按注册表取「非 constants」,加多少卡都不用回改此用例
    for (const id of workbenchRegistry.filter((d) => d.id !== 'constants').map((d) => d.id)) {
      await w.find(`[data-testid="wb-remove-${id}"]`).trigger('click')
      await flushPromises()
    }
    expect(w.find('[data-testid="wb-remove-constants"]').exists()).toBe(false)
    // 尺寸循环钮仍在(最后一张卡只禁删,不禁调尺寸)
    expect(w.find('[data-testid="wb-size-constants"]').exists()).toBe(true)
    w.unmount()
  })
})

describe('工作台尺寸系统(⤢ 单钮循环 S→M→L,设计文档 §4)', () => {
  it('点 ⤢ 一次 M→L:slot 跨 2 列 + 常量池出现搜索框;持久化', async () => {
    const w = mountPage()
    await waitCards(w, 3)
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-card-constants"]').exists()).toBe(true)
    })

    await w.find('[data-testid="wb-size-constants"]').trigger('click')
    await flushPromises()
    // L = span 2 + 卡内搜索框
    expect(w.find('[data-testid="wb-slot-constants"]').classes()).toContain('span-2')
    expect(w.find('[data-testid="wb-card-constants-search"]').exists()).toBe(true)
    const stored = JSON.parse(localStorage.getItem('workbench.layout.v2:alice')!)
    expect(stored.sizes.constants).toBe('L')
    w.unmount()
  })

  it('连点 ⤢ 循环 M→L→S→M:紧凑结论面(大数字)控件簇仍在', async () => {
    const w = mountPage()
    await waitCards(w, 3)
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-card-constants"]').exists()).toBe(true)
    })

    // 两击:M→L→S(S = 紧凑结论;单一交互,⤢ 常驻不随档位消失)
    await w.find('[data-testid="wb-size-constants"]').trigger('click')
    await flushPromises()
    await w.find('[data-testid="wb-size-constants"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="wb-card-constants-s"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-size-constants"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-constants"]').classes()).not.toContain('span-2')

    // 第三击:S→M,回到明细
    await w.find('[data-testid="wb-size-constants"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="wb-card-constants-s"]').exists()).toBe(false)
    const stored = JSON.parse(localStorage.getItem('workbench.layout.v2:alice')!)
    expect(stored.sizes.constants).toBe('M')
    w.unmount()
  })

  it('v1 旧存档 → 刷新后 order 继承、v2 键落盘(迁移接线)', async () => {
    localStorage.setItem('workbench.layout.v1:alice', JSON.stringify(['starred-scenarios', 'constants']))
    const w = mountPage()
    await waitCards(w, 2)
    expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-recent-executions"]').exists()).toBe(false)
    const stored = JSON.parse(localStorage.getItem('workbench.layout.v2:alice')!)
    expect(stored.order).toEqual(['starred-scenarios', 'constants'])
    w.unmount()
  })
})

describe('工作台新卡 — 最近执行', () => {
  it('limit 取数 + 状态色行 + 失败计数;行直达详情', async () => {
    vi.mocked(executionsApi.listExecutions).mockResolvedValue({
      items: [
        { id: 7, scenario_id: 'sc-demo', status: 'failed', total_runs: 4, passed: 2, failed: 2,
          started_at: '2026-09-17T10:00:00Z', finished_at: null, has_scenario_snapshot: false } as never,
      ],
      total: 1,
    })
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-ex-row-7"]').exists()).toBe(true)
    })
    expect(executionsApi.listExecutions).toHaveBeenCalledWith({ limit: 5 })
    const row = w.find('[data-testid="wb-ex-row-7"]')
    expect(row.attributes('href')).toBe('/executions/7')
    expect(row.find('.status-failed').exists()).toBe(true)
    expect(row.text()).toContain('2/2/4')
    w.unmount()
  })
})

describe('工作台新卡 — 收藏场景', () => {
  it('starred 过滤 + 行直达详情', async () => {
    vi.mocked(scenarioApi.listScenarios).mockResolvedValue([
      { meta: { scenarioId: 'sc-a', name: 'A', module: '订单' }, starred: true } as never,
      { meta: { scenarioId: 'sc-b', name: 'B', module: '订单' }, starred: false } as never,
      { meta: { scenarioId: 'sc-c', name: 'C', module: '物流' }, starred: true } as never,
    ])
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-sc-row-sc-a"]').exists()).toBe(true)
    })
    expect(w.find('[data-testid="wb-sc-row-sc-b"]').exists()).toBe(false)   // 未收藏不进卡
    expect(w.find('[data-testid="wb-sc-row-sc-c"]').attributes('href')).toBe('/scenarios/sc-c/detail')
    w.unmount()
  })
})

describe('工作台新卡 — 我的场景 / 公共场景(场景库三页拆分)', () => {
  const MIXED = [
    { meta: { scenarioId: 'm-1', name: '我的A', module: '订单', updateTime: '2026-09-10T00:00:00Z' },
      visibility: 'private' },
    // visibility 缺省 → 与 ScenariosMine.vue 的 `!== 'public'` 同判定,归我的
    { meta: { scenarioId: 'm-2', name: '过期B', module: '物流',
      updateTime: '2026-09-09T00:00:00Z', expire: true } },
    { meta: { scenarioId: 'p-1', name: '公共A', author: 'bob', updateTime: '2026-09-11T00:00:00Z' },
      visibility: 'public', starred: true },
  ] as never[]

  beforeEach(() => {
    vi.mocked(scenarioApi.listScenarios).mockResolvedValue(MIXED)
  })

  it('分桶与完整页同谓词:public 只进公共卡,非 public 只进我的卡', async () => {
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-mine-row-m-1"]').exists()).toBe(true)
    })
    expect(w.find('[data-testid="wb-mine-row-m-2"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-mine-row-p-1"]').exists()).toBe(false)
    expect(w.find('[data-testid="wb-pub-row-p-1"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-pub-row-m-1"]').exists()).toBe(false)
    w.unmount()
  })

  it('计数徽标 = 过滤后条数;过期带标记;行直达详情', async () => {
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-mine-row-m-1"]').exists()).toBe(true)
    })
    const mine = w.find('[data-testid="wb-card-my-scenarios"]')
    const pub = w.find('[data-testid="wb-card-public-scenarios"]')
    expect(mine.find('.chead-count').text()).toBe('2')
    expect(pub.find('.chead-count').text()).toBe('1')
    expect(w.find('[data-testid="wb-mine-row-m-2"]').text()).toContain('已过期')
    expect(w.find('[data-testid="wb-pub-row-p-1"]').attributes('href')).toBe('/scenarios/p-1/detail')
    w.unmount()
  })

  it('卡头深链指向各自的拆分页', async () => {
    const w = mountPage()
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-mine-row-m-1"]').exists()).toBe(true)
    })
    expect(w.find('[data-testid="wb-card-my-scenarios"] .manage-link').attributes('href'))
      .toBe('/scenarios/mine')
    expect(w.find('[data-testid="wb-card-public-scenarios"] .manage-link').attributes('href'))
      .toBe('/scenarios/public')
    w.unmount()
  })
})
