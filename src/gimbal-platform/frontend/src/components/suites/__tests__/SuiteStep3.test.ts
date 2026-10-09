/** 第 3 步钉子:21 页判定门实测值(SuiteRunsTab)+ 单元设置同名改名
 * (UnitSettings map 编辑器)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SuiteRunsTab from '@/components/suites/SuiteRunsTab.vue'
import UnitSettings from '@/components/suites/UnitSettings.vue'
import * as suitesApi from '@/api/suites'
import * as executionsApi from '@/api/executions'

vi.mock('@/api/suites', () => ({
  listSuiteRuns: vi.fn(),
  rerunFailedUnits: vi.fn(),
}))
vi.mock('@/api/executions', () => ({
  getExecutionRows: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

describe('SuiteRunsTab — 判定门实测值(21 页)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('展开失败的编排执行:判定门行显示 实测 op 阈值 ✓/✗ 与总结', async () => {
    vi.mocked(suitesApi.listSuiteRuns).mockResolvedValue([
      {
        executionId: 77, kind: 'suite_graph', batchId: 'b-1', mode: 'compose',
        status: 'failed', totalRuns: 5, passed: 3, failed: 2, skipped: 0,
        createdAt: '2026-10-09T12:00:00Z', finishedAt: '2026-10-09T12:01:00Z',
        gatesEvaluated: {
          gates: [
            { metric: 'pass_rate', op: 'gte', value: 1, actual: 0.6, passed: false },
            { metric: 'max_duration_ms', op: 'lte', value: 3000, actual: 812, passed: true },
          ],
          passed: false,
        },
      },
    ])
    vi.mocked(executionsApi.getExecutionRows).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 500,
    } as never)
    const w = mount(SuiteRunsTab, {
      props: { suiteId: 2, members: [
        { scenarioId: 'sc-login', name: '登录' }] },
    })
    await flushPromises()

    // 展开行(gates 区域 + 逐单元表)
    await w.find('tr[data-testid="suite-run-row-0"]').trigger('click')
    await flushPromises()

    const gates = w.find('[data-testid="suite-runs-gates"]')
    expect(gates.exists()).toBe(true)
    expect(gates.text()).toContain('通过率 60% ≥ 100% ✗')
    expect(gates.text()).toContain('最长耗时 812 ≤ 3000 ✓')
    expect(gates.text()).toContain('未通过(整体判失败)')
    w.unmount()
  })
})

describe('UnitSettings — 同名改名(map)编辑器', () => {
  function mountSettings(unit: suitesApi.SuiteUnitConfig = {}) {
    return mount(UnitSettings, {
      props: {
        member: {
          scenarioId: 'sc-a', name: '下单', module: 'fin',
          visibility: 'private', role: 'main', sort: 0, addedAt: null,
        },
        unit, orchestrate: true, schemes: [], datasetRows: [],
      },
    })
  }

  it('加一行改名 → 填两端 → patch 事件带 map 对象;删除行同步清掉', async () => {
    const w = mountSettings()
    await w.find('[data-testid="suite-unit-map-add"]').trigger('click')
    const inputs = w.findAll('.uset-map-in')
    expect(inputs.length).toBe(2)
    await inputs[0].setValue('token')
    // 只填一端:不发 patch(半行回传 map:{} 会把正在编辑的行冲掉)
    expect(w.emitted('patch')).toBeUndefined()
    await inputs[1].setValue('authToken')
    let events = w.emitted('patch')
    expect(events?.at(-1)?.[0]).toEqual({ map: { token: 'authToken' } })

    // 删除该行 → map 清空
    await w.find('[data-testid="suite-unit-map-remove-0"]').trigger('click')
    events = w.emitted('patch')
    expect(events?.at(-1)?.[0]).toEqual({ map: {} })
    w.unmount()
  })

  it('已有 map 的单元回显;新加的空行留在本地、不触发 patch', async () => {
    const w = mountSettings({ map: { token: 'authToken' } })
    expect(w.findAll('.uset-map-in').length).toBe(2)
    expect((w.findAll('.uset-map-in')[0].element as HTMLInputElement).value)
      .toBe('token')
    // 加空行:本地多一行可编辑,但不发 patch(空端点不落 map)
    await w.find('[data-testid="suite-unit-map-add"]').trigger('click')
    expect(w.findAll('.uset-map-in').length).toBe(4)
    expect(w.emitted('patch')).toBeUndefined()
    w.unmount()
  })
})
