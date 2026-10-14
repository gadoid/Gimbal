/**
 * ExecutionEvents 视图 — 批 4:S3 视图切换 / S4 URL 过滤态 / around 深链。
 *
 * mock getExecutionEvents/getExecutionEventCounts;断言:
 * - 视图切换写 kind(mixed 不发 kind);
 * - 过滤态进 URL query(router.replace)且冷开恢复;
 * - around 深链:带 around_ts/around_id/unit 查询参数 → 请求带锚 +
 *   横幅在场 + 锚行高亮;退出 around 清 URL。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ExecutionEvents from '@/views/ExecutionEvents.vue'
import * as api from '@/api/executions'

function makeRouter(query: Record<string, string> = {}) {
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
  protocol: null, unit: null, attempt: null, step: null, event_type: null,
  message: msg, payload: {},
  ...extra,
})

async function mountEvents(query: Record<string, string> = {}) {
  const router = makeRouter()
  await router.push({ path: '/executions/306/events', query })
  await router.isReady()
  const w = mount(ExecutionEvents, { global: { plugins: [router] } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getExecutionEventCounts').mockResolvedValue(
    { byCategory: { core: 3, step: 2 } } as never)
})

describe('ExecutionEvents 批 4', () => {
  it('S3:视图切换 mixed 不发 kind,log 发 kind=log', async () => {
    const spy = vi.spyOn(api, 'getExecutionEvents').mockResolvedValue(
      { items: [LOG(0, 'a'), LOG(1, 'b')], count: 2 } as never)
    const { w, router } = await mountEvents()
    expect(spy.mock.lastCall?.[1]).toMatchObject({ kind: 'log' })   // 默认视图=日志

    await w.find('[data-testid="view-mixed"]').trigger('click')
    await flushPromises()
    expect(spy.mock.lastCall?.[1]).not.toHaveProperty('kind')       // 混合:kind 不发
    expect(router.currentRoute.value.query.view).toBe('mixed')
    w.unmount()
  })

  it('S4:过滤变更写进 URL;冷开从 URL 恢复', async () => {
    vi.spyOn(api, 'getExecutionEvents').mockResolvedValue(
      { items: [LOG(0, 'a')], count: 1 } as never)
    const { w, router } = await mountEvents()
    await w.find('input[placeholder="step"]').setValue('step-002')
    await w.find('[data-testid="f-apply"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.step).toBe('step-002')
    w.unmount()

    // 冷开:同 URL 恢复过滤态
    const spy2 = vi.spyOn(api, 'getExecutionEvents').mockResolvedValue(
      { items: [LOG(0, 'a')], count: 1 } as never)
    const { w: w2 } = await mountEvents({ step: 'step-002', view: 'log' })
    expect((w2.find('input[placeholder="step"]').element as HTMLInputElement).value)
      .toBe('step-002')
    expect(spy2.mock.lastCall?.[1]).toMatchObject({ step: 'step-002' })
    w2.unmount()
  })

  it('S1/S2:around 深链 → 带锚请求 + 横幅 + 锚行高亮;退出清锚', async () => {
    const spy = vi.spyOn(api, 'getExecutionEvents').mockResolvedValue(
      { items: [LOG(0, 'before'), LOG(1, 'anchor-row', { id: 4242 }), LOG(2, 'after')],
        count: 3 } as never)
    const { w, router } = await mountEvents({
      view: 'mixed', around_ts: '2026-10-14T05:00:01.000000+00:00',
      around_id: '4242', unit: 'sc-x', n: '80',
    })
    // 请求带锚与 unit(S1 维度)
    expect(spy.mock.lastCall?.[1]).toMatchObject({
      around_ts: '2026-10-14T05:00:01.000000+00:00',
      around_id: 4242, n_before: 80, n_after: 80, unit: 'sc-x',
    })
    // 横幅 + 锚行高亮
    expect(w.find('[data-testid="around-banner"]').exists()).toBe(true)
    const anchorRow = w.findAll('tbody tr').find((r) => r.classes().includes('row-anchor'))
    expect(anchorRow?.text()).toContain('anchor-row')
    // 退出
    await w.find('[data-testid="exit-around"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="around-banner"]').exists()).toBe(false)
    expect(router.currentRoute.value.query.around_ts).toBeUndefined()
    expect(spy.mock.lastCall?.[1]).not.toHaveProperty('around_ts')
    w.unmount()
  })
})
