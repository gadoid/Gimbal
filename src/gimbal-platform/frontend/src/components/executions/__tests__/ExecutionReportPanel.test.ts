/**
 * ExecutionReportPanel — 执行报告(B4,2026-11-06)。
 *
 * 钉住:①概览计数;②失败聚焦回答「哪步 / 哪条断言 / 期望与实际 /
 * 请求与响应」;③步骤详情展开看全部断言与提取;④无步骤数据的提示;
 * ⑤404 文案;⑥S1 失败根因深链(2026-11-12 自行级明细「查看日志」
 * 迁入:失败 unit 锚定 around 窗口,锚取末条,不跨 unit 回落)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ExecutionReportPanel from '@/components/executions/ExecutionReportPanel.vue'
import type { ExecutionReport } from '@/api/executions'

const getReport = vi.fn()
const getEvents = vi.fn()
vi.mock('@/api/executions', () => ({
  getExecutionReport: (id: number) => getReport(id),
  getExecutionEvents: (id: number, q: Record<string, unknown>) => getEvents(id, q),
}))

function step(over: Record<string, unknown> = {}) {
  return {
    rowSeq: 1, unit: 'sc-r', attempt: '1.1', stepId: 'step-001',
    stepName: 'step-001', description: '查订单', callSummary: 'GET http://h/orders/7',
    status: 'failed', durationMs: 28.4, error: "[verifying] FAIL: actual '7', expected eq '8'",
    assertionCount: 2, assertionPassed: 1,
    assertions: [
      { name: '$.call.response.status', target: '$.call.response.status', operator: 'eq',
        expected: 200, actual: 200, passed: true, message: 'PASS: 200 eq 200' },
      { name: '$.call.response.body.id', target: '$.call.response.body.id', operator: 'eq',
        expected: '8', actual: '7', passed: false, message: "FAIL: actual '7', expected eq '8'" },
    ],
    extracts: [{ target: 'oid', value: '7' }],
    hasEvidence: true,
    ...over,
  }
}

function report(over: Partial<ExecutionReport> = {}): ExecutionReport {
  const failed = step()
  return {
    execution: {
      id: 9, scenarioId: 'sc-r', scenarioName: '报告场景', status: 'failed', kind: 'scenario',
      suiteId: null, batchId: null, startedAt: null, finishedAt: null, durationMs: 3200,
      totalRuns: 2, passed: 1, failed: 1, skipped: 0,
    },
    summary: { steps: 2, stepsPassed: 1, stepsFailed: 1, stepsOther: 0,
               assertions: 3, assertionsPassed: 2 },
    groups: [
      { key: 'row-0', rowSeq: 0, unit: 'sc-r', datasetId: null, rowIndex: 0, rep: 0,
        status: 'passed', caseDir: 'case-000', serverSlot: null,
        steps: [step({ rowSeq: 0, status: 'passed', error: null, assertionCount: 1,
                       assertionPassed: 1, assertions: [], extracts: [] })] },
      { key: 'row-1', rowSeq: 1, unit: 'sc-r', datasetId: 'ds-a', rowIndex: 3, rep: 0,
        status: 'failed', caseDir: 'case-001', serverSlot: 2, steps: [failed] },
    ],
    failure: {
      ...failed,
      failedAssertions: [failed.assertions[1]],
      evidence: {
        request: { method: 'GET', url: 'http://h/orders/7',
                   headers: { Authorization: '***redacted***' } },
        response: { status: 200, body: { id: '7' } },
      },
    },
    hasStepData: true,
    ...over,
  } as ExecutionReport
}

beforeEach(() => {
  getReport.mockReset()
  getEvents.mockReset()
  setActivePinia(createPinia())
})

async function mountPanel(executionId = 9) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/executions/:id/events', component: { template: '<div/>' } }],
  })
  await router.push('/executions/9')
  await router.isReady()
  const w = mount(ExecutionReportPanel, {
    props: { executionId, running: false },
    global: { plugins: [router] },
  })
  await flushPromises()
  return { w, router }
}

describe('ExecutionReportPanel', () => {
  it('概览 + 失败聚焦:哪步、哪条断言、期望/实际、请求响应', async () => {
    getReport.mockResolvedValue(report())
    const w = mount(ExecutionReportPanel, { props: { executionId: 9, running: false } })
    await flushPromises()
    expect(getReport).toHaveBeenCalledWith(9)

    const sum = w.get('[data-testid="report-summary"]').text()
    expect(sum).toContain('步骤 1 / 2 通过')
    expect(sum).toContain('断言 2 / 3 通过')

    const f = w.get('[data-testid="report-failure"]')
    expect(f.text()).toContain('查订单')
    expect(f.text()).toContain('行 #1 · 数据集 ds-a · 第 3 行')
    expect(f.text()).toContain('GET http://h/orders/7')
    const rows = w.get('[data-testid="report-failed-assertions"]').findAll('tbody tr')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('$.call.response.body.id')
    expect(rows[0].text()).toContain('"8"')
    expect(rows[0].text()).toContain('"7"')
    const ev = w.get('[data-testid="report-evidence"]').text()
    expect(ev).toContain('***redacted***')
    expect(ev).toContain('"id": "7"')

    // 槽位提示随分组头出现
    expect(w.get('[data-testid="report-group-row-1"]').text()).toContain('server 槽位 2')
  })

  it('步骤详情展开:全部断言与提取值', async () => {
    getReport.mockResolvedValue(report())
    const w = mount(ExecutionReportPanel, { props: { executionId: 9, running: false } })
    await flushPromises()
    await w.get('[data-testid="report-step-toggle-1:sc-r:1.1:step-001"]').trigger('click')
    const g = w.get('[data-testid="report-group-row-1"]').text()
    expect(g).toContain('$.call.response.status')
    expect(g).toContain('oid')
  })

  it('无步骤数据:提示早于步骤落库 + 工件 14 天保留期(不再指路执行明细)', async () => {
    getReport.mockResolvedValue(report({ hasStepData: false, failure: null, groups: [],
      summary: { steps: 0, stepsPassed: 0, stepsFailed: 0, stepsOther: 0,
                 assertions: 0, assertionsPassed: 0 } }))
    const w = mount(ExecutionReportPanel, { props: { executionId: 9, running: false } })
    await flushPromises()
    const t = w.get('[data-testid="report-no-steps"]').text()
    expect(t).toContain('没有步骤结果')
    expect(t).toContain('14 天')
    expect(t).not.toContain('执行明细')
    expect(w.find('[data-testid="report-failure"]').exists()).toBe(false)
  })

  it('404:无权或不存在', async () => {
    getReport.mockRejectedValue({ status: 404 })
    const w = mount(ExecutionReportPanel, { props: { executionId: 9, running: false } })
    await flushPromises()
    expect(w.get('[data-testid="report-error"]').text()).toContain('无权查看')
  })

  it('运行中轮询,转终态后再拉一次并停止', async () => {
    vi.useFakeTimers()
    try {
      getReport.mockResolvedValue(report())
      const w = mount(ExecutionReportPanel, { props: { executionId: 9, running: true } })
      await flushPromises()
      expect(getReport).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(3000)
      expect(getReport).toHaveBeenCalledTimes(2)
      await w.setProps({ running: false })
      await flushPromises()
      const n = getReport.mock.calls.length
      await vi.advanceTimersByTimeAsync(10000)
      expect(getReport.mock.calls.length).toBe(n)
    } finally {
      vi.useRealTimers()
    }
  })

  // ── S1 失败根因深链(2026-11-12 自行级明细「查看日志」迁入)──────
  it('定位失败上下文:锚点查询限定失败 unit;命中 → 取末条(最终失败)around 深链', async () => {
    // seq 升序两条(重试):第一次失败 id=20,最终失败 id=25 —— 锚须取末条
    getReport.mockResolvedValue(report())
    getEvents.mockResolvedValue({
      items: [
        { id: 20, seq: 5, ts: '2026-10-14T01:02:03', kind: 'event',
          level: 'ERROR', category: null, module: null, service: null,
          protocol: null, unit: 'sc-r', attempt: '1.1', step: 'step-001',
          event_type: 'step.failed', message: null },
        { id: 25, seq: 9, ts: '2026-10-14T01:03:03', kind: 'event',
          level: 'ERROR', category: null, module: null, service: null,
          protocol: null, unit: 'sc-r', attempt: '2.1', step: 'step-001',
          event_type: 'step.failed', message: null },
      ],
      count: 2,
    })
    const { w, router } = await mountPanel()
    await w.get('[data-testid="report-failure-locate"]').trigger('click')
    await flushPromises()

    // 查询限定失败 unit(不按全局前 50 条找锚)
    expect(getEvents).toHaveBeenCalledWith(9, expect.objectContaining(
      { kind: 'event', event_type: 'step.failed', unit: 'sc-r' }))
    // 深链:锚点取末条(最终失败)+ unit 过滤
    expect(router.currentRoute.value.path).toBe('/executions/9/events')
    expect(router.currentRoute.value.query).toMatchObject({
      view: 'mixed', unit: 'sc-r', around_id: '25', n: '80',
    })
    w.unmount()
  })

  it('定位失败上下文:本 unit 无失败事件 → 退化 unit 视图,不跨 unit 回落锚点', async () => {
    getReport.mockResolvedValue(report())
    getEvents.mockResolvedValue({ items: [], count: 0 })
    const { w, router } = await mountPanel()
    await w.get('[data-testid="report-failure-locate"]').trigger('click')
    await flushPromises()

    const q = router.currentRoute.value.query
    expect(q).toMatchObject({ view: 'mixed', unit: 'sc-r' })
    expect(q.around_ts).toBeUndefined()
    expect(q.around_id).toBeUndefined()
    w.unmount()
  })
})
