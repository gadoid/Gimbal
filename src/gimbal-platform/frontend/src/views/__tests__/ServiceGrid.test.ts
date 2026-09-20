/**
 * ServiceGrid.vue — 服务画像热力网格(P1 切片):
 *   - 统计条数字与四枚筛选 chip;点 chip 即筛(§2.1);
 *   - 瓦片四格状态条:槽①恒占位、②③④按 signals 着色(§2.3);
 *   - plateReachable=false → 降级横幅(§2.4);
 *   - 点瓦片 → 线索板深链(占位路由)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ServiceGrid from '@/views/ServiceGrid.vue'
import * as api from '@/api/service-profile'
import type { ServiceGrid as ServiceGridData } from '@/api/service-profile'

function ep(id: string, method: string, signals: Partial<api.GridSignals>): api.GridEndpoint {
  return {
    id, method, path: `/api/home/${id}`, name: id,
    signals: { req: null, cases: true, lastRun: 'pass', alarm: false, ...signals },
    caseCount: 1, lastRunAt: '2026-09-10T00:00:00',
  }
}

const sample: ServiceGridData = {
  service: 'fin-service',
  plateReachable: true,
  stats: { total: 4, noCases: 2, hasAlarm: 1, neverRun: 2 },
  endpoints: [
    ep('fin.order.add', 'POST', { cases: true, lastRun: 'pass', alarm: true }),
    ep('fin.order.get', 'GET', { cases: true, lastRun: 'fail', alarm: false }),
    ep('fin.order.book', 'GET', { cases: false, lastRun: null, alarm: false }),
    ep('fin.order.void', 'DELETE', { cases: false, lastRun: null, alarm: false }),
  ],
}

async function mountPage(path = '/services/fin-service') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/services/:name', component: ServiceGrid },
    {
      path: '/services/:name/endpoints/:endpointId',
      component: { template: '<div data-testid="board-stub"/>' },
    },
  ] })
  await router.push(path)
  await router.isReady()
  return mount(ServiceGrid, { global: { plugins: [router, createPinia()] } })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

it('统计条 + 全量瓦片渲染;四枚 chip 带计数', async () => {
  vi.spyOn(api, 'fetchGrid').mockResolvedValue(sample)
  const w = await mountPage()
  await flushPromises()

  expect(w.find('[data-testid="grid-stats"]').text()).toContain('4 个接口')
  expect(w.find('[data-testid="grid-stats"]').text()).toContain('2 个没有用例覆盖')
  expect(w.findAll('[data-testid^="grid-tile-"]')).toHaveLength(4)
  expect(w.find('[data-testid="grid-chip-noCases"]').text()).toContain('无用例覆盖（2）')
  // 槽①占位恒在(斜纹格),四格恒为 4 段
  const slots = w.find('[data-testid="grid-slots-fin.order.add"]').findAll('span')
  expect(slots).toHaveLength(4)
})

it('chip 即筛:无用例覆盖只剩 2 块;从未执行只剩 2 块', async () => {
  vi.spyOn(api, 'fetchGrid').mockResolvedValue(sample)
  const w = await mountPage()
  await flushPromises()

  await w.find('[data-testid="grid-chip-noCases"]').trigger('click')
  let tiles = w.findAll('[data-testid^="grid-tile-"]')
  expect(tiles.map((t) => t.attributes('data-testid'))).toEqual([
    'grid-tile-fin.order.book', 'grid-tile-fin.order.void',
  ])

  await w.find('[data-testid="grid-chip-neverRun"]').trigger('click')
  tiles = w.findAll('[data-testid^="grid-tile-"]')
  expect(tiles).toHaveLength(2)

  await w.find('[data-testid="grid-chip-all"]').trigger('click')
  expect(w.findAll('[data-testid^="grid-tile-"]')).toHaveLength(4)
})

it('plate 不可达 → 降级横幅而非白屏', async () => {
  vi.spyOn(api, 'fetchGrid').mockResolvedValue({
    ...sample, plateReachable: false, endpoints: [],
    stats: { total: 0, noCases: 0, hasAlarm: 0, neverRun: 0 },
  })
  const w = await mountPage()
  await flushPromises()
  expect(w.find('[data-testid="grid-plate-down"]').exists()).toBe(true)
  expect(w.findAll('[data-testid^="grid-tile-"]')).toHaveLength(0)
})

it('点瓦片 → 线索板深链(endpoint_id 保持原样)', async () => {
  vi.spyOn(api, 'fetchGrid').mockResolvedValue(sample)
  const w = await mountPage()
  await flushPromises()
  await w.find('[data-testid="grid-tile-fin.order.add"]').trigger('click')
  await flushPromises()
  expect(w.vm.$route.fullPath).toBe('/services/fin-service/endpoints/fin.order.add')
})
