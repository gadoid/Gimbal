/**
 * 工作台组装(Jira 看板式)— 添加 / 删除 / 布局持久化 / 新卡渲染。
 * 拖拽落点的换序纯函数在 layout.test 已钉;此处验证视图接线
 * (draggable 渲染按 orderedIds 顺序,removable 门控,市场候选)。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import WorkbenchView from '@/views/WorkbenchView.vue'
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

describe('工作台组装 — 添加卡片(市场)', () => {
  it('默认渲染全部注册卡;「+ 添加卡片」打开市场,候选 = 未启用卡', async () => {
    const w = mountPage()
    await waitCards(w, 3)
    expect(w.find('[data-testid="wb-slot-constants"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-recent-executions"]').exists()).toBe(true)
    expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(true)

    await w.find('[data-testid="wb-add-card"]').trigger('click')
    await flushPromises()
    // 全部已启用 → 市场空态提示
    expect(document.body.textContent).toContain('所有卡片都已在工作台上')
    w.unmount()
  })

  it('移除后市场出现该卡;点「添加」→ 卡片回到工作台且持久化', async () => {
    const w = mountPage()
    await waitCards(w, 3)

    // 移除最近执行卡
    await w.find('[data-testid="wb-remove-recent-executions"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="wb-slot-recent-executions"]').exists()).toBe(false)
    // 持久化:存档不含该卡
    const stored = JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)
    expect(stored).not.toContain('recent-executions')

    // 市场里出现,点添加 → 回来
    await w.find('[data-testid="wb-add-card"]').trigger('click')
    await flushPromises()
    const addBtn = q('[data-testid="gal-add-recent-executions"]')
    await addBtn.trigger('click')
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-slot-recent-executions"]').exists()).toBe(true)
    })
    // 追加到尾部
    const after = JSON.parse(localStorage.getItem('workbench.layout.v1:alice')!)
    expect(after[after.length - 1]).toBe('recent-executions')
    w.unmount()
  })

  it('重挂载(刷新模拟)按存档渲染;「重置布局」回默认', async () => {
    let w = mountPage()
    await waitCards(w, 3)
    await w.find('[data-testid="wb-remove-starred-scenarios"]').trigger('click')
    await flushPromises()
    w.unmount()
    document.body.innerHTML = ''

    // 刷新:新挂载读存档 — 只有 2 卡
    w = mountPage()
    await waitCards(w, 2)
    expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(false)

    // 重置 → 3 卡回默认
    await w.find('[data-testid="wb-reset"]').trigger('click')
    await vi.waitFor(() => {
      expect(w.find('[data-testid="wb-slot-starred-scenarios"]').exists()).toBe(true)
    })
    w.unmount()
  })

  it('最后一张卡不可移除(防空工作台)', async () => {
    const w = mountPage()
    await waitCards(w, 3)
    // 移到只剩一张
    for (const id of ['recent-executions', 'starred-scenarios']) {
      await w.find(`[data-testid="wb-remove-${id}"]`).trigger('click')
      await flushPromises()
    }
    // 最后一张(constants)没有移除钮
    expect(w.find('[data-testid="wb-remove-constants"]').exists()).toBe(false)
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
    // limit 契约
    expect(executionsApi.listExecutions).toHaveBeenCalledWith({ limit: 5 })
    const row = w.find('[data-testid="wb-ex-row-7"]')
    expect(row.attributes('href')).toBe('/executions/7')
    expect(row.find('.status-failed').exists()).toBe(true)
    expect(row.text()).toContain('2/2/4')
    w.unmount()
  })
})

describe('工作台新卡 — 收藏场景', () => {
  it('starred 过滤 + top5 截断 + 行直达详情', async () => {
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
