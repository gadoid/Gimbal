/**
 * ExecutionEvents 视图 — 批 5/S5:连续重复折叠(调用点键)。
 *
 * mock getExecutionEvents/getExecutionEventCounts;断言:
 * - 同调用点 (step,function,line,level) 的**连续**日志行折叠为一行 ×N;
 * - 非连续(中隔不同调用点/事件行)不误折;
 * - 关闭折叠开关 → 全量单行呈现;
 * - 折叠组点击 → 右抽屉列成员,点成员切行详情(payload 全文可见);
 * - 无 function/line 的行(payload 缺)不参与折叠。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ExecutionEvents from '@/views/ExecutionEvents.vue'
import * as api from '@/api/executions'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/executions/:id/events', component: ExecutionEvents },
      { path: '/executions/:id', component: { template: '<div/>' } },
    ],
  })
}

const LOG = (i: number, msg: string, extra: object = {}) => ({
  id: 1000 + i, seq: -(i + 1), ts: `2026-10-14T05:00:0${i}.000000+00:00`,
  kind: 'log', level: 'INFO', category: 'core', module: null, service: null,
  protocol: null, unit: 'bl-001', attempt: null, step: 'step-001',
  event_type: null, message: msg, payload: {},
  ...extra,
})

/** payload 带 JsonSink 的 function/line(调用点键素材) */
const CALL = (fn: string, line: number) => ({ payload: { function: fn, line } })

async function mountEvents() {
  const router = makeRouter()
  await router.push({ path: '/executions/306/events' })
  await router.isReady()
  const w = mount(ExecutionEvents, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getExecutionEventCounts').mockResolvedValue(
    { byCategory: { core: 3 } } as never)
})

describe('ExecutionEvents 批 5(S5 折叠)', () => {
  it('同调用点连续行折叠 ×N;非连续不误折;事件行不折', async () => {
    vi.spyOn(api, 'getExecutionEvents').mockResolvedValue({
      items: [
        LOG(0, 'poll attempt=1', CALL('poll_loop', 42)),
        LOG(1, 'poll attempt=2', CALL('poll_loop', 42)),
        LOG(2, 'poll attempt=3', CALL('poll_loop', 42)),
        LOG(3, 'unrelated info', CALL('other_fn', 7)),   // 不同调用点 → 断链
        LOG(4, 'poll attempt=4', CALL('poll_loop', 42)), // 非连续 → 独立组
        LOG(5, 'step end', {
          kind: 'event', event_type: 'step.end',
          payload: { function: 'poll_loop', line: 42 },  // 事件行不折
        }),
      ], count: 6,
    } as never)
    const w = await mountEvents()

    const folds = w.findAll('[data-testid^="fold-"]')
    expect(folds.length).toBe(2)                       // 两组:3 连续 + 1 单行组
    expect(w.find('[data-testid="fold-count"]').text()).toBe('×3')
    // 首行概览 + 调用点注记
    expect(folds[0]!.text()).toContain('poll attempt=1')
    expect(folds[0]!.text()).toContain('poll_loop:42')
    w.unmount()
  })

  it('无 function/line 的行不折(payload 缺 → 单行)', async () => {
    vi.spyOn(api, 'getExecutionEvents').mockResolvedValue({
      items: [
        LOG(0, 'legacy a'), LOG(1, 'legacy b'),   // payload 无调用点
      ], count: 2,
    } as never)
    const w = await mountEvents()
    expect(w.findAll('[data-testid^="fold-"]').length).toBe(0)
    expect(w.findAll('tbody tr').length).toBe(2)
    w.unmount()
  })

  it('关闭折叠 → 全量单行;折叠组点击开抽屉看成员、点成员切行详情', async () => {
    vi.spyOn(api, 'getExecutionEvents').mockResolvedValue({
      items: [
        LOG(0, 'poll attempt=1', CALL('poll_loop', 42)),
        LOG(1, 'poll attempt=2', CALL('poll_loop', 42)),
        LOG(2, 'poll attempt=3', CALL('poll_loop', 42)),
      ], count: 3,
    } as never)
    const w = await mountEvents()

    // 关闭折叠 → 三行独立呈现
    await w.find('[data-testid="f-fold"] input').setValue(false)
    await flushPromises()
    expect(w.findAll('[data-testid^="fold-"]').length).toBe(0)
    expect(w.findAll('tbody tr').length).toBe(3)

    // 重新打开折叠 → 组行 → 抽屉成员明细 → 成员切行详情
    await w.find('[data-testid="f-fold"] input').setValue(true)
    await flushPromises()
    await w.find('[data-testid^="fold-"]').trigger('click')
    await flushPromises()
    // Sheet 内容 teleport 到 body(仓库测试惯例):走 document 查询
    const members = Array.from(
      document.querySelectorAll<HTMLElement>('[data-testid^="fold-member-"]'))
    expect(members.length).toBe(3)
    expect(members[1]!.textContent).toContain('poll attempt=2')
    members[1]!.click()
    await flushPromises()
    expect(document.body.textContent).toContain('payload 全字段')
    expect(document.body.textContent).toContain('poll attempt=2')
    w.unmount()
  })
})
