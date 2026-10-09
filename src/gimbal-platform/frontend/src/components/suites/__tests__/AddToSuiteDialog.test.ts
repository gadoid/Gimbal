/**
 * AddToSuiteDialog — P1 尾巴①钉子:库侧批量「加入 Suite」弹窗。
 * 覆盖:我的 suite 单选列表(scope=mine 接线)、提交载荷(去重由后端
 * 保证,前端原样传勾选 id)、成功 toast + added 事件 + 关闭、
 * 空 suite 引导、失败透出后端人话(404 他人场景/409 上限)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AddToSuiteDialog from '@/components/suites/AddToSuiteDialog.vue'
import * as suitesApi from '@/api/suites'
import { toast } from '@/utils/toast'

vi.mock('@/api/suites', () => ({
  listSuites: vi.fn(),
  addSuiteMembers: vi.fn(),
  // 重构:提交走 suiteErrDetail 透出后端 409 机器面;默认无 detail
  suiteErrDetail: vi.fn(() => null),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

/* reka-ui DialogPortal 真实 teleport 到 document.body(ScenarioExportMenu
 * 惯例):attachTo body + document.querySelectorAll 检索 + 原生 click。 */
const q = (sel: string) =>
  document.querySelector(sel) as HTMLElement | null
const qAll = (sel: string) =>
  [...document.querySelectorAll(sel)] as HTMLElement[]

const SCENARIOS = [
  { id: 'sc-1', name: '下单' },
  { id: 'sc-2', name: '查单' },
]

function suitesPage(items: unknown[] = []) {
  return { items, total: items.length, page: 1, pageSize: 100 } as never
}

function mountDialog() {
  return mount(AddToSuiteDialog, {
    props: { open: true, scenarios: SCENARIOS },
    attachTo: document.body,
    global: {
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })
}

afterEach(() => {
  // 手工摘除 teleport 残留,避免跨测试串到 document.querySelectorAll
  document.body.innerHTML = ''
})

describe('AddToSuiteDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(suitesApi.listSuites).mockResolvedValue(suitesPage([
      { suiteId: 1, name: '冒烟集', description: '', visibility: 'private',
        mode: 'aggregate', memberCount: 5, createdAt: null, updatedAt: null },
      { suiteId: 2, name: '回归集', description: '', visibility: 'private',
        mode: 'aggregate', memberCount: 12, createdAt: null, updatedAt: null },
    ]))
    vi.mocked(suitesApi.addSuiteMembers).mockResolvedValue({} as never)
  })

  it('打开即拉我的 suite(scope=mine),单选后提交传勾选 id 全集', async () => {
    const w = mountDialog()
    await flushPromises()
    expect(suitesApi.listSuites).toHaveBeenCalledWith(
      { scope: 'mine', page_size: 100 })

    q('[data-testid="add-to-suite-item-2"] input')!.click()
    await flushPromises()
    q('[data-testid="add-to-suite-submit"]')!.click()
    await flushPromises()

    expect(suitesApi.addSuiteMembers).toHaveBeenCalledWith(
      2, ['sc-1', 'sc-2'])
    expect(toast.success).toHaveBeenCalledWith(
      '已把 2 个场景加入「回归集」')
    expect(w.emitted('added')).toEqual([
      [{ suiteId: 2, suiteName: '回归集', count: 2 }]])
    expect(w.emitted('update:open')).toEqual([[false]])
  })

  it('没有 suite 时空态引导 + 提交禁用', async () => {
    vi.mocked(suitesApi.listSuites).mockResolvedValue(suitesPage())
    mountDialog()
    await flushPromises()
    expect(q('[data-testid="add-to-suite-empty"]')).not.toBeNull()
    expect(
      (q('[data-testid="add-to-suite-submit"]') as HTMLButtonElement).disabled,
    ).toBe(true)
    expect(suitesApi.addSuiteMembers).not.toHaveBeenCalled()
  })

  it('加入失败(404 他人场景/409 上限)toast 后端人话,弹窗不关', async () => {
    vi.mocked(suitesApi.addSuiteMembers).mockRejectedValue(
      new Error('suite member cap is 100'))
    const w = mountDialog()
    await flushPromises()
    q('[data-testid="add-to-suite-item-1"] input')!.click()
    await flushPromises()
    q('[data-testid="add-to-suite-submit"]')!.click()
    await flushPromises()

    expect(toast.error).toHaveBeenCalledWith(
      '加入失败:suite member cap is 100')
    expect(w.emitted('update:open')).toBeUndefined()
    expect(w.emitted('added')).toBeUndefined()
  })
})
